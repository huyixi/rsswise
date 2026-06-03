import { useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link, useSearchParams } from "react-router-dom"
import { FileTextIcon } from "lucide-react"

import { RecommendationBadge } from "@/components/recommendation-badge"
import { apiGet, type ArticleListItem } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

function formatDate(value: string | null) {
  if (!value) return "未发布"
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
}

function statusLinkClassName(active: boolean) {
  return active
    ? "rounded-md bg-foreground px-2.5 py-1.5 text-xs font-medium text-background"
    : "rounded-md px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
}

function normalizeStatus(value: string | null) {
  return value === "read" || value === "unread" ? value : "all"
}

function SkeletonCard() {
  return (
    <div className="animate-pulse p-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 flex-1 flex-col gap-3">
          <div className="h-4 w-3/5 rounded bg-muted" />
          <div className="h-3.5 w-2/5 rounded bg-muted" />
          <div className="h-3.5 w-4/5 rounded bg-muted" />
        </div>
        <div className="h-5 w-16 shrink-0 rounded bg-muted" />
      </div>
    </div>
  )
}

export function ArticlesPage() {
  const [searchParams] = useSearchParams()
  const status = normalizeStatus(searchParams.get("status"))

  useEffect(() => {
    document.title = "文章 - RSSWise"
  }, [])

  const articlesQuery = useQuery({
    queryKey: queryKeys.articles.list(status),
    queryFn: () =>
      apiGet<ArticleListItem[]>(
        `/articles?status_filter=${encodeURIComponent(status)}`,
      ),
  })

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-xl font-semibold text-foreground">文章</h1>
        <div className="flex w-fit rounded-lg border bg-card p-0.5">
          <Link className={statusLinkClassName(status === "all")} to="/articles">
            全部
          </Link>
          <Link
            className={statusLinkClassName(status === "read")}
            to="/articles?status=read"
          >
            已读
          </Link>
          <Link
            className={statusLinkClassName(status === "unread")}
            to="/articles?status=unread"
          >
            未读
          </Link>
        </div>
      </div>

      <div className="divide-y overflow-hidden rounded-lg border bg-card">
        {articlesQuery.isLoading ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : articlesQuery.isError ? (
          <div className="flex items-center gap-2 p-6 text-sm text-destructive-foreground">
            <span aria-hidden="true" className="size-1.5 rounded-full bg-destructive" />
            {articlesQuery.error.message || "加载文章失败"}
          </div>
        ) : articlesQuery.data?.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <FileTextIcon aria-hidden="true" className="size-9 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">暂无文章</p>
          </div>
        ) : (
          articlesQuery.data?.map((article) => (
            <Link
              key={article.id}
              to={`/articles/${article.id}`}
              className="block p-4 transition-colors hover:bg-accent/50"
            >
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex min-w-0 flex-col gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2
                      className={
                        article.is_read
                          ? "text-base font-medium text-muted-foreground"
                          : "text-base font-semibold text-foreground"
                      }
                    >
                      {article.title}
                    </h2>
                    {article.is_read ? (
                      <span className="rounded bg-muted px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">
                        已读
                      </span>
                    ) : (
                      <span className="rounded bg-foreground px-1.5 py-0.5 text-[11px] font-medium text-background">
                        未读
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {article.source_title} · {formatDate(article.published_at)}
                  </p>
                  {article.one_sentence_summary ? (
                    <p className="line-clamp-2 text-sm leading-6 text-muted-foreground">
                      {article.one_sentence_summary}
                    </p>
                  ) : null}
                </div>
                {article.reading_recommendation ? (
                  <div className="shrink-0">
                    <RecommendationBadge value={article.reading_recommendation} />
                  </div>
                ) : null}
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  )
}
