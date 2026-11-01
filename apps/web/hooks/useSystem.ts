"use client";

import { systemApi } from "@/api/system";
import type { BenchResults, DeadLetter, JobStats, SystemStatus } from "@/types";
import { useApi } from "./useApi";

export function useSystemStatus() {
  return useApi<SystemStatus>(systemApi.statusPath, { refreshInterval: 15000 });
}

export function useBench() {
  return useApi<BenchResults>(systemApi.benchPath, { shouldRetryOnError: false });
}

export function useJobStats() {
  return useApi<JobStats>(systemApi.jobStatsPath, { refreshInterval: 5000 });
}

export function useDeadLetters() {
  return useApi<DeadLetter[]>(systemApi.deadPath, { refreshInterval: 5000 });
}
