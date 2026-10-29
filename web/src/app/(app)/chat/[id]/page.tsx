import Link from "next/link";
import { notFound } from "next/navigation";
import { ScopeTag } from "@/components/ScopeTag";
import { ApiError } from "@/lib/api/client";
import { guard, serverApi } from "@/lib/api/server";
import { ChatView } from "./ChatView";

export const metadata = { title: "Conversation" };

export default async function ChatPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const api = await serverApi();
  const [{ scopes }, data, { job }] = await Promise.all([
    guard(api.tree()),
    guard(api.chat(id)).catch((e) => {
      if (e instanceof ApiError && e.status === 404) notFound();
      throw e;
    }),
    guard(api.activeRun(id)),
  ]);
  const scope = scopes.find((s) => s.key === data.chat.scope);
  return (
    <>
      <div className="crumbs"><Link href="/chat">Conversations</Link></div>
      <div className="page-head">
        <div>
          <h1>{data.chat.title}</h1>
          <p><ScopeTag scope={scope} fallback={data.chat.scope ?? "All scopes you can read"} /></p>
        </div>
      </div>
      <ChatView chatId={id} scope={data.chat.scope} initial={data.messages} activeJob={job?.id ?? null} />
    </>
  );
}
