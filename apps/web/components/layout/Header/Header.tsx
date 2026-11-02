"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Badge } from "@/components/ui/Badge/Badge";
import { ROUTES } from "@/constants/routes";
import { useSystemStatus } from "@/hooks/useSystem";
import { cx } from "@/lib/utils";
import styles from "./Header.module.css";

const NAV = [
  { href: ROUTES.agent, label: "Buyer agent" },
  { href: ROUTES.merchant, label: "Merchant" },
  { href: ROUTES.cases, label: "Dispute console" },
  { href: ROUTES.login, label: "Analyst login" },
];

export function Header() {
  const path = usePathname() ?? "/";
  const { data: status, error } = useSystemStatus();

  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <Link href={ROUTES.home} className={styles.brand}>
          <span className={styles.mark} aria-hidden>
            C
          </span>
          Culpa
        </Link>
        <nav className={styles.nav}>
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} className={cx(styles.link, path.startsWith(n.href) && styles.active)}>
              {n.label}
            </Link>
          ))}
        </nav>
        <div className={styles.status}>
          {error ? (
            <Badge tone="bad">API offline</Badge>
          ) : status ? (
            <>
              {/* <Badge tone={status.paypal.configured ? "good" : "warn"}
                     title={status.paypal.configured ? `PayPal ${status.paypal.env}` : "No PayPal keys: orders are simulated"}>
                PayPal {status.paypal.configured ? status.paypal.env : "simulated"}
              </Badge>
              <Badge tone={status.llm.configured ? "good" : "neutral"}
                     title={status.llm.configured ? status.llm.judge_model : "No Gemini key: rule-based checks only"}>
                AI {status.llm.configured ? "on" : "off"}
              </Badge>
              <Badge tone="neutral" title="Queue transport">
                Queue: {status.queue.mode}
              </Badge> */}
            </>
          ) : null}
        </div>
      </div>
    </header>
  );
}
