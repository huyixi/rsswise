import Link from "next/link";

import { RecommendationBadge } from "@/components/recommendation-badge";
import { apiGet, type ArticleListItem } from "@/lib/api";

export const dynamic = "force-dynamic";

function formatDate(value: string | null) {
  if (!value) return "未发布";
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function statusLinkClassName(active: boolean) {
  return active
    ? "rounded border border-slate-900 bg-slate-900 px-3 py-1.5 text-sm font-medium text-white"
    : "rounded border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 hover:border-slate-300 hover:text-slate-900";
}

export default async function ArticlesPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>;
}) {
  const params = await searchParams;
  const status =
    params.status === "read" || params.status === "unread"
      ? params.status
      : "all";
  const articles = await apiGet<ArticleListItem[]>(
    `/articles?status_filter=${status}`,
  );

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-semibold">文章</h1>
        <div className="flex gap-2">
          <Link className={statusLinkClassName(status === "all")} href="/articles">
            全部
          </Link>
          <Link
            className={statusLinkClassName(status === "read")}
            href="/articles?status=read"
          >
            已读
          </Link>
          <Link
            className={statusLinkClassName(status === "unread")}
            href="/articles?status=unread"
          >
            未读
          </Link>
        </div>
      </div>

      <div className="divide-y rounded border border-slate-200 bg-white">
        {articles.length === 0 ? (
          <div className="p-6 text-sm text-slate-500">暂无文章</div>
        ) : (
          articles.map((article) => (
            <Link
              key={article.id}
              href={`/articles/${article.id}`}
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
  );
}
