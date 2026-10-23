import Link from "next/link";
import { Suspense } from "react";
import { currentOrg, serverApi, guard } from "@/lib/api/server";
import { CreateOrg } from "./CreateOrg";
import { NavLinks } from "./NavLinks";
import { OrgSwitcher } from "./OrgSwitcher";
import { OrgProvider } from "./Providers";
import { ScopeTree } from "./ScopeTree";

/** App chrome: brand, org switcher, sections, and the scope/file tree. */
export async function Shell({ children }: { children: React.ReactNode }) {
  const { org, organizations } = await currentOrg();
  if (!org) {
    return (
      <main className="auth">
        <h1>Name your organization</h1>
        <p className="muted">Wikis live inside an organization. Create one, or ask a teammate to invite you to theirs.</p>
        <CreateOrg />
      </main>
    );
  }
  const api = await serverApi();
  const { scopes } = await guard(api.tree());
  return (
    <OrgProvider org={org._id}>
      <div className="shell">
        <aside className="rail">
          <Link href="/wiki" className="brand">
            self<b>memory</b>
          </Link>
          <OrgSwitcher current={org._id} organizations={organizations.map((o) => ({ id: o._id, name: o.name }))} />
          <NavLinks />
          <div>
            <h2>Wikis</h2>
            <Suspense fallback={null}>
              <ScopeTree scopes={scopes} />
            </Suspense>
          </div>
        </aside>
        <main className="main">{children}</main>
      </div>
    </OrgProvider>
  );
}
