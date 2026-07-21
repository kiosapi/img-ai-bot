# imgaai public web (CF Pages)

Static export Next.js app for end users. Admin stays in `../web/`.

## Spec

See `../PUBLIC-WEB.md`.

## Setup

```bash
cd web-app
cp .env.example .env.local
# set NEXT_PUBLIC_API_URL + NEXT_PUBLIC_BOT_USERNAME
npm ci
npm run dev   # http://localhost:3001
```

## Build / deploy CF Pages

```bash
npm run build
# upload out/ via wrangler pages deploy out/ --project-name=imgaai
```

BotFather: `/setdomain` → your Pages hostname (e.g. `imgaai.pages.dev`).

## Env

| Key | Example |
|-----|---------|
| NEXT_PUBLIC_API_URL | `https://api.example.com` or `http://IP:PORT` |
| NEXT_PUBLIC_BOT_USERNAME | `imgaai_bot` (no @) |

API must allow CORS origin of this site (`WEB_CORS_ORIGINS`) and prefer Bearer token auth (stored in localStorage) for cross-origin.
