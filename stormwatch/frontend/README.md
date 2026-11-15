# STORMWATCH Frontend

The frontend is a Vite, TypeScript, and Phaser application. It presents the Eastbank flood map, interactive data science learning tasks, contextual briefings from Maya, and the end-of-mission report.

## Requirements

- Node.js 20 or newer
- npm (the project includes `package-lock.json`)
- The FastAPI backend running at `http://127.0.0.1:8000`

## Local development

```powershell
npm ci
npm run dev
```

Open <http://127.0.0.1:5173>. Vite proxies `/api` requests to the local backend. To use a different backend URL, copy `.env.example` to `.env.local` and set `VITE_API_PROXY_TARGET`.

## Production build

```powershell
npm run build
```

The generated site is written to `dist/`. Build output and dependencies are ignored by Git.
