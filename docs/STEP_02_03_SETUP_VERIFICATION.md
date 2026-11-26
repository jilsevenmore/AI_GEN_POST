# Step 02 & 03 — Setup and Verification Checklist

This checklist covers what is implemented in code and what must be configured/validated in a running environment.

## Step 02 — Brand & Digital Setup (Software)

### Implemented in code
- Public landing page at `/` (`frontend/src/pages/LandingPage.tsx`) with hero, modules, CTA, lead form, and social links.
- SEO component and global page-view tracking (`frontend/src/components/SEO.tsx`, `frontend/src/components/PixelTracker.tsx`, mounted in `frontend/src/App.tsx`).
- Public lead capture posts to `POST /api/v1/leads` (`frontend/src/api/services.ts`, `backend/app/api/v1/endpoints/leads.py`).
- Routing split so `/` is public and app routes (`/dashboard`, `/leads/dashboard`, `/create/:type`, `/review/:jobId`, `/library`, `/brand`, `/publish/:contentId`, `/settings`, `/legal/:page`, `/beta/*`) require authentication.
- Static SEO assets/defaults present: `frontend/public/robots.txt`, `frontend/public/sitemap.xml`, `frontend/public/og-default.svg`.

### Configure
- `frontend/.env` (copy from `frontend/.env.example`):
  - `VITE_SITE_URL` — production canonical/site URL.
  - `VITE_SOCIAL_LINKEDIN_URL`, `VITE_SOCIAL_INSTAGRAM_URL`, `VITE_SOCIAL_FACEBOOK_URL` — real profile URLs.
  - `VITE_META_PIXEL_ID`, `VITE_GOOGLE_MEASUREMENT_ID` — optional ad/analytics IDs.
  - `VITE_OG_IMAGE_URL` — optional absolute OG image override.
- Final brand assets/copy: logo, colors/typography, testimonials, module/pricing copy, and production OG image if replacing the placeholder SVG.
- Update hardcoded production-domain strings where needed for your deployment (`frontend/index.html`, `frontend/public/sitemap.xml`, `frontend/public/robots.txt` sitemap URL) if the domain differs.

### Verify in browser
- Unauthenticated visit to `/` renders the landing page.
- CTA scrolls/focuses the contact/lead form and submits successfully (success state shown; lead stored).
- Header/footer social links point to correct profiles.
- View page source / inspect head: title, description, canonical, OG/Twitter tags, JSON-LD, and OG image resolve correctly for the target domain.
- Pixel scripts initialize and page/lead events fire when IDs are configured (browser devtools/network + platform debuggers).
- Unauthenticated access to `/dashboard` (and other protected routes) redirects to `/login`; authenticated users can access app routes.

## Step 03 — Awareness & Content Marketing (Buffer publishing)

### Implemented in code
- AI job/create/generate/review flows and Buffer integration endpoints/UI exist.
- **Approve & Publish**: `POST /review/{job_id}/approve` can auto-enqueue publishing to connected/selected channels after uploading the approved image to Cloudinary (`backend/app/api/v1/endpoints/review.py`).
- Publish API: Buffer OAuth URL/connect/callback handling, channel list/disconnect, manual publish enqueue, attempt history, retry, queue stats (`backend/app/api/v1/endpoints/publish.py`, frontend Settings/Callback/Publish pages).

### Configure (required)
- **Buffer developer app**: set in `backend/.env`:
  - `BUFFER_CLIENT_ID`
  - `BUFFER_CLIENT_SECRET`
  - `BUFFER_REDIRECT_URI` (must match exactly; Buffer requires `https://` — use ngrok for local dev, e.g. `https://<id>.ngrok-free.app/auth/buffer/callback`)
  - Ensure frontend origin is allowed by CORS (`CORS_ORIGINS`) and app can reach Buffer API.
- **Redis/queue**: `REDIS_URL` configured and Redis running (publish queue depends on Redis).
- **Cloudinary**: `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` (and folders/preset as needed) so approved images get public URLs for Buffer.
- **AI/image/model keys** as required by your generation path (OpenRouter/OpenAI/Sunburst/HF/Ollama settings in `backend/.env`).
- Feature flags: `ENABLE_BUFFER_PUBLISHING=True` (default).

### Verify end-to-end
1. Start infra/services (Postgres, Redis, backend, frontend; worker/queue behavior as implemented).
2. Authenticate in app, open **Settings → Channels**, click **Connect Buffer**, complete OAuth, confirm channels appear and are active.
3. Create/generate content, review it, select image/text edits, choose schedule or immediate publish, and click **Approve & Publish**.
4. Confirm publish attempts are created/enqueued and reach success for Instagram/Facebook/LinkedIn targets; verify posts in Buffer/platforms.
5. Validate retry, token refresh/expiry, permissions, and failure surfaces (queue unavailable/Redis down, Cloudinary upload failure, Buffer errors).
6. Confirm content cadence/channel strategy and production accounts are the intended ones.

## Local run (reference)
- Infra: `cd infra && docker-compose up -d`
- Backend: `cd backend && pip install -r requirements.txt && cp .env.example .env` (edit) then `uvicorn app.main:app --reload --port 8000`
- Frontend: `cd frontend && npm install && cp .env.example .env` (edit) then `npm run dev`
- App: `http://localhost:5173`, API docs: `http://localhost:8000/api/v1/docs`
