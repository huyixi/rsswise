import type { ComponentPropsWithoutRef } from "react"
import ReactMarkdown from "react-markdown"
import rehypeSanitize from "rehype-sanitize"
import remarkGfm from "remark-gfm"

import { cn } from "@/lib/utils"

type MarkdownContentVariant = "article" | "compact"

type MarkdownContentProps = {
  markdown: string
  variant?: MarkdownContentVariant
  stripLeadingHeading?: boolean
}

function stripLeadingHeading(markdown: string) {
  return markdown.replace(/^#{1,2}\s+[^\n]+(?:\n\n?)?/, "")
}

const variantClasses: Record<MarkdownContentVariant, string> = {
  article:
    "text-[16.5px] leading-8 text-foreground [overflow-wrap:anywhere] md:text-[17px]",
  compact:
    "text-sm leading-6 text-foreground [overflow-wrap:anywhere]",
}

const headingClasses: Record<MarkdownContentVariant, string> = {
  article:
    "mt-8 scroll-mt-20 text-xl font-semibold leading-snug text-foreground first:mt-0",
  compact:
    "mt-4 scroll-mt-20 text-xs font-semibold uppercase tracking-normal text-muted-foreground first:mt-0",
}

const paragraphClasses: Record<MarkdownContentVariant, string> = {
  article: "my-4 leading-8",
  compact: "my-2 leading-6",
}

const listClasses: Record<MarkdownContentVariant, string> = {
  article: "my-4 space-y-2 pl-6",
  compact: "my-2 space-y-1 pl-5",
}

const listItemClasses: Record<MarkdownContentVariant, string> = {
  article: "pl-1 leading-8",
  compact: "pl-1 leading-6",
}

function createMarkdownComponents(variant: MarkdownContentVariant) {
  return {
    h1({ className, ...props }: ComponentPropsWithoutRef<"h1">) {
      return <h2 className={cn(headingClasses[variant], className)} {...props} />
    },
    h2({ className, ...props }: ComponentPropsWithoutRef<"h2">) {
      return <h2 className={cn(headingClasses[variant], className)} {...props} />
    },
    h3({ className, ...props }: ComponentPropsWithoutRef<"h3">) {
      return (
        <h3
          className={cn(
            variant === "article"
              ? "mt-6 scroll-mt-20 text-lg font-semibold leading-snug text-foreground first:mt-0"
              : "mt-3 scroll-mt-20 text-xs font-medium text-muted-foreground first:mt-0",
            className,
          )}
          {...props}
        />
      )
    },
    p({ className, ...props }: ComponentPropsWithoutRef<"p">) {
      return <p className={cn(paragraphClasses[variant], className)} {...props} />
    },
    ul({ className, ...props }: ComponentPropsWithoutRef<"ul">) {
      return (
        <ul
          className={cn("list-disc", listClasses[variant], className)}
          {...props}
        />
      )
    },
    ol({ className, ...props }: ComponentPropsWithoutRef<"ol">) {
      return (
        <ol
          className={cn("list-decimal", listClasses[variant], className)}
          {...props}
        />
      )
    },
    li({ className, ...props }: ComponentPropsWithoutRef<"li">) {
      return <li className={cn(listItemClasses[variant], className)} {...props} />
    },
    blockquote({ className, ...props }: ComponentPropsWithoutRef<"blockquote">) {
      return (
        <blockquote
          className={cn(
            "my-4 border-l-2 border-muted-foreground/30 pl-4 italic text-muted-foreground",
            variant === "compact" && "my-3 pl-3",
            className,
          )}
          {...props}
        />
      )
    },
    a({ className, ...props }: ComponentPropsWithoutRef<"a">) {
      return (
        <a
          className={cn(
            "break-words text-foreground underline underline-offset-4",
            className,
          )}
          target="_blank"
          rel="noreferrer"
          {...props}
        />
      )
    },
    pre({ className, ...props }: ComponentPropsWithoutRef<"pre">) {
      return (
        <pre
          className={cn(
            "my-4 max-w-full overflow-x-auto rounded-md border border-border bg-muted p-3 text-sm leading-6 text-foreground",
            variant === "compact" && "my-3 p-2 text-xs leading-5",
            className,
          )}
          {...props}
        />
      )
    },
    code({ className, ...props }: ComponentPropsWithoutRef<"code">) {
      return (
        <code
          className={cn(
            "rounded bg-muted px-1 py-0.5 font-mono text-[0.9em]",
            className,
          )}
          {...props}
        />
      )
    },
    table({ className, ...props }: ComponentPropsWithoutRef<"table">) {
      return (
        <div className="my-4 max-w-full overflow-x-auto">
          <table
            className={cn(
              "w-full min-w-max border-collapse text-left text-sm",
              variant === "compact" && "text-xs",
              className,
            )}
            {...props}
          />
        </div>
      )
    },
    th({ className, ...props }: ComponentPropsWithoutRef<"th">) {
      return (
        <th
          className={cn("border-b border-border px-3 py-2 font-medium", className)}
          {...props}
        />
      )
    },
    td({ className, ...props }: ComponentPropsWithoutRef<"td">) {
      return (
        <td
          className={cn("border-b border-border px-3 py-2 align-top", className)}
          {...props}
        />
      )
    },
    img({ className, ...props }: ComponentPropsWithoutRef<"img">) {
      return (
        <img
          className={cn("my-4 h-auto max-w-full rounded-lg", className)}
          loading="lazy"
          {...props}
        />
      )
    },
  }
}

export function MarkdownContent({
  markdown,
  variant = "article",
  stripLeadingHeading: shouldStripLeadingHeading = false,
}: MarkdownContentProps) {
  const renderedMarkdown = shouldStripLeadingHeading
    ? stripLeadingHeading(markdown)
    : markdown

  return (
    <article className={cn("max-w-none", variantClasses[variant])}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
        components={createMarkdownComponents(variant)}
      >
        {renderedMarkdown}
      </ReactMarkdown>
    </article>
  )
}
