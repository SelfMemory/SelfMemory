import { guard, serverApi } from "@/lib/api/server";
import { UploadForm } from "./UploadForm";

export const metadata = { title: "Add sources" };

export default async function UploadPage({ searchParams }: { searchParams: Promise<{ scope?: string }> }) {
  const { scope } = await searchParams;
  const api = await serverApi();
  const { scopes } = await guard(api.tree());
  const writable = scopes.filter((s) => s.writable).map((s) => ({ key: s.key, label: s.label, kind: s.kind }));
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Add sources</h1>
          <p>
            Drop in documents, notes, PDFs or whole folders. They’re kept as raw sources, and the agent reads them to
            write or update pages.
          </p>
        </div>
      </div>
      {writable.length === 0 ? (
        <div className="empty">You can only read these wikis. Ask a project admin for write access.</div>
      ) : (
        <UploadForm scopes={writable} initialScope={writable.some((s) => s.key === scope) ? scope! : writable[0].key} />
      )}
    </>
  );
}
