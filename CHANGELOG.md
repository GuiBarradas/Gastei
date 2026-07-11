# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] — 2026-07-10

### Added
- **Degraded mode in the categorization pipeline**: if the LLM stage fails (503/429/quota), rule results are kept and a per-request circuit breaker stops further LLM calls — a batch against a dead provider costs one failed call instead of twenty timeouts.
- `GET /categories` endpoint exposing the taxonomy; the UI now offers human-labeled dropdowns instead of raw category codes.
- `renda.presentes` and `renda.pensao` income categories (migrations 0002/0003).
- Log redaction helpers (`utils/logging.py`): API keys, bearer tokens, CPF, and account-number-like digit runs are masked in the `gastei` logger tree.
- Per-request 30s timeout on the Gemini client.

### Changed
- **UI redesign**: `st.navigation`/`st.Page` router with Material (SVG) icons, custom light theme, shared design tokens, validated chart palette; the category donut became labeled horizontal bars; transaction tables use typed `column_config`.
- LLM classification runs on the *fast* model tier (`claude-haiku-4-5` / Gemini Flash Lite); the chat agent keeps the smart tier. Gemini models use rolling `-latest` aliases (pinned versions get retired by the API).
- Streamlit pages moved from emoji-named `pages/` files to `views/` + router.

### Fixed
- Scheduled sync job crashed on every run: it called the FastAPI DI wrapper outside a request cycle, receiving unresolved `Depends` objects. Jobs now build the classifier through a plain constructor (`build_classifier`).
- An LLM failure in one chunk no longer discards the rule matches of that chunk.
- Retired Gemini model (`gemini-2.5-flash` → 404) replaced by rolling aliases.
- Gemini contract test now skips on free-tier capacity errors (429/503) instead of failing — contract drift (404, schema change) still fails loudly.

## [0.3.1] — 2026-05-29

### Added
- This changelog.
- `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`.
- GitHub Actions CI running `ruff check` + `pytest` on push and PR.
- Pre-commit hooks for `ruff format` and `ruff check`.
- All public docstrings, error messages, log strings, and test names translated to English (Brazilian-context data such as `seeds/*.yaml` and the chat agent's system prompt remain in pt-BR by design — they are user-facing content).

## [0.3.0] — 2026-05-03

### Added
- **Phase 3 — Open Finance + scheduling.**
  - `PluggyClient` wrapping the Pluggy Data API with automatic API-key refresh.
  - `PluggyBankConnector` adapter implementing the `BankConnector` port.
  - `SyncService` orchestrating items → accounts → transactions ingestion.
  - `APScheduler` background sync (`ENABLE_SCHEDULER=true`) running every `SYNC_INTERVAL_HOURS`.
  - `POST /sync` endpoint to trigger sync on demand.
  - `Dockerfile` + `docker-compose.yml` with healthcheck and Streamlit service.
  - `DEPLOY.md` covering Fly.io free-tier deployment.

### Changed
- README rewritten as portfolio-grade English documentation.

## [0.2.0] — 2026-05-02

### Added
- **Phase 2 — AI categorization + chat.**
  - `LLMClassifier` using Anthropic tool-use with strict taxonomy validation.
  - `AnthropicLLMClient` (Claude Haiku for classification, Claude Opus for the agent).
  - `GeminiLLMClient` adapter (Google AI Studio free tier; 1500 req/day).
  - Provider switching via `LLM_PROVIDER=anthropic|gemini`.
  - `CategorizationPipeline` orchestrating rules → LLM → example store.
  - `InsightAgent` with tool-use loop (max 8 iterations) and 4 tools.
  - `ChatService` persisting conversations and messages in SQLite.
  - `POST /chat` endpoint and Streamlit chat page with persistent history.
  - `SQLAlchemyExampleStore` implementing the `ExampleStore` port (feedback loop).
  - `PATCH /transactions/{id}` automatically records corrections as few-shot examples.
  - OFX bank auto-detection via BACEN codes (`BANKID`/`ACCTID`).
  - Bank-first UX in Dashboard and Transactions pages.

### Changed
- `get_classifier()` now builds a full `CategorizationPipeline` instead of returning `None`.
- Transactions/insights endpoints accept either `account_id` or `item_id` (or neither = consolidated view).

## [0.1.0] — 2026-05-01

### Added
- **Phase 1 — Static MVP.**
  - Project scaffolding with `uv`, ruff, pytest, Docker.
  - SQLAlchemy 2.0 models for items, accounts, transactions, categories, rules, examples, conversations, messages.
  - Alembic migrations and seeded category taxonomy.
  - 5 Protocols (`TransactionRepository`, `ExampleStore`, `Classifier`, `LLMClient`, `BankConnector`) in `domain/ports.py`.
  - 5 in-memory fakes in `tests/fakes/` for TDD.
  - `RuleEngine` with substring/regex/merchant_exact matchers, 84+ Brazilian patterns in `seeds/rules.yaml`.
  - `OFXImportService` with deterministic transaction IDs and optional auto-categorization.
  - FastAPI app with routers for items, accounts, transactions, insights, imports.
  - Streamlit Phase-1 UI (Dashboard, Transactions, Connections).
  - 200+ tests across unit, integration, and contract suites.

[Unreleased]: https://github.com/GuiBarradas/Gastei/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/GuiBarradas/Gastei/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/GuiBarradas/Gastei/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/GuiBarradas/Gastei/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/GuiBarradas/Gastei/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/GuiBarradas/Gastei/releases/tag/v0.1.0
