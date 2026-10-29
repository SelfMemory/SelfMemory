"use client";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { fileUrl } from "@/lib/api/browser";
import { pageHref, resolveLink } from "@/lib/paths";
import { useOrg } from "./Providers";

/** Split YAML-ish front matter (key: value lines) from the body. */
export function splitFrontmatter(src: string): { meta: [string, string][]; body: string } {
  const m = /^---\n([\s\S]*?)\n---\n?/.exec(src);
  if (!m) return { meta: [], body: src };
  const meta = m[1]
    .split("\n")
    .map((l) => /^([\w-]+):\s*(.*)$/.exec(l))
    .filter((x): x is RegExpExecArray => !!x && !!x[2])
    .map((x) => [x[1], x[2].replace(/^["']|["']$/g, "")] as [string, string]);
  return { meta, body: src.slice(m[0].length) };
}

/** [[page]] and [[page|label]] become ordinary relative links. */
const wikilinks = (s: string) =>
  s.replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (_, t: string, l?: string) => {
    const target = t.trim().endsWith(".md") ? t.trim() : `${t.trim()}.md`;
    return `[${(l ?? t).trim()}](${encodeURI(target)})`;
  });

/** Renders a wiki page. `path` is the page's org-relative path, for resolving links. */
export function Markdown({ source, path, frontmatter = true }: { source: string; path: string; frontmatter?: boolean }) {
  const org = useOrg();
  const { meta, body } = frontmatter ? splitFrontmatter(source) : { meta: [], body: source };
  return (
    <>
      {meta.length > 0 && (
        <dl className="frontmatter">
          {meta.map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      )}
      <div className="prose">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            a: ({ href = "", children }) => {
              const target = resolveLink(path, href);
              if (target === null) return <a href={href} target="_blank" rel="noreferrer">{children}</a>;
              return <Link href={pageHref(target)}>{children}</Link>;
            },
            img: ({ src, alt }) => {
              const target = typeof src === "string" ? resolveLink(path, src) : null;
              // eslint-disable-next-line @next/next/no-img-element
              return <img src={target ? fileUrl(target, org) : String(src ?? "")} alt={alt ?? ""} />;
            },
          }}
        >
          {wikilinks(body)}
        </ReactMarkdown>
      </div>
    </>
  );
}
