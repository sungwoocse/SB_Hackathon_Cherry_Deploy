# ===============================
# SB_Hackathon_Cherry_Chatbot FE 배포용 디렉토리 구조 생성 스크립트 (안정 버전 v2)
# ===============================

# 1️⃣ 기본 경로 설정
$basePath = "C:\Users\unknown\Documents\SB_Hackathon_Cherry_Deploy"
$deployPath = Join-Path $basePath "deploy"

# 2️⃣ 기존 deploy 폴더 삭제 후 새로 생성
if (Test-Path $deployPath) {
    Write-Host "🔁 기존 deploy 폴더를 삭제 중..."
    Remove-Item -Recurse -Force $deployPath
}
New-Item -ItemType Directory -Force -Path $deployPath | Out-Null

# 3️⃣ 필수 폴더 생성
$folders = @(
    "public/lottie",
    "mock",
    "src/app/deploy",
    "src/components",
    "src/styles"
)
foreach ($f in $folders) {
    New-Item -ItemType Directory -Force -Path (Join-Path $deployPath $f) | Out-Null
}

# 4️⃣ 기본 package.json 생성
@'
{
  "name": "devops-frontend",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "14.2.4",
    "react": "18.3.1",
    "react-dom": "18.3.1",
    "lottie-react": "^2.4.0",
    "framer-motion": "^11.0.0"
  },
  "devDependencies": {
    "typescript": "^5.6.3",
    "tailwindcss": "^4.0.0",
    "@types/react": "^19.0.0",
    "@types/node": "^20.0.0"
  }
}
'@ | Out-File -FilePath (Join-Path $deployPath "package.json") -Encoding utf8

# 5️⃣ 예시 mock 데이터 생성
@'
{
  "status": "idle",
  "cost": 0,
  "risk": "low",
  "timestamp": "2025-11-06T00:00:00"
}
'@ | Out-File -FilePath (Join-Path $deployPath "mock\deployStatus.json") -Encoding utf8

# 6️⃣ 완료 메시지 (문자열 따옴표 충돌 완전 방지)
Write-Host '✅ deploy 디렉토리 구조 생성 완료!'
Write-Host ("📁 경로: " + $deployPath)
Write-Host ''
Write-Host '이제 아래 명령을 실행하세요:'
Write-Host ('  cd "' + $deployPath + '"')
Write-Host '  npm install'
Write-Host '  npm run build'
