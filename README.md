# FasttrackrAI — Financial Advisor Client Management System

A full-stack application that helps financial advisors manage and understand their clients' financial data, built with **Python (FastAPI)** and **React (TypeScript)**.

---

## Features

- **Excel/CSV Import** — Upload variable-format spreadsheets; fuzzy column matching handles inconsistent headers
- **Audio Transcription** — Transcribe client meeting recordings (Whisper) and extract structured financial insights (Claude AI)
- **Household Dashboard** — List all households with key financial stats, search/filter
- **Household Detail** — Full member profiles, accounts, bank details, audio insights, inline editing
- **Insights & Charts** — 6 interactive Recharts visualizations: net worth, income, account types, tax brackets, risk tolerance, members per household

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Python 3.11, FastAPI | Async-ready, automatic OpenAPI docs, Pydantic validation |
| Database | PostgreSQL 16 | ACID, FK enforcement, concurrent writes, production-grade |
| ORM | SQLAlchemy 2.0 | Type-safe queries, DB-agnostic, connection pooling |
| Migrations | Alembic | Schema versioning, safe rollbacks, autogenerate from models |
| AI / Audio | OpenAI Whisper (local) + Claude claude-opus-4-6 | No per-minute cost for transcription; Claude for structured extraction |
| Data Parsing | Pandas | Fuzzy column matching handles variable Excel/CSV headers |
| Frontend | React 18, TypeScript, Vite | Type safety, fast HMR dev experience |
| Charts | Recharts | React-native charting, composable API |
| Styling | Plain CSS + CSS variables | Zero dependency, full control, no runtime overhead |

---

## Setup Instructions

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 16 (`brew install postgresql@16`)
- ffmpeg (`brew install ffmpeg`) — required for audio transcription
- An Anthropic API key — optional, only needed for audio insight extraction

### 1. Database Setup

```bash
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
brew services start postgresql@16

psql postgres -c "CREATE DATABASE fasttrackr;"
psql postgres -c "CREATE USER fasttrackr_user WITH PASSWORD 'fasttrackr_pass';"
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE fasttrackr TO fasttrackr_user;"
psql postgres -c "ALTER DATABASE fasttrackr OWNER TO fasttrackr_user;"
```

### 2. Backend Setup

```bash
cd backend

python3.11 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY if you have one (optional)

# Run database migrations
alembic upgrade head
```

### 3. Frontend Setup

```bash
cd ../frontend
npm install
```

### 4. Running the Application

**Terminal 1 — Backend:**
```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

### 5. Load the Sample Data

1. Navigate to **Upload** in the app
2. Drag the provided `.csv` file into the Excel/CSV panel → **Upload & Import**
3. 22 households will be parsed and stored in PostgreSQL
4. Optionally upload the `.mp3` file linked to a household to transcribe it

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/households` | List all households |
| GET | `/api/households/{id}` | Get household detail |
| PUT | `/api/households/{id}` | Update household fields |
| DELETE | `/api/households/{id}` | Delete household |
| GET | `/api/households/{id}/audio-insights` | Get audio insights for household |
| POST | `/api/upload/excel` | Upload CSV/XLSX file |
| POST | `/api/upload/audio` | Upload audio file (transcribe + extract) |
| GET | `/api/insights/summary` | Aggregated chart data |
| GET | `/api/insights/household/{id}` | Household-specific insights |

Interactive API docs: **http://localhost:8000/docs**

---

## Project Structure

```
FasttrackrAI/
├── backend/
│   ├── main.py                 # FastAPI app — CORS, router mounting, lifespan
│   ├── database.py             # PostgreSQL engine, connection pool, session factory
│   ├── models.py               # SQLAlchemy ORM models
│   ├── schemas.py              # Pydantic v2 request/response schemas
│   ├── alembic.ini             # Alembic migration config
│   ├── migrations/             # Database migration scripts (versioned)
│   │   └── versions/           # One file per schema change
│   ├── parsers/
│   │   ├── csv_parser.py       # Fuzzy-column CSV/Excel parser
│   │   └── audio_parser.py     # Whisper transcription + Claude extraction
│   ├── routers/
│   │   ├── households.py       # Household CRUD + audio insights endpoint
│   │   ├── upload.py           # File upload (CSV & audio) with upsert logic
│   │   └── insights.py         # Aggregated analytics for charts
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    └── src/
        ├── App.tsx             # React Router v6 setup
        ├── api/index.ts        # Typed Axios client (all API calls in one place)
        ├── types/index.ts      # Shared TypeScript interfaces
        ├── components/
        │   └── Navbar.tsx      # Sticky navigation bar
        └── pages/
            ├── HouseholdList.tsx   # Card grid + summary stats + search
            ├── HouseholdDetail.tsx # Full detail + inline edit + audio insights
            ├── Insights.tsx        # 6-chart analytics dashboard
            └── Upload.tsx          # Drag-and-drop CSV & audio uploader
```

---

## Database Schema

```
Household (1) ──< Member (1) ──< Account ──< Beneficiary
                           └───< BankDetail
Household ──< AudioInsight
```

- **Household**: Core entity — name, net worth, income, investment preferences
- **Member**: Individual family members with personal/contact info
- **Account**: Financial accounts (IRA, Roth, Joint, etc.) linked to members
- **BankDetail**: Banking information per member
- **AudioInsight**: Transcription + Claude-extracted data from meeting recordings

---

## Architecture & Design Decisions

### Why PostgreSQL over SQLite or MongoDB?

**SQLite** was the initial choice for zero-setup speed, but it has a single-writer lock, no real connection pooling, and a ~1GB practical file-size limit — none of which are appropriate for a financial data system that could grow.

**MongoDB** was considered but ruled out because the data is inherently relational. Households have members; members have accounts; accounts have beneficiaries. Embedding documents would duplicate data and make cross-household analytics (aggregation queries for the Insights page) significantly harder to write and slower to execute.

**PostgreSQL 16** is the right fit:
- Full ACID compliance — financial data must never be partially written
- Foreign key constraints enforced at the DB level, not just the ORM
- `JOIN`-friendly for analytics queries (net worth by bracket, account type distribution)
- Production-grade concurrent writes — no file locks
- Industry standard for financial applications

### Why SQLAlchemy + Alembic?

- **SQLAlchemy** provides a DB-agnostic ORM. Switching from SQLite to PostgreSQL required changing exactly one line (the connection URL). The same will be true for any future DB change.
- **Alembic** tracks schema changes as versioned migration files. Every change is auditable, reversible, and reproducible on any environment — critical when multiple developers or staging/prod environments are involved.
- **Connection pooling** (`pool_size=10, max_overflow=20`) means the API reuses TCP connections instead of opening a new one per request — typically a 10–50ms saving per call.

### Why FastAPI?

- Async-native — handles I/O-bound work (DB queries, file uploads, Whisper transcription) efficiently
- Automatic OpenAPI docs at `/docs` — the interviewer can explore every endpoint interactively without Postman
- Pydantic v2 validation — request and response shapes are enforced at runtime, not just at compile time

### Why Whisper (local) + Claude (cloud) for audio?

Two-stage pipeline:
1. **Whisper `base` model** runs entirely locally — no per-minute API cost, no data leaving the machine for transcription
2. **Claude claude-opus-4-6** gets the transcript and returns structured JSON (financial updates, insights, action items) — Claude is better than Whisper at understanding financial language and intent

Tradeoff: Whisper `base` can mishear proper nouns (names, account numbers). Switching to `medium` or `large` improves accuracy at the cost of 3–5× transcription time.

### Why fuzzy column matching for CSV/Excel?

The spec explicitly states "column names may vary." A rigid column-name map would break on any variation (e.g. `Phone #` vs `Phone Number` vs `phone`). The fuzzy matcher in `parsers/csv_parser.py` does case-insensitive partial substring matching — it handles every variation in the sample data and unknown future variations without code changes.

---

## AI Agent Architecture

### Overview

The audio pipeline is a two-stage system built around a **Human-in-the-Loop (HITL) review pattern** — the AI proposes changes, a human approves or corrects them, and only approved changes are written to the database. This is the industry standard in financial services where FINRA/SEC regulations require an advisor to own every change to client records.

```
Upload Audio
     │
     ▼
[Stage 1 — Transcription]
  OpenAI Whisper (local, free)
  → Raw text transcript saved to backend/transcripts/
     │
     ▼
[Stage 2 — Structured Extraction]   audio_parser.py → extract_financial_data()
  Claude claude-opus-4-6
  → Key insights + action items (stored in AudioInsight table)
     │
     ▼
[Stage 3 — Review Agent]            review_agent.py → run_agent()
  Claude claude-opus-4-6
  → 10–20 field-level proposed changes (stored in ProposedChange table)
     │
     ▼
[Stage 4 — Human Review Queue]      /review UI
  Wealth manager reviews each change:
    ✓ Approve  → marked approved
    ✗ Reject + feedback → agent re-analyzes (revise_single_change())
                          → back and forth until dismissed or approved
     │
     ▼
[Stage 5 — Apply]                   POST /review/{id}/apply
  Only approved changes written to DB
  Full audit trail: every change traceable to source audio file
```

---

### What Context the LLM Receives

Getting reliable structured output from an LLM requires injecting the right context. The agent receives six layers:

#### 0. Client Pre-Identification (before the LLM call)

Before building any prompt, `run_agent()` does a cheap **regex + fuzzy-match** step to figure out which household the transcript is about:

```python
name_hint  = _extract_client_name_hint(transcript)   # regex scan — no API call
matched_id = _find_matching_household(name_hint, db)  # fuzzy match against household names
db_context = _build_household_context(matched_id, db) # scoped to ONE household
```

`_extract_client_name_hint()` tries several patterns in priority order:
1. Explicit statement: `"full legal name is Benjamin Walter Thompson Jr."`
2. `"new client prospect, Benjamin Walter"`
3. `"meeting with / spoke with / call with <Name>"`
4. `"client / named <Name>"`

**Why do this before the LLM call?**  
The DB context is scoped to the single matched household. All other clients' data is excluded from the prompt entirely — improving privacy, reducing token count, and eliminating any risk of Claude confusing fields across different households.

#### 1. Targeted Client Snapshot (`_build_household_context`)

```
┌─ Household  id:3  ← use this id for entity_id when entity_type='household'
│  name:                        Raj and Priya Sharma
│  risk_tolerance:               Aggressive
│  annual_income:                200000.0
│  ...all other fields...
│  ├─ Member  id:5  ← use this id for entity_id when entity_type='member'
│  │  name:           Raj Sharma
│  │  email:          raj@example.com
│  │  occupation:     Engineer
│  ├─ Account  id:8  ← use this id for entity_id when entity_type='account'
│    type:Roth IRA  custodian:Fidelity
```

If no fuzzy match is found (new client), Claude receives instead:
```
No matching household found in the database — treat this as a NEW CLIENT.
Use entity_type = 'new_household', 'new_member', 'new_account' and set entity_id = null.
```

**Why:** Claude needs to see current field values — not just household names — so it can:
- Avoid proposing changes to fields that are already correct
- Generate the right `entity_id` for member and account updates (not just household)
- Know which fields are still null and need filling

Without this, Claude proposes `risk_tolerance = "Moderate"` even when the DB already says `"Moderate"`, creating noise in the review queue.

#### 2. Typed Schema Reference (`_SCHEMA_REFERENCE`)
Every field name with its type, description, and an example value:
```
risk_tolerance   String   Investment risk posture.   e.g. "Conservative", "Moderate", "Aggressive"
annual_income    Float    Total gross annual income. e.g. 175000.0
```
**Why:** Without this, Claude invents field names like `"risk"` or `"income"` instead of the exact DB column names `"risk_tolerance"` and `"annual_income"`. The apply step uses `setattr(obj, field_name, value)` — a wrong field name silently does nothing.

#### 3. Entity Resolution Rules (`_ENTITY_RULES`)
Explicit rules for when to use `household` vs `new_household`, how to assign `entity_id`, and the grouping rule (all fields for the same person share `entity_label`).

**Why:** The apply step groups `new_member` changes by `entity_label` to create one Member record per person. If Claude uses inconsistent labels (`"Benjamin Thompson"` vs `"Benjamin Walter Thompson"`), it creates duplicate members.

#### 4. Whisper Awareness (`_WHISPER_AWARENESS`)
Known Whisper error patterns:
- Numbers spoken digit-by-digit → hyphenated: `"78746"` → `"7-8-7-4-6"`
- Email domains mangled phonetically: `"@gmail.com"` → `"atgmail.com"`
- Names misheard when speaker changes topic mid-sentence

**Why:** Without this instruction, Claude either (a) faithfully reproduces the garbled value (`"7-8-7-4-6"` as the ZIP code) or (b) silently "corrects" it with full confidence. We want it to correct AND flag low confidence so the reviewer knows to verify.

#### 5. Few-Shot Example (`_FEW_SHOT`)
One complete input→output example showing the exact JSON structure expected, including a case where fields are NOT proposed because the DB already has correct values.

**Why:** Even well-designed schemas are misunderstood without a concrete example. The few-shot example is the single highest-ROI addition to any LLM prompt.

---

### The Iterative Feedback Loop

When a reviewer rejects a change with feedback, `revise_single_change()` is called synchronously. It receives:

1. **The original transcript** — to re-read from scratch
2. **The full schema** — so it knows valid field values
3. **The Whisper guidance** — so it can correct artifacts in its revision
4. **The current proposed value** — what it said last time
5. **The full conversation history** — all previous rounds of feedback/revision for this field
6. **The latest reviewer feedback** — what's wrong with the current proposal

This means if you reject `email` and say "the domain is gmail.com not atgmail.com", Claude has:
- The original transcript to re-read
- The knowledge that Whisper mangles email domains
- The history showing it previously proposed `atgmail.com`
- Your specific correction

And responds with a targeted revision — not a generic "I'll try again."

The loop can continue indefinitely:
```
Agent:    "email = BenjaminWalter.atx@atgmail.com"  (confidence 0.84)
Reviewer: [Reject] "the domain should be gmail.com"
Agent:    "email = BenjaminWalter.atx@gmail.com"    (revised, confidence 0.88)
Reviewer: [Still Wrong] "the username has a typo — it's BenjWalter not BenjaminWalter"
Agent:    "email = BenjWalter.atx@gmail.com"        (revised again, confidence 0.75)
Reviewer: [Approve]
```

---

### Mock Mode (No API Key)

When `ANTHROPIC_API_KEY` is not set, every Claude call is intercepted by `_mock_mode()` and returns a hardcoded response based on the Benjamin Walter Thompson Jr. demo transcript.

The mock data mirrors exactly what a real Claude response would look like:
- All 20 field-level proposed changes with exact transcript quotes
- Realistic confidence scores (72% for the "Jack/Benjamin" Whisper mishearing, 84% for garbled email)
- Field-aware revision responses (knows the "Jack" artifact, the hyphenated address, the garbled domain)

**Switching to real mode:** Add `ANTHROPIC_API_KEY=sk-ant-...` to `backend/.env` and restart. No code changes needed.

---

### Is This a True AI Agent Orchestrator?

**No — and it's important to understand the distinction.**

#### What is actually built: Context-Stuffed Single-Shot Extraction

```
Python code                           Claude
──────────────────────────────────    ─────────────────────────────────────
1. Query ALL households from DB   →
2. Serialize to a string          →   Reads a frozen text snapshot of the DB
3. Assemble prompt with context   →   Reasons over it in one pass
4. One API call                   →   Returns structured JSON
5. Parse JSON, write to DB        ←
```

Claude makes **zero database calls**. It receives a text snapshot prepared by Python, reasons over it once, and returns JSON. It is a sophisticated text-in / text-out transformer — not an orchestrator.

The client snapshot injected via `_build_household_context()` is a **frozen photograph** of that one household taken at call time. If the DB changes while Claude is processing, it will not know. If Claude needs deeper information about a specific account, it cannot ask.

---

#### What a True Agent Orchestrator looks like

A real agent uses **Anthropic's tool use API** — Claude is given a set of callable functions and an agent loop drives it until it signals it is done:

```python
# Tools Claude can call at will during its reasoning
TOOLS = [
    {
        "name": "search_households",
        "description": "Search existing households by name. Use this to check if a client already exists before proposing new records.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Partial or full household name"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_household_details",
        "description": "Get full details of a specific household including all members, accounts, and current field values.",
        "input_schema": {
            "type": "object",
            "properties": {
                "household_id": {"type": "integer"}
            },
            "required": ["household_id"]
        }
    },
    {
        "name": "propose_change",
        "description": "Propose a field-level change for human review. Call once per field.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_type":    {"type": "string"},
                "entity_id":      {"type": ["integer", "null"]},
                "entity_label":   {"type": "string"},
                "field_name":     {"type": "string"},
                "proposed_value": {"type": "string"},
                "source_quote":   {"type": "string"},
                "confidence":     {"type": "number"}
            },
            "required": ["entity_type", "field_name", "proposed_value", "source_quote", "confidence"]
        }
    }
]

# Agent loop — runs until Claude stops calling tools
def run_true_agent(transcript: str, db: Session) -> list:
    messages = [{"role": "user", "content": f"Analyze this transcript:\n{transcript}"}]
    proposed_changes = []

    while True:
        response = client.messages.create(
            model="claude-opus-4-6",
            tools=TOOLS,
            messages=messages,
            max_tokens=4096,
        )

        if response.stop_reason == "end_turn":
            break  # Claude is satisfied — no more tool calls

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                if block.name == "search_households":
                    results = db.query(models.Household).filter(
                        models.Household.name.ilike(f"%{block.input['query']}%")
                    ).limit(5).all()
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps([{"id": h.id, "name": h.name} for h in results])
                    })

                elif block.name == "get_household_details":
                    hh = db.query(models.Household).get(block.input["household_id"])
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(_serialize_household(hh))
                    })

                elif block.name == "propose_change":
                    proposed_changes.append(block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Change recorded."
                    })

            # Feed tool results back so Claude can continue reasoning
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

    return proposed_changes
```

**The key difference:** Claude drives the DB queries. It decides what to look up and when. Python only executes what Claude asks for. The agent can do multiple rounds of search → read → propose before finishing.

---

#### Comparison

| | Current (single-shot) | True agent (tool use) |
|---|---|---|
| DB queries | Python queries everything upfront | Claude decides what to query |
| Handles large DB (50k+ households) | ❌ Prompt too large | ✅ Searches on demand |
| Can drill into specific records | ❌ Sees only what's pre-fetched | ✅ Calls get_household_details() |
| Reacts to what it finds | ❌ One pass only | ✅ Iterates: search → read → propose |
| Debuggability | ✅ Simple, every step visible | Harder — reasoning is inside tool call loop |
| Right for this demo (~22 households) | ✅ Perfect fit | Overkill |
| Right for production (10k+ households) | ❌ Breaks at scale | ✅ Required |

#### Why single-shot was chosen for this implementation

1. **Fits the data size** — 22 households comfortably fits in a prompt. No search needed.
2. **Simpler to debug** — the prompt is a readable string. You can inspect exactly what Claude saw.
3. **Faster** — one API call vs potentially 5–10 round trips in an agent loop.
4. **Deterministic** — same DB state → same input → reproducible output. Agent loops can behave differently each run.

#### Migration path to true agent

The current system already scopes context to one client per transcript via `_build_household_context()`. When the matched household itself becomes too large (hundreds of accounts/members) or when multi-client transcripts arise:

1. Replace `_build_household_context()` with the three tools above (`search_households`, `get_household_details`, `propose_change`)
2. Replace the single `client.messages.create()` call with the agent loop shown above
3. The rest of the system (Review Queue, apply step, human-in-the-loop) stays identical

The review queue, proposed_changes table, and apply logic are **agent-pattern-ready** — they were designed assuming Claude would eventually propose changes via tools rather than a single JSON dump.

---

### Why Not LangGraph?

This workflow was deliberately implemented as plain Python functions rather than using a graph orchestration framework. The reasoning:

| Factor | Plain Python (chosen) | LangGraph |
|---|---|---|
| Workflow complexity | 2 Claude calls, 1 loop | Worth it at 5+ agents |
| Debuggability | Every line is yours | Errors inside framework abstractions |
| Interview explainability | Walk through any line | "I used LangGraph" without depth is a red flag |
| Dependencies | Zero new deps | LangChain ecosystem (frequent breaking changes) |
| Streaming | Not needed for this use case | Built-in |
| State persistence | `conversation_history` JSON column | Checkpointer (better at scale) |

**When to migrate to LangGraph:** When the workflow expands to parallel specialized agents (compliance checker, portfolio risk analyzer, tax implications analyzer) that must merge their outputs before the human review step. At that point, managing state across 5+ agents manually becomes error-prone and LangGraph's graph model pays off.

---

## Review Queue — New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/review` | List all review sessions with change counts |
| GET | `/api/review/{id}` | Full session with all proposed changes |
| POST | `/api/review/{id}/changes/{cid}/approve` | Approve a proposed change |
| POST | `/api/review/{id}/changes/{cid}/reject` | Reject with feedback → triggers agent revision |
| POST | `/api/review/{id}/changes/{cid}/accept-revision` | Accept the agent's revised value |
| POST | `/api/review/{id}/apply` | Write all approved changes to the database |

---

## Assumptions

1. **Household deduplication** — matched by exact name; re-uploading the same file is idempotent (safe to run multiple times)
2. **Account values** — not present in the sample CSV; displayed as `—` and can be updated via the inline editor or audio upload
3. **Audio enriches existing households** — per the spec; a household must be imported before audio is linked to it
4. **Whisper model** — `base` for speed (~140MB, runs on CPU); upgrade to `medium`/`large` in `audio_parser.py` for higher accuracy
5. **Tax brackets** stored as strings (`"25%"`, `"Highest"`) exactly as they appear in the source — normalisation would require a lookup table outside the scope of this assignment
6. **No authentication** — out of scope for this assignment; in production, add JWT + role-based access (advisor can only see their own clients)
