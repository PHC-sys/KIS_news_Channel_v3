"""
낮 시간 실시간 뉴스 알림

동작:
  - 최근 10분 이내 새 기사만 수집
  - 오늘 already 처리한 URL (alert_db + digest_db) 중복 제거
  - Claude Haiku로 FICC 중요도 판단
  - 중요한 기사만 텔레그램 발송
  - 처리한 URL을 alert_db/YYYY-MM-DD.json 에 저장

사용법:
    python daytime_alert.py          # 최근 10분 윈도우
    python daytime_alert.py --test   # 최근 2시간 윈도우 (테스트용)
"""

import asyncio
import io
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

import anthropic
import feedparser
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE_DIR  = Path(__file__).parent
DIGEST_DB = BASE_DIR / "digest_db"
ALERT_DB  = BASE_DIR / "alert_db"
ALERT_DB.mkdir(exist_ok=True)

KST       = timezone(timedelta(hours=9))
TEST_MODE = "--test" in sys.argv

# 테스트: 2시간 / 일반: 20분 (RSS 반영 지연 + 크론 경계 허용치 5분 추가)
WINDOW_MINUTES = 120 if TEST_MODE else 20

HEADERS     = {"User-Agent": "Mozilla/5.0 (compatible; RSSReader/1.0)"}
MAX_PER_FEED = 20

from config import ALL_SOURCES, TELEGRAM_BOT_TOKEN, DIGEST_CHAT_ID


# ─────────────────────────────────────────────────────────────────
# seen URL 관리
# ─────────────────────────────────────────────────────────────────

def load_seen_urls() -> set:
    """오늘 이미 처리한 URL (alert_db + digest_db 합산)"""
    today = datetime.now(KST).strftime("%Y-%m-%d")
    seen = set()

    # 낮 알림에서 이미 처리한 것
    alert_path = ALERT_DB / f"{today}.json"
    if alert_path.exists():
        try:
            data = json.loads(alert_path.read_text(encoding="utf-8"))
            seen.update(data.get("sent_urls", []))
        except Exception:
            pass

    # 아침 브리핑에 포함된 것
    digest_path = DIGEST_DB / f"{today}.json"
    if digest_path.exists():
        try:
            articles = json.loads(digest_path.read_text(encoding="utf-8"))
            seen.update(a["url"] for a in articles)
        except Exception:
            pass

    return seen


def save_seen_urls(urls: list):
    """처리한 URL을 alert_db에 추가 저장 (중요하든 아니든 모두)"""
    today = datetime.now(KST).strftime("%Y-%m-%d")
    alert_path = ALERT_DB / f"{today}.json"

    existing = []
    if alert_path.exists():
        try:
            data = json.loads(alert_path.read_text(encoding="utf-8"))
            existing = data.get("sent_urls", [])
        except Exception:
            pass

    merged = list(set(existing + urls))
    alert_path.write_text(
        json.dumps({"sent_urls": merged}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ─────────────────────────────────────────────────────────────────
# RSS 수집
# ─────────────────────────────────────────────────────────────────

def fetch_new_articles(seen_urls: set) -> list[dict]:
    """최근 N분 이내 & 미처리 기사 수집"""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=WINDOW_MINUTES)
    articles = []
    seen_in_run = set(seen_urls)

    for source_name, feeds in ALL_SOURCES.items():
        for section, url in feeds.items():
            try:
                feed = feedparser.parse(url, request_headers=HEADERS)
            except Exception as e:
                print(f"[오류] {source_name}/{section}: {e}")
                continue

            count = 0
            for entry in feed.entries[: MAX_PER_FEED * 3]:
                link = (
                    (getattr(entry, "link", "") or "")
                    .strip()
                    .split("?")[0]
                    .split("#")[0]
                )
                if not link or link in seen_in_run:
                    continue

                # published 파싱
                published = None
                for field in ("published", "updated"):
                    val = getattr(entry, field, None)
                    if val:
                        try:
                            published = parsedate_to_datetime(val).astimezone(
                                timezone.utc
                            )
                            break
                        except Exception:
                            pass
                if not published:
                    continue

                if published < cutoff:
                    continue

                title = (getattr(entry, "title", "") or "").strip()
                if not title or len(title) < 5:
                    continue

                raw = getattr(entry, "summary", "") or ""
                summary = re.sub(r"<[^>]+>", " ", raw)
                summary = re.sub(r"\s+", " ", summary).strip()[:500]

                articles.append(
                    {
                        "url": link,
                        "title": title,
                        "summary": summary,
                        "source": source_name,
                        "published": published.isoformat(),
                    }
                )
                seen_in_run.add(link)
                count += 1
                if count >= MAX_PER_FEED:
                    break

    label = f"최근 {WINDOW_MINUTES}분" if not TEST_MODE else "최근 2시간 [테스트]"
    print(f"신규 기사 수집: {len(articles)}건 ({label})")
    return articles


# ─────────────────────────────────────────────────────────────────
# Haiku 필터링
# ─────────────────────────────────────────────────────────────────

def filter_with_haiku(
    client: anthropic.Anthropic, articles: list[dict]
) -> list[dict]:
    """Haiku로 FICC 중요 기사 선별"""

    lines = []
    for i, a in enumerate(articles, 1):
        lines.append(
            f"{i}. [{a['source']}] {a['title']}\n"
            f"   요약: {a['summary'][:200]}\n"
            f"   URL: {a['url']}"
        )

    prompt = (
        "아래는 WSJ·FT·Economist 피드에서 수집한 기사들이다.\n"
        "모든 기사는 기본적으로 IMPORTANT다.\n"
        "아래 [무조건 포함] 항목에 해당하면 다른 조건 보지 말고 포함해라.\n"
        "[제외] 항목에 명백히 해당하는 것만 걸러내고, 나머지는 전부 포함해라.\n"
        "의심스러우면 반드시 포함해라.\n\n"
        "=== [무조건 포함] ===\n"
        "- 금리·채권·국채·수익률 (bond, yield, rate, JGB, gilt, treasury 등)\n"
        "- 외환·FX·달러·엔·위안·원화 개입·변동성\n"
        "- 원유·가스·상품·에너지 (가격·거래·감시·규제·OPEC 등)\n"
        "- 중앙은행·Fed·ECB·BOJ·한국은행 정책·발언\n"
        "- 금융시장 규제·감시 (이상거래, 조작, 내부자 등)\n"
        "- 거시경제 지표 (CPI, 고용, GDP, PMI, 생산 등)\n"
        "- 이란·중동·핵 관련 뉴스 (지정학, 제재, 에너지 영향)\n"
        "- 미국 대통령·행정부·의회 주요 결정·인사·선거 결과\n"
        "- 무역분쟁·관세·제재·지정학적 리스크\n"
        "- 주요국 재무장관·경제장관 발언 및 정책\n\n"
        "=== [제외] (명백히 이것만 해당하는 것) ===\n"
        "- 스포츠 경기 결과, 선수 이적\n"
        "- 여행·관광·호텔·리조트·식음료 후기 (예: hotel binge, best restaurants)\n"
        "- 영화·음악·연예·오락·패션·뷰티\n"
        "- 스타트업 펀딩·VC 투자 (핀테크·거시 무관)\n"
        "- 지역 복지·교육·육아·주거 생활 팁\n"
        "- 순수 사회면 사건사고 (살인, 재판 등 금융 무관)\n\n"
        "해당 없으면 → NONE\n"
        "있으면 → IMPORTANT: 1,3,5  (번호만, 설명 없이)\n\n"
        f"=== 기사 목록 ({len(articles)}건) ===\n"
        + "\n\n".join(lines)
    )

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=150,
        system=(
            "FICC 채권·외환·원자재 트레이더 전용 뉴스 필터. "
            "기본값은 IMPORTANT. "
            "이란·핵·중동·미국정치·선거 기사는 무조건 포함. "
            "라스베가스 호텔, 여행, 스포츠, 연예는 무조건 제외. "
            "지정된 형식으로만 응답."
        ),
        messages=[{"role": "user", "content": prompt}],
    )

    result = response.content[0].text.strip()
    print(f"Haiku 응답: {result}")

    if result == "NONE" or "IMPORTANT:" not in result:
        return []

    try:
        idx_str = result.replace("IMPORTANT:", "").strip()
        indices = [int(x.strip()) for x in idx_str.split(",")]
        return [articles[i - 1] for i in indices if 1 <= i <= len(articles)]
    except Exception as e:
        print(f"[경고] Haiku 응답 파싱 오류: {e}")
        return []


# ─────────────────────────────────────────────────────────────────
# 메시지 포맷
# ─────────────────────────────────────────────────────────────────

def format_alert(articles: list[dict]) -> str:
    parts = []

    for i, a in enumerate(articles, 1):
        summary = a["summary"][:200] if a["summary"] else ""
        parts.append(
            f"<b>{i}. {a['title']}</b>\n"
            f"<blockquote>{summary}\n"
            f"<a href=\"{a['url']}\">[{a['source']}]</a></blockquote>"
        )

    return "\n\n".join(parts)


def sanitize_html(text: str) -> str:
    for tag in ("b", "strong", "i", "em", "u", "s", "blockquote"):
        text = re.sub(rf"<{tag}\s[^>]*>", f"<{tag}>", text, flags=re.IGNORECASE)
    text = re.sub(
        r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>',
        r'<a href="\1">',
        text,
        flags=re.IGNORECASE,
    )
    return text


# ─────────────────────────────────────────────────────────────────
# 텔레그램 발송
# ─────────────────────────────────────────────────────────────────

async def send(text: str):
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(
            chat_id=DIGEST_CHAT_ID,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        print("텔레그램 발송 완료")
    except TelegramError as e:
        print(f"[오류] 발송 실패: {e}")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────────

def main():
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        print("[오류] ANTHROPIC_API_KEY 미설정")
        sys.exit(1)

    print(f"=== 낮 시간 알림{'  [테스트 모드]' if TEST_MODE else ''} ===")

    # 1. 오늘 이미 처리한 URL
    seen_urls = load_seen_urls()
    print(f"기존 처리 URL: {len(seen_urls)}건")

    # 2. 새 기사 수집
    articles = fetch_new_articles(seen_urls)
    if not articles:
        print("새 기사 없음 → 종료")
        return

    # 3. Haiku 필터링
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], max_retries=3)
    important = filter_with_haiku(client, articles)

    # 4. 결과 처리
    if not important:
        print("중요 기사 없음 → 발송 없이 종료")
    else:
        print(f"중요 기사: {len(important)}건 → 발송")
        text = sanitize_html(format_alert(important))
        asyncio.run(send(text))

    # 5. 처리한 모든 URL 저장 (중요하든 아니든 — 재처리 방지)
    save_seen_urls([a["url"] for a in articles])
    print("완료")


if __name__ == "__main__":
    main()
