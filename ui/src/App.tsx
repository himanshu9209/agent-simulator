import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Layout from "@/components/Layout/Layout";
import DashboardPage from "@/pages/DashboardPage";
import ProfilesPage from "@/pages/ProfilesPage";
import ProfileEditorPage from "@/pages/ProfileEditorPage";
import ConfigPage from "@/pages/ConfigPage";
import RunPage from "@/pages/RunPage";
import PricingPage from "@/pages/PricingPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5_000,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<DashboardPage />} />
            <Route path="profiles" element={<ProfilesPage />} />
            <Route path="profiles/:name" element={<ProfileEditorPage />} />
            <Route path="config" element={<ConfigPage />} />
            <Route path="run" element={<RunPage />} />
            <Route path="pricing" element={<PricingPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
