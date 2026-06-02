import { useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link, useSearchParams } from "react-router-dom"

import { RecommendationBadge } from "@/components/recommendation-badge"
import { Spinner } from "@/components/ui/spinner"
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
    ? "rounded border border-slate-900 bg-slate-900 px-3 py-1.5 text-sm font-medium text-white"
    : "rounded border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 hover:border-slate-300 hover:text-slate-900"
}

function normalizeStatus(value: string | null) {
  return value === "read" || value === "unread" ? value : "all"
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
        <h1 className="text-2xl font-semibold">文章</h1>
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

      <div className="divide-y rounded border border-slate-200 bg-white">
        {articlesQuery.isLoading ? (
          <div className="flex items-center gap-2 p-6 text-sm text-slate-500">
            <Spinner />
            <span>加载文章中</span>
          </div>
        ) : articlesQuery.isError ? (
          <div className="p-6 text-sm text-red-600">
            {articlesQuery.error.message || "加载文章失败"}
          </div>
        ) : articlesQuery.data?.length === 0 ? (
          <div className="p-6 text-sm text-slate-500">暂无文章</div>
        ) : (
          articlesQuery.data?.map((article) => (
            <Link
              key={article.id}
              to={`/articles/${article.id}`}
              className="block p-4 transition-colors hover:bg-slate-50"
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
                    <span className="text-xs text-slate-400">
                      {article.is_read ? "已读" : "未读"}
                    </span>
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
