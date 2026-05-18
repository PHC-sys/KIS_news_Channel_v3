"""
RSS 수집기 — WSJ / FT / Economist
수집된 기사를 digest_db/YYYY-MM-DD.json 에 저장.

중복 제거 방식:
  - 날짜 파일 내부에서 URL 기준으로만 중복 제거
  - seen_urls 같은 날짜 간 글로벌 추적 없음
  - 같은 날 여러 번 실행해도 동일 파일에 안전하게 병합

사용법:
    python collect.py          # 시간 필터 적용 (최근 12시간, KST 기준)
    python collect.py --test   # 시간 필터 없이 전체 수집 (테스트용)
"""

import json
import sys
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from email.utils import parsedate_to_datetime

import feedparser

# WSJ 등 일부 피드가 기본 User-Agent 차단하는 경우 대응
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; RSSReader/1.0)"}

# 피드당 최대 수집 기사 수 (Economist 등 대용량 피드 제한)
MAX_PER_FEED = 15

from config import (
    ALL_SOURCES,
    COLLECT_WINDOW_HOURS,
    DIGEST_DB_DIR,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TEST_MODE = "--test" in sys.argv
KST = timezone(timedelta(hours=9))


# ─────────────────────────────────────────────
# 날짜 파싱
# ─────────────────────────────────────────────

def _parse_published(entry) -> datetime:
    for field in ("published", "updated"):
        val = getattr(entry, field, None)
        if val:
            try:
                return parsedate_to_datetime(val).astimezone(timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


def _parse_summary(entry) -> str:
    raw = getattr(entry, "summary", "") or ""
    import re
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw[:500]


# ─────────────────────────────────────────────
# RSS 파싱
# ─────────────────────────────────────────────

def fetch_source(source_name: str, feeds: dict, cutoff: datetime, skip_urls: set) -> list[dict]:
    """
    skip_urls: 이번 실행 중 이미 다른 피드에서 수집한 URL (피드 간 중복 방지용)
    """
    articles = []
    for section, url in feeds.items():
        logger.info("[%s/%s] 피드 수신 중...", source_name, section)
        try:
            feed = feedparser.parse(url, request_headers=HEADERS)
        except Exception as e:
            logger.error("[%s/%s] 파싱 오류: %s", source_name, section, e)
            continue

        section_count = 0
        for entry in feed.entries[:MAX_PER_FEED * 3]:
            link = (getattr(entry, "link", "") or "").strip().split("?")[0].split("#")[0]
            if not link:
                continue
            if link in skip_urls:
                continue

            title = (getattr(entry, "title", "") or "").strip()
            if not title or len(title) < 5:
                continue

            published = _parse_published(entry)

            if not TEST_MODE and published < cutoff:
                continue

            summary = _parse_summary(entry)

            articles.append({
                "url":       link,
                "title":     title,
                "summary":   summary,
                "source":    source_name,
                "section":   section,
                "published": published.isoformat(),
            })
            skip_urls.add(link)
            section_count += 1
            if section_count >= MAX_PER_FEED:
                break

        logger.info("[%s/%s] %d건 수집", source_name, section, section_count)

    return articles


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────

def main():
    if TEST_MODE:
        logger.info("=== 테스트 모드: 시간 필터 없음 ===")
        cutoff = datetime.min.replace(tzinfo=timezone.utc)
    else:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=COLLECT_WINDOW_HOURS)
        logger.info("수집 기준: %s KST 이후 기사",
                    cutoff.astimezone(KST).strftime("%Y-%m-%d %H:%M"))

    # 이번 실행 내 피드 간 중복 방지용 URL 집합
    seen_in_run: set = set()
    all_articles: list[dict] = []

    for source_name, feeds in ALL_SOURCES.items():
        fetched = fetch_source(source_name, feeds, cutoff, seen_in_run)
        all_articles.extend(fetched)

    # 발행 시각 기준 최신순 정렬
    all_articles.sort(key=lambda x: x["published"], reverse=True)

    # ── KST 날짜 기준 파일에 저장 ──────────────────
    today = datetime.now(KST).strftime("%Y-%m-%d")
    out_path = DIGEST_DB_DIR / f"{today}.json"

    # 기존 파일 있으면 병합 (파일 내 URL 중복 제거)
    existing: list[dict] = []
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    existing_urls = {a["url"] for a in existing}
    new_articles  = [a for a in all_articles if a["url"] not in existing_urls]
    merged        = new_articles + existing   # 새 기사를 앞에 배치

    out_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    if not new_articles:
        logger.info("새로운 기사 없음 (파일 내 중복). 파일 유지: %s", out_path.name)
        return

    counts = {}
    for a in new_articles:
        counts[a["source"]] = counts.get(a["source"], 0) + 1

    logger.info("수집 완료: 신규 %d건 추가 → %s (누적 %d건)",
                len(new_articles), out_path.name, len(merged))
    for src, cnt in counts.items():
        logger.info("  %s: %d건", src, cnt)


if __name__ == "__main__":
    main()
