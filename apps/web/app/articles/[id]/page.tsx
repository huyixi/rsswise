import { MarkdownContent } from "@/components/markdown-content";
import { RecommendationBadge } from "@/components/recommendation-badge";
import { Button } from "@/components/ui/button";
import { apiGet, apiPost, type ArticleDetail } from "@/lib/api";
import { markUnread, reanalyze } from "./actions";

export const dynamic = "force-dynamic";

function formatDate(value: string | null) {
  if (!value) return "未发布";
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function statusLabel(value: string | null) {
  if (value === "success") return "完成";
  if (value === "processing") return "处理中";
  if (value === "failed") return "失败";
  return "等待中";
}

export default async function ArticleDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  await apiPost(`/articles/${id}/read`);
  const article = await apiGet<ArticleDetail>(`/articles/${id}`);

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
          <span>{article.source_title}</span>
          <span>·</span>
          <span>{formatDate(article.published_at)}</span>
        </div>
        <h1 className="text-3xl font-semibold leading-tight text-slate-950">
          {article.title}
        </h1>
        <a
          href={article.url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex text-sm font-medium text-slate-700 underline-offset-4 hover:underline"
        >
          原文链接
        </a>
      </div>

      <section className="space-y-3 rounded border border-slate-200 bg-white p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-base font-semibold">AI 信息</h2>
          <div className="flex flex-wrap gap-2 text-xs text-slate-500">
            <span>正文：{statusLabel(article.extraction_status)}</span>
            <span>分析：{statusLabel(article.analysis_status)}</span>
          </div>
        </div>
        {article.reading_recommendation ? (
          <RecommendationBadge value={article.reading_recommendation} />
        ) : null}
        {article.one_sentence_summary ? (
          <p className="text-sm leading-6 text-slate-900">
            {article.one_sentence_summary}
          </p>
        ) : null}
        {article.reading_reason ? (
          <p className="text-sm leading-6 text-slate-600">
            {article.reading_reason}
          </p>
        ) : null}
        <div className="flex flex-wrap gap-2 pt-1">
          <form action={markUnread.bind(null, article.id)}>
            <Button type="submit" variant="outline" size="sm">
              标记未读
            </Button>
          </form>
          <form action={reanalyze.bind(null, article.id)}>
            <Button type="submit" variant="secondary" size="sm">
              重新 AI 分析
            </Button>
          </form>
        </div>
      </section>

      <MarkdownContent markdown={article.content_markdown ?? "正文处理中"} />
    </div>
  );
}
