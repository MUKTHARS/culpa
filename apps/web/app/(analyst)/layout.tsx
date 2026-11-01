import type { ReactNode } from "react";
import { Sidebar } from "@/components/layout/Sidebar/Sidebar";
import styles from "./layout.module.css";

export default function AnalystLayout({ children }: { children: ReactNode }) {
  return (
    <div className={styles.shell}>
      <Sidebar />
      <main className={styles.main}>{children}</main>
    </div>
  );
}
