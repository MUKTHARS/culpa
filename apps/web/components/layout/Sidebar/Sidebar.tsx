"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ANALYST_NAV, ROUTES } from "@/constants/routes";
import { useAuth } from "@/context/AuthContext";
import { cx } from "@/lib/utils";
import styles from "./Sidebar.module.css";

export function Sidebar() {
  const path = usePathname() ?? "";
  const { username, loggedIn, logout } = useAuth();
  return (
    <aside className={styles.sidebar}>
      <p className={styles.heading}>Dispute console</p>
      <nav className={styles.nav}>
        {ANALYST_NAV.map((n) => (
          <Link key={n.href} href={n.href} className={cx(styles.link, path.startsWith(n.href) && styles.active)}>
            {n.label}
          </Link>
        ))}
      </nav>
      {loggedIn ? (
        <p className={styles.token}>
          Signed in as {username} ·{" "}
          <button type="button" className={styles.logout} onClick={() => logout()}>
            Log out
          </button>
        </p>
      ) : (
        <Link href={ROUTES.login} className={styles.token}>
          Log in
        </Link>
      )}
    </aside>
  );
}
