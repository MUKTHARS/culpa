Culpa

The referee for agentic commerce. When an AI shopping agent buys the wrong thing, Culpa works out who is at fault, the buyer, the merchant or the company behind the agent, and settles the dispute on PayPal with the evidence to back it up.

Built for the PayPal AI Hackathon 2026. MIT licensed.


The problem

AI agents now shop for people. You tell an agent "running shoes, size 9, under 120 dollars", it searches, picks one and pays. When the wrong pair arrives, today's dispute system has no way to tell what went wrong. Was the instruction unclear? Did the agent ignore it? Did the merchant ship something different from the listing? Or is the buyer simply blaming the agent to get a refund?

Card networks still route agent purchases through ordinary reason codes such as "item not as described". Visa's April 2026 rules add no separate agent dispute category, the EMVCo draft from September 2026 leaves liability for non-fraud disputes open, and the CFPB's January 2026 advisory says buyers keep their dispute rights when an agent buys for them. In the meantime PayPal and merchants absorb the losses. Most agent safety tools stop a bad payment before it happens. Nothing decides fault after the money has moved, which is exactly where the dispute lands.


What Culpa does

Culpa follows a purchase from the moment the buyer gives the agent its instructions to the moment the dispute is settled.

First, the buyer writes a mandate: what to buy, a spending cap, a category and any attributes that must match, such as a size or a colour. The form detects the category from the request and offers only the filters that exist for it, so earphones never ask for a shoe size. The mandate is signed so it cannot be changed later.

Second, the agent searches the store. Products outside the category, over the cap or clearly not matching a required attribute are left out. The agent ranks what is left by how closely each product matches the request and picks one. The buyer sees the full ranked list with filters and sorting, can keep the agent's pick or choose another, and then approves the cart on PayPal. The order is created through the PayPal Agent Toolkit.

Third, at capture Culpa fingerprints the evidence. The mandate, the agent's decision record and the listing exactly as it looked at purchase are each hashed, and the hashes are combined into one tamper-evident root that is stored with the order and linked to the PayPal order.

Fourth, when a dispute arrives, either from a PayPal webhook, a scheduled check of PayPal's dispute list or the built-in dispute simulator, Culpa runs four checks in order. The rule check compares the order with the hard limits of the mandate. The listing check compares what was delivered with what was listed at purchase and notices listing edits made after the sale. The agent replay re-runs the agent's decision on the same inputs, and again on a clarified instruction, to separate an agent mistake from an ambiguous request. The claim check compares the buyer's story with what they approved and what was delivered, and adds supporting signals such as dispute history, linked accounts and a review by Google Gemini.

Fifth, Culpa produces a verdict. Fault follows the cause, not a vote. If nothing was delivered, or the item differs from the listing, the merchant is at fault. If the agent broke the mandate or chose the wrong item, the agent provider is at fault. If the instruction was genuinely ambiguous, the buyer and the agent provider share it, which is the only shared verdict. If the claim contradicts the record, the buyer is at fault. Supporting signals only raise or lower confidence, never the share of blame. Every verdict comes with a plain reason, for example "INR-01 The item was not delivered", and the real-world rule it follows, such as PayPal's Item Not Received rule or Visa reason code 13.1.

Some claims cannot be proven from records at all. An item that arrived broken, a counterfeit, a duplicate charge or a refund that never arrived is sent to a person with a note about what evidence is needed, instead of a guessed percentage.

Sixth, an analyst settles the case in the dispute console. Culpa recommends an action and shows who bears the cost. The analyst can choose a full refund, a partial refund of an amount they set, or contest the claim, and can add a note for the audit log. Each option says exactly what will happen on PayPal: accept the claim, send a refund offer, refund the payment, or submit Culpa's evidence. After settling, the panel shows the outcome in plain words, for example "Dispute contested. No money moved."


Why it can be trusted with money

The AI model never moves money. Gemini only receives the buyer's text as quoted data, must answer in a fixed JSON format, has no tools, and its output only adjusts confidence. A settlement policy written in code decides what happens to money, and anything below 80 percent confidence waits for a person.

Every PayPal request carries an idempotency key that is the same on every retry, so a refund can never happen twice. Settlements move through a strict state machine. Webhooks are signature-checked and deduplicated. Every verdict, approval and PayPal action is written to an append-only audit log in which each entry contains the hash of the one before it, so editing history breaks the chain.

Culpa never sees card data, because PayPal hosts payment entry, which keeps the project out of PCI scope.


Results

AgentDispute-150 is a set of 150 synthetic disputes, 25 for each fault type, with a fifth of them deliberately hard: misleading claim text, formatting noise, repeat disputers, missing delivery records and agents that cannot be reproduced. Labels are true by construction.

A baseline that reads only the buyer's claim gets 73.3 percent right and would move money to the wrong party in 26.7 percent of cases. Culpa without the agent replay never moves money to the wrong party but has to send 34.7 percent of cases to a person. Full Culpa gets 98.7 percent right, moves money to the wrong party in 0 percent of cases, and sends 2.7 percent to a person. The data is synthetic and the engine shares its fault taxonomy, so these are in-distribution numbers, not real-world accuracy.

A second set of 126 scenarios is built from real dispute rules: PayPal Buyer Protection for items not received, items not as described and unauthorized payments, its exclusions such as buyer's remorse, and Visa and Mastercard reason codes for defective goods, counterfeits, duplicate charges, incorrect amounts, refunds not processed and cancelled subscriptions, plus agent mandate breaches. Each scenario states the outcome its rule expects. All 126 pass. The full table is in bench/scenarios.md.


How it is built

The backend is Python 3.11 with FastAPI and SQLAlchemy. It uses SQLite for local work and Postgres in Docker and on Render, Redis for caching and as a job queue when available, and a transactional outbox so a business change and its background job are saved together. Without Redis, jobs run inside the API process. Workers retry with backoff, failed jobs go to a dead-letter list that can be replayed from the Jobs page, and a reconciler picks up disputes whose webhook was missed.

The fault-attribution engine has no database, network or clock access, so the live API and the benchmark run exactly the same code. The AI layer uses Google Gemini through Google's official SDK, gemini-3.5-flash-lite for the agent and the clarifier and gemini-3.5-flash for the claim review, with answers cached by their inputs and a fixed temperature for repeatable results. If Gemini is unavailable, Culpa falls back to its rule-based checks and says so on the case.

The web app is Next.js with one folder per component, data fetching kept in hooks, and an AG Grid case queue. It has three areas: the buyer agent, the merchant store, and the dispute console with cases, orders, the benchmark and a jobs page.

The repository is laid out as apps/api for the backend, apps/web for the web app, bench for the benchmark and scenarios, infra for the Redis configuration and scripts for setup, development and tests.


Running it locally on Windows

You need Python 3.11 or newer, Node 20 or newer and pnpm. From the repository root, run the one-time setup, which creates the Python environment, installs everything and builds the benchmark data:

    powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

Then open apps\api\.env, which setup copies from apps\api\.env.example, and fill in the empty values described below. Start the API and the web app, each in its own window:

    powershell -ExecutionPolicy Bypass -File scripts\dev.ps1

The web app is at http://127.0.0.1:3000 and the API at http://127.0.0.1:8000, with interactive API documentation at http://127.0.0.1:8000/docs.

On macOS or Linux, create a virtual environment in apps/api, install requirements.txt and start the API with uvicorn main:app, then run pnpm install and pnpm dev in apps/web.

To run the whole stack in Docker, with Postgres, Redis, the API, a worker and the web app, copy apps/api/.env.example to apps/api/.env first and then run:

    docker compose up -d --build


Keys and settings

All settings live in apps/api/.env. The PayPal client ID and secret come from developer.paypal.com under Apps and Credentials, sandbox. The PayPal webhook ID is only needed to verify real webhooks; locally Culpa polls PayPal for new disputes instead. The Gemini API key comes from aistudio.google.com under Get API key. The mandate signing secret is any long random string. The analyst username and password create the login for the dispute console; left empty in development, the console stays open without a login, and in production a login is required.

Every key is optional for a first look. Without PayPal keys, orders and settlements run in simulated mode, clearly labelled in the interface. Without a Gemini key, Culpa uses its rule-based checks only.


Trying the main demo

Open the buyer agent and choose the Ambiguous size example. The agent picks UK 9 for "size 9". Approve the cart. As the merchant, ship the order. In the dispute console, open Orders, choose Open dispute on that order, select "It's not as described", pick Size and enter US 9 as what you expected. The case opens as an ambiguous instruction: buyer 60 percent, agent provider 40 percent, with a partial refund recommended. Approve it, and the settlement runs with its idempotency key while the audit log records every step.

For a merchant-fault case, buy something, change the listing's material on the merchant page before shipping, then ship and dispute it as not as described. For a friendly-fraud case, buy and ship normally, then open a dispute saying your agent bought the wrong thing.


Testing

One command runs the 213 backend tests, including all 126 dispute scenarios, the benchmark, the web type check and a production build:

    powershell -ExecutionPolicy Bypass -File scripts\test.ps1

The benchmark and the scenarios can also be run on their own with python bench/run.py and python bench/scenarios.py.


License

MIT. See the LICENSE file.
