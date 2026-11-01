"use client";

import { ConfusionMatrix } from "@/components/benchmark/ConfusionMatrix/ConfusionMatrix";
import { ResultsTable } from "@/components/benchmark/ResultsTable/ResultsTable";
import { Card } from "@/components/ui/Card/Card";
import { EmptyState } from "@/components/ui/EmptyState/EmptyState";
import { Loader } from "@/components/ui/Loader/Loader";
import { useBench } from "@/hooks/useSystem";
import { when } from "@/lib/format";

export default function BenchmarkPage() {
  const { data, error } = useBench();
  const full = data?.systems.find((s) => s.name === "culpa_full_llm") ?? data?.systems.find((s) => s.name === "culpa_full");
  const baseline = data?.systems.find((s) => s.name === "claim_keywords");

  return (
    <>
      <div>
        <h1>AgentDispute-150</h1>
        <p className="muted">
          150 labeled agent-purchase disputes, 25 per fault class, 20% hard. Labels are true by construction.
        </p>
      </div>
      {error ? (
        <EmptyState title="No results yet">
          Run <code>python bench/run.py</code> from the repo root, then reload.
        </EmptyState>
      ) : !data ? (
        <Loader />
      ) : (
        <>
          <Card title="Results" subtitle={`Generated ${when(data.generated_at)} · ${data.n_cases} cases · ${data.n_hard} hard`}>
            <ResultsTable results={data} />
            <p className="muted" style={{ marginTop: 12 }}>
              Wrong-money rate is the share of cases where money would move to the wrong party. Escalated cases move no
              money. The data is synthetic and the engine shares its fault taxonomy, so treat these as in-distribution numbers.
            </p>
          </Card>
          {full && (
            <div className="grid-2">
              <Card title={`Confusion matrix · ${full.name}`}>
                <ConfusionMatrix confusion={full.metrics.confusion} />
              </Card>
              {baseline && (
                <Card title="Confusion matrix · claim-only baseline">
                  <ConfusionMatrix confusion={baseline.metrics.confusion} />
                </Card>
              )}
            </div>
          )}
        </>
      )}
    </>
  );
}
