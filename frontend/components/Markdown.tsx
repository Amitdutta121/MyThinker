import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Renders assistant message text as Markdown. LLM replies routinely contain
 * lists, emphasis, inline code, fenced code, tables, and links; before this the
 * transcript showed all of that as raw `whitespace-pre-wrap` text.
 *
 * No `rehype-raw` / HTML pass-through on purpose — model output is untrusted, so
 * embedded HTML stays inert. Styling lives in the `.md-prose` block in
 * `globals.css` rather than a per-element `components` map.
 */
export default function Markdown({ children }: { children: string }) {
  return (
    <div className="md-prose">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
