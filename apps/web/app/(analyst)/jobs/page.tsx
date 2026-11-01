"use client";

import { systemApi } from "@/api/system";
import { Badge } from "@/components/ui/Badge/Badge";
import { Button } from "@/components/ui/Button/Button";
import { Card } from "@/components/ui/Card/Card";
import { EmptyState } from "@/components/ui/EmptyState/EmptyState";
import { Loader } from "@/components/ui/Loader/Loader";
import { useAsyncAction } from "@/hooks/useAsyncAction";
import { useDeadLetters, useJobStats, useSystemStatus } from "@/hooks/useSystem";
import { humanize, when } from "@/lib/format";

export default function JobsPage() {
  const stats = useJobStats();
  const dead = useDeadLetters();
  const status = useSystemStatus();
  const replay = useAsyncAction(async (id: number) => {
    await systemApi.replayDead(id);
    await Promise.all([dead.mutate(), stats.mutate()]);
  });

  return (
    <>
      <div>
        <h1>Jobs and reliability</h1>
        <p className="muted">Transactional outbox, retries with backoff, dead letters, circuit breakers and the audit chain.</p>
      </div>
      <div className="grid-2">
        <Card title="Queue">
          {!stats.data ? (
            <Loader />
          ) : (
            <div className="stack">
              <div className="row">
                {Object.entries(stats.data.outbox).map(([k, n]) => (
                  <Badge key={k} tone={k === "dead" ? "bad" : k === "done" ? "good" : "info"}>
                    {humanize(k)}: {n}
                  </Badge>
                ))}
                {Object.keys(stats.data.outbox).length === 0 && <span className="muted">No jobs yet.</span>}
              </div>
              <p>
                Audit chain:{" "}
                {stats.data.audit_chain_ok ? (
                  <Badge tone="good">intact</Badge>
                ) : (
                  <Badge tone="bad">broken at row {stats.data.audit_chain_broken_at}</Badge>
                )}
              </p>
            </div>
          )}
        </Card>
        <Card title="Dependencies">
          {!status.data ? (
            <Loader />
          ) : (
            <div className="row">
              <Badge tone={status.data.paypal.breaker === "closed" ? "good" : "bad"}>PayPal breaker: {status.data.paypal.breaker}</Badge>
              <Badge tone={status.data.llm.breaker === "closed" ? "good" : "bad"}>Claude breaker: {status.data.llm.breaker}</Badge>
              <Badge tone="neutral">Transport: {status.data.queue.mode}</Badge>
              {status.data.queue.depth != null && <Badge tone="neutral">Stream length: {status.data.queue.depth}</Badge>}
            </div>
          )}
        </Card>
      </div>
      <Card title="Dead letters" subtitle="Jobs that ran out of retries. Nothing is dropped silently.">
        {replay.error && <p className="error">{replay.error}</p>}
        {!dead.data ? (
          <Loader />
        ) : dead.data.length === 0 ? (
          <EmptyState title="No failed jobs" />
        ) : (
          <div className="scroll-x">
            <table className="table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Topic</th>
                  <th>Attempts</th>
                  <th>Error</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {dead.data.map((d) => (
                  <tr key={d.id}>
                    <td>{when(d.created_at)}</td>
                    <td className="mono">{d.topic}</td>
                    <td>{d.attempts}</td>
                    <td>{d.error}</td>
                    <td>
                      {d.replayed_at ? (
                        <Badge tone="neutral">replayed</Badge>
                      ) : (
                        <Button size="sm" variant="secondary" onClick={() => replay.run(d.id)} loading={replay.pending}>
                          Replay
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
