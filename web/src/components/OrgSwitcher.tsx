"use client";
import { useRouter } from "next/navigation";
import { ORG_COOKIE } from "@/lib/config";

export function OrgSwitcher({ current, organizations }: { current: string; organizations: { id: string; name: string }[] }) {
  const router = useRouter();
  if (organizations.length < 2) return <div style={{ padding: "0 10px", color: "var(--rail-muted)" }}>{organizations[0]?.name}</div>;
  return (
    <select
      className="org-select"
      aria-label="Organization"
      value={current}
      onChange={(e) => {
        document.cookie = `${ORG_COOKIE}=${encodeURIComponent(e.target.value)}; path=/; max-age=31536000; samesite=lax`;
        router.push("/wiki");
        router.refresh();
      }}
    >
      {organizations.map((o) => (
        <option key={o.id} value={o.id}>
          {o.name}
        </option>
      ))}
    </select>
  );
}
