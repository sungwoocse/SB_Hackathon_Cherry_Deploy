# Cherry Deploy Project (가제)

SoftBank Hackathon 2025 (Team Cherry) - "Make Deployment Delightful" 테마 프로젝트

---

### 🍒 Team
* Cherry

### 🛠️ Core Tech Stack (예정)
* **Frontend:** Next.js
* **Backend:** Python
* **Cloud:** AWS EC2

chatbot 단독 배포

“이번 deploy 브랜치는 chatbot 서비스만 배포 대상입니다.”

/SB_Hackathon_Cherry_Deploy/
├── frontend/
│   └── my-dashboard/
│       ├── src/
│       │   ├── app/
│       │   │   ├── chatbot/      ← ✅ 실제 배포 대상 (서비스 단위)
│       │   │   ├── globals.css
│       │   │   ├── layout.tsx
│       │   │   └── page.tsx
│       │   └── components/
│       ├── package.json
│       └── tailwind.config.js
└── deploy/
    ├── deploy.sh                ← ✅ EC2 배포 자동 스크립트
    ├── ecosystem.config.js      ← PM2 프로세스 관리 설정
    └── nginx.conf               ← Nginx 리버스 프록시 설정


    
