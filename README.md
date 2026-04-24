# FasttrackrAI — Financial Advisor Client Management System

A full-stack AI-powered CRM that helps financial advisors manage client data, transcribe meeting recordings, and review AI-proposed changes before they reach the database.

---

## Features

- **Excel / CSV Import** — Upload any spreadsheet format; a LangGraph agent maps column headers to DB fields using Claude, handling completely novel column names without hardcoded rules
- **Audio Transcription** — Record a client meeting, upload the audio; Whisper transcribes it and a LangGraph agent extracts structured financial data
- **Human-in-the-Loop Review Queue** — Every AI-proposed change is held for compliance review; reviewers approve, reject with feedback, or trigger an agent revision
- **Household Dashboard** — All households with key financial stats and search
- **Household Detail** — Full member profiles, accounts, action items, audio insights, inline editing
- **Insights & Charts** — 6 interactive charts: net worth, income, account types, tax brackets, risk tolerance, members per household

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11, FastAPI |
| Database | PostgreSQL 16, SQLAlchemy 2.0, Alembic |
| Agent Orchestration | LangGraph |
| LLM | Anthropic Claude (via LangChain structured output) |
| Audio Transcription | OpenAI Whisper (local) |
| Data Parsing | Pandas |
| Frontend | React 18, TypeScript, Vite, Recharts |

---

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 16 (`brew install postgresql@16`)
- ffmpeg (`brew install ffmpeg`) — required by Whisper
- Anthropic API key — required for audio extraction

### 1. Database

```bash
brew services start postgresql@16

psql postgres -c "CREATE DATABASE fasttrackr;"
psql postgres -c "CREATE USER fasttrackr_user WITH PASSWORD 'fasttrackr_pass';"
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE fasttrackr TO fasttrackr_user;"
psql postgres -c "ALTER DATABASE fasttrackr OWNER TO fasttrackr_user;"
```

### 2. Backend

```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

alembic upgrade head
```

### 3. Frontend

```bash
cd frontend
npm install
```

### 4. Run

**Terminal 1 — Backend:**
```bash
cd backend && source venv/bin/activate
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend && npm run dev
```

Open **http://localhost:5173**

---

## Project Structure

```
FasttrackrAI/
├── backend/
│   ├── main.py                 # FastAPI app — CORS, router mounting
│   ├── database.py             # PostgreSQL engine, session factory
│   ├── models.py               # SQLAlchemy ORM models
│   ├── schemas.py              # Pydantic v2 request/response schemas
│   ├── migrations/             # Alembic versioned schema migrations
│   ├── parsers/
│   │   ├── prompts.py          # All LLM prompt constants (schema, rules, Whisper guidance)
│   │   ├── context.py          # DB context builder — fetches one household's snapshot
│   │   ├── agent.py            # LangGraph audio extraction graph (build_context → extract_with_claude)
│   │   ├── column_mapper.py    # LangGraph column mapping graph (map_columns → validate_mapping)
│   │   ├── review_agent.py     # LangChain revision call for rejected changes
│   │   ├── audio_parser.py     # Whisper transcription
│   │   └── csv_parser.py       # CSV/Excel parser — uses column_mapper for field resolution
│   ├── routers/
│   │   ├── households.py       # Household CRUD + action items endpoints
│   │   ├── upload.py           # File upload handler (CSV + audio)
│   │   ├── review.py           # HITL review queue endpoints
│   │   └── insights.py         # Aggregated analytics
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    └── src/
        ├── App.tsx
        ├── api/index.ts
        ├── types/index.ts
        └── pages/
            ├── HouseholdList.tsx
            ├── HouseholdDetail.tsx
            ├── Insights.tsx
            ├── Upload.tsx
            ├── ReviewQueue.tsx
            └── ReviewDetail.tsx
```

---

## Database Schema

```
Household (1) ──< Member ──< Account ──< Beneficiary
                        └──< BankDetail
Household ──< AudioInsight ──< ActionItem
Household ──< ActionItem
AudioInsight ──< ReviewSession ──< ProposedChange
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/households` | List all households |
| GET | `/api/households/{id}` | Household detail |
| PUT | `/api/households/{id}` | Update household fields |
| DELETE | `/api/households/{id}` | Delete household |
| GET | `/api/households/{id}/action-items` | Action items for a household |
| PATCH | `/api/households/{id}/action-items/{aid}` | Toggle action item status |
| POST | `/api/upload/excel` | Import CSV / XLSX |
| POST | `/api/upload/audio` | Upload audio (transcribe + extract + create review session) |
| GET | `/api/review` | List all review sessions |
| GET | `/api/review/{id}` | Full session with proposed changes |
| POST | `/api/review/{id}/changes/{cid}/approve` | Approve a change |
| POST | `/api/review/{id}/changes/{cid}/reject` | Reject with feedback → triggers agent revision |
| POST | `/api/review/{id}/changes/{cid}/accept-revision` | Accept the revised value |
| POST | `/api/review/{id}/apply` | Write all approved changes to DB |
| GET | `/api/insights/summary` | Aggregated chart data |

Interactive docs: **http://localhost:8000/docs**

---

## AI Agent Architecture

### Excel / CSV Pipeline

```
User uploads CSV or XLSX file
         │
         ▼
[LangGraph — parsers/column_mapper.py]
         │
         ├── Node 1: map_columns
         │     Reads headers + 3 sample rows
         │     Calls claude-haiku once with structured output
         │     Returns ColumnMapping — exact CSV column for every DB field
         │     e.g. "Client Annual Gross Income" → annual_income
         │          "Given Name"                 → first_name
         │          "Beneficiary 1 Name"         → beneficiaries[0].name
         │
         └── Node 2: validate_mapping
               Checks household_name was resolved
               Raises clear error if not
         │
         ▼
[csv_parser.parse_file()]
  Loads full file with pandas (all sheets merged for Excel)
  Groups rows by household name
  Extracts members, accounts, bank details, beneficiaries
  using exact column names from ColumnMapping — no guessing
         │
         ▼
[FastAPI — _upsert_household()]
  Household exists by name → update fields
  Household new → insert
  Same for members, accounts, beneficiaries
  Written directly to PostgreSQL — no review queue needed
  (advisor explicitly prepared and uploaded this file)
```

**Why LLM for column mapping instead of regex:**

The old approach hardcoded candidate strings (`"annual income"`, `"income"`, `"yearly income"`) and substring-matched them against column headers. It failed silently on anything outside those candidates — `"Client Annual Gross Revenue"` would return null with no error.

The LLM understands semantic equivalence. It maps `"Client Annual Gross Income"` → `annual_income` and `"Given Name"` → `first_name` without any hardcoded rules. One call per file using claude-haiku keeps cost negligible (~$0.001 per upload).

**Why no review queue for Excel:**

Excel is structured data the advisor explicitly prepared. They formatted it, they own it, they uploaded it intentionally. There is no AI interpretation involved — the LLM only reads column headers to produce a mapping, not to interpret or infer client data. The data values go straight to the DB unchanged.

Audio is different — an AI is interpreting unstructured speech. That interpretation can be wrong, which is why every proposed change goes through human review.

---

### Audio Pipeline

```
User selects client from dropdown + uploads audio file
         │
         ▼
[Whisper — local transcription]
  Audio file → plain-text transcript
         │
         ▼
[LangGraph — parsers/agent.py]
         │
         ├── Node 1: build_context
         │     Fetches selected household's current DB record
         │     (all field values, member IDs, account IDs)
         │     Scoped to ONE client — other clients' data never enters the prompt
         │
         └── Node 2: extract_with_claude
               ChatAnthropic.with_structured_output(ExtractionOutput)
               Returns: proposed_changes, key_insights, action_items
         │
         ▼
[FastAPI — routers/upload.py]
  Saves AudioInsight, ActionItem records, ReviewSession + ProposedChange records
         │
         ▼
[Human Review Queue — /review UI]
  Reviewer sees each proposed change with source quote + confidence score
    ✓ Approve  → marked approved
    ✗ Reject + feedback → LangChain revision call (review_agent.py)
                          → back and forth until approved or dismissed
         │
         ▼
[POST /review/{id}/apply]
  Only approved changes written to DB
  Full audit trail: every change traceable to source audio + transcript quote
```

### Why the user selects the client explicitly

The user picks the client from a dropdown before uploading audio. The `household_id` goes straight to `build_context` which does a direct DB fetch — no name extraction, no string matching. This is the correct production approach: the advisor knows whose meeting it was.

### What the LLM receives

**Node 1 output — client snapshot injected into the prompt:**

```
┌─ Household id:3
│  name:                        Raj and Priya Sharma
│  risk_tolerance:               —
│  annual_income:                200000.0
│  ...all fields...
│  ├─ Member id:5  Raj Sharma
│  │  email: raj@example.com   phone: —   occupation: Engineer
│  ├─ Account id:8  type:Roth IRA  custodian:Fidelity
```

For new clients (`household_id = None`) Claude receives:
```
No matching household found — treat as NEW CLIENT.
Use entity_type 'new_household', 'new_member', 'new_account' with entity_id = null.
```

**Also injected:**

- **Typed schema reference** — exact DB column names and types so Claude uses `risk_tolerance` not `"risk"`, `annual_income` not `"income"`
- **Entity resolution rules** — when to use `household` vs `new_household`, grouping rule (all fields for the same person share `entity_label` so the apply step creates one record)
- **Whisper artifact guidance** — known error patterns: digit-by-digit numbers get hyphenated, email domains get phonetically mangled; Claude corrects and flags these at lower confidence

### Why `with_structured_output` instead of prompt-engineered JSON

`ChatAnthropic.with_structured_output(ExtractionOutput)` binds a Pydantic model as a tool schema. Claude is forced by the API to return a response that conforms to the model — no JSON parsing, no code-fence stripping, no `try/except json.loads`. Invalid fields are rejected before the response reaches application code.

### The iterative feedback loop

When a reviewer rejects a change, `revise_single_change()` in `review_agent.py` is called. Claude receives:

1. The original transcript
2. The current proposed value and the source quote it came from
3. The full conversation history for this field (all prior rejection/revision rounds)
4. The latest reviewer feedback

This gives Claude full context for a targeted correction — not a generic retry. The loop continues until the reviewer approves or dismisses the change.

---

## Design Decisions

### PostgreSQL over SQLite / MongoDB

Financial data is inherently relational — households have members, members have accounts, accounts have beneficiaries. PostgreSQL gives full ACID compliance, FK enforcement, and JOIN-friendly analytics queries. SQLite has a single-writer lock inappropriate for concurrent advisors; MongoDB adds complexity without benefit for a relational data model.

### LangGraph for orchestration

The extraction pipeline is a two-node directed graph. LangGraph makes the data flow between nodes explicit and typed via `AgentState`. Each node is a pure Python function — testable in isolation. Adding new nodes (e.g. a compliance checker, a risk scorer) is an `add_node` + `add_edge` call without restructuring existing logic.

### Whisper local vs cloud STT

Whisper runs locally — no per-minute API cost, no audio data sent to a third party. The `base` model runs on CPU; upgrade to `small` or `medium` in `audio_parser.py` for better accuracy on financial terminology and accented speech.

### HITL before any DB write

No AI output touches the database without a human approving it. Every proposed change is stored in `proposed_changes` with its source quote and confidence score. The reviewer sees exactly what the transcript said and why Claude proposed the change. This is the compliance-required pattern for financial data in regulated environments.

### Audit trail

Every `ProposedChange` row records: source audio, exact transcript quote, confidence score, current DB value, proposed value, reviewer decision, conversation history of any rejection/revision rounds, and timestamp. The full history of how any client record was changed is queryable.
