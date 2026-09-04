# Travel Agent Web Form (Next.js)

Custom web form / booking wizard for the YB Travel Agent. It collects structured
trip requests (destination, dates, travelers, budget, preferences) with an RTL
Hebrew UI and forwards them to the FastAPI backend (`POST /api/webform`).

## Stack
- Next.js (App Router) + TypeScript
- Tailwind CSS (RTL Hebrew UI)
- Prisma
- Google Analytics 4

## Getting started
```bash
cp .env.example .env   # fill in values
yarn install
yarn dev
```

## Environment variables
See `.env.example`. Key values:
- `NEXT_PUBLIC_API_URL` — base URL of the FastAPI backend.
- `NEXT_PUBLIC_GA_MEASUREMENT_ID` — Google Analytics 4 ID.
- `DATABASE_URL` — Prisma connection string.

## Notes
- All user-facing text is in Hebrew (RTL); source code is in English.
- This app is the "Web Form" channel of the multi-channel travel agent bot
  (the shared agent core lives in the repository root).
