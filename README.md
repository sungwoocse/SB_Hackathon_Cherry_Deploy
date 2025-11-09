# 🚀 Cherry Deploy — Delightful DevOps Backend

> **SoftBank Hackathon 2025 · Team Cherry**

프론트엔드 배포를 “테마파크 놀이기구”처럼 **빠르고, 안전하고, 재미있게** 만드는 DevOps 자동화 백엔드입니다. 이 README 하나로 막 클론한 사람도 전체 구조·배포 흐름·운영 팁의 95% 이상을 이해할 수 있도록 구성했습니다.

---

## TL;DR
- **2개 레포**(Deploy API + Next.js 타겟)로 충돌 없이 작업
- FastAPI + MongoDB가 **배포 Task/이력**을 관리하고, `DeployService`(1586 lines) 가 Git → npm build → Blue/Green 컷오버까지 실행
- Google Gemini 2.5 Flash를 사용한 **LLM 프리뷰**와 비용/위험도 추정
- **Auto rollback** + `AsyncReentrantLock` 으로 실패에도 안전
- `/api/v1/*` API + `/healthz` + Swagger YAML 로 모든 기능 호출 가능
- PM2 + Nginx + 로컬 MongoDB 번들까지 포함된 **자가 포함형 DevOps 백엔드**

---

## 📚 목차
1. [시스템 개요](#-시스템-개요)
2. [디렉터리 안내](#-디렉터리-안내)
3. [핵심 컴포넌트](#-핵심-컴포넌트)
4. [배포 파이프라인](#-배포-파이프라인)
5. [데이터 및 상태 저장](#-데이터-및-상태-저장)
6. [API 표면](#-api-표면)
7. [셋업 & 로컬 실행](#-셋업--로컬-실행)
8. [운영 환경 팁 (EC2/PM2/Nginx)](#-운영-환경-팁-ec2pm2nginx)
9. [운영 Runbook](#-운영-runbook)
10. [환경변수 레퍼런스](#-환경변수-레퍼런스)
11. [AI 프리뷰 & Git Diff](#-ai-프리뷰--git-diff)
12. [Observability & Troubleshooting](#-observability--troubleshooting)
13. [Testing & 개발 루틴](#-testing--개발-루틴)
14. [추가 문서 & 팀](#-추가-문서--팀)

---

## 🧠 시스템 개요

### 1. Two-Repo 모델
```
/home/ec2-user/projects/
├─ SB_Hackathon_Cherry_Chatbot/   # Repo1: Next.js 대상 (deploy/main 브랜치)
│  └─ frontend/my-dashboard       # npm install/build 대상
└─ SB_Hackathon_Cherry_Deploy/    # Repo2: 현재 FastAPI DevOps 백엔드
```
- Deploy API에서 Repo1까지 Git 작업을 직접 수행하므로 두 레포를 같은 서버에 둡니다.
- 기본 브랜치 `deploy`, 필요 시 `main` 만 허용. (기타 브랜치는 API에서 거부)

## 🗂️ 디렉터리 안내

| 경로 | 설명 |
|------|------|
| `app_main.py` | FastAPI 엔트리포인트, CORS, 라우터 주입, Mongo 폴백 처리 |
| `api-code/settings.py` | 환경변수 → Pydantic Settings. Blue/Green 경로, LLM, GitHub Compare 등 전체 설정 정의 |
| `api-code/services/deploy_service.py` | 배포 파이프라인/락/롤백/LLM 프리뷰 등 핵심 로직 (1586 lines) |
| `api-code/services/auth_service.py` | 정적 자격증명 → JWT cookie 발급, `auth_token` 쿠키 의무화 |
| `api-code/services/chat_service.py` | Gemini 2.5 Flash wrapper, API 키 없으면 에코 fallback |
| `api-code/repositories/*` | MongoDB 저장소 + 인메모리 폴백, `deploy_tasks`/`deploy_reports` 관리 |
| `api-code/routers/*` | `/api/v1/deploy`, `/api/v1/preview`, `/api/v1/chat`, `/healthz`, `/api/v1/auth/*` |
| `mongodb/`, `mongodb-data/` | AWS Linux용 MongoDB 바이너리 + 데이터 디렉터리(깃 무시) |
| `swagger-api/*.yaml` | OpenAPI/Swagger 스펙 (Postman 없이도 요청 구조 확인 가능) |
| `tests/test_deploy_service.py` | DeployService dry-run 시나리오 테스트 (unittest + asyncio) |
| `AGENTS.md`, `developmentplan.html`, `systemDevPlan.html` | 운영 메모, 전략, 설계 문서 |

---

## 🧩 핵심 컴포넌트
- **FastAPI 앱** (`app_main.py`): `.env` 로딩, Settings 주입, CORS 허용, uvicorn 엔트리포인트.
- **AuthService**: `LOGIN_USER`/`LOGIN_PASSWORD` 환경변수로 인증, `JWT_SECRET_KEY` 가 기본값이면 실행 자체를 막음.
- **DeployService**:
  - Git stage (`git fetch/checkout/reset/clean`) → npm install/build/export → Blue/Green 컷오버 → Observability.
  - `AsyncReentrantLock` 로 서버 전체에서 동시에 하나의 배포만 허용.
  - 실패 시 `failure_context`에 `CommandExecutionError` 정보와 auto rollback 결과 저장.
  - 프리뷰용 diff/LLM/cost snapshot 을 `metadata.summary.preflight`에 선저장.
- **Gemini 통합**: `GeminiChatService`(chat) + `DeployService._generate_llm_preview`(preview). API 키 없으면 친절한 fallback 문구.
- **Health Router**: PM2 `jlist` 결과 + Mongo ping + 최근 task + Blue/Green 상태 리턴, 장애 감지시 `status: degraded`.

---

## 🛤️ 배포 파이프라인

| Stage (DeployStatus) | 실행 내용 | 대표 명령 |
|----------------------|-----------|-----------|
| `running_clone` | Repo1 동기화, 브랜치/커밋 체크아웃, 깨끗한 워킹트리 유지 | `git fetch`, `git checkout -B <branch> origin/<branch>`, `git reset --hard`, `git clean -fdx` |
| `running_build` | Next.js 프로젝트에서 의존성 설치 + 빌드 + export | `npm install`, `npm run build`, `npm run export` (커맨드는 Settings로 재정의 가능) |
| `running_cutover` | Blue ↔ Green 디렉터리 중 standby에 산출물 복사 후 `/var/www/.../current` 심볼릭 링크 스위치 | `shutil.copytree`, `Path.symlink_to` |
| `running_observability` | PM2 / Nginx / 헬스체크 자리. 현재는 “미구현” 메시지 반환 (추후 Lighthouse 등 확장 예정) | placeholder |

- 각 단계 결과는 `deploy_tasks.metadata.<stage>` 에 stdout/stderr, 명령, dry-run 여부까지 저장됩니다.
- 완료 시 `metadata.summary` 안에 `{result, commit, git_commit, actor, preflight}` 정보가 남습니다.

---

## 🗄️ 데이터 및 상태 저장
- **컬렉션**
  - `deploy_tasks`: Task 본문. `_id`(uuid4 hex), `status`, `started_at/completed_at`, `metadata`, `error_log`.
  - `deploy_reports`: 추가 metric 저장용 (현재는 구조만 존재).
- **메타데이터 구조**
  - `metadata.branch`, `metadata.action`(`deploy`/`rollback`), `metadata.actor/requested_by`.
  - `metadata.summary.preflight`: LLM 요약, 비용, 위험도 스냅샷.
  - `metadata.failure_context`: 실패 시각, 명령, stdout/stderr, auto_recovery 결과.
  - Stage별 stdout/stderr 는 500자까지 보존.
- **인덱스**: `status`, `started_at`, `metadata.branch`, `deploy_reports.task_id`.
- **폴백 전략**: Mongo 연결 실패 시 `InMemoryDeployTaskRepository`로 대체되어 API는 계속 동작하나, 재시작 시 데이터는 소멸.

---

## 🌐 API 표면

### 인증 (고정 계정)
| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/v1/auth/login` | `{"username":"<LOGIN_USER>", "password":"<LOGIN_PASSWORD>"}` → JWT 쿠키 발급 (`auth_token`) |
| `POST` | `/api/v1/auth/logout` | 쿠키 삭제 |
| `GET` | `/api/v1/auth/me` | 현재 사용자 정보 리턴 (미들웨어용 헬퍼) |

> 기본값: USER `cherry`, PASSWORD `coffee`. 반드시 `.env`에서 덮어써야 합니다.

### 배포/롤백/관제
| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/v1/deploy` | 배포 Task 생성 → BackgroundTasks 로 파이프라인 비동기 실행 |
| `POST` | `/api/v1/rollback` | 최근 2개 성공 배포 기준 롤백 Task 생성/실행 |
| `GET` | `/api/v1/status/{task_id}` | stage snapshots, preflight, 비용, LLM 요약, Blue/Green 상태 제공 |
| `GET` | `/api/v1/preview` | 다음 배포가 실행할 명령/타임라인/위험도/LLM 요약 미리 확인 |
| `GET` | `/api/v1/tasks/recent?limit=5` | 최근 N개의 Task 요약 |
| `GET` | `/api/v1/tasks/{task_id}/logs` | 메타데이터 + stage 로그 |

### 기타
| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/v1/chat` | Gemini 챗봇 (인증 불필요, API 키 없으면 fallback) |
| `GET` | `/healthz` | PM2 상태, Mongo ping, Blue/Green 슬롯, 최근 Task 등 |

### 샘플 cURL
```bash
# 1) 로그인
curl -X POST http://127.0.0.1:9001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"cherry","password":"coffee"}' -i

# 2) 쿠키 재사용해 배포 실행
curl -X POST http://127.0.0.1:9001/api/v1/deploy \
  -H "Cookie: auth_token=<JWT>" \
  -H "Content-Type: application/json" \
  -d '{"branch":"deploy"}'
```

Swagger/OpenAPI 문서는 `swagger-api/*.yaml` 에 정의되어 있으며 `openapi.yaml` 로 전체 스펙을 확인할 수 있습니다.

---

## 🛠️ 셋업 & 로컬 실행

### 1. 필수 버전
```
Python 3.10+
Node.js 18+ / npm 9+
PM2 (npm install -g pm2)
AWS Linux용 MongoDB 바이너리 (이미 repo 동봉)
```

### 2. 레포 클론
```bash
cd /home/ec2-user/projects
git clone <deploy-repo-url> SB_Hackathon_Cherry_Deploy
git clone <chatbot-repo-url> SB_Hackathon_Cherry_Chatbot
```

### 3. Python 의존성
```bash
cd SB_Hackathon_Cherry_Deploy
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 4. 환경변수 (.env) 생성
> ⚠️ 실서버 키/비밀번호는 절대 Git에 올리지 마세요. 아래 값들은 모두 예시/플레이스홀더입니다.
`.env` 파일은 직접 작성해야 합니다 (예시):
```
GEMINI_API_KEY=<필요 시 입력>
JWT_SECRET_KEY=<랜덤 문자열 필수>
LOGIN_USER=cherry
LOGIN_PASSWORD=coffee
CHATBOT_REPO_PATH=/home/ec2-user/projects/SB_Hackathon_Cherry_Chatbot
DEPLOY_DRY_RUN=true          # 로컬 테스트 시 추천
```

### 5. MongoDB 기동
```bash
mkdir -p mongodb-data
./mongodb/bin/mongod \
  --dbpath mongodb-data \
  --bind_ip 127.0.0.1 \
  --port 27017 \
  --fork \
  --logpath mongodb-data/mongod.log
```

### 6. FastAPI 실행
```bash
uvicorn app_main:app --host 0.0.0.0 --port 9001
# 또는
pm2 start "uvicorn app_main:app --host 0.0.0.0 --port 9001" --name main-api
```

### 7. Repo1 준비
```bash
cd /home/ec2-user/projects/SB_Hackathon_Cherry_Chatbot/frontend/my-dashboard
npm install
```
`DEPLOY_DRY_RUN=true` 상태에서 `/api/v1/deploy` 를 호출하면 명령만 기록되고 실제 파일 변경/pm2 실행은 건너뜁니다.

---

## 🏗️ 운영 환경 팁 (EC2/PM2/Nginx)
- **PM2 프로세스명**
  - `main-api`: `uvicorn app_main:app --host 0.0.0.0 --port 9001`
  - `frontend-dev`: 필요 시 Next.js dev 서버를 띄울 때 사용
- **Nginx 경로**: `/etc/nginx/conf.d/cherry_deploy.conf`, 루트는 `/var/www/cherry-deploy/current`
- **Blue/Green 슬롯**: `/var/www/cherry-deploy/{blue,green}`. DeployService가 standby로 복사 후 `current` 심볼릭 링크를 새 슬롯으로 이동.
- **HTTPS**: nip.io 도메인 (`delight.13-125-116-92.nip.io`) + certbot 자동화 (명령은 `AGENTS.md` 참고)
- **MongoDB 데이터**: `/home/ec2-user/projects/SB_Hackathon_Cherry_Deploy/mongodb-data`
- **서비스 재시작**:
  ```bash
  pm2 restart main-api
  sudo systemctl reload nginx
  ```

---

## 📘 운영 Runbook
1. **배포 준비**
   - Repo1 `deploy` 브랜치에 최신 변경사항 push
   - `GET /api/v1/preview`로 예상 시간/비용/위험 확인
2. **배포 실행**
   ```bash
   curl -X POST https://delight.../api/v1/deploy \
     -H "Cookie: auth_token=..." \
     -H "Content-Type: application/json" \
     -d '{"branch":"deploy"}'
   ```
3. **상태 모니터링**
   - `GET /api/v1/status/{task_id}` → stage 진행률/LLM 요약 확인
   - `GET /healthz` → PM2/Nginx/Mongo 상태
4. **롤백**
   - 최근 2회 성공 배포가 있을 때만 가능
   ```bash
   curl -X POST https://delight.../api/v1/rollback \
     -H "Cookie: auth_token=..." \
     -H "Content-Type: application/json" \
     -d '{"branch":"deploy"}'
   ```
5. **로그 확인**
   - `/api/v1/tasks/{task_id}/logs`
   - 서버 쉘: `pm2 logs main-api`, `tail -f mongodb-data/mongod.log`

---

## 🔐 보안 체크리스트
- **비밀 관리**: `.env`는 Git에서 제외되어 있으며(`.gitignore`), README에도 플레이스홀더만 표기됩니다. 모든 키/비밀번호는 환경변수로만 주입합니다.
- **JWT 쿠키 방어**: `AuthService`가 발급하는 `auth_token`은 HTTPOnly, Secure(기본 true), SameSite=Lax, 만료 시간(기본 60분)을 강제합니다. `JWT_SECRET_KEY`가 `change-me`면 서버가 기동을 거부합니다.
- **엔드포인트 보호**: `/api/v1/chat`과 `/healthz`를 제외한 모든 DevOps·프리뷰·로그 엔드포인트는 JWT 쿠키가 없으면 401을 반환합니다.
- **브랜치 화이트리스트**: `DEPLOY_ALLOWED_BRANCHES`(기본 `deploy,main`) 외 브랜치는 서버에서 거부되어 임의 배포를 차단합니다.
- **동시성 제어**: `AsyncReentrantLock`으로 단일 배포만 허용해 레이스 컨디션·충돌 커밋을 예방합니다.
- **서버 경계**: 프론트엔드는 FastAPI를 통해서만 내부 Repo/PM2에 접근하므로 클라이언트가 직접 `.env`나 Git에 접근할 경로가 없습니다. EC2/PM2/Nginx 권한, 보안 그룹 등 인프라 레벨 제한은 항상 설정 상태로 유지해야 합니다.

---

## ⚙️ 환경변수 레퍼런스

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `GEMINI_API_KEY` | `None` | Gemini 2.5 Flash 키. 없으면 모든 LLM 기능 fallback |
| `MONGODB_URI` / `MONGODB_DB_NAME` | `mongodb://127.0.0.1:27017` / `cherry_deploy` | Motor 클라이언트 설정 |
| `CHATBOT_REPO_PATH` | `/home/ec2-user/projects/SB_Hackathon_Cherry_Chatbot` | Repo1 루트 |
| `NGINX_{GREEN,BLUE}_PATH`, `NGINX_LIVE_SYMLINK` | `/var/www/cherry-deploy/...` | Blue/Green 경로 |
| `DEPLOY_DRY_RUN` | `false` | true 시 모든 명령은 실행 대신 메타데이터로만 기록 |
| `DEPLOY_DEFAULT_BRANCH`, `DEPLOY_ALLOWED_BRANCHES` | `deploy`, `deploy,main` | 파이프라인 허용 브랜치 |
| `FRONTEND_PROJECT_SUBDIR` | `frontend/my-dashboard` | npm 명령 실행 위치 |
| `FRONTEND_INSTALL_COMMAND` | `npm install` | 빈 문자열로 두면 단계 건너뜀 |
| `FRONTEND_BUILD_COMMAND` | `bash -lc "npm run build"` | 빌드 명령 |
| `FRONTEND_EXPORT_COMMAND` | `npm run export` | 빈값이면 export 생략 (= dev-server 모드) |
| `FRONTEND_BUILD_OUTPUT_SUBDIR` | `out` | export 결과 디렉터리. 공백이면 dev-server 모드로 컷오버 단계 skip |
| `PREVIEW_USE_GITHUB_COMPARE` | `false` | true + `GITHUB_COMPARE_*` 설정 시 GitHub Compare API 사용 |
| `PREVIEW_DIFF_MAX_CHARS` | `4000` | LLM prompt에 넣을 diff 길이 제한 |
| `LOGIN_USER`, `LOGIN_PASSWORD` | `cherry`, `coffee` | 고정 계정 |
| `JWT_SECRET_KEY` | `change-me` | 반드시 변경해야 하며 기본값이면 앱이 종료됨 |
| `AUTH_COOKIE_NAME` | `auth_token` | JWT 쿠키 키 |
| `DISPLAY_TIMEZONE` | `Asia/Seoul` | Status 응답에서 표시할 TZ |

전체 목록은 `api-code/settings.py` 에서 확인할 수 있습니다.

---

## 🤖 AI 프리뷰 & Git Diff
- `DeployService._prime_preflight_metadata()` 가 배포 시작 전에 diff/LLM/비용을 계산해 `metadata.summary.preflight`에 저장합니다.
- Diff 수집 순서: ① (옵션) GitHub Compare API → ② 로컬 `git diff --name-status`.
- `PREVIEW_DIFF_COMMAND` 템플릿으로 diff 커맨드를 조정 가능.
- LLM 프롬프트는 JSON 응답만 허용하도록 강제하며, 실패 시 fallback 요약 제공.
- Diff가 너무 크면 `PREVIEW_DIFF_MAX_CHARS` 길이만큼 잘라 `… (truncated)` 표시.

---

## 🔍 Observability & Troubleshooting
- **자동 롤백**: `npm install`, `pm2 start`, `pm2 npm` 명령 실패 시 `auto_recovery`가 실행되어 직전 성공 커밋으로 되돌립니다 (`force_push` 포함).
- **`/healthz`** 출력:
  - `pm2_processes`: `main-api`, `frontend-dev` 상태
  - `mongo`: ping 결과
  - `blue_green`: 현재 슬롯/standby/마지막 컷오버 타임스탬프
- **로그 위치**:
  - API: `pm2 logs main-api`
  - Mongo: `mongodb-data/mongod.log`
  - 배포 단계별 stdout/stderr: `/api/v1/tasks/{id}/logs` 응답 또는 Mongo 문서
- **자주 겪는 이슈**
  1. `JWT_SECRET_KEY must be configured` → `.env`에서 안전한 값 지정 후 재시작
  2. `motor` ImportError → `pip install -r requirements.txt` 재실행
  3. Gemini 키 없음 → 프리뷰/챗봇에서 fallback 메시지 (정상 동작)
  4. Blue/Green 디렉터리 권한 문제 → `/var/www/cherry-deploy/*` 소유자/권한 확인
  5. Mongo 비가동 → `/healthz` `mongo: unreachable` 로 표기되며, 앱은 인메모리 모드로 계속 동작하지만 배포 이력은 휘발됨

---

## 🧪 Testing & 개발 루틴
```bash
export DEPLOY_DRY_RUN=true
python -m pytest tests -q          # pytest 사용
# 혹은
python -m unittest tests/test_deploy_service.py
```
- 테스트에서는 InMemory Repo를 사용하므로 실제 Git/Nginx를 건드리지 않습니다.
- 실제 커맨드 실행을 검증하려면 `DEPLOY_DRY_RUN=false` + sandboxed Repo에서 수동으로 `/api/v1/deploy` 호출 후 stage 메타데이터를 확인하세요.

개발 팁:
- `uvicorn app_main:app --reload` 로 핫리로드
- Github Compare API 사용 시 `PREVIEW_USE_GITHUB_COMPARE=true`, `GITHUB_COMPARE_REPO=owner/repo`, `GITHUB_COMPARE_TOKEN=<PAT>` 설정
- 환경변수 변경 시 PM2 프로세스를 재시작해야 합니다.

---

## 📄 추가 문서 & 팀
- `AGENTS.md`: 실서버 운영 명령 모음 (PM2, certbot, Repo1 주의사항 등)
- `developmentplan.html`, `systemDevPlan.html`: 기획·설계 문서
- `swagger-api/*.yaml`: REST 스펙
- `tests/test_deploy_service.py`: 배포 파이프라인 dry-run 테스트 케이스

**Team Cherry**
- Backend / DevOps: sungwoo
- Infra: AWS EC2 + Nginx + PM2 + MongoDB
- AI: Gemini 2.5 Flash 연동

> 📬 서버: `13.125.116.92`, 도메인: `https://delight.13-125-116-92.nip.io`

---

배포를 “또 하고 싶어지는” 경험으로 만들기 위해 Cherry Deploy는 **안전장치·가시성·자동화를 기본값**으로 제공합니다. 문제가 생기면 `failure_context` 와 `/healthz` 로 즉시 파악하고, Auto rollback 으로 빠르게 복구하세요. 즐거운 배포 되세요! 🎢
