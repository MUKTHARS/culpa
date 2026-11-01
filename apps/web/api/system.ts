import type { BenchResults, DeadLetter, JobStats, SystemStatus } from "@/types";
import { api } from "./client";

export const systemApi = {
  statusPath: "/system/status",
  benchPath: "/bench/results",
  jobStatsPath: "/jobs/stats",
  deadPath: "/jobs/dead",
  status: () => api.get<SystemStatus>("/system/status"),
  bench: () => api.get<BenchResults>("/bench/results"),
  jobStats: () => api.get<JobStats>("/jobs/stats"),
  dead: () => api.get<DeadLetter[]>("/jobs/dead"),
  replayDead: (id: number) => api.post<{ outbox_id: number }>(`/jobs/dead/${id}/replay`),
};
