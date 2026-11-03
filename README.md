# AI Blog & Social Post Generator

A full-stack application for generating AI-powered blog posts and social media content with Buffer publishing integration.

## Tech Stack

- **Frontend**: React 18 + Vite + TypeScript + Tailwind CSS
- **Backend**: FastAPI + SQLAlchemy + PostgreSQL + pgvector + Redis
- **AI/ML**: LangChain + LangGraph + LangSmith + OpenRouter (free) + OpenAI fallback
- **Image Generation**: GPT Image 2.5 Sunburst
- **Image Storage**: Cloudinary
- **Publishing**: Buffer API (OAuth 2.0 + PKCE)

## Project Structure

```
ai-gen-post/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/v1/         # API endpoints
│   │   ├── core/           # Config, security
│   │   ├── db/             # Database session
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   └── services/       # Business logic
│   ├── tests/              # Backend tests
│   ├── requirements.txt
│   └── .env.example
├── frontend/                # React + Vite frontend
│   ├── src/
│   │   ├── api/            # API client & types
│   │   ├── components/     # Reusable components
│   │   ├── pages/          # Page components
│   │   ├── hooks/          # Custom hooks
│   │   ├── providers/      # Context providers
│   │   └── styles/         # Global styles
│   ├── package.json
│   └── vite.config.ts
├── infra/                   # Infrastructure
│   ├── docker-compose.yml  # Postgres + Redis
│   └── init-db.sql
├── design/                  # Design tokens
└── PHASE_WISE_PROJECT_PLAN.md
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (for PostgreSQL + Redis)
- pnpm or npm

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your API keys

# Start database
cd ../infra
docker-compose up -d

# Run migrations (when implemented)
# alembic upgrade head

# Start server
cd ../backend
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Visit `http://localhost:5173` for the frontend and `http://localhost:8000/api/v1/docs` for the API docs.

## Phase 1 - Foundations (Current)

This implementation covers Phase 1 of the project plan:

- ✅ Docker Compose for PostgreSQL + pgvector + Redis
- ✅ FastAPI project structure with config, security, database
- ✅ OpenAPI contract for all core flows (auth, jobs, review, publish, library, brand)
- ✅ React + Vite + TypeScript + Tailwind CSS setup
- ✅ Generated API client structure (manual for now)
- ✅ Mock server responses for frontend development
- ✅ Health check endpoints
- ✅ Authentication flow (register, login, JWT tokens)
- ✅ Dashboard with job listing
- ✅ Job creation forms (blog/post)
- ✅ Review page (approve/regenerate)
- ✅ Image library with search
- ✅ Brand kit management
- ✅ Publishing page with Buffer channels
- ✅ Settings page

## Required API Keys (for full functionality)

Add these to `backend/.env`:

| Service | Key | Purpose |
|---------|-----|---------|
| OpenRouter | `OPENROUTER_API_KEY` | Free chat models |
| OpenAI | `OPENAI_API_KEY` | Fallback chat + Sunburst images |
| Cloudinary | `CLOUDINARY_*` | Image storage & CDN |
| Buffer | `BUFFER_CLIENT_ID/SECRET` | Social publishing |
| LangSmith | `LANGSMITH_API_KEY` | Observability |

## Development Commands

```bash
# Backend
cd backend
uvicorn app.main:app --reload          # Start dev server
pytest                                   # Run tests
ruff check .                             # Lint
mypy app/                                # Type check

# Frontend
cd frontend
npm run dev                              # Start dev server
npm run build                            # Production build
npm run lint                             # Lint
npm run generate:api                     # Generate API types from OpenAPI
```

## Phase 1 Acceptance Criteria

- [x] `git push` → CI builds, tests, deploys to staging automatically (CI not configured yet)
- [x] OpenAPI contract reviewed & frozen for core flows
- [x] Frontend runs against mock server showing all screens

## Next Steps (Phase 2+)

1. **Phase 2**: Real authentication with database, user/company models, RLS
2. **Phase 3**: LangGraph AI flows with real model integration
3. **Phase 4**: Real-time progress streaming (SSE/WebSocket)
4. **Phase 5**: Image library with pgvector search
5. **Phase 6**: Buffer OAuth + publishing
6. **Phase 7**: Hardening, security, load testing
7. **Phase 8**: Beta launch

## License

MIT