# KIS Global Brief — 전체 설정 매뉴얼

처음부터 다시 설정해야 할 때, 또는 구조를 다시 파악하고 싶을 때 이 문서를 읽는다.

---

## 전체 구조

```
cron-job.org (매일 08:00 KST)
    ↓ GitHub API 호출
GitHub Actions (morning_digest.yml)
    ↓ 순서대로 실행
  1. collect.py       → RSS 수집 → digest_db/YYYY-MM-DD.json 저장
  2. generate_digest.py → Claude API → last_digest.txt 생성
  3. send_digest.py   → 텔레그램 채널 발송
  4. git commit/push  → digest_db/, last_digest.txt 저장
```

---

## 1. 텔레그램 봇 설정

### 봇 토큰 발급
1. 텔레그램에서 **@BotFather** 검색
2. `/newbot` 입력 → 봇 이름, 사용자명 설정
3. 발급된 토큰 복사 (예: `8480887507:AAEuo1U...`)

### 채널에 봇 추가
1. 텔레그램 채널 → 관리자 설정 → 관리자 추가
2. 봇 사용자명 검색해서 추가
3. 권한: **메시지 전송** 체크

### 채널 ID 확인
방법 1 (가장 쉬움): 채널에 메시지 하나 보낸 뒤,
```
https://api.telegram.org/bot{봇토큰}/getUpdates
```
브라우저에서 열면 `"chat":{"id":-100xxxxxxxxxx}` 형태로 나옴

방법 2: **@username_to_id_bot** 에 채널 포워딩

채널 ID는 보통 `-100`으로 시작하는 음수.

---

## 2. Anthropic API Key 발급

1. https://console.anthropic.com 로그인
2. **API Keys** → **Create Key**
3. 발급된 키 복사 (sk-ant-...로 시작)

---

## 3. GitHub 레포 설정

### 레포 생성
- https://github.com/new
- 레포명: 원하는 이름
- Public 또는 Private (Actions 무료 한도: Public 무제한, Private 월 500분)
- `.gitignore`: Python 선택

### 코드 업로드
```powershell
git clone https://github.com/{계정}/{레포명}.git
# 파일 복사 후
git add .
git commit -m "initial commit"
git push
```

### Secrets 설정 (중요)
레포 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret 이름 | 값 | 설명 |
|------------|-----|------|
| `TELEGRAM_BOT_TOKEN` | `8480887507:AAEuo1U...` | BotFather에서 발급한 봇 토큰 |
| `DIGEST_CHAT_ID` | `-1003710986831` | 텔레그램 채널 ID |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Anthropic 콘솔에서 발급 |

> **테스트 채널 → 실제 채널 전환 시**: `DIGEST_CHAT_ID`만 실제 채널 ID로 변경하면 됨.
> 현재 실제 채널 ID: `-1003855361230` (KIS Global Brief)

---

## 4. GitHub Actions Workflow

파일 위치: `.github/workflows/morning_digest.yml`

### 핵심 구조
```yaml
on:
  workflow_dispatch:   # cron-job.org 또는 수동 실행만 허용

jobs:
  morning-digest:
    permissions:
      contents: write  # digest_db git 커밋 권한
    env:
      TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
      DIGEST_CHAT_ID:     ${{ secrets.DIGEST_CHAT_ID }}
      ANTHROPIC_API_KEY:  ${{ secrets.ANTHROPIC_API_KEY }}
    steps:
      - collect.py       # RSS 수집
      - generate_digest.py  # Claude API로 다이제스트 생성
      - send_digest.py   # 텔레그램 발송
      - git commit/push  # digest_db 저장
```

### 수동 실행
GitHub → Actions → Morning Digest → **Run workflow**

---

## 5. cron-job.org 설정

자세한 내용은 `CRON_SETUP.md` 참고.

### 요약
- URL: `https://api.github.com/repos/{계정}/{레포}/actions/workflows/morning_digest.yml/dispatches`
- Method: `POST`
- Headers: `Authorization: Bearer {GitHub_PAT}`, `Accept: application/vnd.github.v3+json`, `Content-Type: application/json`
- Body: `{"ref": "main"}`
- Schedule: 매일 08:00 (Asia/Seoul)

### GitHub PAT (Personal Access Token)
- GitHub 프로필 → Settings → Developer settings → Personal access tokens → Tokens (classic)
- Scope: `workflow` 하나만 체크
- **만료 시**: 새 토큰 발급 후 cron-job.org 해당 job의 Authorization 헤더 값만 교체

---

## 6. 로컬에서 수동 실행 (Claude와 함께 실제 채널 운영 시)

### 환경변수 설정 (PowerShell)
```powershell
$env:TELEGRAM_BOT_TOKEN = "8480887507:AAEuo1UStll7u40p362tap9tZ0J6IJ0zblc"
$env:DIGEST_CHAT_ID     = "-1003855361230"   # 실제 채널
$env:ANTHROPIC_API_KEY  = "sk-ant-..."
```

### 실행 순서
```powershell
cd "C:\Users\infomax\OneDrive\바탕 화면\ClaudeProject\newsChannel_v3"

# Step 1: RSS 수집
python collect.py

# Step 2: 다이제스트 생성 (Claude API 사용)
python generate_digest.py

# Step 3: 미리보기 확인
python send_digest.py --preview

# Step 4: 발송 (확인 후)
python send_digest.py
```

---

## 7. 채널 운영 방식

| 채널 | 운영 방식 | 채널 ID |
|------|----------|---------|
| 테스트 채널 | cron-job.org 자동 (매일 08:00) | `-1003710986831` |
| 실제 채널 (KIS Global Brief) | Claude와 수동 작성 | `-1003855361230` |

**실제 채널 자동화 전환 조건**: 테스트 채널에서 품질 확인 후 `DIGEST_CHAT_ID` Secret만 변경.

---

## 8. 주요 파일 구조

```
newsChannel_v3/
├── collect.py           # RSS 수집
├── generate_digest.py   # Claude API 다이제스트 생성 (2단계)
├── send_digest.py       # 텔레그램 발송
├── config.py            # RSS 피드 URL, 설정값
├── README.md            # 다이제스트 작성 가이드라인 (Claude 지침)
├── last_digest.txt      # 가장 최근 생성된 다이제스트
├── digest_db/           # 날짜별 수집 기사 JSON
│   └── YYYY-MM-DD.json
├── SETUP.md             # 이 파일 (전체 설정 매뉴얼)
├── CRON_SETUP.md        # cron-job.org 상세 설정
└── .github/
    └── workflows/
        └── morning_digest.yml
```

---

## 9. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| GitHub Actions 안 돌아감 | cron-job.org job 비활성화 | cron-job.org에서 job 활성화 확인 |
| 텔레그램 발송 실패 | HTML 파싱 오류 | GitHub Actions 로그에서 오류 메시지 확인 |
| `ANTHROPIC_API_KEY` 오류 | Secret 미설정 | GitHub Secrets 재확인 |
| PAT 만료 | 토큰 유효기간 경과 | 새 PAT 발급 후 cron-job.org 헤더 업데이트 |
| digest_db 파일 없음 | collect.py 미실행 | 워크플로우 로그에서 collect.py 단계 확인 |
