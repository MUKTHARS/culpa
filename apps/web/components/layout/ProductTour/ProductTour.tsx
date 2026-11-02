"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ROUTES } from "@/constants/routes";
import styles from "./ProductTour.module.css";

const STEPS: { title: string; where: string; href: string; body: string }[] = [
  { title: "Welcome to Culpa", where: "Home", href: ROUTES.home,
    body: "Culpa decides who is at fault when an AI shopping agent buys the wrong thing, and settles the dispute on PayPal. This tour walks through one purchase from start to finish." },
  { title: "1. Write the mandate", where: "Buyer agent", href: ROUTES.agent,
    body: "Describe what to buy, set a spending cap and pick the details that must match. Try the Ambiguous size example. Signing turns your instructions into a mandate that cannot be changed later." },
  { title: "2. The agent searches and picks", where: "Buyer agent", href: ROUTES.agent,
    body: "The agent searches the store within your limits and picks the best match. The search results show every match with filters. Keep the agent's pick or select another product." },
  { title: "3. Approve on PayPal", where: "Buyer agent", href: ROUTES.agent,
    body: "Click Approve with PayPal and log in with the sandbox buyer from START_HERE.md. At capture, Culpa fingerprints the mandate, the agent's decision and the listing as evidence." },
  { title: "4. Ship the order", where: "Merchant", href: ROUTES.merchant,
    body: "As the merchant, click Ship. To try a merchant-fault case, edit the listing first: shipping sends whatever the listing says at that moment." },
  { title: "5. Open a dispute", where: "Dispute console, Orders", href: ROUTES.orders,
    body: "Log in as the analyst, open Orders and click Open dispute. Choose what went wrong, for example the size was not as described, and Culpa files it like a PayPal dispute." },
  { title: "6. Read the verdict", where: "Dispute console, Cases", href: ROUTES.cases,
    body: "Culpa checks the mandate, the listing history, a replay of the agent and the buyer's claim. The case shows who is at fault, the reason and the real-world rule it follows." },
  { title: "7. Settle the dispute", where: "Dispute console, case page", href: ROUTES.cases,
    body: "Choose a full refund, a partial refund or contest the claim, then confirm. Money moves only through PayPal with a one-time request ID, and every step is recorded in the audit log." },
  { title: "8. Check the evidence", where: "Benchmark and Jobs", href: ROUTES.benchmark,
    body: "The Benchmark page shows Culpa against a claim-only baseline on 150 disputes. The Jobs page shows background work, retries and the audit chain. That completes the tour." },
];

export function ProductTour() {
  const [open, setOpen] = useState(false);
  const [i, setI] = useState(0);
  const step = STEPS[i];
  const last = i === STEPS.length - 1;

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
      if (e.key === "ArrowRight") setI((n) => Math.min(n + 1, STEPS.length - 1));
      if (e.key === "ArrowLeft") setI((n) => Math.max(n - 1, 0));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <button type="button" className={styles.launch} onClick={() => { setI(0); setOpen(true); }}>
        Product tour
      </button>
      {open && (
        <div className={styles.backdrop} onClick={() => setOpen(false)}>
          <section className={styles.card} role="dialog" aria-modal="true" aria-labelledby="tour-title"
                   onClick={(e) => e.stopPropagation()}>
            <header className={styles.head}>
              <span className={styles.where}>{step.where}</span>
              <span className={styles.count}>Step {i + 1} of {STEPS.length}</span>
            </header>
            <h2 id="tour-title" className={styles.title}>{step.title}</h2>
            <p className={styles.body}>{step.body}</p>
            <div className={styles.progress} aria-hidden>
              {STEPS.map((s, n) => (
                <span key={s.title} className={n <= i ? `${styles.dot} ${styles.dotOn}` : styles.dot} />
              ))}
            </div>
            <footer className={styles.actions}>
              <Link href={step.href} className={styles.go}>Go to this page</Link>
              <div className={styles.nav}>
                <button type="button" className={styles.secondary} onClick={() => setI(i - 1)} disabled={i === 0}>
                  Back
                </button>
                <button type="button" className={styles.primary} onClick={() => (last ? setOpen(false) : setI(i + 1))}>
                  {last ? "Finish" : "Next"}
                </button>
              </div>
            </footer>
            <button type="button" className={styles.close} onClick={() => setOpen(false)} aria-label="Close the tour">
              ×
            </button>
          </section>
        </div>
      )}
    </>
  );
}
