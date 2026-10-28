"use client";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useApi } from "./Providers";

export function CreateOrg() {
  const api = useApi();
  const router = useRouter();
  const [name, setName] = useState("");
  const create = useMutation({ mutationFn: () => api.createOrganization(name.trim()), onSuccess: () => router.refresh() });
  return (
    <form onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
      <label className="field">
        Organization name
        <input className="input" value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      {create.error && <p className="error">{create.error.message}</p>}
      <button className="btn" disabled={create.isPending || !name.trim()}>Create organization</button>
    </form>
  );
}
