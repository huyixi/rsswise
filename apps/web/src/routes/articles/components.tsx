import { ExternalLinkIcon, SparklesIcon } from "lucide-react"

import { MarkdownContent } from "@/components/markdown-content"
import { RecommendationBadge } from "@/components/recommendation-badge"
import type { ArticleDetail } from "@/lib/api"
import { cn } from "@/lib/utils"

// eslint-disable-next-line react-refresh/only-export-components
export function formatArticleDate(value: string | null) {
  if (!value) return "未发布"
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
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
  const hasAiContent =
    article.reading_recommendation ||
    article.one_sentence_summary ||
    article.reading_reason

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
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">AI 总结处理中</p>
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
