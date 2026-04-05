import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost } from "./client";
import type { RunStartRequest, RunStatusResponse } from "@/types";

export const RUN_STATUS_KEY = ["run", "status"] as const;

export function useRunStatus() {
  return useQuery({
    queryKey: RUN_STATUS_KEY,
    queryFn: () => apiGet<RunStatusResponse>("/api/run/status"),
    refetchInterval: 3000,
  });
}

export function useStartRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: RunStartRequest) => apiPost("/api/run/start", req),
    onSuccess: () => qc.invalidateQueries({ queryKey: RUN_STATUS_KEY }),
  });
}

export function useStopRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost("/api/run/stop"),
    onSuccess: () => qc.invalidateQueries({ queryKey: RUN_STATUS_KEY }),
  });
}

/**
 * Returns a function that opens a WebSocket to /api/run/stream and
 * calls `onMessage` for every JSON frame. Caller is responsible for
 * closing the returned WebSocket when done.
 */
export function openRunStream(
  onMessage: (status: RunStatusResponse) => void,
  onError?: (e: Event) => void,
): WebSocket {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const host = window.location.host; // same host as Vite dev server
  const ws = new WebSocket(`${proto}://${host}/api/run/stream`);

  ws.onmessage = (e) => {
    try {
      onMessage(JSON.parse(e.data) as RunStatusResponse);
    } catch {
      // ignore malformed frames
    }
  };

  if (onError) ws.onerror = onError;
  return ws;
}
