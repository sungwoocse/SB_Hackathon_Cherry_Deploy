# Cherry Deploy Project (가제)

SoftBank Hackathon 2025 (Team Cherry) - "Make Deployment Delightful" 테마 프로젝트

---

### 🍒 Team
* Cherry

### 🛠️ Core Tech Stack (예정)
* **Frontend:** Next.js
* **Backend:** Python
* **Cloud:** AWS EC2

      1. npm install -g pm2 (한 번만 실행)
      2. 백엔드 디렉터리로 이동: cd /home/ec2-user/projects/SB_Hackathon_Cherry_Deploy
      3. 프로세스 등록: pm2 start "uvicorn app_main:app --host 0.0.0.0 --port 9001" --name main-api
      4. 상태 확인: pm2 status (또는 pm2 logs main-api, pm2 restart main-api)
      5. 재부팅 후에도 자동 실행되게: pm2 startup systemd, 안내되는 명령 1회 실행 후 pm2 save
         이렇게 하면 PM2가 uvicorn 프로세스를 백그라운드에서 관리해줍니다.