import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPut } from "./client";
import type { ModelPricing, PricingTableResponse } from "@/types";

export const PRICING_KEY = ["pricing"] as const;

export function usePricing() {
  return useQuery({
    queryKey: PRICING_KEY,
    queryFn: () => apiGet<PricingTableResponse>("/api/pricing"),
  });
}

export function useUpdatePricing() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (pricing: Record<string, ModelPricing>) =>
      apiPut<PricingTableResponse>("/api/pricing", { pricing }),
    onSuccess: () => qc.invalidateQueries({ queryKey: PRICING_KEY }),
  });
}
