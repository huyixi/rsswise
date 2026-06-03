import { useEffect, useRef } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { useSearchParams } from "react-router-dom"
import {
  SparklesIcon,
  ExternalLinkIcon,
  BookOpenIcon,
  InboxIcon,
} from "lucide-react"

import { MarkdownContent } from "@/components/markdown-content"
import { RecommendationBadge } from "@/components/recommendation-badge"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { WorkflowStepper, type Step } from "@/components/workflow-stepper"
import { cn } from "@/lib/utils"
import { apiGet, apiPost, type ArticleDetail, type ArticleListItem } from "@/lib/api"
import { queryClient } from "@/lib/query-client"
import { queryKeys } from "@/lib/query-keys"

function formatDate(value: string | null) {
  if (!value) return "未发布"
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
}

function normalizeStatus(value: string | null) {
  return value === "read" || value === "unread" ? value : "all"
}

function statusLinkClassName(active: boolean) {
  return active
    ? "rounded-lg border border-slate-900 bg-slate-900 px-3 py-1.5 text-sm font-medium text-white shadow-xs"
    : "rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 shadow-xs hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900 transition-colors"
}

function SkeletonCard() {
  return (
    <div className="animate-pulse space-y-3 rounded-lg border border-slate-100 bg-white p-4">
      <div className="space-y-2">
        <div className="h-4 w-4/5 rounded bg-slate-200" />
        <div className="h-3 w-3/5 rounded bg-slate-100" />
        <div className="h-3 w-2/5 rounded bg-slate-100" />
      </div>
    </div>
  )
}

function buildWorkflowSteps(
  extraction: string | null,
  analysis: string | null,
  onRetry?: () => void,
): Step[] {
  return [
    {
      id: "extraction",
      label: "获取正文",
      description:
        extraction === "pending"
          ? "正在排队等待提取"
          : extraction === "processing"
            ? "正在提取文章正文内容"
            : extraction === "success"
              ? "正文提取完成"
              : extraction === "failed"
                ? "正文提取失败"
                : "等待提取",
      status: statusToStepStatus(extraction),
      failureMessage:
        extraction === "failed" ? "无法从原文链接提取正文，请检查原文是否可访问。" : undefined,
      onRetry: extraction === "failed" ? onRetry : undefined,
      retryLabel: "重新提取",
    },
    {
      id: "analysis",
      label: "AI 分析",
      description:
        analysis === "pending"
          ? extraction !== "success"
            ? "等待正文提取完成后自动开始"
            : "正在排队等待 AI 分析"
          : analysis === "processing"
            ? "正在生成摘要和阅读建议"
            : analysis === "success"
              ? "AI 分析完成"
              : analysis === "failed"
                ? "AI 分析失败"
                : "等待分析",
      status: statusToStepStatus(analysis),
      failureMessage:
        analysis === "failed" ? "AI 服务暂时不可用，请稍后重试。" : undefined,
      onRetry: analysis === "failed" ? onRetry : undefined,
      retryLabel: "重新分析",
    },
    {
      id: "ready",
      label: "阅读准备就绪",
      description:
        extraction === "success" && analysis === "success"
          ? "所有处理已完成，可以开始阅读"
          : extraction === "failed" || analysis === "failed"
            ? "部分步骤失败，请重试后继续"
            : "等待上游步骤完成",
      status:
        extraction === "success" && analysis === "success"
          ? "success"
          : extraction === "failed" || analysis === "failed"
            ? "failed"
            : "pending",
      failureMessage:
        extraction === "failed"
          ? "正文提取失败，无法进入阅读环节"
          : analysis === "failed"
            ? "AI 分析失败，但不影响阅读正文"
            : undefined,
    },
  ]
}

function statusToStepStatus(value: string | null): "pending" | "processing" | "success" | "failed" {
  if (value === "success") return "success"
  if (value === "processing") return "processing"
  if (value === "failed") return "failed"
  return "pending"
}

function ArticleListPanel({
  articles,
  selectedId,
  onSelect,
  status,
  onStatusChange,
  isLoading,
  isError,
  errorMessage,
}: {
  articles: ArticleListItem[] | undefined
  selectedId: string | null
  onSelect: (id: string) => void
  status: string
  onStatusChange: (status: string) => void
  isLoading: boolean
  isError: boolean
  errorMessage: string
}) {
  return (
    <aside className="flex w-[320px] shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="border-b border-slate-100 px-4 py-3">
        <h2 className="mb-3 text-sm font-semibold text-slate-900">文章列表</h2>
        <div className="flex gap-1.5">
          {(["all", "read", "unread"] as const).map((s) => (
            <button
              key={s}
              type="button"
              className={statusLinkClassName(status === s)}
              onClick={() => onStatusChange(s)}
            >
              {s === "all" ? "全部" : s === "read" ? "已读" : "未读"}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="space-y-2 p-4">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        ) : isError ? (
          <div className="flex items-center justify-center p-8">
            <p className="text-sm text-red-600">{errorMessage}</p>
          </div>
        ) : !articles || articles.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <InboxIcon className="size-10 text-slate-300" />
            <p className="text-sm text-slate-500">暂无文章</p>
            <p className="text-xs text-slate-400">添加 Feed 后文章将自动出现</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {articles.map((article) => {
              const isSelected = article.id === selectedId
              return (
                <button
                  key={article.id}
                  type="button"
                  className={cn(
                    "w-full text-left transition-colors",
                    isSelected
                      ? "border-l-2 border-blue-500 bg-blue-50/50"
                      : "border-l-2 border-transparent hover:bg-slate-50",
                  )}
                  onClick={() => onSelect(article.id)}
                >
                  <div className="px-4 py-3">
                    <div className="flex items-start gap-2">
                      <div className="min-w-0 flex-1">
                        <p
                          className={cn(
                            "truncate text-sm leading-snug",
                            article.is_read
                              ? "font-normal text-slate-500"
                              : "font-semibold text-slate-900",
                            isSelected && "text-blue-900",
                          )}
                        >
                          {article.title}
                        </p>
                        <p className="mt-1 truncate text-xs text-slate-400">
                          {article.source_title} · {formatDate(article.published_at)}
                        </p>
                        {article.one_sentence_summary && (
                          <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-slate-500">
                            {article.one_sentence_summary}
                          </p>
                        )}
                      </div>
                      <div className="shrink-0 pt-0.5">
                        {article.reading_recommendation ? (
                          <RecommendationBadge value={article.reading_recommendation} />
                        ) : !article.is_read ? (
                          <span className="inline-block size-2 rounded-full bg-blue-500" />
                        ) : null}
                      </div>
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </div>
    </aside>
  )
}

function ArticleContentPanel({
  article,
  isLoading,
  isError,
  errorMessage,
}: {
  article: ArticleDetail | undefined
  isLoading: boolean
  isError: boolean
  errorMessage: string
}) {
  if (!article && !isLoading && !isError) {
    return (
      <div className="flex flex-1 items-center justify-center bg-slate-50/50">
        <div className="flex flex-col items-center gap-4 text-center">
          <div className="flex size-16 items-center justify-center rounded-2xl border border-slate-200 bg-white shadow-xs">
            <BookOpenIcon className="size-7 text-slate-400" />
          </div>
          <div>
            <p className="text-base font-medium text-slate-900">选择一篇文章开始阅读</p>
            <p className="mt-1 text-sm text-slate-500">
              从左侧列表中选择文章后，正文将显示在这里
            </p>
          </div>
        </div>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center bg-slate-50/50">
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner />
          <span>加载文章中</span>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex flex-1 items-center justify-center bg-slate-50/50">
        <div className="text-center">
          <p className="text-sm text-red-600">{errorMessage}</p>
        </div>
      </div>
    )
  }

  if (!article) return null

  return (
    <main className="flex-1 overflow-y-auto bg-white">
      <article className="mx-auto max-w-3xl px-8 py-6">
        <header className="space-y-3">
          <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
            <span className="font-medium text-slate-700">{article.source_title}</span>
            <span className="text-slate-300">·</span>
            <span>{formatDate(article.published_at)}</span>
          </div>

          <h1 className="text-2xl font-semibold leading-tight tracking-tight text-slate-950">
            {article.title}
          </h1>

          <a
            href={article.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-sm font-medium text-blue-600 underline-offset-4 hover:underline"
          >
            阅读原文
            <ExternalLinkIcon className="size-3.5" />
          </a>
        </header>

        <div className="mt-6 border-t border-slate-100 pt-6">
          <MarkdownContent markdown={article.content_markdown ?? "正文处理中……"} />
        </div>
      </article>
    </main>
  )
}

function AISummaryPanel({
  article,
  isLoading,
  onReanalyze,
  onMarkUnread,
  isReanalyzing,
  isMarkingUnread,
}: {
  article: ArticleDetail | undefined
  isLoading: boolean
  onReanalyze: () => void
  onMarkUnread: () => void
  isReanalyzing: boolean
  isMarkingUnread: boolean
}) {
  if (!article && !isLoading) {
    return (
      <aside className="flex w-[340px] shrink-0 flex-col border-l border-slate-200 bg-white">
        <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
          <div className="flex size-12 items-center justify-center rounded-xl bg-slate-50">
            <SparklesIcon className="size-6 text-slate-400" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-700">AI 分析</p>
            <p className="mt-1 text-xs text-slate-400">选择文章后将显示处理进度和分析结果</p>
          </div>
        </div>
      </aside>
    )
  }

  return (
    <aside className="flex w-[340px] shrink-0 flex-col border-l border-slate-200 bg-white">
      <div className="border-b border-slate-100 px-5 py-4">
        <div className="flex items-center gap-2">
          <SparklesIcon className="size-4 text-blue-500" />
          <h2 className="text-sm font-semibold text-slate-900">AI 分析</h2>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Spinner />
          </div>
        ) : article ? (
          <div className="space-y-6">
            <WorkflowStepper
              steps={buildWorkflowSteps(
                article.extraction_status,
                article.analysis_status,
                onReanalyze,
              )}
            />

            {article.reading_recommendation && (
              <div className="space-y-3 rounded-lg border border-slate-100 bg-slate-50/50 p-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-500">阅读建议</span>
                  <RecommendationBadge value={article.reading_recommendation} />
                </div>

                {article.one_sentence_summary && (
                  <div>
                    <p className="mb-1 text-xs font-medium text-slate-500">摘要</p>
                    <p className="text-sm leading-relaxed text-slate-900">
                      {article.one_sentence_summary}
                    </p>
                  </div>
                )}

                {article.reading_reason && (
                  <div>
                    <p className="mb-1 text-xs font-medium text-slate-500">理由</p>
                    <p className="text-sm leading-relaxed text-slate-600">
                      {article.reading_reason}
                    </p>
                  </div>
                )}
              </div>
            )}

            <div className="flex flex-col gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="w-full"
                loading={isMarkingUnread}
                disabled={isMarkingUnread}
                onClick={onMarkUnread}
              >
                标记未读
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                className="w-full"
                loading={isReanalyzing}
                disabled={isReanalyzing}
                onClick={onReanalyze}
              >
                重新 AI 分析
              </Button>
            </div>

            <div className="space-y-2 rounded-lg border border-slate-100 bg-slate-50/50 px-4 py-3">
              <p className="text-xs font-medium text-slate-500">当前状态</p>
              <div className="space-y-1.5 text-xs text-slate-600">
                <div className="flex items-center justify-between">
                  <span>正文提取</span>
                  <span
                    className={cn(
                      "font-medium",
                      article.extraction_status === "success" && "text-emerald-600",
                      article.extraction_status === "processing" && "text-blue-600",
                      article.extraction_status === "failed" && "text-red-600",
                      (!article.extraction_status || article.extraction_status === "pending") &&
                        "text-slate-400",
                    )}
                  >
                    {statusLabel(article.extraction_status)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span>AI 分析</span>
                  <span
                    className={cn(
                      "font-medium",
                      article.analysis_status === "success" && "text-emerald-600",
                      article.analysis_status === "processing" && "text-blue-600",
                      article.analysis_status === "failed" && "text-red-600",
                      (!article.analysis_status || article.analysis_status === "pending") &&
                        "text-slate-400",
                    )}
                  >
                    {statusLabel(article.analysis_status)}
                  </span>
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </aside>
  )
}

function statusLabel(value: string | null) {
  if (value === "success") return "完成"
  if (value === "processing") return "处理中"
  if (value === "failed") return "失败"
  return "等待中"
}

export function ArticleWorkbenchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedId = searchParams.get("id")
  const status = normalizeStatus(searchParams.get("status"))

  const markedReadIdRef = useRef<string | null>(null)

  const articlesQuery = useQuery({
    queryKey: queryKeys.articles.list(status),
    queryFn: () =>
      apiGet<ArticleListItem[]>(
        `/articles?status_filter=${encodeURIComponent(status)}`,
      ),
  })

  const articleQuery = useQuery({
    queryKey: queryKeys.articles.detail(selectedId ?? ""),
    queryFn: () => apiGet<ArticleDetail>(`/articles/${selectedId}`),
    enabled: Boolean(selectedId),
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return false
      if (
        data.extraction_status === "processing" ||
        data.analysis_status === "processing"
      ) {
        return 3000
      }
      return false
    },
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
    if (!selectedId || markedReadIdRef.current === selectedId) return
    markedReadIdRef.current = selectedId
    markReadMutation.mutate(selectedId)
  }, [selectedId, markReadMutation])

  function handleSelectArticle(id: string) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set("id", id)
      return next
    })
  }

  function handleStatusChange(newStatus: string) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (newStatus === "all") {
        next.delete("status")
      } else {
        next.set("status", newStatus)
      }
      next.delete("id")
      return next
    })
  }

  function handleReanalyze() {
    if (selectedId) {
      reanalyzeMutation.mutate(selectedId)
    }
  }

  function handleMarkUnread() {
    if (selectedId) {
      markUnreadMutation.mutate(selectedId)
    }
  }

  return (
    <div className="flex h-[calc(100vh-57px)]">
      <ArticleListPanel
        articles={articlesQuery.data}
        selectedId={selectedId}
        onSelect={handleSelectArticle}
        status={status}
        onStatusChange={handleStatusChange}
        isLoading={articlesQuery.isLoading}
        isError={articlesQuery.isError}
        errorMessage={articlesQuery.error?.message ?? "加载文章列表失败"}
      />

      <ArticleContentPanel
        article={articleQuery.data}
        isLoading={articleQuery.isLoading}
        isError={articleQuery.isError}
        errorMessage={articleQuery.error?.message ?? "加载文章失败"}
      />

      <AISummaryPanel
        article={articleQuery.data}
        isLoading={articleQuery.isLoading}
        onReanalyze={handleReanalyze}
        onMarkUnread={handleMarkUnread}
        isReanalyzing={reanalyzeMutation.isPending}
        isMarkingUnread={markUnreadMutation.isPending}
      />
    </div>
  )
}
