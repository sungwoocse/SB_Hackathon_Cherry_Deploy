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
- 구성 검증: `sudo nginx -t`, 재시작/리로드: `sudo systemctl reload nginx`

## 4. 서버 정보
- EC2 퍼블릭 IP: `13.125.116.92`
- 프로젝트 루트: `/home/ec2-user/projects/SB_Hackathon_Cherry_Deploy`
- MongoDB 로컬 설치 경로: `./mongodb` (tarball 전개) / 데이터: `./mongodb-data` (Git 추적 제외)
- MongoDB 실행 명령: `./mongodb/bin/mongod --dbpath mongodb-data --bind_ip 127.0.0.1 --port 27017 --fork --logpath mongodb-data/mongod.log`
- FastAPI 기본값은 **실제 배포** 수행 (`DEPLOY_DRY_RUN=false`). 드라이런이 필요하면 환경변수 `DEPLOY_DRY_RUN=true`로 PM2를 재시작하세요.
- Repo1(SB_Hackathon_Cherry_Chatbot) 기본 배포 브랜치는 `deploy` (옵션으로 `main`). Deploy 레포의 `upload` 브랜치는 백엔드 작업용으로만 사용합니다.
- 롤백 API: `/api/v1/rollback` → 최근 두 번의 성공 배포 commit 기준으로 <code>git fetch → checkout -B → reset --hard → clean -fdx → npm run build</code>를 수행. 실제 모드에서는 <code>git push origin +commit:branch</code>까지 실행해 원격 브랜치도 되돌립니다.

## 5. 향후 TODO 힌트
- 정적 프론트엔드 build 결과물을 Nginx로 서빙하려면 `location /` 블록 수정
