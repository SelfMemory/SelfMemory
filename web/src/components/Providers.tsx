"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createContext, useContext, useMemo, useState } from "react";
import { browserApi } from "@/lib/api/browser";

const OrgContext = createContext<string | undefined>(undefined);

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { staleTime: 10_000, retry: 1 } } }),
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

/** Set by the app shell once the server knows which org is selected. */
export function OrgProvider({ org, children }: { org?: string; children: React.ReactNode }) {
  return <OrgContext.Provider value={org}>{children}</OrgContext.Provider>;
}

export function useOrg() {
  return useContext(OrgContext);
}

export function useApi() {
  const org = useOrg();
  return useMemo(() => browserApi(org), [org]);
}
