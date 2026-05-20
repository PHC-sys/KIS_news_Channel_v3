"""
KIS Global Brief — 설정 파일
RSS 전용 다이제스트 봇 (Chrome 불필요)

환경변수 설정 (PowerShell):
    $env:TELEGRAM_BOT_TOKEN = "123456:ABC..."
    $env:DIGEST_CHAT_ID     = "-100xxxxxxxxxx"   ← KIS Global Brief 채널 ID
"""

import os
import sys
from pathlib import Path


def _require(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        print(f"[오류] 환경변수 '{name}' 가 설정되지 않았습니다.")
        print(f"       PowerShell: $env:{name} = \"값\"")
        sys.exit(1)
    return val


# ─────────────────────────────────────────────
# Telegram
# ─────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = _require("TELEGRAM_BOT_TOKEN")
DIGEST_CHAT_ID     = _require("DIGEST_CHAT_ID")   # KIS Global Brief 채널

# ─────────────────────────────────────────────
# RSS 피드
# ─────────────────────────────────────────────
WSJ_RSS_FEEDS = {
    "markets":    "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",
    "world":      "https://feeds.content.dowjones.io/public/rss/RSSWorldNews",
    "economy":    "https://feeds.content.dowjones.io/public/rss/socialeconomyfeed",
    "business":   "https://feeds.content.dowjones.io/public/rss/WSJcomUSBusiness",
    "us":         "https://feeds.content.dowjones.io/public/rss/RSSUSnews",
    "politics":   "https://feeds.content.dowjones.io/public/rss/socialpoliticsfeed",
    "whats-news": "https://feeds.content.dowjones.io/public/rss/RSSWSJD",
    "opinion":    "https://feeds.content.dowjones.io/public/rss/RSSOpinion",
}

FT_RSS_FEEDS = {
    # 기존
    "markets":          "https://www.ft.com/markets?format=rss",
    "world":            "https://www.ft.com/world?format=rss",
    "economy":          "https://www.ft.com/global-economy?format=rss",
    "commodities":      "https://www.ft.com/commodities?format=rss",
    "emerging-markets": "https://www.ft.com/emerging-markets?format=rss",
    "currencies":       "https://www.ft.com/currencies?format=rss",
    "equities":         "https://www.ft.com/equities?format=rss",
    "us":               "https://www.ft.com/us?format=rss",
    "asia-pacific":     "https://www.ft.com/asia-pacific?format=rss",
    "europe":           "https://www.ft.com/europe?format=rss",
    # 신규
    "lex":              "https://www.ft.com/lex?format=rss",
    "capital-markets":  "https://www.ft.com/capital-markets?format=rss",
    "banking":          "https://www.ft.com/banking?format=rss",
    "alphaville":       "https://www.ft.com/alphaville?format=rss",
    "opinion":          "https://www.ft.com/opinion?format=rss",
    "fund-management":  "https://www.ft.com/fund-management?format=rss",
    "middle-east":      "https://www.ft.com/middle-east?format=rss",
    "companies":        "https://www.ft.com/companies?format=rss",
    "technology":       "https://www.ft.com/technology?format=rss",
    "homepage":         "https://www.ft.com/?format=rss",
}

ECONOMIST_RSS_FEEDS = {
    # 기존
    "finance":       "https://www.economist.com/finance-and-economics/rss.xml",
    "business":      "https://www.economist.com/business/rss.xml",
    "leaders":       "https://www.economist.com/leaders/rss.xml",
    "briefing":      "https://www.economist.com/briefing/rss.xml",
    "united-states": "https://www.economist.com/united-states/rss.xml",
    "europe":        "https://www.economist.com/europe/rss.xml",
    "asia":          "https://www.economist.com/asia/rss.xml",
    "china":         "https://www.economist.com/china/rss.xml",
    "international": "https://www.economist.com/international/rss.xml",
    # 신규
    "middle-east-africa": "https://www.economist.com/middle-east-and-africa/rss.xml",
    "special-report":     "https://www.economist.com/special-report/rss.xml",
    "world-this-week":    "https://www.economist.com/the-world-this-week/rss.xml",
}

ALL_SOURCES = {
    "WSJ":       WSJ_RSS_FEEDS,
    "FT":        FT_RSS_FEEDS,
    "Economist": ECONOMIST_RSS_FEEDS,
}

# ─────────────────────────────────────────────
# 수집 설정
# ─────────────────────────────────────────────
# 다이제스트 수집 시간 윈도우 (시간 단위)
# 매일 오전 8시 발송 기준 → 전날 20:00 ~ 당일 08:00 KST (12시간)
COLLECT_WINDOW_HOURS = 12

# 파일 경로
BASE_DIR        = Path(__file__).parent
DIGEST_DB_DIR   = BASE_DIR / "digest_db"
DIGEST_FILE     = BASE_DIR / "last_digest.txt"

DIGEST_DB_DIR.mkdir(exist_ok=True)
