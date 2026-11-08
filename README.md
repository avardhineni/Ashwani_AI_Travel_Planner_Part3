# ✈️ AI Travel Planner — LangGraph + MCP + Supervisor + Guardrails + Human-in-the-Loop

**An educational multi-agent travel-planning project that grows from basic LangGraph orchestration to MCP tool integrations, dynamic agent selection, auditable budget arithmetic, human approval and PDF export.**

> **Project status:** End-to-end application source is provided, and deterministic offline tests are included. A live run requires your own Groq account, PostgreSQL instance, and optional MCP credentials/third-party server. **This is a learning/prototype application—not a production booking engine.** No flight/hotel is actually booked, no real-time fare is guaranteed, and the lowest supplied quote combination is *not* necessarily a bookable itinerary.

## Contents

1. [What the project does](#what-the-project-does)
2. [Learning journey: Part 1 → Part 2 → Part 3](#learning-journey-part-1--part-2--part-3)
3. [System architecture](#system-architecture)
4. [Repository structure and file-by-file explanation](#repository-structure-and-file-by-file-explanation)
5. [New: Budget Feasibility Validation and Alternative Planning](#new-budget-feasibility-validation-and-alternative-planning)
6. [Human-in-the-Loop reviews and revision loop](#human-in-the-loop-reviews-and-revision-loop)
7. [Windows quick start](#windows-quick-start)
8. [Configure the external MCP integrations](#configure-the-external-mcp-integrations)
9. [Run the application](#run-the-application)
10. [How to use the budget feature](#how-to-use-the-budget-feature)
11. [Testing and troubleshooting](#testing-and-troubleshooting)
12. [Limitations, security and future roadmap](#limitations-security-and-future-roadmap)
13. [GitHub publishing](#github-publishing)

## What the project does

The user enters a trip request in a Streamlit web app. A **scope guardrail** classifies the request as travel-related or not. A **supervisor LLM** extracts travel constraints and chooses specialist MCP agents. Flight/Hotel/Weather specialists retrieve information through external services if configured. A **deterministic budget validator** calculates totals from user-entered INR price quotes and flags incomplete data or a plan that exceeds the specified budget. A **alternative-planning node** explains the lowest supplied combination (or missing evidence), and a **budget decision interruption** asks the user before proceeding when cost is unsupported or over the cap. An itinerary LLM creates a draft, and a separate **human approval interruption** allows approval or revisions. Only **approved plans** are exported to PDF.

**Main features**

- Scope validation and rejected-request termination at `END`.
- LLM supervisor chooses only needed Flight, Hotel and Weather specialists; LangGraph preserves the execution order.
- Tavily remote MCP, AviationStack third-party local stdio MCP, custom OpenWeatherMap FastMCP server.
- Budget Agent performs **Python/Decimal** arithmetic instead of trusting LLM-generated totals; an Alternative Planning Agent then describes evidence-bounded options.
- Incomplete price evidence explicitly produces `unknown`, not a fabricated minimum.
- Budget HITL: preview with warning, lowest *user-supplied* quote combination, change cap, change trip, or cancel.
- Draft HITL: approve or request revision, rerunning relevant specialists before review again (up to three reviews).
- PostgreSQL LangGraph checkpointing with `autocommit=True` and `dict_row`.
- Human-approved final output, native Streamlit rendering, PDF auto-save and download.
- Tests that need no API keys, Groq tokens, or live travel fares.

## Learning journey: Part 1 → Part 2 → Part 3

| Stage | What was implemented | Key learning |
|---|---|---|
| **Part 1** | LangGraph Flight, Hotel, Itinerary and Final Response nodes; direct APIs; PostgreSQL checkpoints; Streamlit | `StateGraph`, `TravelState`, tool calls and state reducers |
| **Part 2** | AviationStack local MCP, Tavily remote MCP, custom weather MCP server, Weather Agent | MCP client/server, `stdio`, Streamable HTTP, tool discovery and `ainvoke()` |
| **Part 3** | Scope Guardrail, Supervisor Agent, conditional routing, Budget Agent, budget gate, dual HITL and final-output checks | `add_conditional_edges`, `interrupt`, `Command(resume=...)`, deterministic validations, feedback loops |

The original Part 3 tutorial places the guardrail inside the Supervisor Agent and sends rejected requests to an empty list. This repository additionally fixes the graph routing so an empty/blocked selection really terminates. It also adds a **true revision loop** and deterministic cost validation. These are **project enhancements**, not features asserted to exist in the original tutorial source.

## System architecture

```mermaid
flowchart TD
  U[User in Streamlit frontend.py] --> G[Scope Guardrail and Supervisor agents.py]
  G -->|Blocked| STOP([END: rejected request])
  G -->|Allowed| R{Selected specialists? graph.py}
  R --> F[Flight Agent via AviationStack MCP]
  R --> H[Hotel Agent via Tavily MCP]
  R --> W[Weather Agent via custom Weather MCP]
  F --> B[Deterministic Budget Agent]
  H --> B
  W --> B
  R --> B
  B --> C{Budget status}
  C -->|Within supplied estimate / no budget| I[Itinerary Agent]
  C -->|Unknown or over budget| ALT[Alternative Planning Agent]
  ALT --> HITLB[HITL: budget review]
  HITLB -->|Change cap| B
  HITLB -->|Continue as preview / quoted lowest| I
  HITLB -->|Cancel/change trip| STOP
  I --> HITLI[HITL: itinerary approval]
  HITLI -->|Approve| FIN[Final Response + Output Guardrail]
  HITLI -->|Request changes| REV[Revision selector]
  REV --> R
  FIN --> PDF[Human-approved PDF download]
  FIN --> DONE([END])
  DB[(PostgreSQL checkpoints)] -.-> G
  DB -.-> HITLB
  DB -.-> HITLI
```

**Graph selection vs order:** The supervisor chooses relevant specialist *names*, but `graph.py` runs those selected specialists in a dependency-friendly order: Flight → Hotel → Weather → Budget → Itinerary. It does *not* let the LLM arbitrarily reorder nodes.

## Repository structure and file-by-file explanation

```text
Ashwani_AI_Travel_Planner_Part3_GitHub/
├── README.md                          # This detailed documentation
├── LICENSE                            # MIT for this project's own files
├── SECURITY.md                        # Security and credential safeguards
├── requirements.txt                   # App dependencies
├── .env.example                       # Placeholder configuration only
├── .gitignore                         # Excludes secrets, venvs and generated PDFs
├── config.py                          # Load env, model selection, API config
├── state.py                           # TypedDict TravelState + reducers
├── mcp_client.py                      # MCP server discovery and tool invocation
├── weather_mcp_server.py              # Custom FastMCP Weather server
├── agents.py                          # Guardrail, supervisor, specialists, HITL, revision
├── graph.py                           # Conditional edges, graph compilation, PG saver
├── frontend.py                        # Streamlit UI, approvals, quotes, PDF download
├── pdf_export.py                      # ReportLab PDF with safe escaped user text
├── cli.py                             # Optional CLI demo
├── guardrails/
│   ├── __init__.py
│   ├── alternatives.py               # Evidence-bound suggestions, no invented minimum
│   ├── budget.py                      # Quote validation, totals, budgets, INR parsing
│   └── output.py                      # Removes unsourced monetary claims from AI draft
├── samples/
│   └── quote_format.json             # Template; NULL prices, no invented fares
├── tests/
│   ├── test_budget.py                 # Budget/quote/guardrail tests
│   ├── test_pdf.py                    # Generates and validates PDF file header
│   └── test_static.py                 # Syntax and publishing checks
└── .github/workflows/quality.yml     # Offline GitHub Actions checks
```

**`config.py`** loads `.env` using `python-dotenv` and lazily initializes Groq through `get_llm()`. The default model is `openai/gpt-oss-120b`, not the tutorial's Llama 3.3 70B model. Confirm this model is accessible to your Groq API key.

**`state.py`** defines the keys every node can read/write. `messages` uses `operator.add` to append new messages; `llm_calls` also uses an additive reducer so each executing LLM node contributes its actual invocation count.

**`mcp_client.py`** configures only the MCP integrations for which a key/path exists. Each helper invokes a server-specific tool (`list_airports`, `list_airlines`, `tavily_search`, `get_current_weather`, `get_forecast`). MCP failure or missing configuration is surfaced visibly and is **never interpreted as a fare quote**.

**`weather_mcp_server.py`** implements FastMCP tools. OpenWeatherMap current conditions and the next five **3-hour intervals** are not forecasts for a seven-day trip next year.

**`agents.py`** implements the initial guardrail, supervisor, Flight/Hotel/Weather specialists, Python-based Budget Agent, Alternative Planning Agent, budget decision node, Itinerary Agent, human approval, revision selector and final response. The system does not ask the LLM to decide numerical total correctness.

**`graph.py`** connects these nodes using conditionals; blocked prompts terminate. Revision feedback can rerun selected specialists before budget and itinerary generation. A new review occurs after every revision. The workflow is checkpointed in PostgreSQL.

**`frontend.py`** is the user interface. It accepts optional user-observed INR price quotes, renders the budget decision and itinerary review forms, resumes the graph with the same thread ID, and exports only human-approved text as a PDF.

**`pdf_export.py`** uses ReportLab. It exports the final plan including the deterministically calculated budget table. Raw MCP result text is excluded to avoid copying unvalidated prices into a PDF.

## New: Budget Feasibility Validation and Alternative Planning

### Problem from the original project

A user requested: **"Plan a complete 7 days Japan trip including flights, hotels and sightseeing under ₹10,000."** The old AI-generated PDF displayed **₹73,850**, exceeding the cap and containing line-item arithmetic inconsistencies. This is a **budget constraint violation** and an **LLM arithmetic error**.

### What changed

Budget analysis is no longer merely an LLM paragraph. `guardrails/budget.py` normalizes price quotes and calculates `quantity × unit_cost_inr` for each row using `Decimal`. It chooses the lowest supplied subtotal for each of six categories and sums the chosen rows in Python.

```python
subtotal_inr = quantity * unit_cost_inr
quoted_combination_total = sum(category_minimum_subtotals)
within_supplied_estimate = quoted_combination_total <= approved_budget_inr
```

The mandatory categories are: **flights, accommodation, transport, food, activities, fees**. Include passenger quantities, nights, days, visa, insurance, baggage and taxes in your own estimates. A category with a genuinely zero fee must explicitly have `unit_cost_inr=0`, not be left blank.

The validator returns one of four statuses:

| Status | Meaning | Action |
|---|---|---|
| `within_estimate` | All six categories supplied, origin known, quoted combination <= cap | Generate a draft. **Not a verified/bookable price.** |
| `over_budget` | All six supplied, origin known, quoted combination > cap | Pause for **budget HITL**, show the shortfall. |
| `unknown` | At least one required category missing, origin missing or invalid evidence | Pause for budget HITL; **do not invent a minimum fare**. |
| `no_budget` | User provided no INR cap | Produce an indicative plan with no affordability guarantee. |

**Important evidence caveat:** Quotes typed into the UI are **user-provided, unverified observations**. The app cannot automatically determine whether a flight or hotel quote is currently available, whether a quote is recent, whether two low-cost options are mutually compatible, or whether a visa is required. The calculated minimum is **the least total among supplied category options**, not the *lowest realistic fare in the market*. It must not be described as a verified bookable minimum.

### Behavior for an impossible-looking request

For Japan + ₹10,000, if the user provides no price quotes, the app correctly displays **unknown feasibility** and asks for a decision. It **cannot factually say Japan is impossible or give a price floor** without evidence. With complete user-supplied quotes whose combined cost exceeds ₹10,000, it clearly marks **over budget**, shows the arithmetic and the difference, and refuses to claim the final plan is within ₹10,000.

The budget review provides these options:

1. **Continue with a warning:** generate an exploratory itinerary, never representing it as within budget.
2. **Show lowest quoted combination:** only when all categories were entered; an indicative quote combination, not a confirmed booking.
3. **Raise the approved budget:** enter a new cap; LangGraph reruns budget validation.
4. **Change destination/dates:** safely stop the current trip and begin a new request with new evidence (automatic destination substitution is not yet implemented).
5. **Cancel:** terminate without generating an approved PDF.

This is the **first practical version of intelligent alternative planning**. Its Alternative Planning Agent proposes evidence-bound adjustments and its HITL collects a choice; it does **not** scrape/guarantee the true cheapest destination or flight. A future alternative-planning agent can call a dedicated priced travel-inventory API for verified candidate packages and compare them deterministically.

### Cost arithmetic illustration — SYNTHETIC TEST DATA ONLY

To test the calculator without claiming real Japan prices, `tests/test_budget.py` uses the following fictional values:

| Category | Illustrative subtotal |
|---|---:|
| Flight | ₹40,000 |
| Accommodation | ₹12,000 |
| Local transport | ₹3,500 |
| Food | ₹4,200 |
| Sightseeing | ₹1,500 |
| Fees | ₹2,000 |
| **Calculated total (NOT REAL FARES)** | **₹63,200** |

Against a synthetic cap of ₹10,000, the validator reports `over_budget` and shortfall **₹53,200**. This is **a unit test fixture, not a quotation or recommended real-world minimum**.

### What can the project guarantee?

- Every supplied row uses exact decimal multiplication rather than LLM math.
- A missing category is not silently treated as zero.
- It does not silently claim a trip is affordable when supplied complete quotes exceed the cap.
- LLM-generated currency amounts and unsupported “within budget” phrases are filtered from draft text. All displayed budget arithmetic is produced by the calculator.
- Final PDF export only becomes available **after explicit human itinerary approval**.

The text filter is intentionally conservative and is **not a complete guarantee against every form of misleading prose**. To further harden a production system, use structured itinerary fields, provider-verified inventory, date/currency validation and comprehensive LLM evaluation tests.

### Data quality and user input

Users may enter multiple options per category in Streamlit's quote editor. For each category the calculator picks the row with the lowest `quantity × unit cost`; the interface labels each as **user supplied and unverified**. You can attach a source URL and observation date. The app validates the URL scheme and date format; it **does not validate whether the provider's page actually supports that price**. Do not commit private travel details or exported PDFs.

## Human-in-the-Loop reviews and revision loop

LangGraph uses `interrupt(payload)` to suspend a node and `Command(resume=payload)` to resume the **same** persisted thread.

**Budget HITL** happens *after alternative suggestions and before itinerary generation* for `over_budget` or `unknown` status. Resume choices can return the graph to `budget_agent`, continue to `itinerary_agent`, or end.

**Itinerary HITL** happens after `itinerary_agent`. Approval routes to `final_response`. Rejection with non-empty feedback goes to `revision_agent`. The revision selector routes back to Flight/Hotel/Weather when their keywords appear in feedback, otherwise to Budget and Itinerary. A new itinerary is reviewed again. A maximum of **three rejected reviews** stops the workflow; no unapproved plan is exported.

The example is deliberately educational: it uses keyword selection for revision, so vague or ambiguous feedback may not trigger the exact intended specialist. Large changes in destination/dates should begin in a new thread and require new travel quotes. It is not a fully general planner.

Checkpoint storage persists workflow state and pause/resume history, but this project **does not** build a distinct semantic long-term user-memory store or user authentication service.

## Windows quick start

**Requirements:** Windows 10/11 with PowerShell, Python **3.11 or 3.12**, Git, PostgreSQL (for example PostgreSQL 18 if installed), a Groq key, and network access for optional MCP providers.

> Keep the new repository files **outside** your Python virtual environment. The old `ashwani-travel-agent` environment may work, but a new isolated `.venv` is easiest to reproduce publicly. Avoid Python 3.14 for now if your dependencies are not confirmed compatible with it.

### 1. Extract and open the repository

```powershell
cd "C:\path\to\Ashwani_AI_Travel_Planner_Part3_GitHub"
```

### 2. Create and activate the virtual environment

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` for that terminal session, or run `.venv\Scripts\python.exe` directly without activation.

### 3. Set up PostgreSQL

Use pgAdmin or `psql` to create a database **if it does not already exist**:

```sql
CREATE DATABASE ashwani_travel_agent;
```

Your existing database may already use that name. Do **not** recreate or delete an existing database unnecessarily.

The app calls `PostgresSaver.setup()` to create LangGraph checkpoint tables. `graph.py` uses:

```python
conn = psycopg.connect(DATABASE_URL, autocommit=True, row_factory=dict_row)
checkpointer = PostgresSaver(conn)
checkpointer.setup()
```

Those two connection options avoid the `CREATE INDEX CONCURRENTLY cannot run inside a transaction block` error and give checkpoint rows the expected dictionary shape.

### 4. Configure environment values

```powershell
Copy-Item .env.example .env
notepad .env
```

Required for graph execution:

```dotenv
GROQ_API_KEY=your_current_groq_key
GROQ_MODEL=openai/gpt-oss-120b
DATABASE_URL=postgresql://postgres:YOUR_URL_ENCODED_PASSWORD@localhost:5432/ashwani_travel_agent
```

Optional for MCP tools:

```dotenv
TAVILY_API_KEY=...
AVIATION_STACK_API_KEY=...
OPENWEATHER_API_KEY=...
AVIATION_MCP_PYTHON=...
AVIATION_MCP_DIR=...
```

The **Groq model must be accessible to your key**. The previous tutorial's `llama-3.3-70b-versatile` is not available to all plans. Check [Groq's supported model IDs](https://console.groq.com/docs/models) if `model_not_found` occurs.

When a PostgreSQL password contains `@`, `#`, `:` or other reserved URL characters, URL-encode it in the connection string. Never publish it.

## Configure the external MCP integrations

### Tavily remote MCP

Add a Tavily API key to `.env`. The client uses the provider's `https://mcp.tavily.com/mcp/` endpoint via Streamable HTTP. Verify Tavily's current authentication/setup instructions in [Tavily MCP docs](https://docs.tavily.com/documentation/mcp). If not configured, the Hotel Agent shows a transparent unavailable message instead of fake results.

### AviationStack third-party local MCP

**Third-party project is not vendored/copied here.** Install it separately and review its license and implementation before trusting it:

```powershell
cd C:\path\to\another-folder
 git clone https://github.com/Pradumnasaraf/aviationstack-mcp.git
cd aviationstack-mcp
python -m pip install uv
uv sync
```

Configure your `.env` with real absolute paths (examples—replace the user directory):

```dotenv
AVIATION_STACK_API_KEY=your_aviationstack_key
AVIATION_MCP_PYTHON=C:\Users\YOUR_USERNAME\Documents\aviationstack-mcp\.venv\Scripts\python.exe
AVIATION_MCP_DIR=C:\Users\YOUR_USERNAME\Documents\aviationstack-mcp
```

The MCP client starts the third-party package using `python -m aviationstack_mcp mcp run` through stdio; do not keep a second manual server process running unless separately testing it. The `list_airports` and `list_airlines` tools supply guidance, **not bookable future-date fares**. If the upstream tool names or arguments change, inspect its tools and adapt `mcp_client.py`.

### Custom Weather MCP

Set `OPENWEATHER_API_KEY` in `.env`. The main project itself contains `weather_mcp_server.py`; `mcp_client.py` launches it with `sys.executable`, avoiding the original tutorial's hardcoded `E:\...` path. The MCP server invokes the current and forecast endpoints with a network timeout and returns explicit errors.

### Why there are several Python processes

The Streamlit host and LangGraph nodes run in the main `.venv`. AviationStack's local MCP server runs in **its own** `.venv`. The custom weather server is spawned by the main app using its Python executable. A remote Tavily MCP endpoint runs on Tavily's infrastructure. LangGraph and MCP solve different problems: **workflow orchestration** versus **tool communication**.

## Run the application

### Streamlit UI (recommended)

From the repository root and with the environment activated:

```powershell
python -m streamlit run frontend.py
```

Open http://localhost:8501 in a browser.

1. Enter a travel query with **origin**, destination, duration and budget. For example: `Plan 7 days in Japan from Hyderabad under ₹10,000 with flights, hotels and sightseeing.`
2. Optionally enter price quotes for every cost category in the expandable quote editor. Leave `unit_cost_inr` blank if unknown; blank prices must **not** be turned into zero.
3. Click **Create Draft Plan**.
4. Read the supervisor and budget outputs; if budget is over cap/unknown, choose a budget action and submit.
5. Review the draft itinerary. Approve, or request changes to trigger a re-run and another review.
6. After approval, download the PDF. The same file is auto-saved locally under `travel_plans/` (ignored by Git).

For a travel query **without any quoted price evidence**, the app can generate suggestions after you explicitly choose **Continue with a non-bookable planning preview**. It will not supply a fabricated minimum cost.

### CLI demonstration

```powershell
python cli.py
```

The CLI is a smaller interactive demonstration that supports both budget and itinerary interruptions. Streamlit is recommended for normal use.

## How to use the budget feature

### Example A — Japan under ₹10,000 without quotes

- Query: `Plan 7 days in Japan from Hyderabad under 10000 Rupees.`
- Budget extraction: `10000` (INR).
- No quotes -> missing 6 categories -> status `unknown`.
- Outcome: budget HITL explains that it **cannot establish an actual lowest feasible trip cost**. The user can supply sourced prices, continue with a warning, change cap or change the trip.

### Example B — Complete illustrative test quotes (not real prices)

- Use the synthetic amounts documented above for all six categories.
- Calculator computes total `₹63,200.00` and difference `₹53,200.00` from the user cap.
- Status `over_budget` -> budget HITL.
- The user can elect to preview a plan based on those quoted figures, while the final plan retains the explicit **over-budget warning**.

### Example C — Missing origin

Even if six category quotes exist, a flight plan without an origin must not be treated as a verified trip cost. The validator reports `unknown` until the origin is supplied in the next request.

### Example D — Cost-table discrepancy

A hotel row such as quantity `7`, rate `2500`, computes subtotal `17500.00` in Python. The model cannot override this with a contradictory result. This addresses the earlier PDF's incorrect multiplication.

## Testing and troubleshooting

### Offline tests

```powershell
python -m pytest tests -q
python -m compileall -q agents.py graph.py frontend.py mcp_client.py
```

The tests include INR budget parsing, precise money math, negative/NaN rejection, missing evidence, over-budget/within-estimate routing states, quote options, unsupported monetary-text filtering, real PDF bytes, and syntax checks. **They do not exercise actual third-party service availability or full LangGraph resume behavior.** Live integration tests must be run with your credentials.

### Common errors

| Error | Why it happens | Fix |
|---|---|---|
| `ActiveSqlTransaction CREATE INDEX CONCURRENTLY` | Psycopg opened a transaction around checkpoint migrations | Confirm `autocommit=True` and restart Streamlit |
| `model_not_found` from Groq | Requested model not accessible to your key | Query current Groq model IDs; set `GROQ_MODEL` |
| `getaddrinfo failed` | Badly formed `DATABASE_URL` | Ensure `@localhost:5432` correctly separates credentials and hostname; URL-encode password |
| `AVIATION_MCP_PYTHON does not exist` | Wrong path for third-party venv | Confirm `Test-Path` on the `.venv\Scripts\python.exe` path |
| MCP `MISSING TOOL` | Upstream MCP server exposes different names | Inspect tool discovery and update wrappers |
| MCP `[NOT CONFIGURED]` | Optional key/server not configured | Configure `.env` or accept a no-provider-results plan |
| Budget `unknown` | Incomplete quotes or missing origin | Supply all six categories, origin and correct quantities |
| No final PDF | HITL not yet approved or execution stopped | Review draft and approve; blocked requests must not produce PDFs |
| PDF ₹ glyph issue | System lacks a Unicode TrueType font | Install a Unicode font locally; `pdf_export.py` probes Windows/Linux fonts and does not bundle fonts |

## Limitations, security and future roadmap

**What is implemented:** scope guardrail, conditional supervisor routing, three MCP integrations, budget arithmetic and over-budget warnings from supplied quotes, two explicit HITL points, revision routing, checkpoints and approved-only PDF export.

**What is NOT implemented:** automatic discovery of the *true cheapest* flights/hotels, live booking/payment, provider-verified fare totals, actual user login and authorization, automatic destination substitution, universal prompt-injection immunity, long-range forecast accuracy, or a comprehensive production eval pipeline. The system remains a **prototype**.

**Security and operations:**

- **NEVER commit `.env`**. A previous version of this project exposed API credentials; rotate those keys and the PostgreSQL password before publishing a repository based on it.
- Don't log raw API keys, personal travel details or database passwords.
- The default user label is not authentication. `thread_id` alone is not an authorization boundary. Add authentication and per-user ownership for any multi-user deployment.
- `stdio` third-party MCP servers run executable code on your machine; review their source and trust level. Only connect to approved servers.
- Avoid serving a single long-lived Psycopg connection to concurrent public users. Use managed pools and scoped connection lifecycles for server deployment.
- The tool wrappers show explicit unavailable/errors; they should not be mistaken for verified prices.
- For a production release, quote observation dates should be checked for freshness; tickets, accommodation and conditions should be reconciled against confirmed provider inventory and currency FX sources.
- Users must verify travel advisories, visa rules, health requirements and provider terms before traveling.

**Suggested next improvements:**

1. Structured supervisor outputs using Pydantic or schema-constrained generation; strong prompt-injection tests.
2. Dedicated pricing adapters returning origin/destination/date/currency/passenger-aware **provider-verified** offers with provenance and booking links, then compute the cheapest *feasible package* (not independently selected incompatible components).
3. A destination-alternatives agent with ranked *verified* candidate packages and explicit user approval of changes.
4. Stronger output validation: typed itinerary schema and explicit separation between descriptive content and calculated prices.
5. LangSmith traces, retrieval/tool evaluation datasets, deterministic cost checks, scenario and regression tests, latency and monetary/token budgets.
6. Persistent user preferences in an authorized, separate memory store; proper access controls.
7. Async graph nodes, managed MCP connections and PostgreSQL pools for concurrent deployments.

## GitHub publishing

1. Rotate any previously exposed keys and check `.gitignore`.
2. Review the whole source, especially `mcp_client.py`, `.env.example` and any provider terms/licenses.
3. Create an **empty** GitHub repository, e.g. `ai-travel-planner-langgraph-mcp-guardrails`.
4. Publish from the repository root:

```powershell
git init
git add .
git status --short
git commit -m "Part 3: supervisor, MCP, budget guardrails and HITL"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ai-travel-planner-langgraph-mcp-guardrails.git
git push -u origin main
```

GitHub Actions runs offline tests only; live MCP and Groq tests remain your responsibility.

### References and acknowledgments

This project builds on the ideas in the **CodeWithAarohi LangGraph Multi-Agent Travel Planner Part 1–3 video series**, with educational adaptations and additional deterministic budget constraints, stronger blocked routing and revision handling. The third-party AviationStack MCP package is installed separately; this repository does not republish its source code.

- [LangGraph interrupts, resumable workflows and checkpoint requirements](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangChain MCP adapters — server-specific tool discovery](https://reference.langchain.com/python/langchain-mcp-adapters/client/MultiServerMCPClient/get_tools)
- [Groq supported models](https://console.groq.com/docs/models)
- [PostgreSQL](https://www.postgresql.org/)
- [Streamlit](https://docs.streamlit.io/)
- [OpenWeatherMap](https://openweathermap.org/api)
- [Tavily MCP](https://docs.tavily.com/documentation/mcp)
- [AviationStack MCP external repository](https://github.com/Pradumnasaraf/aviationstack-mcp)

**Disclaimer:** AI-generated travel suggestions are not bookings or legal/immigration advice. User-supplied quotes are not independently verified. Validate all rates, taxes, travel rules and schedules before making purchases.
