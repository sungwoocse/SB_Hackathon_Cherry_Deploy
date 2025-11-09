This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## API Base URL 설정

대시보드는 FastAPI 백엔드와 통신하므로, 환경변수 `NEXT_PUBLIC_API_BASE_URL`을 이용해 대상 서버를 지정할 수 있습니다.

```bash
# 예시) 로컬 FastAPI (swagger spec 의 127.0.0.1:9001)
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:9001 npm run dev

# 예시) 배포된 Nginx HTTPS 엔드포인트
NEXT_PUBLIC_API_BASE_URL=https://delight.13-125-116-92.nip.io npm run dev
```

값을 지정하지 않으면 개발 모드에서는 `http://127.0.0.1:9001`, 프로덕션 빌드에서는 `https://delight.13-125-116-92.nip.io`가 기본값으로 사용됩니다.
