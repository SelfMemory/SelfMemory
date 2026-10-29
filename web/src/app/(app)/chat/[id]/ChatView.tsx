"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Markdown } from "@/components/Markdown";
import { useApi } from "@/components/Providers";
import type { ChatMessage } from "@/lib/api/types";
import { useRunStream } from "@/lib/useRunStream";

/**
 * One chat: each question queues a query run tied to the chat; its answer
 * streams in over SSE, then the stored transcript is refetched.
 */
export function ChatView({ chatId, scope, initial, activeJob }: {
  chatId: string; scope: string | null; initial: ChatMessage[]; activeJob: string | null;
}) {
  const api = useApi();
  const qc = useQueryClient();
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [job, setJob] = useState<string | null>(activeJob);
  const key = ["chat", chatId];
  const { data: messages = initial } = useQuery({
    queryKey: key,
    queryFn: () => api.chat(chatId).then((r) => r.messages),
    initialData: initial,
  });
  const stream = useRunStream(job);

  const ask = useMutation({
    mutationFn: (text: string) =>
      api.startRun({ command: "query", message: text, chat_id: chatId, scope: scope ?? undefined, display_text: text.slice(0, 200) }),
    onMutate: (text) => { setPending(text); setDraft(""); },
    onSuccess: (r) => setJob(r.job_id),
    onError: (_e, text) => { setPending(null); setDraft(text); },
  });

  useEffect(() => {
    if (!stream.done || !job) return;
    qc.invalidateQueries({ queryKey: key }).then(() => { setJob(null); setPending(null); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stream.done, job]);

  const busy = ask.isPending || !!job;
  const lastError = stream.events.findLast?.((e) => e.kind === "error");

  return (
    <div className="chat">
      {messages.length === 0 && !pending && <div className="empty">Ask anything the wiki might know.</div>}
      {messages.map((m, i) => (
        <div key={i} className={`msg ${m.role === "user" ? "user" : "assistant"}`}>
          {m.role === "user" ? m.text : <Markdown source={m.text} path="wiki/" frontmatter={false} />}
        </div>
      ))}
      {pending && !messages.some((m) => m.role === "user" && m.text === pending) && <div className="msg user">{pending}</div>}
      {job && (
        <div className="msg assistant">
          {stream.text ? (
            <Markdown source={stream.text} path="wiki/" frontmatter={false} />
          ) : (
            <span className="muted">
              {stream.status === "queued" ? "Waiting for a sandbox…" : `Reading${toolNote(stream.events)}…`}
            </span>
          )}
        </div>
      )}
      {lastError && <p className="error">{String(lastError.message)}</p>}
      {ask.error && <p className="error">{ask.error.message}</p>}
      <form className="composer" onSubmit={(e) => { e.preventDefault(); if (draft.trim()) ask.mutate(draft.trim()); }}>
        <textarea
          className="textarea"
          value={draft}
          placeholder="Ask a question"
          aria-label="Question"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (draft.trim() && !busy) ask.mutate(draft.trim()); }
          }}
        />
        <button className="btn" disabled={busy || !draft.trim()}>{busy ? "Answering…" : "Ask"}</button>
      </form>
    </div>
  );
}

function toolNote(events: { kind: string; [k: string]: unknown }[]) {
  const t = [...events].reverse().find((e) => e.kind === "tool");
  return t?.title ? ` ${String(t.title)}` : "";
}
