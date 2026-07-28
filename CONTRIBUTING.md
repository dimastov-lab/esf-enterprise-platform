# Contributing

This is a private, commercial project (see `LICENSE` — all rights reserved). External
contributions are not solicited; these guidelines exist for authorized contributors and
to keep the codebase consistent. The authoritative engineering charter is `CLAUDE.md`;
this file mirrors its standards.

## Architecture — non-negotiable

Always use the layered architecture:

**Controller (router) → Service → Repository → Database**

- No business logic in controllers.
- No SQL outside repositories.
- No direct database access from templates.
- No duplicate logic; no temporary hacks.
- **No `TODO` / `FIXME` / `HACK` markers in production code.** Track outstanding work in
  `TECHNICAL_DEBT.md` instead.
- One template `app/templates/esf/form.html` renders edit / view / public / pdf modes —
  do not fork it into duplicate layouts.

## Development setup & tests

The application lives under `backend/`.

```bash
# From the repo root:
docker compose up -d                 # PostgreSQL 15 on localhost:5432

cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Run the transaction-isolated regression suite (currently 75 tests):
DATABASE_URL=postgresql+psycopg2://esf:esf@localhost:5432/esf pytest
```

All tests must pass before a change is considered done.

## Linting & formatting

- Lint and format with **ruff**:

  ```bash
  cd backend
  ruff check .
  ruff format .
  ```

- Respect `.editorconfig` (Python: 4-space indent, LF line endings, final newline, no
  trailing whitespace; target max line length 100).
- A `.pre-commit-config.yaml` is provided — run `pre-commit install` once and let hooks
  run on every commit.

## Commit messages — Conventional Commits

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>
```

Common types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `security`.
Examples from this repo's history:

```
fix(security): DB-level immutability for snapshots & audit log
fix(validation): buyer INN digits, foreign-currency rate, VAT vs base
```

## Definition of done

A change is done only when: code runs locally, there are no import errors, tests pass,
the architecture stays clean, and the relevant docs are updated (`PROJECT_STATE.md`,
`ROADMAP.md`, `CHANGELOG.md`, `TECHNICAL_DEBT.md`). See `DEFINITION_OF_DONE.md`.
