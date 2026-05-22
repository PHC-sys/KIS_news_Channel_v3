"""
Claude API를 사용해 overnight 수집 기사로 다이제스트를 자동 생성.
생성된 내용을 last_digest.txt에 저장.

2단계 호출:
  1단계 — 기사 분석: 오늘의 매크로 서사 파악, 기사 선별·묶기·순서 계획
  2단계 — 다이제스트 작성: 1단계 계획을 바탕으로 실제 작성

지침 원천: README.md (단일 진실 원천)

사용법:
    python generate_digest.py
"""

import json
import math
import os
import re
import sys
import io
from datetime import datetime, timezone, timedelta
from pathlib import Path

import anthropic

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE_DIR    = Path(__file__).parent
DIGEST_DB   = BASE_DIR / "digest_db"
DIGEST_FILE = BASE_DIR / "last_digest.txt"
KST         = timezone(timedelta(hours=9))


# ─────────────────────────────────────────────────────────────────
# README 로드
# ─────────────────────────────────────────────────────────────────
def load_readme() -> str:
    return (BASE_DIR / "README.md").read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────
# 기사 로드
# ─────────────────────────────────────────────────────────────────
def load_articles() -> list[dict]:
    today = datetime.now(KST).strftime("%Y-%m-%d")
    path  = DIGEST_DB / f"{today}.json"
    if not path.exists():
        print(f"[오류] 오늘 기사 파일 없음: {path}")
        print("       collect.py를 먼저 실행하세요.")
        sys.exit(1)
    articles = json.loads(path.read_text(encoding="utf-8"))
    print(f"기사 로드: {len(articles)}건  ({today}.json)")
    return articles


def format_for_prompt(articles: list[dict]) -> str:
    lines = []
    for i, a in enumerate(articles, 1):
        lines.append(
            f"{i}. [{a['source']}] {a['title']}\n"
            f"   요약: {a['summary']}\n"
            f"   URL: {a['url']}\n"
            f"   발행: {a['published']}"
        )
    return "\n\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# Haiku 사전 필터 (144건 → ~50건으로 압축)
# ─────────────────────────────────────────────────────────────────
HAIKU_BATCH = 30   # 배치당 기사 수


def prefilter_with_haiku(client: anthropic.Anthropic, articles: list[dict]) -> list[dict]:
    """Haiku로 FICC 무관 기사를 사전 제거 (배치 처리)"""
    print(f"  Haiku 사전 필터: {len(articles)}건 처리 중...")

    kept: list[dict] = []
    total_batches = math.ceil(len(articles) / HAIKU_BATCH)

    for batch_num in range(total_batches):
        batch = articles[batch_num * HAIKU_BATCH : (batch_num + 1) * HAIKU_BATCH]

        lines = []
        for i, a in enumerate(batch, 1):
            lines.append(
                f"{i}. [{a['source']}] {a['title']}\n"
                f"   요약: {a['summary'][:200]}\n"
                f"   URL: {a['url']}"
            )

        prompt = (
            "아래는 WSJ·FT·Economist에서 수집한 기사들이다.\n"
            "FICC 매크로 트레이더 아침 브리핑에 포함할 기사 번호를 골라라.\n\n"
            "=== [포함] ===\n"
            "- 금리·채권·국채·수익률·크레딧스프레드\n"
            "- 외환·FX·달러·엔·위안·원화 개입·변동성\n"
            "- 원유·가스·금속·농산물 등 원자재\n"
            "- 중앙은행·Fed·ECB·BOJ·한국은행 정책·발언\n"
            "- 거시경제 지표 (CPI, PCE, 고용, GDP, PMI, 무역수지 등)\n"
            "- 미국·유럽·중국 재정·통화 정책\n"
            "- 무역분쟁·관세·제재·지정학적 리스크\n"
            "- 이란·중동·핵·에너지 지정학\n"
            "- 시장 전체에 영향하는 대형 빅테크 실적 (Apple·Nvidia·TSMC·Walmart 등)\n"
            "- 주요국 정치 (재무장관 발언, 예산안, 선거 결과 등)\n"
            "- 금융 규제·시스템 리스크·레버리지\n\n"
            "=== [제외] ===\n"
            "- 스포츠 (F1·골프·축구·NBA 등 경기·선수·구단)\n"
            "- 게임·영화·음악·연예·팟캐스트\n"
            "- 패션·뷰티·여행·호텔·식음료\n"
            "- 소매 유통 개별 실적 (Ross·Target·Deckers·Foot Locker 등)\n"
            "- 스타트업·VC 펀딩 (핀테크·거시 무관)\n"
            "- 지역 사건사고·범죄 (금융 무관)\n"
            "- 전염병·보건 단신 (금융 무관)\n"
            "- 마케팅·광고·브랜드 캠페인\n"
            "- 학교·교육·육아·주거 생활 팁\n\n"
            "없으면 → NONE\n"
            "있으면 → KEEP: 1,3,5  (번호만, 설명 없이)\n\n"
            f"=== 기사 ({len(batch)}건) ===\n"
            + "\n\n".join(lines)
        )

        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=200,
            system=(
                "FICC 매크로 트레이더 뉴스 필터. "
                "금리·환율·원자재·중앙은행·지정학 관련 기사만 통과. "
                "스포츠·연예·여행·소매유통·스타트업은 제외. "
                "지정된 형식으로만 응답."
            ),
            messages=[{"role": "user", "content": prompt}],
        )

        result = response.content[0].text.strip()
        print(f"  배치 {batch_num + 1}/{total_batches} Haiku: {result}")

        if result == "NONE" or "KEEP:" not in result:
            continue

        try:
            idx_str = result.replace("KEEP:", "").strip()
            indices = [int(x.strip()) for x in idx_str.split(",")]
            for i in indices:
                if 1 <= i <= len(batch):
                    kept.append(batch[i - 1])
        except Exception as e:
            print(f"  [경고] 배치 {batch_num + 1} 파싱 오류: {e} — 배치 전체 유지")
            kept.extend(batch)

    print(f"  Haiku 사전 필터 완료: {len(articles)}건 → {len(kept)}건")
    return kept


# ─────────────────────────────────────────────────────────────────
# 1단계: 서사 분석 및 편집 계획
# ─────────────────────────────────────────────────────────────────
def plan_digest(client: anthropic.Anthropic, articles: list[dict]) -> str:
    print("  1단계: 서사 분석 중...")

    msg = (
        "아래 기사들을 FICC 매크로 트레이더 관점에서 분석해줘.\n\n"
        "다음 순서로 계획을 짜줘:\n"
        "1. 오늘의 핵심 매크로 서사 2~3개 (예: 이란전쟁→에너지충격→연준매파전환→금약세)\n"
        "2. 포함할 기사 목록 (번호) — 애매하면 포함 방향으로, 아래 항목만 제외:\n"
        "   - 스포츠·라이프스타일·문화\n"
        "   - 오피니언·칼럼 (팩트 없는 것)\n"
        "   - Q&A·독자 질의응답 형식 기사 (예: FT Live Q&A, 에디터 독자 문답)\n"
        "   - 뉴스레터·데일리브리핑 (예: FirstFT)\n"
        "   - 스타트업 펀딩·밸류에이션 기사 (예: AI 스타트업 시리즈 투자, 기업가치)\n"
        "   - 테러·군사 충돌 단신 (지정학 리스크 확대가 아닌 것, 예: IS 전투원 사살)\n"
        "   - 전염병·보건 이슈 (금리·환율·원자재에 직접 영향 없는 것, 예: 에볼라 단신)\n"
        "   - 지역 선거·내정 (단, 영국·유로존·미국 정치는 환율·금리 영향 있으면 포함)\n"
        "   - 개별 기업 M&A (시장 전체 영향 없는 것, 예: 광고·미디어·소비재 기업 딜)\n"
        "   - 개별 기업 노사 이슈 (예: 파업 가처분 등)\n"
        "   - 특정 기업의 섹터 저평가 주장·자사 투자 발표\n"
        "3. 주제가 겹치는 기사는 하나로 묶을 것 (묶을 기사 번호와 이유)\n"
        "4. 서사 흐름에 맞는 최종 순서\n\n"
        "계획만 간략히 출력하고, 다이제스트 본문은 쓰지 마.\n\n"
        f"=== 기사 목록 ({len(articles)}건) ===\n"
        + format_for_prompt(articles)
    )

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1500,
        system="당신은 FICC 매크로 트레이딩 전문 뉴스 에디터입니다.",
        messages=[{"role": "user", "content": msg}],
    )
    plan = response.content[0].text.strip()
    print("  1단계 완료.")
    return plan


# ─────────────────────────────────────────────────────────────────
# 2단계: 다이제스트 작성
# ─────────────────────────────────────────────────────────────────
def write_digest(client: anthropic.Anthropic, articles: list[dict], plan: str) -> str:
    print("  2단계: 다이제스트 작성 중...")

    readme = load_readme()

    msg = (
        "아래 README.md를 읽고, 오늘 아침 글로벌 마켓 뉴스 다이제스트를 작성해줘.\n"
        "1단계에서 이미 서사 분석과 편집 계획이 완성돼 있으니, 그 계획을 그대로 따라서 작성해줘.\n"
        "다이제스트 텍스트만 출력하고, 앞뒤 설명은 일절 쓰지 마세요.\n\n"
        f"=== README.md ===\n{readme}\n\n"
        f"=== 1단계 편집 계획 ===\n{plan}\n\n"
        f"=== 전체 기사 목록 ({len(articles)}건) ===\n"
        + format_for_prompt(articles)
    )

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=8192,
        system="당신은 KIS Global Brief 텔레그램 채널의 글로벌 마켓 뉴스 에디터입니다.",
        messages=[{"role": "user", "content": msg}],
    )
    # max_tokens 도달 시 응답이 중간에 잘려 unclosed HTML 태그가 생길 수 있음
    stop_reason = response.stop_reason
    if stop_reason == "max_tokens":
        print("[경고] max_tokens 도달 — 응답이 잘렸을 수 있음. 다이제스트를 확인하세요.")
    result = response.content[0].text.strip()
    print(f"  2단계 완료. (stop_reason={stop_reason})")
    return result


# ─────────────────────────────────────────────────────────────────
# HTML 정제 — 텔레그램이 허용하지 않는 태그 속성 제거
# ─────────────────────────────────────────────────────────────────
def sanitize_html(text: str) -> str:
    """
    텔레그램 HTML 모드는 <b>, <i>, <u>, <s>, <a href="...">, <blockquote>,
    <code>, <pre> 만 지원한다.
    Claude 가 <b > (공백) 또는 <b class="..."> 등을 출력할 경우 파싱 오류 발생.
    → 허용 태그에서 속성을 모두 제거하고, 그 외 태그는 이스케이프 처리.
    """
    # 속성 있는 단순 태그 → 속성 제거 (<b style="x"> → <b>)
    for tag in ("b", "strong", "i", "em", "u", "s", "strike", "del", "code", "blockquote"):
        text = re.sub(rf'<{tag}\s[^>]*>', f'<{tag}>', text, flags=re.IGNORECASE)
    # <a> 는 href 만 남긴다 (<a href="URL" target="_blank"> → <a href="URL">)
    text = re.sub(
        r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>',
        r'<a href="\1">',
        text,
        flags=re.IGNORECASE,
    )
    # 미닫힌 <blockquote> 자동 보정 (max_tokens 초과로 잘린 경우 대비)
    open_count  = len(re.findall(r'<blockquote>', text, re.IGNORECASE))
    close_count = len(re.findall(r'</blockquote>', text, re.IGNORECASE))
    if open_count > close_count:
        text = text.rstrip() + '</blockquote>' * (open_count - close_count)
        print(f"[HTML 보정] 미닫힌 blockquote {open_count - close_count}개 자동 닫음")
    return text


# ─────────────────────────────────────────────────────────────────
# {DATE} 복원
# ─────────────────────────────────────────────────────────────────
def restore_date_placeholder(text: str) -> str:
    # 한국어 형식: 2026년 5월 18일 (월)
    # 점/슬래시/대시 형식: 2026.05.18 / 2026/05/18 / 2026-05-18
    return re.sub(
        r'\[\s*(?:'
        r'\d{4}년\s*\d{1,2}월\s*\d{1,2}일?\s*(?:\([월화수목금토일]\))?'
        r'|\d{4}[./\-]\d{1,2}[./\-]\d{1,2}\s*(?:\([월화수목금토일]\))?'
        r')\s*\|',
        '[{DATE} |',
        text,
    )


# ─────────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────────
def main():
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        print("[오류] 환경변수 ANTHROPIC_API_KEY 가 설정되지 않았습니다.")
        sys.exit(1)

    articles = load_articles()
    client   = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Haiku 사전 필터: FICC 무관 기사 제거 (입력 토큰·출력 길이 동시 절감)
    articles = prefilter_with_haiku(client, articles)
    if not articles:
        print("[오류] Haiku 필터 후 기사 없음 — collect.py 재실행 필요")
        sys.exit(1)

    print(f"Claude Sonnet 호출 중... (2단계, 입력 {len(articles)}건)")
    plan   = plan_digest(client, articles)
    digest = write_digest(client, articles, plan)
    digest = sanitize_html(digest)
    digest = restore_date_placeholder(digest)

    DIGEST_FILE.write_text(digest, encoding="utf-8")
    print(f"저장 완료: {DIGEST_FILE.name}  ({len(digest)}자)")


if __name__ == "__main__":
    main()
