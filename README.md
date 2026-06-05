# KIS Global Brief — 매일 아침 운영 가이드

## 한 줄 요약
WSJ · FT · Economist RSS를 수집해 FICC 매크로 트레이더용 한국어 뉴스 다이제스트를 생성, KIS Global Brief 텔레그램 채널에 발송한다.

---

## Claude에게: 매일 아침 실행 순서

### Step 1 — RSS 수집
```powershell
cd "C:\Users\infomax\OneDrive\바탕 화면\ClaudeProject\newsChannel_v3"
python collect.py
```
- 최근 12시간 기사만 수집 (간밤 기사)
- `digest_db/YYYY-MM-DD.json` 에 저장됨

### Step 2 — 기사 파일 읽기
```
C:\Users\infomax\OneDrive\바탕 화면\ClaudeProject\newsChannel_v3\digest_db\YYYY-MM-DD.json
```
오늘 날짜 파일을 Read 툴로 읽는다.

### Step 3 — 다이제스트 작성 및 사용자 컨펌
1. 아래 **작성 가이드라인**을 따라 다이제스트를 작성하고 `last_digest.txt`에 저장한다.
2. **작성한 내용을 콘솔에 출력해서 사용자에게 먼저 보여준다.**
3. 사용자가 컨펌("보내줘")하면 Step 4로 진행한다.
4. 수정 요청이 있으면 수정 후 다시 보여준다.

### Step 4 — 발송 (사용자 컨펌 후에만)
```powershell
python send_digest.py
```

---

## 다이제스트 작성 가이드라인

### 기사 선별 기준
FICC 매크로 트레이딩 관점에서 중요한 기사는 개수 제한 없이 모두 포함한다.

**우선 포함:**
- 중앙은행 결정·발언 (Fed, ECB, BOJ 등)
- 금리·인플레이션·고용 지표
- 지정학 리스크 (전쟁, 제재, 분쟁)
- 에너지·원자재 공급망 이슈
- 주요국 무역협상·관세
- 환율·채권시장 움직임
- 주요 기업 실적 (시장 전체에 영향을 주는 것)

**제외:**
- 스포츠, 라이프스타일, 문화
- 지역 정치 (지방선거, 지역 내정 — 단, 영국·유로존·미국 정치는 금리·환율 영향 있으면 포함)
- 개별 기업 M&A (시장 전체 영향 없는 것, 예: 광고·미디어·소비재 기업 딜)
- 오피니언·칼럼 (팩트가 없는 것)
- Q&A·독자 질의응답 형식 기사 (예: FT Live Q&A, 에디터 독자 문답 등)
- 스타트업 펀딩·밸류에이션 기사 (예: AI 스타트업 시리즈 투자, 기업가치 평가)
- 금리·환율·원자재·채권에 직접 영향 없는 기업 이벤트 (예: 행동주의 펀드 개별 기업 지분 취득, 바이오/제약 M&A 등)
- 테러·군사 충돌 단신 (지정학 리스크 확대가 아닌 것, 예: IS 전투원 소탕 작전)
- 전염병·보건 이슈 (금리·환율·원자재에 직접 영향 없는 것, 예: 에볼라 발생 단신)

### 메시지 포맷
```
🌙 <b>간밤의 글로벌 마켓 뉴스</b>
[ {DATE} | WSJ · FT · Economist ]
━━━━━━━━━━━━━━━━━━━━

✅ <b>간밤의 주요 헤드라인</b>

<b>1. 제목...핵심 키워드</b>
<blockquote>2~3줄 한국어 요약. 팩트 중심, 수치 포함 권장.
<a href="URL">[WSJ]</a></blockquote>

출처 링크 레이블은 반드시 [WSJ], [FT], [Economist] 세 가지만 사용한다. [FT 사설], [WSJ 칼럼] 등 변형 금지.

(반복)

━━━━━━━━━━━━━━━━━━━━
📡 <b>출처: WSJ · FT · The Economist</b>
```

### 문체 원칙
- **한국 경제 뉴스 문체**: 연합뉴스·한국경제·매일경제처럼 자연스러운 한국어로 쓴다
- 영어 원문을 직역하거나 번역투 문장을 쓰지 않는다
- 한국 독자가 읽었을 때 어색함이 없어야 한다
- **마켓 센티먼트 표기 금지**: "Risk-On / Risk-Off" 등 방향성 판단 문구는 넣지 않는다
- **외국 인명·기관명은 영어 원문 그대로 표기한다**: 한국어 음역 금지. 예) Kevin Warsh (O) / 워시·위시 (X), Jerome Powell (O) / 파월 (X), ECB (O). 단, 이미 한국 언론에서 굳어진 표기(예: 트럼프, 시진핑)는 한국어 사용 가능.

### 헤드라인 스타일
- 형식: `핵심 팩트...시장 시사점 또는 의미` (말줄임표로 연결, 두 파트 모두 필수)
- 좋은 예: `UAE 핵발전소 인근 드론 피격...이란 전쟁 극한 확전 신호`
- 좋은 예: `이란발 에너지 위기 새 국면...여름 성수기 앞두고 재고 바닥`
- 좋은 예: `미중, 무역·투자 협의체 설립 합의...베이징 회담 핵심 성과`
- 나쁜 예: `UAE 원전 인근 드론 공격으로 화재 발생` (팩트만 있고 시사점 없음)
- 나쁜 예: `글로벌 채권 매도세에 일본 국채도 하락` (밋밋하고 임팩트 없음)

### 요약 스타일
- 영어 RSS summary를 직역하지 말고 한국어 맥락에 맞게 풀어쓴다
- 수치가 있으면 반드시 포함 (예: +11.5만 명, €80억, $4.50)
- 문장 말미를 다양하게: "~했다", "~나왔다", "~주목된다", "~전망이다" 등 반복 금지
- 마지막 문장이 모두 "~할 전망이다"로 끝나는 것은 기계적으로 보이므로 지양
- **사실 왜곡 금지**: 본문은 제공된 기사 제목과 RSS 요약에 있는 내용만 근거로 작성한다. 요약에 없는 수치·통계·배경 사실을 임의로 추가하지 않는다.

---

## 환경변수
GitHub Secrets에 등록 (Settings → Secrets and variables → Actions):
- `TELEGRAM_BOT_TOKEN` — 텔레그램 봇 토큰
- `DIGEST_CHAT_ID` — 발송 대상 채널 ID
- `ANTHROPIC_API_KEY` — Claude API 키

## RSS 피드 구성
| 소스 | 섹션 |
|------|------|
| WSJ | markets, world, economy, business |
| FT | markets, world, economy, commodities, currencies, equities, us, asia-pacific, europe |
| Economist | finance, business, leaders, briefing, united-states, europe, asia, china, international |

## 테스트 (시간 필터 없이 전체 수집)
```powershell
python collect.py --test
python send_digest.py --preview   # 발송 없이 미리보기
```
