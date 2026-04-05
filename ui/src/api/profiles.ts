import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiDelete, apiGet, apiPost, apiPut } from "./client";
import type {
  AgentProfile,
  ProfileDetailResponse,
  ProfileListResponse,
} from "@/types";

export const PROFILES_KEY = ["profiles"] as const;

export function useProfiles() {
  return useQuery({
    queryKey: PROFILES_KEY,
    queryFn: () => apiGet<ProfileListResponse>("/api/profiles"),
  });
}

export function useProfile(name: string) {
  return useQuery({
    queryKey: [...PROFILES_KEY, name],
    queryFn: () => apiGet<ProfileDetailResponse>(`/api/profiles/${name}`),
    enabled: !!name,
  });
}

export function useCreateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { name: string; profile: AgentProfile }) =>
      apiPost<ProfileDetailResponse>("/api/profiles", vars),
    onSuccess: () => qc.invalidateQueries({ queryKey: PROFILES_KEY }),
  });
}

export function useUpdateProfile(name: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (profile: AgentProfile) =>
      apiPut<ProfileDetailResponse>(`/api/profiles/${name}`, { profile }),
    onSuccess: () => qc.invalidateQueries({ queryKey: PROFILES_KEY }),
  });
}

export function useDeleteProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => apiDelete(`/api/profiles/${name}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: PROFILES_KEY }),
  });
}
