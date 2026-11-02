# Culpa

**The referee for agentic commerce.** When an AI agent's purchase goes wrong, Culpa decides *who is at fault* (the buyer, the merchant or the agent provider) and settles the dispute on PayPal with cited evidence.

Built for the PayPal AI Hackathon 2026. MIT licensed.

## The problem

AI agents now buy things for people. When an agent buys the wrong size, overspends, or the merchant ships something different, today's dispute system has no way to tell who caused it:

- Card networks route agent purchases through ordinary reason codes; Visa's April 2026 rules add no agent dispute category, and the EMVCo draft (Sept 2026) leaves non-fraud liability unresolved.
- The CFPB's January 2026 advisory says buyers keep dispute rights when an agent buys for them, narrowed only by a documented mandate.
- PayPal's Q3 2026 10-Q notes it absorbs substantial losses from protection programs.

Most "agent safety" tools stop a bad payment *before* it happens. Nothing decides fault *after* the money moved, which is where the dispute lands.

## What Culpa does

1. **At checkout** the buyer signs a mandate (cap, category, required attributes). The agent chooses a product and creates the order through the **PayPal Agent Toolkit**. When the buyer approves and the payment is captured, Culpa hashes the mandate, the agent's decision trace and the listing snapshot into one **Merkle root**.
2. **When a dispute arrives** (PayPal `CUSTOMER.DISPUTE.CREATED` webhook, or the simulator) Culpa runs four checks, cheapest first:

| # | Check | Uses AI | Finds |
| --- | --- | --- | --- |
| 1 | Rules: cap, currency, quantity, merchant, category, expiry | No | F1 mandate breach (decisive) |
| 2 | Listing: delivered item vs listing at purchase, listing history | No | F4 misrepresentation, F5 non-delivery |
| 3 | Agent replay: re-run the agent on the same inputs, then on a clarified instruction | Optional | F2 agent error vs F3 ambiguous instruction |
| 4 | Claim: claim vs approved cart, dispute velocity, account graph, Gemini judge | Optional | F6 friendly fraud |

3. The evidence becomes a **fault split** (e.g. buyer 60% / agent provider 40%) with a confidence. A **code-enforced policy** picks the action: full refund, partial refund, contest, or human review below 0.8 confidence.
4. An analyst approves, and the settlement worker executes on PayPal: accept claim or refund for full refunds, a refund offer for partial refunds, evidence for contests. Every PayPal POST carries a deterministic `PayPal-Request-Id`.

## Benchmark: AgentDispute-150

150 synthetic disputes, 25 per fault class, 20% hard (misleading claim text, formatting noise, repeat disputers, missing delivery records, non-reproducible agents). Labels are true by construction.

| System | Accuracy | Wrong-money rate | Escalated to human |
| --- | --- | --- | --- |
| Baseline: reads the buyer's claim only | 73.3% | 26.7% | 0% |
| Culpa without agent replay | 65.3% | 0.0% | 38.0% |
| **Culpa (all four checks)** | **98.7%** | **0.0%** | 6.0% |

*Wrong-money rate* = share of cases where money would move to the wrong party. Full table: [bench/results.md](bench/results.md). Reproduce: `python bench/generate.py && python bench/run.py` (add `--llm` to include the Gemini judge).

**Real-world dispute scenarios.** [bench/scenarios.md](bench/scenarios.md) runs 126 cases (42 situations x 3 product families) modelled on PayPal Buyer Protection rules and Visa / Mastercard reason codes: not received, not as described, condition claims, unauthorized, buyer's remorse, processing errors and agent mandate breaches. Each states the outcome its rule expects; all pass, and every verdict carries a reason code. Reproduce: `python bench/scenarios.py`.

**Limitations.** The data is synthetic and the engine was designed around the same fault taxonomy, so these are in-distribution numbers, not real-world accuracy. The value of the benchmark is the comparison and the failure analysis: claim-only classification moves money to the wrong party in roughly a quarter of cases, and replay is what separates F2 from F3.

## Architecture

```
Browser ─► Next.js web (CDN-cached static assets)
              │ /api
              ▼
PayPal ──► FastAPI (routers → services) ──► Postgres (partition-ready, outbox, audit chain)
webhooks      │ verify · dedup · 200 in <1s        │
              ▼                                    ▼
          Redis cache                       Outbox relay ─► Redis Streams ─► workers
                                                                   │            │
                                                     dead letters ◄┘   Gemini API · PayPal REST
```

- **Transactional outbox**: business writes and the job message commit together. Redis carries only outbox ids, so a Redis outage delays work but never loses it. Without Redis the relay runs jobs inline.
- **Idempotency everywhere**: unique webhook event ids, one case per PayPal dispute, `UNIQUE(case_id, action)` on settlements, and UUIDv5 idempotency keys on PayPal POSTs.
- **Resilience**: retries with exponential backoff and full jitter, circuit breakers on PayPal and Gemini, a settlement state machine (`approved → executing → succeeded | failed_retryable | failed_final`), dead-letter replay, and a reconciler that pulls missed disputes.
- **Integrity**: canonical-JSON SHA-256 hashes, a Merkle root per order, HMAC-signed mandates, and a hash-chained append-only audit log.
- **The LLM never moves money.** Gemini gets buyer text only as quoted data, returns schema-validated JSON, has no tools, and its output only feeds weights the code policy reads.

Data structures used in the engine: hash maps, LRU cache, sliding window (rate limiter + dispute velocity), binary search (listing version at purchase time), Merkle tree, trie (category allowlist), heap (review queue), DAG + topological sort (check ordering), union-find (fraud rings), edit-distance DP, two-pointer timeline merge.

## PayPal integration

| Surface | Used for |
| --- | --- |
| Agent Toolkit (`paypal-agent-toolkit`) `create_order` | The buyer agent creates its order |
| Orders v2: PATCH `custom_id`, capture, tracking | Link evidence, capture after buyer approval, delivery evidence |
| Webhooks + `verify-webhook-signature` | Dispute intake |
| Disputes: get, list, accept-claim, make-offer, provide-evidence | Settle or contest |
| Payments v2 refunds | Simulator-case refunds |

Without PayPal keys, orders and settlements run in **simulated** mode (clearly labelled in the UI), so the whole flow can be demoed offline.

## Quick start (Windows)

Requirements: Python 3.11+, Node 20+, pnpm.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1   # venv, deps, benchmark
# paste keys into apps\api\.env (optional; see below)
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1     # API :8000, web :3000
```

macOS/Linux: `cd apps/api && python -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/uvicorn main:app --reload`, then `cd apps/web && pnpm install && pnpm dev`.

**Full stack in Docker** (Postgres, Redis, API, worker, web): `docker compose up -d --build`.

### Keys (`apps/api/.env`)

| Variable | Where | Needed for |
| --- | --- | --- |
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` | developer.paypal.com → Apps & Credentials → Sandbox | Real sandbox orders, refunds, disputes |
| `PAYPAL_WEBHOOK_ID` | Your app → Webhooks → add `https://<public-api>/webhooks/paypal`, events `CUSTOMER.DISPUTE.CREATED`, `CUSTOMER.DISPUTE.UPDATED` | Verified webhooks |
| `GEMINI_API_KEY` | aistudio.google.com → Get API key (free tier) | AI agent, clarifier and claim judge (models set by `LLM_FAST_MODEL`, `LLM_JUDGE_MODEL`) |
| `REDIS_URL` | `redis://localhost:6379/0` after `docker compose up -d redis` | Redis cache and Streams transport |
| `ANALYST_USERNAME`, `ANALYST_PASSWORD` | choose them | The dispute-console login, stored hashed in the database |

### Demo script

1. **Buyer agent** → "Ambiguous size" example → the agent picks UK 9 → approve with PayPal.
2. **Merchant** → ship the order. (For F4, first edit the listing's material, then ship.)
3. **Orders** → Open dispute → "Wrong size" → the case opens with **F3: buyer 60% / agent provider 40%, partial refund**.
4. Approve → the settlement executes with an idempotency key; the audit chain shows every step.

## Tests

```powershell
powershell -File scripts\test.ps1   # 67 backend tests, benchmark, web type-check and build
```

## Repository layout

```
apps/api      FastAPI: core/ (config, db, cache, queue, security, resilience), routers/, services/ (paypal/, cases,
              settlement, evidence, outbox, audit), engine/ (pure checks, scoring, policy, DSA), workers/, models/, tests/
apps/web      Next.js: app/ route groups (buyer, merchant, analyst), components/<Area>/<Name>/{Name.tsx,Name.module.css},
              hooks/, api/, lib/, constants/, context/, styles/, types/
bench/        AgentDispute-150 generator, runner, results
infra/        Redis config
```

## Security notes

Culpa never sees card data (PayPal hosts payment entry), so it is outside PCI scope. Secrets live only in environment variables. The API sets `nosniff`, `X-Frame-Options: DENY`, `no-store`, and HSTS in production; the web app sets a strict CSP. The dispute console uses a database-backed login: the password is stored as a salted scrypt hash, sessions are random tokens stored only as SHA-256 hashes and expire after 12 hours, and logins are rate-limited. An analyst account is required in production.

## License

MIT, see [LICENSE](LICENSE).
