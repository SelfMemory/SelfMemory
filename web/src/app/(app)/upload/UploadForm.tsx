"use client";
import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useRef, useState } from "react";
import { useApi } from "@/components/Providers";
import { RunLog } from "@/components/RunLog";
import { useRunStream } from "@/lib/useRunStream";

type Picked = { file: File; path: string };

export function UploadForm({ scopes, initialScope }: { scopes: { key: string; label: string }[]; initialScope: string }) {
  const api = useApi();
  const [scope, setScope] = useState(initialScope);
  const [files, setFiles] = useState<Picked[]>([]);
  const [note, setNote] = useState("");
  const [ingest, setIngest] = useState(true);
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const upload = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.set("scope", scope);
      form.set("ingest", String(ingest));
      if (note.trim()) form.set("note", note.trim());
      for (const f of files) {
        form.append("files", f.file, f.file.name);
        form.append("paths", f.path);
      }
      return api.upload(form);
    },
    onSuccess: () => setFiles([]),
  });
  const stream = useRunStream(upload.data?.job_id ?? null);

  const add = (list: FileList | null) => {
    if (!list) return;
    setFiles((prev) => [
      ...prev,
      ...Array.from(list).map((file) => ({ file, path: (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name })),
    ]);
  };

  return (
    <div className="split">
      <form className="stack" onSubmit={(e) => { e.preventDefault(); upload.mutate(); }}>
        <div
          className={`drop${over ? " over" : ""}`}
          role="button"
          tabIndex={0}
          onClick={() => input.current?.click()}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setOver(true); }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); add(e.dataTransfer.files); }}
        >
          <strong>Drop files here</strong> or click to choose
          <div className="muted" style={{ fontSize: 13 }}>Office files and PDFs are converted to Markdown on the way in.</div>
          <input ref={input} type="file" multiple hidden onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
        </div>
        {files.length > 0 && (
          <ul className="list">
            {files.map((f, i) => (
              <li key={i}>
                <span className="grow">{f.path}</span>
                <span className="muted">{Math.ceil(f.file.size / 1024)} KB</span>
                <button type="button" className="btn ghost" onClick={() => setFiles(files.filter((_, j) => j !== i))}>Remove</button>
              </li>
            ))}
          </ul>
        )}
        <div className="row">
          <label className="field">
            Into
            <select className="select" value={scope} onChange={(e) => setScope(e.target.value)}>
              {scopes.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
            </select>
          </label>
          <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 8, fontWeight: 400 }}>
            <input type="checkbox" checked={ingest} onChange={(e) => setIngest(e.target.checked)} />
            Have the agent read them now
          </label>
        </div>
        <label className="field">
          Anything to focus on? <span className="hint">Optional, passed to the agent with the files</span>
          <textarea className="textarea" value={note} onChange={(e) => setNote(e.target.value)} disabled={!ingest} />
        </label>
        {upload.error && <p className="error">{upload.error.message}</p>}
        <div>
          <button className="btn" disabled={!files.length || upload.isPending}>
            {upload.isPending ? "Uploading…" : `Upload ${files.length || ""} file${files.length === 1 ? "" : "s"}`}
          </button>
        </div>
      </form>

      <aside className="aside">
        {upload.data ? (
          <div className="stack">
            <h3>Uploaded {upload.data.written.length} file{upload.data.written.length === 1 ? "" : "s"}</h3>
            {upload.data.skipped.length > 0 && (
              <ul className="history">
                {upload.data.skipped.map((s) => <li key={s.name} className="error">{s.name}: {s.why}</li>)}
              </ul>
            )}
            {upload.data.job_id ? (
              <>
                <Link href={`/runs/${upload.data.job_id}`}>Open the ingest run</Link>
                <RunLog events={stream.events} live={!stream.done} />
              </>
            ) : (
              <p className="muted">Saved as sources. Nothing was ingested.</p>
            )}
          </div>
        ) : (
          <p className="muted">The ingest log appears here once the upload finishes.</p>
        )}
      </aside>
    </div>
  );
}
