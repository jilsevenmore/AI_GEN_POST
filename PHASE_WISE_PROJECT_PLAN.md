# AI Blog & Social Post Generator – Phase-Wise Project Plan

**Prepared:** 30 October 2026  
**Stack:** React · FastAPI · LangChain + LangGraph + LangSmith · OpenRouter (free) + OpenAI fallback · GPT Image 2.5 Sunburst · Cloudinary · Buffer · PostgreSQL + pgvector · Redis  
**Target Launch:** ~5 February 2027 (14 weeks from 2 Nov 2026)

---

## Overview

This document breaks the distilled project plan into eight execution phases. Each phase lists:

- **Goal** – the single outcome that marks the phase complete
- **Timeline** – weeks and calendar dates
- **Owner(s)** – who drives the work
- **Key Deliverables** – concrete, verifiable outputs
- **Dependencies** – what must finish first
- **Acceptance Criteria** – how we know it's done
- **Risks & Mitigations** – specific to this phase

Phases overlap; the frontend works against mock data while the backend is built.

---

## Phase 0 – Discovery & Spikes
**Weeks 1–2** | **2 Nov – 13 Nov 2026**  
**Owner:** PM + AI/ML + Backend + DevOps + Design  
**Dependency:** None

### Goal
Validate every risky assumption before writing production code.

### Key Deliverables
| Spike | Question | Success Metric |
|-------|----------|----------------|
| **Sunburst** | Accepts 1–16 refs? Real cost/time/quality? | Cost per image known ±30%; ref limit confirmed |
| **Free chat models** | Which 3 named models + `openrouter/free` router pass test briefs? | JSON reliability, writing quality, limits measured |
| **Fallback** | 429 → OpenAI switch works? Circuit breaker triggers? | Automatic failover in <5 s, LangSmith logs count |
| **Buffer OAuth** | Can register app, complete PKCE, post to IG/FB/LI test accounts? | End-to-end test post succeeds |
| **Cloudinary links** | Buffer + IG accept Cloudinary URLs? What happens at credit exhaustion? | Verified; alerts at 70%/90% credits designed |
| **Model health check** | Daily automated eval against 30 briefs catches vanishing models? | Alert fires when model drops/vanishes |
| **Design flows** | Low-fi screens for: Login, Blog/Post forms, Review, Library, Brand Kit | Screens reviewed with PM |

### Acceptance Criteria
- [ ] All spike reports written and handed to PM
- [ ] One manual end-to-end run (prompt → image → Buffer test post) works
- [ ] Cost per post estimated within ~30%
- [ ] Go/no-go decisions recorded for Buffer OAuth and free-first routing

### Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| Buffer OAuth not available | Shortlist alternatives (Meta API, LinkedIn API) behind `Publisher` interface |
| Free models too limited | $10 top-up raises cap to 1,000 req/day (~250 generations) |
| Cloudinary stops serving at credit limit | Tigris/R2 bucket behind own domain as fallback |

---

## Phase 1 – Foundations
**Weeks 2–4** | **9 Nov – 27 Nov 2026**  
**Owner:** DevOps + Backend + Frontend + Design + QA  
**Dependency:** Phase 0 decisions

### Goal
A working skeleton every role can build on: infra, repo, CI/CD, DB, API contract, mock server.

### Key Deliverables

| Area | Deliverable |
|------|-------------|
| **DevOps** | Docker Compose / containers; local, dev, staging envs; Postgres + pgvector; Redis; Cloudinary folders & upload presets; secrets manager; basic logging; spend alerts (OpenAI, OpenRouter, Cloudinary) |
| **Backend** | FastAPI project structure; settings (model lists, limits, feature flags); health endpoints; OpenAPI contract for: auth, jobs, review, publish, library |
| **Frontend** | React + Vite/Next.js; routing; generated API client from OpenAPI; MSW mock server mirroring contract |
| **Design** | Final hi-fi screens + design tokens (colors, spacing, components) |
| **QA** | Test strategy; test accounts matrix; Playwright scaffold |

### Hand-offs
1. DevOps → Backend/AI/ML: credentials, DB connection strings
2. Backend → Frontend: frozen OpenAPI spec (core flows)
3. Design → Frontend: component library, screen specs

### Acceptance Criteria
- [ ] `git push` → CI builds, tests, deploys to staging automatically
- [ ] OpenAPI contract reviewed & frozen for core flows
- [ ] Frontend runs against mock server showing all screens

### Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| Schema drift between contract & implementation | Contract tests in CI (Schemathesis / Pact) |
| pgvector not available on managed Postgres | Use Neon / Supabase / self-hosted with extension |

---

## Phase 2 – Login & Data Model
**Weeks 3–5** | **16 Nov – 4 Dec 2026**  
**Owner:** Backend + Frontend + DevOps + Security + QA  
**Dependency:** Phase 1 skeleton

### Goal
Safe multi-tenant sign-in and the core relational schema.

### Key Deliverables

| Component | Details |
|-----------|---------|
| **Auth** | Signup, login, JWT access + refresh tokens, password reset (or Clerk/Auth0 to save time); OAuth tokens encrypted at rest |
| **Tables** | `users`, `companies`, `brand_kits`, `jobs`, `contents`, `images`, `channel_connections`, `publish_attempts`, `quotas` |
| **RLS / Scoping** | Every query filtered by `company_id`; automated tests prove user A ≠ user B |
| **Migrations** | Alembic; forward + backward verified |
| **Frontend** | Login/signup pages; protected routes; empty dashboard with "Write Blog" / "Generate Post" cards |

### Acceptance Criteria
- [ ] New user signs up → logs in on staging
- [ ] Automated tests: cross-company data access returns 403/empty
- [ ] Migrations run up & down cleanly
- [ ] Security review of token storage & company separation signed off

### Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| Auth complexity eats time | Use hosted auth (Clerk) for MVP; migrate later if needed |
| Schema changes after Phase 3 | Keep migrations small; review with AI/ML before Phase 3 |

---

## Phase 3 – AI Core (LangGraph Flows)
**Weeks 4–8** | **23 Nov – 1 Jan 2027**  
**Owner:** AI/ML + Backend + QA + DevOps  
**Dependency:** Phases 1 & 2

### Goal
Reliable, regenerable text + image generation with free-first routing, fallback, safety, and human-in-the-loop.

### Key Deliverables

#### LangGraph Flow (per Section 3)
1. **Load context** – brand kit, preferences
2. **Expand prompt** – short description → text brief + image brief
3. **Find reference images** – keyword → tag match → vector search → rank → top 1–4
4. **Parallel: Write text + Generate image** – streaming progress
5. **Safety check** – text + image moderation
6. **Adapt per network** – LI long, FB medium, IG short + hashtags
7. **Human review (interrupt)** – pause, show preview, accept / regenerate with note
8. **Publish prep** – upload image to Cloudinary (public link), queue Buffer job
9. **Save to library** – approved image + tags + prompt + vector

#### Model Router
- Free OpenRouter models (pinned list + `openrouter/free` router)
- OpenAI fallback on 429 / timeout / bad JSON (1 retry)
- Circuit breaker: N failures → route all to OpenAI for T minutes
- Company setting: "OpenAI only" (no prompt logging)

#### Observability & Guards
- Full LangSmith traces (prompts, latency, cost, fallback count)
- Daily model health check (30 briefs) → alert on quality drop
- Per-user quotas: daily free-request budget, daily spend cap
- Background workers (Celery / Dramatiq / FastAPI BackgroundTasks) with timeouts & idempotency

### Hand-off
AI/ML → Backend: flow inputs/outputs (Pydantic models) by **Week 5** so integration starts early.

### Acceptance Criteria
- [ ] 90% of 30 test briefs → acceptable text + image within 2 tries on free models
- [ ] OpenAI fallback triggers when free route disabled
- [ ] Regenerate preserves previous result; feedback note incorporated
- [ ] LangSmith shows complete traces for every step
- [ ] Safety step blocks known bad content

### Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| Free model quality inconsistent | Pinned list + daily eval; $10 top-up for higher limits |
| LangGraph checkpoint perf | Postgres checkpoints; tune `checkpoint_interval` |
| Image gen too slow for web request | **Must** run in background worker; stream progress via SSE/WS |

---

## Phase 4 – Frontend Flows
**Weeks 4–9** | **23 Nov – 8 Jan 2027**  
**Owner:** Frontend + Design + QA + Backend (API tweaks)  
**Dependency:** API contract (Phase 1), real AI output (Phase 3 Week 5+)

### Goal
Polished, accessible, tested UX for the entire happy path + regenerate loop.

### Key Deliverables

| Screen / Feature | Details |
|------------------|---------|
| **Dashboard** | Two cards: "Write Blog" / "Generate Post" |
| **Forms** | Title, topic, tone, audience, keywords, image description, platforms (multi-select) |
| **Live Progress** | SSE/WS: expanding prompt → writing → generating image → safety → adapting |
| **Review** | Side-by-side text + image; inline text edit; regenerate button + note box; version history drawer |
| **Error/Empty States** | Rate limit, timeout, safety block, quota exceeded – with retry / upgrade CTA |
| **Free-model Notice** | Banner when free models used; link to terms |
| **Accessibility** | WCAG 2.1 AA: focus order, ARIA labels, contrast, keyboard nav |

### QA & Design
- Week 7: 3–5 real-user tests → fix list
- Playwright e2e: login → form → preview → regenerate → approve
- Component tests (React Testing Library)

### Acceptance Criteria
- [ ] User completes full journey on staging with real AI output
- [ ] Buttons enable/disable correctly (no double-submit)
- [ ] Zero critical a11y issues (axe-core)
- [ ] Test users finish unaided

### Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| Backend API changes late | Contract tests; Backend adjusts within 1 day of Frontend feedback |
| Long AI waits feel broken | Skeleton loaders, stepper progress, optimistic UI for regenerate |

---

## Phase 5 – Image Library & Brand Memory
**Weeks 7–10** | **14 Dec 2026 – 15 Jan 2027**  
**Owner:** AI/ML + Backend + Frontend + PM/Content + QA  
**Dependency:** Phase 3 image flow working

### Goal
Reuse approved images via references; enforce brand consistency without re-typing.

### Key Deliverables

#### AI/ML
- Keyword extraction from prompt → tag match → vector search (pgvector) → rank by recency + past approval
- Reference-role prompts: "style ref", "subject ref", "logo ref" (max 2 style + logo)
- A/B comparison: with vs. without references → measurable quality delta

#### Backend
- `POST /library/images` (save on approve), `GET /library/search`, `PATCH /library/tags`
- Private scope (per company) + global scope (curated, opt-in)
- Brand kit CRUD: name, logo, colors, address, tagline, tone
- Logo/address compositing via Pillow **after** Sunburst (model misses small text)
- Cloudinary cleanup job: published >30 days → delete; rejected drafts >7 days → delete
- Vector index on `images.search_vector` (pgvector HNSW)

#### Frontend
- Brand Kit page (form + logo upload + preview)
- Library browser: grid, search, tag edit, "Use as reference" picker, ref on/off toggle

#### Content / PM
- Seed global library: 50–100 curated festival/occasion images (tagged, vectorized)

### Acceptance Criteria
- [ ] Relevant reference ranks top-3 for ≥80% of test prompts with a stored match
- [ ] Zero cross-company leakage in automated tests
- [ ] Logo + address render correctly on composited image
- [ ] References measurably improve output (or default OFF)

### Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| Near-copies from too many refs | Limit to 2 style + logo; explicit role in prompt; A/B test |
| Vector search slow at scale | HNSW index; `ivfflat` fallback; monitor `EXPLAIN ANALYZE` |
| Global library contamination | Review gate before global insert; company opt-in only |

---

## Phase 6 – Buffer Publishing
**Weeks 8–11** | **21 Dec 2026 – 22 Jan 2027**  
**Owner:** Backend + Frontend + AI/ML + DevOps + QA + PM  
**Dependency:** Phase 2 (OAuth tokens), Phase 3 (content ready), Phase 0 spike results

### Goal
Approved content reaches Instagram, Facebook, LinkedIn safely, with scheduling, retries, and clear errors.

### Key Deliverables

#### Backend
- `Publisher` interface (Buffer impl + stub for alternatives)
- Buffer Connect / Disconnect (OAuth PKCE, token refresh, encrypted storage)
- Channel list → channel picker on approval
- Per-network text (LI/FB/IG) + image shapes (square 1:1, 4:5)
- Public Cloudinary link created **at approval moment**
- Throttled queue: ≤100 req/15 min/app (verify) → Redis + worker
- Idempotency key per publish attempt → prevent double-post
- Retries: exponential backoff, dead-letter queue after N failures
- Stored status: `pending` | `sent` | `failed` | `retrying` with error detail
- Errors surfaced: disconnected channel, expired token, rejected image, image fetch fail, rate limit

#### Frontend
- Connect Channels screen (OAuth flow)
- Channel picker + schedule / post-now on approval
- Status page: per-channel result + retry button

#### AI/ML
- Final per-network text variants + image aspect ratios

#### DevOps
- Worker autoscaling; dead-letter monitoring; Cloudinary credit alerts (70%/90%)

#### PM
- Confirm each network's automation/AI-content rules → write into Terms

### Acceptance Criteria
- [ ] Approve → correct posts on all 3 test channels
- [ ] Failure gives user a clear next step (reconnect, retry, edit image)
- [ ] Rapid double-click never double-posts (idempotency key)
- [ ] Burst test (50 posts) respects rate limit, no 429s

### Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| Buffer OAuth not multi-user | Spike in Phase 0; `Publisher` interface allows swap |
| Rate limits lower than docs | Conservative throttle (80% of documented); monitor 429s |
| Cloudinary link rejected | Fallback: R2/Tigris bucket behind own domain |

---

## Phase 7 – Hardening
**Weeks 11–12** | **11 Jan – 22 Jan 2027**  
**Owner:** QA + Security + Backend + AI/ML + DevOps + PM  
**Dependency:** Phases 3–6 feature-complete

### Goal
Production-ready: secure, performant, observable, legally covered, runbooks written.

### Key Deliverables

| Area | Tasks |
|------|-------|
| **QA** | Full regression; browser (Chrome/FF/Safari) + mobile (iOS/Android); exploratory testing |
| **Security** | Threat model review; dependency scan (Dependabot/Trivy); container scan; OWASP Top 10 checks; secrets audit; pen-test auth & company isolation; prompt-injection tests (override instructions, leak brand data) |
| **Perf/Load** | 50 concurrent generations → tune workers, timeouts, caching; p95 job wait <10 s; spend guards (daily cap alerts) |
| **DevOps** | Prod infra (managed K8s / Fly.io / Render); blue-green deploys; practiced backup restore; dashboards (latency, error rate, fallback %, spend, Cloudinary credits); alerts (PagerDuty / Slack) |
| **PM/Legal** | Privacy Policy; Terms (free-model logging notice, AI content disclosure); Data retention & deletion policy; Runbooks: expired keys, provider outages, failed publishing, Cloudinary credit exhaustion |

### Acceptance Criteria
- [ ] Zero critical/high security issues open
- [ ] Load test meets targets (p95 <10 s @ 50 concurrent)
- [ ] Backup restore drill successful
- [ ] Legal pages live
- [ ] Runbooks exist for all 4 scenarios above

### Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| Prompt injection exfiltrates brand data | Sanitize user input; strict system prompts; LangSmith trace review |
| Cloudinary credit exhaustion mid-campaign | Alerts at 70%/90%; auto-switch to R2 fallback; quota tied to credits |

---

## Phase 8 – Beta & Launch
**Weeks 12–14** | **18 Jan – 5 Feb 2027**  
**Owner:** PM + Frontend + Backend + AI/ML + DevOps + QA  
**Dependency:** Phase 7 passed

### Goal
Learn from real users, fix top issues, launch publicly with rollback plan.

### Key Deliverables

| Week | Activity |
|------|----------|
| 12 | Recruit 10–20 beta users (target segments); weekly feedback sessions |
| 12–13 | Track: approval rate, regenerations/post, time-to-publish, publish failures, fallback rate, cost/post |
| 13 | Fix top issues; add onboarding checklist (connect channels → fill brand kit → first post) |
| 13 | AI/ML: prompt tuning from real use; refresh free-model list |
| 13 | DevOps: cost/credit/error dashboards watched daily |
| 14 | Final release checklist; go/no-go meeting with rollback plan |

### Acceptance Criteria
- [ ] Beta users make first post within 15 min unaided
- [ ] Publish success rate ≥98%
- [ ] Spend/post within budget
- [ ] Go/no-go meeting held; rollback plan documented

### Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| Beta feedback requires scope change | PM owns MVP list; new ideas → backlog |
| Cost spikes at launch | Daily spend cap; circuit breaker to OpenAI-only mode |

---

## Solo-Builder Variant
**If one person builds this:** calendar ~5–6 months. Order:
1. Spikes (Phase 0)
2. Login + Data Model (Phase 2)
3. One LangGraph flow (Post + Image) + plain React page (Phases 3+4 combined)
4. Buffer posting to own accounts (Phase 6 subset)
5. Blog flow (Phase 3 second flow)
6. Brand Kit + Image Library (Phase 5)
7. Polish, Security, Launch (Phases 7+8)

Use hosted services: Clerk/Auth0, managed Postgres (Neon/Supabase), single container host (Fly/Render/Railway). Skip Kubernetes.

---

## MVP Scope (Launch Day)

| Must Have | First Month After Launch | Later Ideas |
|-----------|--------------------------|-------------|
| Login | Scheduling (simple calendar) | Occasion calendar suggestions |
| Blog flow + Post flow | Saved templates | Voice learning |
| Prompt expansion | 3 image variants to choose | Engagement analytics → prompts |
| Text + Image gen | Edit image by instruction | More languages |
| Approve / Regenerate + feedback | Team members per company | Carousels / short video |
| Buffer → IG, FB, LI | | Client approval workflows |
| Brand Kit | | Credit-based billing |
| Image Library (private + search) | | Direct Meta/LI posting (backup) |
| Usage quotas | | |
| Safety checks | | |
| Free-first + OpenAI fallback | | |
| Monitoring (LangSmith + dashboards) | | |

---

## Top Risks Summary

| # | Risk | Phase Mitigated |
|---|------|-----------------|
| 1 | Buffer OAuth/limits differ from docs | 0 (spike), 6 (Publisher interface) |
| 2 | Free models throttled/changed/removed | 0, 3 (pinned list, $10 top-up, health check, fallback, circuit breaker) |
| 3 | Free providers log prompts/brand data | 3 (terms notice, OpenAI-only setting), 7 (legal pages) |
| 4 | Cloudinary credits exhausted → images stop | 0, 5 (cleanup job), 6, 7 (alerts, R2 fallback) |
| 5 | Image cost > expected | 0 (measure), 3 (cap regens, cheap drafts), 7 (spend alerts) |
| 6 | References cause near-copies | 5 (limit refs, explicit roles, A/B test) |
| 7 | Cross-company data leak | 2 (RLS), 5 (private libs), 7 (automated leak tests, pen-test) |
| 8 | Unsafe/off-brand output | 3 (safety step), 4 (human approval), 7 (prompt-injection tests) |
| 9 | Network rules change / bans | 6 (official Buffer only, rate limit, audit log) |
| 10 | Scope creep | All (PM owns MVP list) |

---

## Week-One Checklist (VERIFY Items)

1. [ ] Sunburst: accepts 16 refs? Real cost/image?
2. [ ] Buffer: OAuth app registration works? Real rate limits?
3. [ ] Buffer + IG accept Cloudinary links?
4. [ ] Cloudinary free tier: what happens at credit exhaustion?
5. [ ] Which free OpenRouter models pass JSON + quality test briefs today?
6. [ ] Business/Creator IG accounts work via Buffer?

---

## Glossary (Quick Reference)

| Term | Meaning |
|------|---------|
| **Agent / Graph** | Multi-step program calling models & tools; drawn as graph in LangGraph |
| **Checkpoint** | Saved flow snapshot → pause for human → resume later |
| **Embedding / Search Vector** | Numeric representation of meaning for semantic search |
| **pgvector** | Postgres extension storing/searching vectors |
| **OAuth + PKCE** | User authorizes app without sharing password |
| **Circuit Breaker** | Stop calling failing service temporarily; use backup |
| **Idempotency Key** | Unique request label → prevents double execution |
| **Spike** | Short experiment answering one technical question |

---

## Open Questions for Stakeholders

1. **Multi-tenant or single-company?** → Drives Phase 2/5 separation effort.
2. **Blog publishing target?** → Only social, or also own site (WordPress/Ghost)?
3. **Monthly AI + hosting budget?**
4. **Priority markets & languages?**

---

*End of Phase-Wise Plan*  
*Next: Assign owners, set up repo, kick off Phase 0 spikes.*