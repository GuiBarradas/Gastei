# Contributing

Thanks for considering a contribution. This project is single-maintainer and personal-portfolio scoped, but I welcome issues and pull requests that improve the codebase.

## Quick start

```bash
git clone https://github.com/GuiBarradas/Gastei.git
cd Gastei
cp .env.example .env       # fill in at minimum LLM_PROVIDER and the matching key
uv sync                    # installs runtime + dev deps and pins a Python toolchain
uv run alembic upgrade head
uv run pytest              # the full suite should pass
```

## Development workflow

This project follows **test-first development** in the `domain/` and `services/` layers; API and UI layers may use post-fact tests. See [`ARCHITECTURE.md`](./ARCHITECTURE.md) §8 for the full testing strategy.

1. **Branch off `main`** with a topic name: `feat/...`, `fix/...`, `docs/...`, `refactor/...`, `test/...`.
2. **Write the failing test first** when touching `domain/` or `services/`. Commit it red, then green — the git log should show this discipline.
3. **Run the full suite** before pushing: `uv run pytest`.
4. **Lint clean**: `uv run ruff check . && uv run ruff format --check .`.
5. **Open a PR** against `main` with a description that explains *why*, not just *what*.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):

```
feat(categorizer): support merchant_exact pattern type
fix(api): return 422 instead of 500 on malformed OFX
docs(readme): add deployment screenshot
test(pipeline): cover the no-LLM fallback path
refactor(repositories): extract base SQLAlchemy adapter
chore(deps): bump anthropic to 0.45
```

This makes the changelog generation trivial and the history skim-able.

## Code style

- **Python 3.11+**, fully type-hinted.
- **Ruff** is the single source of truth for formatting and linting; rules are in `pyproject.toml`. Don't add a separate Black or isort config.
- **Docstrings** use Google style (`Args:`, `Returns:`, `Raises:`). Public functions in `domain/` and `services/` should be documented.
- **Imports** sorted by ruff's `I` rule; relative imports forbidden in `src/`.
- **No comments narrating obvious code.** Comments earn their keep by explaining *why*, not *what*.

## Architecture rules (Hexagonal)

These are checked socially, not by tooling — please respect them when reviewing PRs:

1. `domain/` and `services/` may **only** import from `gastei.domain.*`, `gastei.schemas.*`, and standard library / Pydantic. They may not import from `gastei.clients.*`, `gastei.repositories.*`, `gastei.api.*`, or `sqlalchemy` directly.
2. Adapters live in `clients/` (external services), `repositories/` (databases), and `api/` (HTTP). They implement Protocols defined in `domain/ports.py`.
3. Tests for `domain/` and `services/` use fakes from `tests/fakes/`. Tests for adapters may use the real backing technology (SQLite in-memory, recorded HTTP fixtures).

## Issue and PR templates

Issue and PR templates live in `.github/`. Please use them — they save reviewer time.

## Security

Vulnerabilities go through [`SECURITY.md`](./SECURITY.md), not the issue tracker.

## License

By contributing you agree your work is licensed under the MIT License (see [`LICENSE`](./LICENSE)).
