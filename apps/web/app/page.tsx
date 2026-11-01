import Link from "next/link";
import { ROUTES } from "@/constants/routes";
import styles from "./page.module.css";

const STEPS = [
  { n: "1", title: "Buyer signs a mandate", body: "Budget, category and required attributes are hashed and HMAC-signed." },
  { n: "2", title: "Agent buys on PayPal", body: "The agent picks a product and creates the order through the PayPal Agent Toolkit." },
  { n: "3", title: "Evidence is fingerprinted", body: "Mandate, agent trace and listing snapshot roll into one Merkle root at capture." },
  { n: "4", title: "Dispute arrives", body: "PayPal's webhook is verified, deduplicated and queued in under a second." },
  { n: "5", title: "Culpa assigns fault", body: "Rule checks, listing diff, agent replay and a claim check produce a fault split." },
  { n: "6", title: "Code moves the money", body: "Refund, partial refund or contest, with an idempotency key. Low confidence goes to a human." },
];

export default function Home() {
  return (
    <main className="page">
      <section className={styles.hero}>
        <p className={styles.kicker}>Fault attribution for agentic commerce</p>
        <h1 className={styles.title}>When an AI agent buys the wrong thing, who pays?</h1>
        <p className={styles.lead}>
          Card networks have no dispute rules for agent purchases yet. Culpa is the referee: it decides whether the
          buyer, the merchant or the agent provider caused the problem, and settles it on PayPal with cited evidence.
        </p>
        <div className={styles.ctas}>
          <Link className={styles.primary} href={ROUTES.agent}>
            Try the buyer agent
          </Link>
          <Link className={styles.secondary} href={ROUTES.cases}>
            Open the dispute console
          </Link>
        </div>
      </section>

      <section className={styles.steps}>
        {STEPS.map((s) => (
          <div key={s.n} className={styles.step}>
            <span className={styles.num}>{s.n}</span>
            <h3>{s.title}</h3>
            <p className="muted">{s.body}</p>
          </div>
        ))}
      </section>

      <section className={styles.roles}>
        <Link href={ROUTES.agent} className={styles.role}>
          <h2>Buyer agent</h2>
          <p className="muted">Give an instruction, set a cap, approve the cart on PayPal.</p>
        </Link>
        <Link href={ROUTES.merchant} className={styles.role}>
          <h2>Merchant</h2>
          <p className="muted">Edit listings and ship orders. Editing after purchase is the merchant-fault demo.</p>
        </Link>
        <Link href={ROUTES.benchmark} className={styles.role}>
          <h2>Benchmark</h2>
          <p className="muted">AgentDispute-150: Culpa against a claim-reading baseline.</p>
        </Link>
      </section>
    </main>
  );
}
