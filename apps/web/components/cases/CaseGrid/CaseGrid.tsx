"use client";

import { AllCommunityModule, ModuleRegistry, themeQuartz, type ColDef } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { useRouter } from "next/navigation";
import { useMemo } from "react";
import { ROUTES } from "@/constants/routes";
import { ACTION_LABEL, FAULT_LABEL, humanize, money, pct, when } from "@/lib/format";
import type { CaseRow } from "@/types";
import styles from "./CaseGrid.module.css";

ModuleRegistry.registerModules([AllCommunityModule]);

const theme = themeQuartz.withParams({
  accentColor: "#0070ba",
  headerBackgroundColor: "#e6f2fb",
  headerTextColor: "#001c64",
  fontFamily: "inherit",
  fontSize: 13,
  borderRadius: 6,
});

export function CaseGrid({ rows }: { rows: CaseRow[] }) {
  const router = useRouter();

  const columns = useMemo<ColDef<CaseRow>[]>(
    () => [
      { field: "created_at", headerName: "Opened", valueFormatter: (p) => when(p.value), width: 140, sort: "desc" },
      { field: "status", headerName: "Status", valueFormatter: (p) => humanize(p.value ?? ""), width: 150 },
      {
        field: "fault_class",
        headerName: "Fault",
        valueFormatter: (p) => (p.value ? `${p.value} · ${FAULT_LABEL[p.value] ?? ""}` : "—"),
        flex: 1,
        minWidth: 210,
      },
      { field: "confidence", headerName: "Confidence", valueFormatter: (p) => pct(p.value), width: 120 },
      {
        field: "recommended_action",
        headerName: "Recommended",
        valueFormatter: (p) => (p.value ? ACTION_LABEL[p.value as keyof typeof ACTION_LABEL] : "—"),
        width: 150,
      },
      {
        field: "amount",
        headerName: "Amount",
        valueFormatter: (p) => money(p.value, p.data?.currency),
        width: 110,
        type: "rightAligned",
        comparator: (a, b) => Number(a) - Number(b),
      },
      { field: "source", headerName: "Source", width: 110 },
      { field: "reason", headerName: "Reason", valueFormatter: (p) => humanize((p.value ?? "").toLowerCase()), width: 190 },
    ],
    [],
  );

  return (
    <div className={styles.wrap}>
      <AgGridReact<CaseRow>
        theme={theme}
        rowData={rows}
        columnDefs={columns}
        defaultColDef={{ sortable: true, filter: true, resizable: true }}
        getRowId={(p) => p.data.id}
        onRowClicked={(e) => e.data && router.push(ROUTES.caseDetail(e.data.id))}
        rowClass={styles.row}
        pagination
        paginationPageSize={20}
        paginationPageSizeSelector={[20, 50, 100]}
        domLayout="autoHeight"
      />
    </div>
  );
}
