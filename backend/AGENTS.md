# Cherry Deploy 운영 메모 (AGENTS)

## 1. FastAPI + Gemini 챗봇
- 앱 엔트리포인트: `app_main.py`
- `/api/v1/chat` → Google Gemini `gemini-2.5-flash` 호출 (API 키는 `.env`의 `GEMINI_API_KEY`)
- 로컬 실행 예시: `uvicorn app_main:app --host 0.0.0.0 --port 9001`

## 2. PM2 프로세스 관리
- 설치: `npm install -g pm2`
- 등록 명령:  
  `pm2 start "uvicorn app_main:app --host 0.0.0.0 --port 9001" --name main-api`
- 부팅 자동 시작:  
  `pm2 save` → `sudo env PATH=$PATH:/usr/bin /usr/lib/node_modules/pm2/bin/pm2 startup systemd -u ec2-user --hp /home/ec2-user`  
  시스템에 `pm2-ec2-user.service` 생성됨(`systemctl enable pm2-ec2-user`)
- 상태/로그 확인: `pm2 status`, `pm2 logs main-api`

## 3. Nginx 리버스 프록시 + HTTPS
- 설정 파일: `/etc/nginx/conf.d/cherry_deploy.conf`
- 80 → 443 리다이렉션 (ACME 검증 경로 제외)
- 발급받은 도메인: `delight.13-125-116-92.nip.io` (nip.io 동적 서브도메인)
- 인증서: `/etc/letsencrypt/live/delight.13-125-116-92.nip.io/fullchain.pem`, 키: `/etc/letsencrypt/live/.../privkey.pem`
- Certbot 명령:
  ```
  sudo /usr/bin/python3.9 -s /usr/bin/certbot --nginx \
    -d delight.13-125-116-92.nip.io \
    --agree-tos --register-unsafely-without-email --no-eff-email
  ```
- FastAPI 프록시 대상: `127.0.0.1:9001`
- 프론트엔드 요청(`https://delight.../`)은 `/var/www/cherry-deploy/current`에 정적 산출물이 있으면 우선 서빙하고, 없으면 PM2가 띄운 Next.js dev 서버(`127.0.0.1:3000`, 프로세스명 `frontend-dev`)로 프록시됩니다. 정적 배포를 다시 사용하려면 `current` 심볼릭 링크를 최신 Green 디렉터리로 맞춰두세요.
- 구성 검증: `sudo nginx -t`, 재시작/리로드: `sudo systemctl reload nginx`

## 4. 서버 정보
- EC2 퍼블릭 IP: `13.125.116.92`
- 프로젝트 루트: `/home/ec2-user/projects/SB_Hackathon_Cherry_Deploy`
- MongoDB 로컬 설치 경로: `./mongodb` (tarball 전개) / 데이터: `./mongodb-data` (Git 추적 제외)
- MongoDB 실행 명령: `./mongodb/bin/mongod --dbpath mongodb-data --bind_ip 127.0.0.1 --port 27017 --fork --logpath mongodb-data/mongod.log`
- FastAPI 기본값은 **실제 배포** 수행 (`DEPLOY_DRY_RUN=false`). 드라이런이 필요하면 환경변수 `DEPLOY_DRY_RUN=true`로 PM2를 재시작하세요.
- Repo1(SB_Hackathon_Cherry_Chatbot) 기본 배포 브랜치는 `deploy` (옵션으로 `main`). Deploy 레포의 `upload` 브랜치는 백엔드 작업용으로만 사용합니다.
- Repo1 프론트엔드는 이제 Next.js 구조(`frontend/my-dashboard`)로 정착했습니다. 새로 클론한 뒤 `cd /home/ec2-user/projects/SB_Hackathon_Cherry_Chatbot/frontend/my-dashboard && npm install`을 실행하면 `npm run dev`, `npm run build`가 정상 동작합니다. Next 빌드는 `.next`(또는 `next export` 사용 시 `out/`)를 생성하므로 Deploy 서비스 연동 시 산출물 경로를 확인하세요.
- 배포 API는 프론트 경로 하위에서 `npm install`을 실행한 뒤, 기본값으로 PM2를 이용해 `npm run dev`를 백그라운드(`frontend-dev` 프로세스명)로 띄웁니다. 정적 산출물을 사용하지 않으므로 컷오버 단계는 Skip 됩니다. 필요 시 `FRONTEND_INSTALL_COMMAND`, `FRONTEND_BUILD_COMMAND`, `FRONTEND_EXPORT_COMMAND`, `FRONTEND_BUILD_OUTPUT_SUBDIR` 환경변수로 명령/동작을 오버라이드할 수 있습니다.
- 롤백 API: `/api/v1/rollback` → 최근 두 번의 성공 배포 commit 기준으로 <code>git fetch → checkout -B → reset --hard → clean -fdx → npm install</code>을 수행한 뒤 동일한 PM2 `npm run dev` 명령을 재적용합니다. 실제 모드에서는 <code>git push origin +commit:branch</code>까지 실행해 원격 브랜치를 되돌립니다.
- 배포 실패 시 `npm install` 또는 PM2 `npm run dev` 단계가 에러를 반환하면 자동으로 롤백 로직을 호출, 직전 성공 배포 커밋으로 강제 복구합니다(성공/실패 상세는 배포 Task 메타데이터의 `failure_context.auto_recovery`에 기록).
- Preview API(`/api/v1/preview`)는 최근 성공 배포 대비 Git diff를 수집해 Gemini 2.5 Flash 모델로 요약을 생성합니다. `GEMINI_API_KEY`가 설정돼 있어야 하며, 모델은 `PREVIEW_LLM_MODEL`로 조정 가능합니다.
- Repo1 <code>deploy</code> 브랜치에는 배포 대상인 <code>frontend/my-dashboard</code>만 두고 다른 디렉터리는 올리지 마세요. (기본 Node 설치/빌드는 프론트 팀에서 별도로 관리)

## 5. 향후 TODO 힌트
- 정적 프론트엔드 build 결과물을 Nginx로 서빙하려면 `location /` 블록 수정
