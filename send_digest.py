"""
last_digest.txt 를 읽어 KIS Global Brief 채널로 발송.

사용법:
    python send_digest.py             # last_digest.txt 발송
    python send_digest.py --preview   # 발송 없이 내용만 출력
"""

import asyncio
import io
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from config import TELEGRAM_BOT_TOKEN, DIGEST_CHAT_ID, DIGEST_FILE

PREVIEW_MODE = "--preview" in sys.argv

MAX_MSG_LEN = 4096


def kst_date_str() -> str:
    KST = timezone(timedelta(hours=9))
    now = datetime.now(KST)
    weekdays = ['월', '화', '수', '목', '금', '토', '일']
    return f"{now.year}년 {now.month}월 {now.day}일 ({weekdays[now.weekday()]})"


def load_digest() -> str:
    if not DIGEST_FILE.exists():
        print(f"[오류] 다이제스트 파일 없음: {DIGEST_FILE}")
        print("      Claude에게 다이제스트 작성을 먼저 요청하세요.")
        return ""
    text = DIGEST_FILE.read_text(encoding="utf-8").strip()
    return text.replace("{DATE}", kst_date_str())


def split_message(text: str, limit: int = MAX_MSG_LEN) -> list[str]:
    """텔레그램 4096자 제한에 맞게 분할 (기사 단위로 끊음 — 제목+본문이 분리되지 않도록)."""
    if len(text) <= limit:
        return [text]

    import re
    # 헤더(첫 번째 <b>N. 이전)와 푸터(마지막 ━ 이후)를 분리
    article_pattern = re.compile(r'(?=\n\n<b>\d+\.)')
    parts = article_pattern.split(text)

    header = parts[0]  # 🌙 헤더 부분
    articles = parts[1:]  # 각 기사 블록

    # 푸터가 마지막 기사에 붙어 있으면 분리
    footer = ""
    if articles:
        footer_match = re.search(r'\n\n━+.*$', articles[-1], re.DOTALL)
        if footer_match:
            footer = footer_match.group(0)
            articles[-1] = articles[-1][:footer_match.start()]

    chunks = []
    current = header
    for article in articles:
        candidate = current + article
        if len(candidate) > limit and current != header:
            chunks.append(current.rstrip())
            current = article.lstrip()
        else:
            current = candidate

    # 푸터를 마지막 청크에 붙이되 초과하면 별도 메시지로
    if len(current) + len(footer) <= limit:
        current += footer
    else:
        chunks.append(current.rstrip())
        current = footer.lstrip()

    chunks.append(current.rstrip())
    return [c for c in chunks if c.strip()]


async def send(text: str) -> None:
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    # 레이블 포함한 최종 청크 생성 (레이블 길이까지 감안해 분할)
    raw_chunks = split_message(text)
    total = len(raw_chunks)

    final_chunks = []
    for i, chunk in enumerate(raw_chunks, 1):
        label = f"\n\n(계속 {i}/{total})" if total > 1 else ""
        final_chunks.append(chunk + label)

    failed = 0
    for i, chunk in enumerate(final_chunks, 1):
        try:
            await bot.send_message(
                chat_id=DIGEST_CHAT_ID,
                text=chunk,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            print(f"[{i}/{total}] 발송 완료  ({len(chunk)}자)")
            if i < total:
                await asyncio.sleep(2)
        except TelegramError as e:
            print(f"[오류] 발송 실패 ({i}/{total}): {e}")
            failed += 1

    if failed:
        sys.exit(f"[실패] {failed}건 전송 오류 — 위 로그 확인")


def main():
    text = load_digest()
    if not text:
        return

    if PREVIEW_MODE:
        print("\n" + "="*60)
        print("[ 발송 예정 다이제스트 미리보기 ]")
        print("="*60)
        print(text)
        print("="*60)
        print(f"\n총 {len(text)}자 / {len(split_message(text))}개 메시지")
        return

    print(f"채널로 발송합니다: {DIGEST_CHAT_ID}")
    print(f"내용 길이: {len(text)}자")
    asyncio.run(send(text))
    print("완료.")


if __name__ == "__main__":
    main()
