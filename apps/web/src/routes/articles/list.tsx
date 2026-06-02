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
    ? "rounded-lg border border-slate-900 bg-slate-900 px-3 py-1.5 text-sm font-medium text-white shadow-xs"
    : "rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 shadow-xs hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900 transition-colors"
}

function normalizeStatus(value: string | null) {
  return value === "read" || value === "unread" ? value : "all"
}

function SkeletonCard() {
  return (
    <div className="animate-pulse p-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex items-center gap-2">
            <div className="h-5 w-3/5 rounded bg-slate-200" />
            <div className="h-4 w-8 rounded bg-slate-200" />
          </div>
          <div className="h-4 w-2/5 rounded bg-slate-100" />
          <div className="h-4 w-4/5 rounded bg-slate-100" />
        </div>
        <div className="h-6 w-16 shrink-0 rounded-full bg-slate-200" />
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
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">文章</h1>
        <div className="flex gap-2">
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

      <div className="divide-y rounded-xl border border-slate-200 bg-white shadow-sm">
        {articlesQuery.isLoading ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : articlesQuery.isError ? (
          <div className="flex items-center gap-2 p-6 text-sm text-red-600">
            <span className="size-1.5 rounded-full bg-red-500" />
            {articlesQuery.error.message || "加载文章失败"}
          </div>
        ) : articlesQuery.data?.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <FileTextIcon className="size-10 text-slate-300" />
            <p className="text-sm text-slate-500">暂无文章</p>
          </div>
        ) : (
          articlesQuery.data?.map((article) => (
            <Link
              key={article.id}
              to={`/articles/${article.id}`}
              className="group block p-4 transition-all hover:bg-slate-50"
            >
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0 space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2
                      className={
                        article.is_read
                          ? "text-base font-medium text-slate-500"
                          : "text-base font-semibold text-slate-950"
                      }
                    >
                      {article.title}
                    </h2>
                    {article.is_read ? (
                      <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-500">
                        已读
                      </span>
                    ) : (
                      <span className="rounded bg-blue-50 px-1.5 py-0.5 text-[11px] font-medium text-blue-600">
                        未读
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-slate-500">
                    {article.source_title} · {formatDate(article.published_at)}
                  </p>
                  {article.one_sentence_summary ? (
                    <p className="line-clamp-2 text-sm leading-6 text-slate-700">
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
