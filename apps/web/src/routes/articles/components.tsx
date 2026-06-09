import { ExternalLinkIcon, SparklesIcon } from "lucide-react"

import { MarkdownContent } from "@/components/markdown-content"
import { RecommendationBadge } from "@/components/recommendation-badge"
import type { AiBlock, ArticleDetail } from "@/lib/api"
import { useArticleAnalysisEvents } from "./use-article-analysis-events"
import { cn } from "@/lib/utils"

// eslint-disable-next-line react-refresh/only-export-components
export function formatArticleDate(value: string | null) {
  if (!value) return "未发布"
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
}

function visibleAiBlocks(blocks: AiBlock[] | null) {
  return [...(blocks ?? [])]
    .sort((a, b) => a.order - b.order)
    .filter((block) => block.type !== "chapters" || block.content.length > 0)
}

export function ArticleHeader({
  article,
  className,
  titleClassName,
}: {
  article: ArticleDetail
  className?: string
  titleClassName?: string
}) {
  return (
    <header className={cn("flex flex-col gap-3", className)}>
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span className="font-medium text-foreground">{article.source_title}</span>
        <span aria-hidden="true">/</span>
        <span>{formatArticleDate(article.published_at)}</span>
      </div>

      <h1
        className={cn(
          "text-2xl font-semibold leading-tight text-foreground",
          titleClassName,
        )}
      >
        {article.title}
      </h1>

      <a
        href={article.url}
        target="_blank"
        rel="noreferrer"
        className="inline-flex w-fit items-center gap-1 text-sm font-medium text-foreground underline-offset-4 hover:underline"
      >
        阅读原文
        <ExternalLinkIcon aria-hidden="true" className="size-3.5" />
      </a>
    </header>
  )
}

export function ArticleAiSummary({
  article,
  className,
}: {
  article: ArticleDetail
  className?: string
}) {
  const { streamText, isStreaming, streamError } = useArticleAnalysisEvents(article)

  const blocks = visibleAiBlocks(article.ai_blocks)

  const hasBlocks = blocks.length > 0
  const hasLegacyContent =
    article.reading_recommendation ||
    article.one_sentence_summary ||
    article.reading_reason
  const hasAiContent = hasBlocks || hasLegacyContent || streamText || streamError

  return (
    <section
      aria-labelledby="article-ai-summary-heading"
      className={cn("flex flex-col gap-3 rounded-lg border bg-card p-4", className)}
    >
      <div className="flex items-center gap-2">
        <SparklesIcon aria-hidden="true" className="size-4 text-muted-foreground" />
        <h2 id="article-ai-summary-heading" className="text-sm font-semibold">
          AI 总结
        </h2>
        {article.reading_recommendation ? (
          <div className="ml-auto">
            <RecommendationBadge value={article.reading_recommendation} />
          </div>
        ) : null}
      </div>

      {hasAiContent ? (
        <div className="flex flex-col gap-3">
          {hasBlocks ? (
            blocks.map((block) => (
              <div key={block.type}>
                {block.type === "reading_question" ? (
                  <p className="text-sm font-medium text-foreground">
                    {block.content}
                  </p>
                ) : null}
                {block.type === "highlights" ? (
                  <ul className="flex list-none flex-col gap-1.5 pl-0">
                    {block.content.map((item, idx) => (
                      <li
                        key={idx}
                        className="border-l-2 border-muted-foreground/30 pl-3 text-sm italic text-muted-foreground"
                      >
                        {item.text}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {block.type === "summary" ? (
                  <p className="text-sm leading-6 text-foreground">
                    {block.content}
                  </p>
                ) : null}
                {block.type === "reading_reason" ? (
                  <p className="text-sm leading-6 text-muted-foreground">
                    {block.content}
                  </p>
                ) : null}
                {block.type === "chapters" ? (
                  <ul className="flex list-none flex-wrap gap-1.5 pl-0">
                    {block.content.map((item, idx) => (
                      <li
                        key={idx}
                        className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground"
                      >
                        {item.title}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ))
          ) : hasLegacyContent ? (
            <>
              {article.one_sentence_summary ? (
                <p className="text-sm leading-6 text-foreground">
                  {article.one_sentence_summary}
                </p>
              ) : null}

              {article.reading_reason ? (
                <p className="text-sm leading-6 text-muted-foreground">
                  {article.reading_reason}
                </p>
              ) : null}
            </>
          ) : null}

          {!hasBlocks && streamText ? (
            <MarkdownContent markdown={streamText} />
          ) : null}

          {streamError ? (
            <p className="text-sm leading-6 text-destructive-foreground">
              {streamError}
            </p>
          ) : null}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          {isStreaming ? "AI 总结生成中" : "AI 总结处理中"}
        </p>
      )}
    </section>
  )
}

export function ArticleBody({
  contentMarkdown,
  className,
}: {
  contentMarkdown: string | null
  className?: string
}) {
  return (
    <div className={cn("border-t pt-6", className)}>
      <MarkdownContent markdown={contentMarkdown ?? "正文处理中……"} />
    </div>
  )
}
