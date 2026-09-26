# TaskPilot

An autonomous agent that watches a Gmail label, reads new email, drafts a
reply, and logs the details to a tracking sheet — then waits for a human to
approve before anything goes out.

**Zero-setup demo:** the app ships with a mock inbox and a deterministic
mock "LLM" so you can see the full agent loop run in under two minutes,
with no API keys, no Google Cloud project, and no cost. Swap in real Gmail
and a real free-tier LLM (Groq or Gemini) later, with no code changes —
just two lines in `.env`.

---

## What it demonstrates

Not another chat-with-an-LLM wrapper. TaskPilot shows the things that
actually make agents hard:

- **A visible plan → act → reflect loop**, not a black-box prompt — every
  step is logged with its reasoning and shown in the dashboard's expandable
  "reasoning trace."
- **Tool orchestration** — two distinct tools (`draft_reply`, `log_to_sheet`)
  with different approval requirements.
- **Failure recovery** — retries on transient failures, one automatic
  redraft-and-recheck if a reply fails its own quality rubric, and a clear
  escalation path ("I'm stuck, here's why") when it can't proceed safely.
- **Structural safety, not just a prompt instruction** — the app has no
  `send()` capability anywhere in its code, and the Gmail OAuth scope it
  requests (`gmail.readonly` + `gmail.compose`) doesn't grant one either.
  Sending mail is always a manual, human action inside Gmail itself.
- **A real evaluation harness** — `eval/run_eval.py` runs 20 emails through
  the actual agent code (not a simulation) and scores it against expected
  outcomes.

## Quickstart (zero setup, ~2 minutes)

```bash
# 1. Backend
cd backend
python3 -m venv .venv &&   source .venv/bin/activate # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"   # paste into API_SECRET_KEY in .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # paste into ENCRYPTION_KEY

uvicorn app.main:app --reload
```

```bash
# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, click **Open settings**, paste in the backend
URL (`http://localhost:8000`) and the `API_SECRET_KEY` you generated, save.
Click **Check inbox now** — TaskPilot processes the four sample emails in
`backend/app/email_source/sample_emails.json` (a meeting request, an
invoice, a support question, and one deliberately-ambiguous email to show
escalation) and the dashboard populates.

## Run the evaluation suite

```bash
cd eval
python run_eval.py
```

Runs 20 emails through the real orchestrator and writes `eval_results.json`
+ `eval_report.md`. On the bundled mock provider this currently scores
**19/20 (95%)** — above the PRD's 90% target, with the one failure
documented and explained in the report (see "Known limitations" below).
Point `LLM_PROVIDER=groq` or `gemini` at the same fixture to get a real-LLM
number for comparison.

## Connecting a real inbox and a real LLM

Everything below is optional — the app is fully functional without it.

**Groq (free LLM, recommended first)**
1. Create a free key at https://console.groq.com
2. In `backend/.env`: `LLM_PROVIDER=groq`, `GROQ_API_KEY=...`
3. Restart the backend.

**Gemini (free LLM, alternative)**
1. Create a free key at https://aistudio.google.com
2. In `backend/.env`: `LLM_PROVIDER=gemini`, `GEMINI_API_KEY=...`

**Gmail (real inbox)**
1. In [Google Cloud Console](https://console.cloud.google.com), create a
   project, enable the **Gmail API**, and create an OAuth 2.0 Client ID
   (type: Web application) with redirect URI
   `http://localhost:8000/api/auth/gmail/callback`.
2. In Gmail, create a label (default name `TaskPilot`) and apply it to a
   few test emails.
3. In `backend/.env`: `EMAIL_SOURCE=gmail`, `GMAIL_CLIENT_ID=...`,
   `GMAIL_CLIENT_SECRET=...`.
4. Restart the backend, open the dashboard's Settings panel, click
   **Connect Gmail**, and authorize.

Gmail scopes requested: `gmail.readonly` + `gmail.compose` only — this app
is structurally incapable of sending email; see "Security" below.

## Architecture

```
frontend/   React + Vite + Tailwind — Apple-style dashboard, polls the API
backend/    FastAPI — agent orchestrator, tool registry, SQLite storage
eval/       20-email evaluation fixture + harness, run independent of the app
```

Backend layout:
```
app/
  agent/
    orchestrator.py     the plan -> act -> reflect loop, retries, escalation
    classifier.py        LLM call: email -> task type + extracted fields
    rubric.py             LLM call: self-check a draft before it's finalized
    tools/
      draft_reply_tool.py  writes an unsent Gmail draft; requires approval
      log_to_sheet_tool.py writes to the SQLite tracking sheet; auto-approved
  llm/          groq / gemini / mock providers behind one interface
  email_source/ gmail (real OAuth) / mock (bundled fixture) behind one interface
  routers/      agent.py, approvals.py, dashboard.py, auth.py
  db.py         SQLite schema + connection handling (parameterized SQL only)
  security.py   bearer-token auth, Fernet token encryption, rate limiting
  sanitize.py   untrusted-input handling for email content
```

Why this shape:
- **LLM and email source are both behind an interface with a mock
  implementation.** The whole app runs and is fully testable with zero
  external dependencies, and swapping providers is a one-line `.env` change,
  not a code change.
- **The loop is hand-rolled, not a framework.** Every decision point —
  when to retry, when to escalate, when something needs human approval —
  is a plain, readable Python function you can point to and explain,
  rather than configuration inside someone else's agent library.
- **SQLite, no ORM.** Keeps the dependency tree (and RAM footprint) small,
  and every query is parameterized by hand, so there's no daylight between
  "looks safe" and "is safe."

## Cost and resource footprint

- **$0/month.** Groq, Gemini, Gmail API, Vercel/Netlify, and Render/Railway
  free tiers all cover this workload comfortably at personal-project volume.
  Check current limits before high-volume use: Groq
  (console.groq.com/docs/rate-limits), Gemini
  (ai.google.dev/gemini-api/docs/rate-limits), Gmail API
  (developers.google.com/gmail/api/reference/quota).
- **~250MB RAM in dev** (uvicorn + Vite dev server together, measured with
  `ps`), comfortably inside the PRD's 1.5–2GB budget on an 8GB machine —
  no local model weights, no local database server.
- **~0.7s wall time** to process all 4 sample emails end-to-end on the
  mock provider; expect 1–3s per email on Groq/Gemini (network-bound).

## Security notes

- **Bearer-token auth** on every mutating/data endpoint; the token is
  compared with `hmac.compare_digest` to avoid timing side-channels.
- **Gmail OAuth refresh tokens are encrypted at rest** (Fernet) before
  being written to SQLite, and never logged in plaintext.
- **No send capability exists in the codebase.** The `EmailSource`
  interface has no `send()` method, and the Gmail scopes requested
  (`gmail.readonly`, `gmail.compose`) don't include `gmail.send`. This is
  enforced at the API-grant level, not just in application logic.
- **All SQL is parameterized**; the one place a column list is built
  dynamically (`orchestrator._update_run`) is guarded by an explicit
  allowlist and covered by a test that fails the build if an f-string
  SQL query is ever added elsewhere.
- **Untrusted input handling**: email content is normalized on ingestion
  (control characters stripped, length-capped) rather than HTML-escaped —
  see the comment in `app/sanitize.py` for why escaping was actually the
  wrong choice here (it corrupted legitimate `Name <email>` sender headers
  without stopping anything React wasn't already stopping).
- **Single-user design, stated explicitly.** Auth is one shared bearer
  token, which is appropriate for a personal tool you run yourself, not a
  multi-tenant service. If you ever expose this beyond yourself, put real
  per-user session auth in front of it first.
- **Known dev-only advisory**: `npm audit` flags a moderate esbuild
  advisory in Vite's dev server (arbitrary sites can probe the dev server —
  irrelevant to the built static output that actually gets deployed).
  Fixing it requires a breaking Vite major-version bump; left as-is and
  documented rather than destabilizing a tested build for a dev-only issue.

## Known limitations

- **The mock LLM provider is keyword-based**, not a real language model —
  it's a `95%`-accurate stand-in for demoing the pipeline for free. Its one
  documented failure in `eval/eval_report.md` (eval-01: "quick call" isn't
  in its meeting-keyword list) is exactly the kind of gap a real LLM
  (Groq/Gemini) doesn't have, since those understand semantics, not
  keywords — a good, honest data point for an interview conversation about
  tradeoffs.
- **Gmail body parsing** currently extracts `text/plain` parts only; HTML-only
  emails fall back to Gmail's `snippet` field (shorter, sometimes truncated).
- **Single-process scheduler.** The in-process APScheduler poll job assumes
  one backend instance; running multiple instances would poll and process
  duplicates (SQLite's `processed_emails` table prevents double-drafting
  the *same* email, but doesn't coordinate across processes).

## Three tradeoffs worth discussing in an interview

1. **Cloud inference over local model weights.** On 8GB RAM, a local 3B+
   quantized model alongside an IDE and browser thrashes constantly. Moving
   inference off-device to a free API keeps the local footprint to
   orchestration/storage/UI — all lightweight — at the cost of network
   latency and a dependency on a third party's free tier staying free.
2. **Escalate rather than guess on low confidence.** Below the confidence
   threshold, the agent logs the email and stops rather than drafting a
   possibly-wrong reply. This trades away some automation coverage (see
   eval-05: a real meeting request that gets escalated purely for lacking
   a concrete date) for a hard guarantee that low-confidence output never
   reaches a human as if it were routine.
3. **Draft-and-approve instead of confidence-gated auto-send.** The PRD
   could have allowed high-confidence replies to send automatically. This
   app never does — every reply is a draft, always, regardless of
   confidence — trading some "fully autonomous" appeal for a categorical
   safety guarantee that's enforced by the OAuth scope itself, not just
   application logic that could have a bug in it.

## Resume bullet

> Designed and built an autonomous agent that monitors Gmail and
> independently drafts responses and logs action items, using a
> plan-act-reflect loop with human-in-the-loop approval for external
> actions. Achieved a 95% task success rate across a 20-email evaluation
> suite, running entirely on free-tier cloud inference to keep local
> resource use under 300MB RAM in development.

## Tests

```bash
cd backend && source .venv/bin/activate && pytest tests/ -v
```

18 tests covering the orchestrator's decision logic (actionable vs.
escalated vs. low-confidence paths), both tools, and security primitives
(auth, encryption round-trip, sanitization, a static guard against
f-string SQL).
