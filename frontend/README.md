# Cherry Chatbot Frontend

SoftBank Hackathon 2025 ― Team Cherry의 DevOps 배포 모니터링 대시보드와 AI 챗봇 UI입니다.  
`frontend/my-dashboard/` 안에 위치한 단일 Next.js 16 (App Router) 애플리케이션으로, FastAPI 백엔드(`SB_Hackathon_Cherry_Deploy`)와 쿠키 세션 기반으로 통신합니다.

---

## 빠른 시작

### 요구 사항
- Node.js 20.x 이상 (Next.js 16 + React 19 지원)
- npm 10.x 이상
- FastAPI 백엔드가 로컬 혹은 원격에서 접근 가능해야 하며 쿠키 인증(CORS `credentials`)을 허용해야 합니다.

### 설치 & 개발 서버

```bash
cd frontend/my-dashboard
npm install
echo "NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:9001" > .env.local  # 필요 시 수정
npm run dev
# http://localhost:3000 접속
```

### npm 스크립트

| 명령 | 설명 |
| --- | --- |
| `npm run dev` | 개발 서버 + Hot Reload |
| `npm run build` | 프로덕션 빌드 및 정적 export (`out/`) |
| `npm run export` | `next build`와 동일 (별도 명령으로 유지) |
| `npm run start` | 빌드 산출물 프리뷰 서버 |
| `npm run lint` | `eslint-config-next` + TypeScript |

---

## 환경 변수

| 변수 | 설명 | 기본값 |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | FastAPI 엔드포인트 기본 경로. 모든 fetch/Axios 요청이 이 값을 기준으로 전송되며, 쿠키 인증을 위해 프로토콜/도메인이 백엔드와 일치해야 합니다. | 개발: `http://127.0.0.1:9001`, 프로덕션: `https://delight.13-125-116-92.nip.io` (`src/lib/api.ts`) |

> `.env.local`은 `frontend/my-dashboard/`에 위치해야 하며 Git에 커밋하지 않습니다. 값 끝에 `/`가 붙어도 `src/lib/api.ts`에서 자동으로 제거됩니다.

---

## 주요 기술 스택

- **Framework**: Next.js 16 (App Router, Client Components 중심)
- **언어**: TypeScript 5, React 19
- **스타일**: Tailwind CSS 4, 커스텀 CSS (`ChatStyles.css`)
- **애니메이션**: Framer Motion, Lottie React
- **데이터**: Axios, Fetch API
- **빌드**: 정적 export (`next.config.ts` → `output: "export"`)

---

## 디렉터리 구조

```
frontend/
├── README.md
└── my-dashboard/
    ├── src/
    │   ├── app/
    │   │   ├── components/        # ChatWidget, FloatingCharacter 등 공용 컴포넌트
    │   │   ├── deploy/            # /deploy 페이지
    │   │   ├── globals.css        # Tailwind 엔트리 + 글로벌 스타일
    │   │   ├── layout.tsx         # 루트 레이아웃
    │   │   └── page.tsx           # 메인 대시보드
    │   ├── lib/api.ts             # API 기본 설정
    │   └── types/deploy.ts        # FastAPI 응답 타입
    ├── public/                    # 이미지, 오디오, mock JSON, Lottie 등
    ├── legacy/                    # 사용하지 않는 실험 UI (빌드 제외)
    ├── out/                       # `npm run build` 결과물
    ├── package.json / lockfile
    ├── tsconfig.json
    ├── tailwind.config.js
    └── eslint.config.mjs
```

### `legacy/` 폴더
초기 UI 실험 코드(`DeployControl.tsx`, `ChatPopup.tsx`, `lib-api.ts`)를 보관합니다. `tsconfig.json`과 ESLint ignore에 포함되어 실제 빌드에 영향이 없습니다.

---

## 애플리케이션 개요

### 1. 메인 대시보드 (`src/app/page.tsx`)
Client Component 하나가 로그인, 배포 프리뷰, 실시간 Stage 폴링, Blue/Green 상태, 위험도, 작업 히스토리, 챗봇 토글까지 모두 처리합니다.

주요 섹션:
- **Hero 카드**: 로그인 폼(세션 없을 때), 현재 task ID 및 진행률(세션 있을 때), Blue/Green 요약.
- **Preview Timeline & Live Stages**: `/api/v1/preview`, `/api/v1/status/{task_id}` 응답을 시각화.
- **Blue/Green 패널**: `/healthz`와 프리뷰 응답의 `blue_green_plan` 메타데이터.
- **Warnings & Risk Assessment**: diff 경고, LLM 요약, 위험 평가.
- **Recent Tasks**: `/api/v1/tasks/recent?limit=5`.
- **Preflight Modal**: LLM summary, GitHub compare 정보, 파일 변경 통계, 예상 단계 타임라인, 실행 명령, Blue/Green 계획 등 배포 전 모든 정보를 집약.
- **Rollback Modal**: 롤백 확인 후 `/api/v1/rollback` 호출.
- **ChatWidget**: 하단 플로팅 챗봇을 토글하는 버튼 포함.

상태 값은 `sessionStorage`(`cherry.currentTaskId`)를 활용해 새로고침 후에도 이어집니다.

### 2. 배포 비주얼라이저 (`src/app/deploy/page.tsx`)
`/deploy` 라우트는 Lottie 애니메이션과 단일 진행 바를 제공하며 `/api/v1/deploy` → `/api/v1/status/{task_id}` 폴링 흐름을 독립적으로 체험할 수 있습니다.

### 3. 챗봇 위젯 (`src/app/components/ChatWidget.tsx`)
- Stage 윈도우(2개씩)와 60초 게이지, 메시지 리스트, 입력창을 포함합니다.
- `/api/v1/chat` 응답을 글자 단위로 출력해 스트리밍처럼 보이게 하며, 성공/실패 시 `public/audios/`에 있는 사운드를 단 한 번만 재생합니다.
- `FloatingCharacter.tsx`는 화면 중앙을 부드럽게 이동하는 캐릭터를 표현해 배포 분위기를 시각적으로 강조합니다.

---

## API 연동 요약

| HTTP | 엔드포인트 | 용도 |
| --- | --- | --- |
| `GET /api/v1/auth/me` | 세션 검증 |
| `POST /api/v1/auth/login` / `logout` | 로그인/로그아웃 |
| `GET /api/v1/preview` | Hero 요약, 타임라인, Preflight 모달 기본 데이터 |
| `GET /api/v1/preview?mode=preflight` | 상세 프리뷰 모드 |
| `POST /api/v1/deploy` | 배포 시작 |
| `POST /api/v1/rollback` | 롤백 시작 |
| `GET /api/v1/status/{task_id}` | 진행률/Stage 폴링 |
| `GET /api/v1/tasks/recent` | 최근 배포 목록 |
| `GET /healthz` | Blue/Green 상태 백업 |
| `POST /api/v1/chat` | 챗봇 대화 |

모든 요청은 `src/lib/api.ts`에서 정의한 `API_BASE_URL`, `JSON_HEADERS`를 사용하며 Axios 인스턴스에는 `withCredentials: true`가 설정되어 있습니다.

---

## 정적 자산 & 빌드

- `public/images/*.png`: 캐릭터 일러스트 (Hero, 프리뷰 모달, FloatingCharacter 등).
- `public/audios/*.mp3`: 성공/실패 사운드.
- `public/mock/*.json`: 로컬 목업 데이터 (현재 코드에서는 자동 사용 X).
- `public/lottie/*.json`: `/deploy` 페이지에서 사용하는 애니메이션. 저장소에는 포함되지 않았으므로 배포 환경에서 제공해야 합니다.
- `out/`: `npm run build` 후 생성되는 정적 산출물. S3, CloudFront 등 정적 호스팅에 그대로 업로드할 수 있습니다.

배포 전 `npm run lint`로 기본 규칙을 통과했는지 확인하는 것을 권장합니다.

---

## 문제 해결

| 증상 | 점검 포인트 |
| --- | --- |
| 401 또는 로그인 실패 반복 | 백엔드 CORS 설정에서 `credentials` 허용 여부, HTTPS 도메인 일치 여부, `.env.local` 값 확인 |
| `/deploy` 애니메이션 미표시 | `public/lottie/*.json` 경로에 파일이 존재하는지 확인 |
| 배포 진행률이 갱신되지 않음 | 세션 스토리지에 오래된 `task_id`가 남아 있거나 백엔드 상태 API가 중단되었을 수 있음 |
| 프리뷰 모달이 비어 있음 | FastAPI에서 `diff_stats`, `risk_assessment`, `llm_preview` 필드를 반환하는지 확인 |
| ChatWidget 응답 지연 | `/api/v1/chat` 처리 시간 확인, 브라우저 콘솔 네트워크 탭으로 요청 상태 점검 |

필요 시 `src/app/page.tsx`의 콘솔 로그를 활성화하고, FastAPI 서버 로그에서 동일한 task_id를 추적하면 원인 파악이 빠릅니다.

---

## 확장 가이드

1. **타입 먼저**: 백엔드 응답이 바뀌면 `src/types/deploy.ts`를 업데이트하세요. 컴파일 타임에 누락을 확인할 수 있습니다.
2. **API 재사용**: 새 fetch 로직을 추가할 때는 `src/lib/api.ts`의 헬퍼를 사용해 Base URL/헤더/쿠키 설정을 공유합니다.
3. **컴포넌트 배치**: 재사용 가능한 UI는 `src/app/components/`에, 라우트 전용 코드는 해당 디렉터리에 배치해 구조 일관성을 유지합니다.
4. **스타일**: Tailwind 유틸리티를 우선 사용하고, 필요 시 `globals.css`나 전용 CSS 파일에서 커스텀 규칙을 정의합니다.
5. **Legacy 활용**: `legacy/` 폴더의 실험 코드를 참고해 새로운 기능을 만들 수 있지만, 실제 적용 시 `src/`로 옮기고 타입/빌드 설정을 조정해야 합니다.

이 문서를 통해 `frontend/my-dashboard` 프로젝트를 처음 클론한 개발자라도 구조와 동작 방식을 빠르게 파악하고 개발을 이어갈 수 있습니다.
