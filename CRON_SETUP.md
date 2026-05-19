# 자동 실행 설정 가이드 (cron-job.org + GitHub Actions)

## 구조

```
cron-job.org  →  GitHub API  →  workflow_dispatch  →  GitHub Actions 실행
   (시계)           (트리거)          (이벤트)              (실제 작업)
```

GitHub Actions 내장 `schedule` 크론은 수십 분 지연이 발생할 수 있어서,
cron-job.org가 정확한 시간에 GitHub API를 호출하는 방식으로 대체했다.

---

## GitHub Personal Access Token 발급

1. GitHub 프로필 → **Settings**
2. 왼쪽 하단 **Developer settings** → **Personal access tokens** → **Tokens (classic)**
3. **Generate new token (classic)**
   - Note: `cron-job-trigger`
   - Expiration: 원하는 기간 (No expiration 가능)
   - Scope: `workflow` 하나만 체크
4. 토큰 복사 후 안전한 곳에 보관 (페이지 벗어나면 다시 볼 수 없음)

---

## cron-job.org 설정

### 1. 가입 및 로그인
https://console.cron-job.org

### 2. CREATE CRONJOB

**COMMON 탭**
| 항목 | 값 |
|------|-----|
| Title | Morning Digest |
| URL | `https://api.github.com/repos/PHC-sys/KIS_news_Channel_v3/actions/workflows/morning_digest.yml/dispatches` |
| Execution schedule | Every day at **8 : 00** |

**ADVANCED 탭**

Headers (ADD 버튼으로 추가):
| Key | Value |
|-----|-------|
| Authorization | `Bearer {GitHub_PAT_토큰}` |
| Accept | `application/vnd.github.v3+json` |
| Content-Type | `application/json` |

Request method: `POST`

Request body:
```json
{"ref": "main"}
```

### 3. TEST RUN으로 확인
- 응답 `204 No Content` = 정상
- GitHub Actions에서 새 run이 즉시 시작되는지 확인

### 4. CREATE

---

## 토큰 만료 시 갱신 방법

1. GitHub에서 새 PAT 발급 (위 과정 반복)
2. cron-job.org → 해당 cronjob 편집
3. Authorization 헤더의 토큰 값만 교체

---

## 참고

- cron-job.org 타임존: **Asia/Seoul** (KST 기준으로 시간 설정)
- GitHub Actions `schedule` 크론은 `morning_digest.yml`에서 제거됨
- `workflow_dispatch`만 남아 있어 cron-job.org 또는 수동(Run workflow 버튼)으로만 실행
