import { useEffect, useRef } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { useNavigate, useSearchParams } from "react-router-dom"
import { SparklesIcon, BookOpenIcon, InboxIcon } from "lucide-react"

import { RecommendationBadge } from "@/components/recommendation-badge"
import { Spinner } from "@/components/ui/spinner"
import { useIsMobile } from "@/hooks/use-media-query"
import { cn } from "@/lib/utils"
import { apiGet, apiPost, type ArticleDetail, type ArticleListItem } from "@/lib/api"
import { queryClient } from "@/lib/query-client"
import { queryKeys } from "@/lib/query-keys"
import {
  ArticleAiSummary,
  ArticleBody,
  ArticleHeader,
  formatArticleDate,
} from "./components"

function normalizeStatus(value: string | null) {
  return value === "read" || value === "unread" ? value : "all"
}

function statusFilterClassName(active: boolean) {
  return active
    ? "rounded-md bg-foreground px-2.5 py-1.5 text-xs font-medium text-background"
    : "rounded-md px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
}

function SkeletonCard() {
  return (
    <div className="animate-pulse border-b px-4 py-3">
      <div className="flex flex-col gap-2">
        <div className="h-3.5 w-4/5 rounded bg-muted" />
        <div className="h-3 w-3/5 rounded bg-muted" />
        <div className="h-3 w-2/5 rounded bg-muted" />
      </div>
    </div>
  )
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
    <aside className="flex w-[320px] shrink-0 flex-col border-r bg-background max-lg:w-full max-lg:border-r-0 max-lg:border-b">
      <div className="border-b px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-foreground">文章列表</h2>
          <div className="flex rounded-lg border bg-card p-0.5">
            {(["all", "read", "unread"] as const).map((s) => (
              <button
                key={s}
                type="button"
                className={statusFilterClassName(status === s)}
                onClick={() => onStatusChange(s)}
              >
                {s === "all" ? "全部" : s === "read" ? "已读" : "未读"}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div>
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        ) : isError ? (
          <div className="flex items-center justify-center p-8">
            <p className="text-sm text-destructive-foreground">{errorMessage}</p>
          </div>
        ) : !articles || articles.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <InboxIcon aria-hidden="true" className="size-9 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">暂无文章</p>
            <p className="text-xs text-muted-foreground/70">添加 Feed 后文章将自动出现</p>
          </div>
        ) : (
          <div className="divide-y">
            {articles.map((article) => {
              const isSelected = article.id === selectedId
              return (
                <button
                  key={article.id}
                  type="button"
                  className={cn(
                    "w-full text-left transition-colors",
                    isSelected
                      ? "bg-accent"
                      : "border-transparent hover:bg-accent/60",
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
                              ? "font-normal text-muted-foreground"
                              : "font-medium text-foreground",
                            isSelected && "text-foreground",
                          )}
                        >
                          {article.title}
                        </p>
                        <p className="mt-1 truncate text-xs text-muted-foreground">
                          {article.source_title} ·{" "}
                          {formatArticleDate(article.published_at)}
                        </p>
                        {article.one_sentence_summary && (
                          <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                            {article.one_sentence_summary}
                          </p>
                        )}
                      </div>
                      <div className="shrink-0 pt-0.5">
                        {article.reading_recommendation ? (
                          <RecommendationBadge value={article.reading_recommendation} />
                        ) : !article.is_read ? (
                          <span className="inline-block size-2 rounded-full bg-foreground" />
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
      <div className="flex flex-1 items-center justify-center bg-card max-lg:min-h-[320px]">
        <div className="flex flex-col items-center gap-4 text-center">
          <div className="flex size-12 items-center justify-center rounded-lg border bg-background">
            <BookOpenIcon aria-hidden="true" className="size-5 text-muted-foreground" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">选择一篇文章开始阅读</p>
            <p className="mt-1 text-sm text-muted-foreground">
              从左侧列表中选择文章后，正文将显示在这里
            </p>
          </div>
        </div>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center bg-card max-lg:min-h-[320px]">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner />
          <span>加载文章中</span>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex flex-1 items-center justify-center bg-card max-lg:min-h-[320px]">
        <div className="text-center">
          <p className="text-sm text-destructive-foreground">{errorMessage}</p>
        </div>
      </div>
    )
  }

  if (!article) return null

  return (
    <main className="min-w-0 flex-1 overflow-y-auto bg-card">
      <article className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-8 md:px-8">
        <ArticleHeader article={article} />
        <ArticleBody contentMarkdown={article.content_markdown} />
      </article>
    </main>
  )
}

function AISummaryPanel({
  article,
  isLoading,
}: {
  article: ArticleDetail | undefined
  isLoading: boolean
}) {
  if (!article && !isLoading) {
    return (
      <aside className="flex w-[340px] shrink-0 flex-col border-l bg-background max-xl:w-[300px] max-lg:w-full max-lg:border-l-0 max-lg:border-t">
        <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
          <div className="flex size-10 items-center justify-center rounded-lg border bg-card">
            <SparklesIcon aria-hidden="true" className="size-5 text-muted-foreground" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">AI 分析</p>
            <p className="mt-1 text-xs text-muted-foreground">选择文章后将显示处理进度和分析结果</p>
          </div>
        </div>
      </aside>
    )
  }

  return (
    <aside className="flex w-[340px] shrink-0 flex-col border-l bg-background max-xl:w-[300px] max-lg:w-full max-lg:border-l-0 max-lg:border-t">
      <div className="flex-1 overflow-y-auto px-5 py-4">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Spinner />
          </div>
        ) : article ? (
          <ArticleAiSummary article={article} />
        ) : null}
      </div>
    </aside>
  )
}

export function ArticleWorkbenchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedId = searchParams.get("id")
  const status = normalizeStatus(searchParams.get("status"))
  const navigate = useNavigate()
  const isMobile = useIsMobile()

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
    enabled: Boolean(selectedId) && !isMobile,
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

  useEffect(() => {
    if (isMobile || !selectedId || markedReadIdRef.current === selectedId) return
    markedReadIdRef.current = selectedId
    markReadMutation.mutate(selectedId)
  }, [isMobile, selectedId, markReadMutation])

  useEffect(() => {
    if (isMobile) return
    if (!articlesQuery.data || articlesQuery.data.length === 0) return
    if (selectedId) return

    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set("id", articlesQuery.data![0].id)
      return next
    })
  }, [isMobile, articlesQuery.data, selectedId, setSearchParams])

  useEffect(() => {
    if (isMobile) return

    function handleKeyDown(event: KeyboardEvent) {
      if (!articlesQuery.data || articlesQuery.data.length === 0) return
      if (!selectedId) return

      const currentIndex = articlesQuery.data.findIndex((a) => a.id === selectedId)
      if (currentIndex === -1) return

      let nextIndex = currentIndex
      if (event.key === "ArrowDown") {
        nextIndex = Math.min(currentIndex + 1, articlesQuery.data.length - 1)
      } else if (event.key === "ArrowUp") {
        nextIndex = Math.max(currentIndex - 1, 0)
      } else {
        return
      }

      event.preventDefault()

      if (nextIndex === currentIndex) return

      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        next.set("id", articlesQuery.data![nextIndex].id)
        return next
      })
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [isMobile, articlesQuery.data, selectedId, setSearchParams])

  function handleSelectArticle(id: string) {
    if (isMobile) {
      navigate(`/articles/${id}`)
      return
    }

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

  if (isMobile) {
    return (
      <div className="min-h-[calc(100vh-49px)] bg-background">
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
      </div>
    )
  }

  return (
    <div className="flex h-[calc(100vh-49px)] overflow-hidden max-lg:h-auto max-lg:min-h-[calc(100vh-49px)] max-lg:flex-col">
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
      />
    </div>
  )
}
