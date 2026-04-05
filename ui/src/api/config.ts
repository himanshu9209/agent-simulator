import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPut, apiPost } from "./client";
import type { ConfigResponse, ConfigValidateResponse } from "@/types";

export const CONFIG_KEY = ["config"] as const;

export function useConfig() {
  return useQuery({
    queryKey: CONFIG_KEY,
    queryFn: () => apiGet<ConfigResponse>("/api/config"),
  });
}

export function useSaveConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (yaml_str: string) =>
      apiPut<ConfigResponse>("/api/config", { yaml_str }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CONFIG_KEY });
      qc.invalidateQueries({ queryKey: ["profiles"] });
      qc.invalidateQueries({ queryKey: ["pricing"] });
    },
  });
}

export function useValidateConfig() {
  return useMutation({
    mutationFn: (yaml_str: string) =>
      apiPost<ConfigValidateResponse>("/api/config/validate", { yaml_str }),
  });
}
