# Working on Culpa

- Backend: `apps/api` (FastAPI, Python 3.11). Keep `routers/` thin, business logic in `services/`, and `engine/` free of I/O (no DB, network, clock or randomness). The benchmark imports `engine/` directly.
- Money moves only in `services/settlement_service.py`, always with the settlement's `idempotency_key` and through the state machine in `models/case.py`.
- New background work = a topic in `workers/handlers.py` + an `outbox_service.add(...)` in the same transaction as the business change. Handlers must be idempotent.
- Web: `apps/web` (Next.js App Router). One folder per component: `components/<Area>/<Name>/<Name>.tsx` + `<Name>.module.css`. Data fetching lives in `hooks/` and `api/`, never in components.
- Money is a decimal string ("19.99") end to end. Times are UTC ISO 8601.
- Run `scripts/test.ps1` before committing.
