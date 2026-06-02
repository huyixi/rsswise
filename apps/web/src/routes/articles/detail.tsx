import { useEffect, useRef } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { useParams } from "react-router-dom"

import { MarkdownContent } from "@/components/markdown-content"
import { RecommendationBadge } from "@/components/recommendation-badge"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { apiGet, apiPost, type ArticleDetail } from "@/lib/api"
import { queryClient } from "@/lib/query-client"
import { queryKeys } from "@/lib/query-keys"

function formatDate(value: string | null) {
  if (!value) return "未发布"
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
}

function statusLabel(value: string | null) {
  if (value === "success") return "完成"
  if (value === "processing") return "处理中"
  if (value === "failed") return "失败"
  return "等待中"
}

export function ArticleDetailPage() {
  const { id } = useParams<{ id: string }>()
  const markedReadIdRef = useRef<string | null>(null)

  const articleQuery = useQuery({
    queryKey: queryKeys.articles.detail(id ?? ""),
    queryFn: () => apiGet<ArticleDetail>(`/articles/${id}`),
    enabled: Boolean(id),
  })

  const markReadMutation = useMutation({
    mutationFn: (articleId: string) => apiPost(`/articles/${articleId}/read`),
    onSuccess: (_, articleId) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.articles.detail(articleId),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.articles.all,
      })
    },
  })

  const markUnreadMutation = useMutation({
    mutationFn: (articleId: string) => apiPost(`/articles/${articleId}/unread`),
    onSuccess: (_, articleId) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.articles.detail(articleId),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.articles.all,
      })
    },
  })

  const reanalyzeMutation = useMutation({
    mutationFn: (articleId: string) =>
      apiPost(`/articles/${articleId}/reanalyze`),
    onSuccess: (_, articleId) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.articles.detail(articleId),
      })
    },
  })

  useEffect(() => {
    if (!id || markedReadIdRef.current === id) return
    markedReadIdRef.current = id
    markReadMutation.mutate(id)
  }, [id, markReadMutation])

  useEffect(() => {
    if (articleQuery.data?.title) {
      document.title = `${articleQuery.data.title} - RSSWise`
    }
  }, [articleQuery.data?.title])

  useEffect(() => {
    if (!articleQuery.data?.title) {
      document.title = "文章详情 - RSSWise"
    }
  }, [articleQuery.data?.title])

  if (!id) {
    return <div className="text-sm text-red-600">文章 ID 无效</div>
  }

  if (articleQuery.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Spinner />
        <span>加载文章中</span>
      </div>
    )
  }

  if (articleQuery.isError) {
    return (
      <div className="text-sm text-red-600">
        {articleQuery.error.message || "加载文章失败"}
      </div>
    )
  }

  const article = articleQuery.data
  if (!article) return null

  const mutationError =
    markReadMutation.error ?? markUnreadMutation.error ?? reanalyzeMutation.error

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
          <Button
            type="button"
            variant="outline"
            size="sm"
            loading={markUnreadMutation.isPending}
            disabled={markUnreadMutation.isPending}
            onClick={() => markUnreadMutation.mutate(article.id)}
          >
            标记未读
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            loading={reanalyzeMutation.isPending}
            disabled={reanalyzeMutation.isPending}
            onClick={() => reanalyzeMutation.mutate(article.id)}
          >
            重新 AI 分析
          </Button>
        </div>
        {mutationError ? (
          <p className="text-sm text-red-600">{mutationError.message}</p>
        ) : null}
      </section>

      <MarkdownContent markdown={article.content_markdown ?? "正文处理中"} />
    </div>
  )
}
