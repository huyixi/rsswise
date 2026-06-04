import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";

function stripLeadingHeading(markdown: string) {
  return markdown.replace(/^#{1,2}\s+[^\n]+(?:\n\n?)?/, "")
}

export function MarkdownContent({ markdown }: { markdown: string }) {
  return (
    <article className="prose prose-neutral max-w-none prose-headings:scroll-mt-20 prose-headings:font-semibold prose-a:text-foreground prose-a:underline prose-a:underline-offset-4 prose-code:rounded prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:text-sm prose-pre:border prose-pre:border-border prose-pre:bg-muted prose-pre:text-foreground prose-img:rounded-lg">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
        {stripLeadingHeading(markdown)}
      </ReactMarkdown>
    </article>
  );
}
