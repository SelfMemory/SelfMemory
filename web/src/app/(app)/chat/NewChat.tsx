"use client";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useApi } from "@/components/Providers";

export function NewChat({ scopes, initialScope }: { scopes: { key: string; label: string }[]; initialScope?: string }) {
  const api = useApi();
  const router = useRouter();
  const [scope, setScope] = useState(initialScope ?? "");
  const create = useMutation({
    mutationFn: () => api.createChat(scope || undefined),
    onSuccess: (c) => router.push(`/chat/${c.id}`),
  });
  return (
    <form className="stack" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
      <label className="field">
        Ask about
        <select className="select" value={scope} onChange={(e) => setScope(e.target.value)}>
          <option value="">Everything I can read</option>
          {scopes.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
        </select>
      </label>
      {create.error && <p className="error">{create.error.message}</p>}
      <button className="btn" disabled={create.isPending}>Start conversation</button>
    </form>
  );
}
