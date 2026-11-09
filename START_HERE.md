Culpa: read this first

This file has everything you need to run Culpa and log in to every part of the demo. The full product description is in README.md.


Demo logins

Dispute console (analyst)
    Username: analyst
    Password: QsHjrvQpsB5qxNXY
Open the dispute console at /login, or click Analyst login in the top bar. Sessions last 12 hours.

PayPal sandbox buyer (for approving carts)
    Email:    sb-3khub53626478@personal.example.com
    Password: ^x.3L25$
When the buyer agent sends you to PayPal, log in with this account to approve the cart. This is a PayPal sandbox test account: it only holds play money and cannot make real payments.

The buyer agent and the merchant pages need no login.


Before you start

You need Python 3.11 or newer, Node 20 or newer and pnpm (npm install -g pnpm). The commands below are for Windows PowerShell, run from the repository root.


First-time setup

    powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

This creates the Python environment, installs everything, copies appspi\.env.example to appspi\.env and builds the benchmark data. Then open appspi\.env and fill in the empty values: the PayPal sandbox client ID and secret, the Gemini API key, a mandate signing secret, and the analyst username and password above. Every key is optional for a first look: without PayPal keys orders run in simulated mode, and without a Gemini key Culpa uses its rule-based checks.


Run the project

    powershell -ExecutionPolicy Bypass -File scripts\dev.ps1

This opens two windows, one for the API and one for the web app. Then open:

    Web app            http://127.0.0.1:3000
    API documentation  http://127.0.0.1:8000/docs

Running dev.ps1 again restarts both servers.


Run with Docker instead

    copy appspi\.env.example appspi\.env
    docker compose up -d --build

This starts Postgres, Redis, the API, a background worker and the web app on the same addresses.


Run the tests

    powershell -ExecutionPolicy Bypass -File scripts	est.ps1

This runs the backend tests (including the 126 dispute scenarios), the benchmark, the web type check and a production build.


A two-minute demo

1. Buyer agent: click the Ambiguous size example, then Sign mandate and shop. The agent picks UK 9 for "size 9".
2. Click Approve with PayPal and log in with the PayPal sandbox buyer above.
3. Merchant: click Ship on the new order.
4. Dispute console, log in as the analyst, open Orders, click Open dispute, choose "It's not as described", pick Size and enter US 9.
5. The case opens as an ambiguous instruction: buyer 60 percent, agent provider 40 percent, partial refund recommended. Choose an option and confirm it.


If something looks wrong

If a page behaves like an older version after code changes, press Ctrl + Shift + R, or run dev.ps1 again. If the login fails, check that the username and password match ANALYST_USERNAME and ANALYST_PASSWORD in appspi\.env; saving that file updates the account.
