# AI Blog & Social Post Generator – Distilled Project Plan&#32;

Prepared 30 October 2026. This is the short, fully explained version of the plan, updated for your final stack: Buffer, Cloudinary, GPT Image 2.5 Sunburst, free OpenRouter chat models with an OpenAI fallback, LangChain + LangGraph + LangSmith, FastAPI and React. Items marked **VERIFY** are things the research could not settle, and they are tested in the first two weeks.

## 1. What we are building, in plain words

A user logs in and picks one of two options: **Write a blog** or **Generate a post**. A form asks for the basics and a short description of what they want. An AI agent turns that description into a detailed brief, writes the text, and creates a matching image. The user then chooses **Approve** or **Regenerate**. When they approve, the content is posted to Instagram, Facebook and LinkedIn through Buffer.

Two extras make it more than a generator. An **image library** keeps approved images, so the next prompt about Diwali can start from an earlier Diwali image. A **brand memory** keeps the company name, logo and address, so every post stays consistent without retyping them.

## 2. The final stack and why each piece is there

| Piece | What it does here | Why it was chosen | Watch out for |
| --- | --- | --- | --- |
| **React** | The screens: login, forms, preview, Approve and Regenerate, channel picker | Standard for interactive web apps, easy to hire for | Needs mock data until the backend is ready |
| **FastAPI** | The backend: login, starts AI jobs, talks to Buffer and Cloudinary | Fast, async, automatic API docs, and you already use it | Long AI jobs must run in background workers, not inside a web request |
| **LangChain** | Connects to the chat models and tools with one common interface | Lets you swap models without rewriting code | Keep prompts in files you can version |
| **LangGraph** | Runs the multi-step flow as a graph and can pause for human approval | Approve and Regenerate is exactly a pause-and-resume step | Needs a database to save its state |
| **LangSmith** | Records every step, prompt, answer, delay and cost | You can see why a bad post happened | Do not log private customer data without a retention rule |
| **OpenRouter (free models)** | Writes the blog text, prompts and captions | Free access to many models through one API | Limits, rotating model list, and prompt logging (section 4) |
| **OpenAI chat model (fallback)** | Takes over when the free route fails | Reliable safety net | Costs money, so watch how often it is used |
| **GPT Image 2.5 Sunburst** | Creates and edits the images, and accepts reference images | Strong at precise edits and reusing earlier images | Slower and more expensive per image; limits to verify |
| **Cloudinary (free plan)** | Stores images and gives each one a public web link | Buffer needs a public link, and Cloudinary provides one | Free credits are limited (section 4) |
| **Buffer API** | Posts to Instagram, Facebook and LinkedIn | One integration instead of three | Needs OAuth for multi-user, rate limits, **VERIFY** |
| **PostgreSQL + pgvector** | Stores users, posts, brand details, image tags and image search data | One database does everything at this size | Not in your list, but required |
| **Redis** | Job queue, caching and rate limiting | Keeps slow AI jobs from blocking the site | Not in your list, but required |

## 3. How one request flows

This is the path of one post, from click to published. Each step is a node in the LangGraph flow.

1. **Load context.** The system fetches the user's brand details (name, logo, address, tone) and preferences.
2. **Expand the prompt.** A chat model turns the short description into two detailed briefs: one for the text, one for the image.
3. **Find reference images.** The system looks in the image library for earlier approved images that match, for example anything tagged Diwali.
4. **Write the text and make the image.** These run at the same time to save waiting time.
5. **Safety check.** Both the text and the image are checked for unsafe content.
6. **Adapt for each network.** LinkedIn gets the long version, Facebook a medium one, Instagram a short caption with hashtags.
7. **Human review.** The flow pauses. The user reads the text, sees the image, edits if needed, then clicks Approve or Regenerate. Regenerate can include a note such as "more festive colours".
8. **Publish.** On Approve, the image is uploaded as a public Cloudinary link, and the post is queued for Buffer.
9. **Save to the library.** The approved image and its tags are stored so later requests can reuse it.

## 4. The key decisions, explained

### 4.1 Free chat models first, OpenAI as fallback

You chose a free OpenRouter model as the main chat model, with an OpenAI model behind it. That works, but only with some care, because free models have three weaknesses.

- **Daily limits.** Free models allow 20 requests a minute and 50 a day. One generation uses about 4 chat calls (expand prompt, write text, write captions, safety check), so 50 a day is only about 12 generations. A one-time purchase of about $10 in credits raises the cap to 1,000 requests a day, about 250 generations, and the models stay free.
- **A changing list.** Free models appear and disappear every few weeks. So the model names live in configuration, not in code, and a daily check runs sample briefs against the list and alerts you if a model vanishes or its quality drops. OpenRouter also offers a router called `openrouter/free` that picks any free model that supports what the request needs (tool calling, structured output).
- **Prompt logging.** Free providers may keep prompts and answers to improve their models. Tell users in the terms, and give each company an "OpenAI only" setting if they do not want that.

The fallback rule: if the free route returns a rate-limit error (429), times out, or gives broken output after one retry, the request goes to OpenAI automatically. If the free route fails several times in a row, a circuit breaker sends everything to OpenAI for a few minutes so users are not left waiting. LangSmith counts how often this happens so you know what the fallback costs.

For images, Sunburst makes the final image. If it fails, the system retries once, then makes a cheaper draft image so the screen never dead-ends.

### 4.2 Cloudinary for image links

Buffer cannot accept uploads directly, so each post image needs a public web link. Cloudinary gives every uploaded image one. The backend uploads using signed requests, so the secret key never reaches the browser.

- **Public versus private.** Only images the user approved for posting become public, using random hard-to-guess names, and only at the moment of approval. Library originals, logos and drafts stay private and are shown through signed links.
- **A few fixed sizes.** Cloudinary can crop one upload into the sizes each network wants (for example square and 4:5). Every different crop counts against your credits, so use about three fixed presets.
- **The free plan.** You get 25 credits a month shared across storage, delivered bandwidth and image processing (1 credit is 1 GB of storage, 1 GB of bandwidth or 1,000 transformations). A beta with 1,000 posts a month uses roughly 4 credits.
- **Cleanup.** Cloudinary does not delete files on a timer, so a scheduled job removes published images after about 30 days and rejected drafts after about 7.
- **The risk.** One report says that when credits run out, Cloudinary stops serving images instead of charging. Scheduled posts would then fail to fetch their image. **VERIFY** this, and set alerts at 70% and 90% of credits. If Buffer or Instagram rejects Cloudinary links, the fallback is a plain storage bucket (Tigris or Cloudflare R2) behind your own domain.

### 4.3 The image library

Your idea of saving approved images by name and reusing them is sound. This is how it works.

- **Saving.** When a user approves and posts an image, it is saved in Cloudinary in a folder like `library/company/festival/diwali`. A database row stores the owner, tags (festival, diwali), the original prompt, the caption and a search vector.
- **Finding.** For a new prompt, the system picks out keywords, looks for exact tag matches first, then searches by meaning using the search vector, then ranks by recency and past approval. The top one to four become references.
- **Using.** The references go to Sunburst's edit function together with the new prompt. Sunburst accepts up to 16 references, but use one or two style references plus the logo, because many similar references produce near-copies. The prompt states what each reference is for: style, subject or logo.
- **Whose images?** Do not let one company's approved images become another company's references. They can contain brand names, logos or people. Keep a private library per company, plus a global library that your team curates with festival and occasion images. Companies can opt in to contribute, after review.
- **Starting empty.** Seed the global library with 50 to 100 curated images before beta.

### 4.4 Brand memory

Company name, logo, colours, address, tagline and tone are stored in a brand kit table, not guessed from past images. They are inserted into every prompt. Because AI models often misspell small text, the logo and address are added onto the finished image by code (Pillow) instead of being drawn by the model.

### 4.5 Posting through Buffer

Buffer has a personal API key for your own use. For an app where many people connect their own accounts, Buffer's documentation describes registering an app with OAuth 2.0 and PKCE, which lets each user authorise posting without sharing passwords. One competitor article disagrees and says this is not available, so the first spike is to register an app and post to test accounts. Buffer sits behind a `Publisher` interface in the code, so if it fails you can switch to another service without touching the rest. Posts go through a throttled queue because Buffer is reported to allow about 100 requests per 15 minutes per app (**VERIFY**). Idempotency keys make sure a double-click never posts twice.

### 4.6 Why Postgres and Redis are in the plan

LangGraph must save its state while it waits for the user to approve, and Postgres is the recommended place for that. The same database stores users, posts and brand kits, and with the pgvector extension it also handles image search, so you do not need a separate vector database yet. Redis runs the background queue so a 30-second image job never blocks the website.

## 5. Roles

| Role | People | Main responsibility |
| --- | --- | --- |
| Project/Product Manager | 0.5–1 | Scope, priorities, beta users, platform rules |
| Backend engineer | 1–2 | FastAPI, database, login, job queue, Buffer and Cloudinary |
| AI/ML engineer | 1 | LangGraph flows, prompts, model routing, evaluation, image search |
| Frontend engineer | 1 | React screens and user experience |
| UI/UX designer | 0.5 (weeks 1–6) | Screens, design system, brand kit and library pages |
| DevOps | 0.5 | Environments, deployment, secrets, monitoring, cost alerts |
| QA | 0.5 (from week 4) | Tests, AI output review, release sign-off |
| Security | 0.1 | Threat review and pre-launch checks |

On a small team one person plays several roles, but the work in each column still has to happen.

## 6. Timeline

Start: Monday 2 November 2026. Public launch: about 5 February 2027 (14 weeks). Phases overlap, and the frontend works against mock data while the backend is built.

| Phase | Weeks | Dates | Needs first |
| --- | --- | --- | --- |
| 0. Discovery and spikes | 1–2 | 2 Nov – 13 Nov | nothing |
| 1. Foundations | 2–4 | 9 Nov – 27 Nov | Phase 0 decisions |
| 2. Login and data model | 3–5 | 16 Nov – 4 Dec | Phase 1 skeleton |
| 3. AI core | 4–8 | 23 Nov – 1 Jan | Phases 1 and 2 |
| 4. Frontend flows | 4–9 | 23 Nov – 8 Jan | API contract |
| 5. Image library and brand memory | 7–10 | 14 Dec – 15 Jan | Phase 3 image flow |
| 6. Buffer publishing | 8–11 | 21 Dec – 22 Jan | Phase 2 and spike results |
| 7. Hardening | 11–12 | 11 Jan – 22 Jan | Phases 3–6 built |
| 8. Beta and launch | 12–14 | 18 Jan – 5 Feb | Phase 7 passed |

Expect lower capacity over the end-of-December holidays (weeks 8 and 9). If time is short, delay Phase 8, never Phase 7.

## 7. Phase by phase

### Phase 0 – Discovery and spikes (weeks 1–2)

**Goal:** test the risky assumptions before building anything. A spike is a short experiment that answers one question.

- **AI/ML:** try Sunburst with 1, 4 and 16 references (real limit, cost, time, quality). Test the free router and three named free models for text quality, JSON reliability and limits, with and without the $10 top-up, and force a 429 to test the OpenAI fallback. Build a first test set of 30 sample briefs.
- **Backend:** register a Buffer app, complete OAuth, and post a test image from a Cloudinary link to Instagram, Facebook and LinkedIn test accounts. Prototype a LangGraph pause with Postgres saving the state. Check what Cloudinary does at its credit limit.
- **PM:** fix the MVP scope, success measures (for example 70% of generations approved within 2 tries) and basic content rules.
- **Design:** rough flows for the two options, review screen, library and brand kit.
- **DevOps:** cloud accounts, repository, secrets approach, spend alerts for OpenAI, OpenRouter and Cloudinary.

**Hand-off:** spike reports go to the PM for a go/no-go on Buffer and on free-first chat routing.

**Done when:** decisions are written down, one end-to-end test (prompt, image, Buffer test post) works by hand, and the cost per post is known within about 30%.

### Phase 1 – Foundations (weeks 2–4)

**Goal:** a working skeleton every role can build on.

- **DevOps:** containers, local setup, automatic tests and deploys, dev and staging environments, Postgres with pgvector, Redis, Cloudinary folders and upload settings, secrets storage, basic logging.
- **Backend:** project structure, settings for model lists and limits, health checks, and the API contract (OpenAPI) for login, jobs, review, publishing and library.
- **Frontend:** React project, routing, an API client generated from the contract, a mock server.
- **Design:** final screens and design tokens. **QA:** test strategy and test accounts.

**Hand-offs:** DevOps gives credentials to Backend and AI/ML; Backend gives the API contract to Frontend; Design gives screens to Frontend.

**Done when:** a code merge builds, tests and deploys to staging by itself, and the contract is reviewed and frozen for the core flows.

### Phase 2 – Login and data model (weeks 3–5)

**Goal:** safe sign-in and the core database.

- **Backend:** signup, login, refresh tokens, password reset (or a hosted service such as Auth0 or Clerk to save time). Tables for users, companies, brand kits, jobs, contents, images, channel connections, publish attempts and quotas. Every query is limited to the owner's company. OAuth tokens are stored encrypted.
- **Frontend:** login and signup, protected pages, an empty dashboard with the two options.
- **DevOps:** backups and automatic database migrations. **Security:** review how tokens and company separation are designed. **QA:** tests for wrong passwords, expired tokens and one user trying to read another's data.

**Done when:** a new user signs up and logs in on staging, automated tests prove user A cannot see user B's data, and migrations run forward and backward.

### Phase 3 – AI core (weeks 4–8)

**Goal:** good text and images, reliably, with regeneration.

- **AI/ML:** build the LangGraph flows from section 3. Write and version the prompts for the blog brief, image brief and platform captions. Build the model router: free list first, OpenAI fallback, circuit breaker, one retry for broken JSON, and the "OpenAI only" company setting. Add the daily model health check, the safety step, progress streaming and regenerate-with-feedback. Trace everything in LangSmith and run the test set automatically.
- **Backend:** endpoints to start a job, stream progress, approve and regenerate. Run graphs in background workers with timeouts and duplicate protection. Enforce per-user quotas, a daily free-request budget and a daily spend cap.
- **QA:** review outputs against a checklist (relevance, tone, safety) and force failures (429, timeouts, bad JSON). **DevOps:** alerts for error rate, delays, fallback rate and spend.

**Hand-off:** AI/ML gives Backend the flow inputs and outputs by week 5, so integration does not wait until the end.

**Done when:** 90% of test briefs give acceptable text and image within two tries on the free models, the OpenAI fallback works when the free route is switched off, regenerating keeps the previous result, and LangSmith shows full traces.

### Phase 4 – Frontend flows (weeks 4–9)

**Goal:** a polished experience for the whole journey.

- **Frontend:** dashboard with the two options; forms (title, topic, tone, audience, keywords, image description, platforms); live progress; text and image side by side; Approve and Regenerate with a note box; version history; editing before approval; error and retry states; a clear notice when free models are used.
- **Design:** test with 3 to 5 real users around week 7 and list fixes. **QA:** component tests, end-to-end tests (Playwright) of the main journey, accessibility checks. **Backend:** adjust APIs from what testing finds.

**Done when:** a user completes login, form, preview, regenerate and approve on staging with real AI output, buttons enable and disable correctly, there are no critical accessibility issues, and test users finish the task without help.

### Phase 5 – Image library and brand memory (weeks 7–10)

**Goal:** reuse approved images and keep brand details consistent.

- **AI/ML:** keyword extraction, search vectors, matching and ranking, reference-role prompts, and a comparison of results with and without references.
- **Backend:** library and tag APIs, vector indexes, private and global scopes, brand kit management, logo and address compositing, save-on-approve, delete and export of a user's images, the Cloudinary cleanup job.
- **Frontend:** brand kit page, library browser with search and tag editing, a "use as reference" picker, and an on/off switch for references.
- **PM/Content:** build and tag the starter global library. **QA:** does "Diwali" find the right images, and does nothing from another company leak?

**Done when:** a relevant reference ranks in the top three for at least 80% of test prompts that have a stored match, all leakage tests pass, logo and address print correctly, and references measurably help (or are off by default).

### Phase 6 – Buffer publishing (weeks 8–11)

**Goal:** approved content reaches the three networks safely.

- **Backend:** Buffer connect and disconnect, token refresh, channel list, the `Publisher` interface, one post per channel with network-specific text and a public Cloudinary link made at approval, post-now and scheduling, a throttled queue, retries with delay, duplicate protection, stored post status, and clear errors (disconnected channel, expired token, rejected image, image fetch failure).
- **Frontend:** connect-channels screen, channel picker on approval, schedule or post-now choice, and a status page with per-channel results and retry.
- **AI/ML:** the per-network text versions and image shapes (square, 4:5). **DevOps:** workers, a dead-letter queue for failed jobs, alerts for failures and Cloudinary credit use. **QA:** real test channels and deliberate failures. **PM:** confirm each network's rules on automation and AI content and write them into the terms.

**Done when:** approving content creates correct posts on all three test channels, failures give the user a next step, repeated clicks never double-post, and a burst test shows the rate limit is handled.

### Phase 7 – Hardening (weeks 11–12)

**Goal:** safe and sturdy enough for real users.

- **QA:** full regression, browser and phone checks, exploratory testing. **Security:** threat review, dependency and container scans, common web-attack checks, a secrets audit, a penetration test of login and company separation, and prompt-injection tests (a user description that tries to override instructions or leak brand data).
- **Backend and AI/ML:** load test with 50 generations at once, tune workers and timeouts, add caching and spend guards. **DevOps:** production setup, safe deploys, a practised backup restore, autoscaling, dashboards, alerts. **PM:** privacy policy, terms (including the free-model logging notice), data retention and deletion.

**Done when:** no critical or high issues remain open, the load test meets targets (for example waiting under 10 seconds for 95% of jobs at 50 at once), a restore has been practised, legal pages are live, and runbooks exist for expired keys, provider outages, failed publishing and Cloudinary credit exhaustion.

### Phase 8 – Beta and launch (weeks 12–14)

**Goal:** learn from real users, fix, then open to everyone.

- **PM:** recruit 10 to 20 beta users, hold weekly feedback sessions, and track approval rate, regenerations per post, time to publish, publish failures, fallback rate and cost per post.
- **Frontend and Backend:** fix top issues and add an onboarding checklist (connect channels, fill brand kit, make a first post). **AI/ML:** tune prompts from real use and refresh the free-model list. **DevOps:** watch costs, free-credit use and errors. **QA:** verify fixes and run the final release checklist.

**Done when:** beta users make a first post within 15 minutes unaided, publishing succeeds at least 98% of the time, spend per post is within budget, and a go/no-go meeting is held with a rollback plan ready.

## 8. If you are building this alone

The order stays the same but the calendar roughly doubles to 5–6 months. A sensible solo order: spikes, then login and data model, then one LangGraph flow (post with image) with a plain React page, then Buffer posting to your own accounts, then the blog flow, brand kit, image library, and finally polish and security. Use hosted services (hosted login, managed Postgres, one container host) and skip Kubernetes.

## 9. MVP scope

**Must have at launch:** login; blog flow and post flow; prompt expansion; text and image generation; approve and regenerate with feedback; Buffer posting to the three networks; brand kit; image library with private storage and search; usage quotas; safety checks; free-first chat with OpenAI fallback; monitoring.

**First month after launch:** scheduling with a simple calendar; saved templates; three image variants to choose from; edit-an-image by instruction; team members per company.

**Later ideas:** an occasion calendar that suggests posts before festivals; learning a company's writing voice; engagement analytics fed back into prompts; more languages; carousels and short video; client approval workflows; billing with credits; direct posting to Meta and LinkedIn as a backup to Buffer.

## 10. Main risks

| Risk | Chance | What reduces it |
| --- | --- | --- |
| Buffer OAuth or limits differ from the docs | Medium | Week 1 spike, `Publisher` interface, shortlist of alternatives |
| Free models throttled, changed or removed | High | $10 top-up, pinned lists, daily health check, OpenAI fallback with circuit breaker, quotas |
| Free providers log prompts and brand details | Medium | Notice in terms and screens, send only what is needed, OpenAI-only option |
| Cloudinary credits run out and images stop loading | Medium | Alerts, three presets, cleanup job, quotas tied to credits, storage-bucket fallback |
| Image cost higher than expected | Medium | Measure in Phase 0, cap regenerations, cheap drafts and high quality only for finals, spend alert |
| References cause near-copies | Medium | Few references, state each one's role, test with and without |
| One company's data leaks to another | Low but severe | Private libraries, company-scoped queries, automated leak tests, security review |
| Unsafe, inaccurate or off-brand output | Medium | Safety step, human approval before every post, editable text, disclosure in terms |
| Network rules change or accounts get banned | Medium | Post only after explicit approval through Buffer's official integrations, rate limiting, audit log |
| Scope creep | High | PM owns the MVP list; new ideas wait for the backlog |

## 11. Week-one checklist (the VERIFY items)

1. Does Sunburst accept 16 reference images on your account, and what does one image really cost?
2. Can you register a Buffer app with OAuth, and what are its real rate limits?
3. Do Buffer and Instagram accept Cloudinary image links?
4. What happens when the Cloudinary free credits run out?
5. Which free OpenRouter models pass your test briefs for JSON and writing quality today?
6. Do business or creator Instagram accounts work for posting through Buffer?

## 12. Plain-language glossary

- **Agent / graph:** a program that follows several steps and can call AI models and tools. LangGraph draws those steps as a graph.
- **Checkpoint:** a saved snapshot of where a flow is, so it can pause for the user and continue later.
- **Embedding / search vector:** a list of numbers that captures the meaning of text, so similar ideas can be found even without matching words.
- **pgvector:** a Postgres add-on that stores and searches those vectors.
- **OAuth with PKCE:** the standard way a user lets an app act on their account without giving it their password.
- **Circuit breaker:** a rule that stops calling a failing service for a short time and uses the backup instead.
- **Idempotency key:** a unique label on a request so repeating it does not repeat the action, which prevents double posts.
- **Spike:** a short experiment to answer one technical question.

## 13. Questions for you

1. Is this a product for many customers, or a tool for one company? That decides how much separation work Phases 2 and 5 need.
2. Should the blog also be published somewhere besides social posts, such as your own site?
3. What is the monthly budget for AI and hosting?
4. Which markets and languages matter first?

## 14. Sources checked

Sunburst details from provider and reference pages (LLM Reference, Atlas Cloud, Shotstack, getimg.ai, AI/ML API). Buffer details from developers.buffer.com, Buffer's help centre and a competing vendor's analysis (treated cautiously). OpenRouter limits and free router from OpenRouter's pages and a TrueFoundry write-up. Cloudinary credit rules from Cloudinary's billing documentation; the suspension behaviour comes from a third-party report. LangGraph checkpointing and interrupts from LangChain documentation and community guides.
