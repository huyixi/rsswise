import { useEffect, useRef, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { Link, useNavigate, useOutletContext, useSearchParams } from "react-router-dom"
import {
  ArrowLeftIcon,
  BookOpenIcon,
  InboxIcon,
  PlusIcon,
  XIcon,
} from "lucide-react"

import { EmailDigestSettingsDialog } from "@/components/email-digest-settings-dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/menu"

import { Spinner } from "@/components/ui/spinner"
import { useIsMobile } from "@/hooks/use-media-query"
import { cn } from "@/lib/utils"
import { apiGet, apiPost, type ArticleDetail, type ArticleListItem, type Feed } from "@/lib/api"
import { queryClient } from "@/lib/query-client"
import { queryKeys } from "@/lib/query-keys"
import {
  ArticleAiSummary,
  ArticleBody,
  ArticleMetadata,
} from "./components"
import { FeedManagementContent } from "../feeds/list"

type ArticleView = "all" | "today" | "unread"
type RecommendationView = "deep_read" | "skim" | "skip"

type AppChromeContext = {
  email: string | undefined
  isLoggingOut: boolean
  onLogout: () => void
}

const primaryNavItems: Array<{
  label: string
  view: ArticleView
}> = [
  { label: "Today", view: "today" },
  { label: "Unread", view: "unread" },
  { label: "All Articles", view: "all" },
]

const recommendationNavItems: Array<{
  label: string
  recommendation: RecommendationView
}> = [
  { label: "Deep Read", recommendation: "deep_read" },
  { label: "Skim", recommendation: "skim" },
  { label: "Skip", recommendation: "skip" },
]

function normalizeView(value: string | null): ArticleView {
  return value === "today" || value === "unread" ? value : "all"
}

function normalizeRecommendation(value: string | null): RecommendationView | null {
  if (value === "deep_read" || value === "skim" || value === "skip") return value
  return null
}

function isToday(value: string | null) {
  if (!value) return false
  const date = new Date(value)
  const now = new Date()
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  )
}

function normalizeStatus(value: string | null) {
  return value === "read" || value === "unread" ? value : "all"
}

function navButtonClassName(active: boolean) {
  return cn(
    "flex w-full items-center justify-between rounded-md px-2.5 py-2 text-left text-sm transition-colors",
    active
      ? "bg-accent font-medium text-foreground"
      : "text-muted-foreground hover:bg-accent/70 hover:text-foreground",
  )
}

function toggleButtonClassName(active: boolean) {
  return cn(
    "flex-1 rounded px-2 py-1 text-center text-xs font-medium transition-colors",
    active ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
  )
}

function WorkbenchSidebar({
  feeds,
  feedId,
  onSelectFeed,
  userEmail,
  isLoggingOut,
  onLogout,
  isFeedPanelOpen,
  onToggleFeedPanel,
}: {
  feeds: Feed[] | undefined
  feedId: string | null
  onSelectFeed: (id: string | null) => void
  userEmail: string | undefined
  isLoggingOut: boolean
  onLogout: () => void
  isFeedPanelOpen: boolean
  onToggleFeedPanel: () => void
}) {
  const [emailDialogOpen, setEmailDialogOpen] = useState(false)

  return (
    <aside className="flex w-[220px] shrink-0 flex-col border-r bg-background px-3 py-3">
      <div className="flex items-center justify-between">
        <h1 className="min-w-0 text-base font-semibold text-foreground">
          RSSWise
        </h1>
        <button
          type="button"
          onClick={onToggleFeedPanel}
          aria-label={isFeedPanelOpen ? "关闭 Feed 管理" : "添加 Feed"}
          className="inline-flex size-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          {isFeedPanelOpen ? (
            <XIcon aria-hidden="true" className="size-4" />
          ) : (
            <PlusIcon aria-hidden="true" className="size-4" />
          )}
        </button>
      </div>

      <nav className="mt-5 flex flex-1 flex-col gap-1 overflow-hidden" aria-label="Feed 导航">
        <button
          type="button"
          className={navButtonClassName(feedId === null)}
          onClick={() => onSelectFeed(null)}
        >
          <span>All Articles</span>
        </button>

        <div className="mx-2 border-t my-1" />

        <div className="flex-1 overflow-y-auto">
          {feeds === undefined ? (
            <div className="flex flex-col gap-1 px-2.5">
              <div className="h-5 w-3/5 animate-pulse rounded bg-muted" />
              <div className="h-5 w-4/5 animate-pulse rounded bg-muted" />
              <div className="h-5 w-2/5 animate-pulse rounded bg-muted" />
            </div>
          ) : feeds.length === 0 ? (
            <p className="px-2.5 py-1 text-sm text-muted-foreground">
              <Link to="/feeds" className="underline transition-colors hover:text-foreground">
                暂无订阅
              </Link>
            </p>
          ) : (
            feeds.map((feed) => (
              <button
                key={feed.id}
                type="button"
                className={navButtonClassName(feed.id === feedId)}
                onClick={() => onSelectFeed(feed.id)}
              >
                {feed.favicon_url ? (
                  <img
                    src={feed.favicon_url}
                    alt=""
                    className="size-3.5 shrink-0 rounded-sm"
                  />
                ) : null}
                <span className="truncate">{feed.title ?? feed.url}</span>
              </button>
            ))
          )}
        </div>
      </nav>

      <div className="border-t pt-3">
        <DropdownMenu>
          <DropdownMenuTrigger
            className="w-full truncate rounded-md px-2.5 py-2 text-left text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            aria-label="用户菜单"
          >
            {userEmail ?? "当前用户"}
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" sideOffset={4}>
            <DropdownMenuItem
              closeOnClick
              onSelect={() => setEmailDialogOpen(true)}
            >
              邮件摘要设置
            </DropdownMenuItem>
            <DropdownMenuItem
              closeOnClick
              onSelect={onLogout}
              disabled={isLoggingOut}
            >
              退出登录
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <EmailDigestSettingsDialog
        open={emailDialogOpen}
        onOpenChange={setEmailDialogOpen}
      />
    </aside>
  )
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
  view,
  recommendation,
  onSelectView,
  onSelectRecommendation,
  feedName,
  isLoading,
  isError,
  errorMessage,
}: {
  articles: ArticleListItem[] | undefined
  selectedId: string | null
  onSelect: (id: string) => void
  view: ArticleView
  recommendation: RecommendationView | null
  onSelectView: (view: ArticleView) => void
  onSelectRecommendation: (recommendation: RecommendationView) => void
  feedName: string | null
  isLoading: boolean
  isError: boolean
  errorMessage: string
}) {
  return (
    <aside className="flex w-[320px] shrink-0 flex-col border-r bg-background max-lg:w-full max-lg:border-r-0 max-lg:border-b">
      <div className="border-b px-3 py-2">
        {feedName ? (
          <p className="mb-1.5 truncate text-xs font-medium text-muted-foreground">{feedName}</p>
        ) : null}
        <div className="mb-1.5 flex gap-0.5 rounded-md bg-muted p-0.5">
          {primaryNavItems.map((item) => (
            <button
              key={item.view}
              type="button"
              className={toggleButtonClassName(view === item.view)}
              onClick={() => onSelectView(item.view)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="flex gap-0.5 rounded-md bg-muted p-0.5">
          {recommendationNavItems.map((item) => (
            <button
              key={item.recommendation}
              type="button"
              className={toggleButtonClassName(recommendation === item.recommendation)}
              onClick={() => onSelectRecommendation(item.recommendation)}
            >
              {item.label}
            </button>
          ))}
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
                  <div className="flex items-start gap-2 px-4 py-3">
                    {!article.is_read ? (
                      <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-foreground" />
                    ) : (
                      <span className="mt-1.5 size-1.5 shrink-0" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p
                        className={cn(
                          "line-clamp-2 text-sm leading-snug",
                          article.is_read ? "font-normal text-muted-foreground" : "font-medium text-foreground",
                          isSelected && "text-foreground",
                        )}
                      >
                        {article.title}
                      </p>
                      {article.one_sentence_summary ? (
                        <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                          {article.one_sentence_summary}
                        </p>
                      ) : null}
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
        <header className="flex flex-col gap-3">
          <h1 className="text-2xl font-semibold leading-tight text-foreground">
            {article.title}
          </h1>
          <ArticleMetadata article={article} />
        </header>
        <ArticleAiSummary article={article} />
        <ArticleBody contentMarkdown={article.content_markdown} className="pt-0" />
      </article>
    </main>
  )
}

function FeedPanel({ onClose }: { onClose: () => void }) {
  return (
    <div className="flex flex-1 flex-col overflow-hidden bg-card">
      <div className="flex shrink-0 items-center justify-between border-b px-4 py-3">
        <h2 className="text-sm font-semibold text-foreground">Feed 管理</h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="关闭 Feed 管理"
          className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <XIcon aria-hidden="true" className="size-4" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        <FeedManagementContent />
      </div>
    </div>
  )
}

function MobileFeedPanel({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-background">
      <div className="flex shrink-0 items-center gap-2 border-b px-4 py-3">
        <button
          type="button"
          onClick={onClose}
          aria-label="返回"
          className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <ArrowLeftIcon aria-hidden="true" className="size-4" />
        </button>
        <h2 className="text-sm font-semibold text-foreground">Feed 管理</h2>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        <FeedManagementContent />
      </div>
    </div>
  )
}

export function ArticleWorkbenchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedId = searchParams.get("id")
  const view = normalizeView(searchParams.get("view"))
  const recommendation = normalizeRecommendation(searchParams.get("recommendation"))
  const status = view === "unread" ? "unread" : normalizeStatus(searchParams.get("status"))
  const navigate = useNavigate()
  const isMobile = useIsMobile()

  const appChrome = useOutletContext<AppChromeContext>()

  const [isFeedPanelOpen, setIsFeedPanelOpen] = useState(false)

  const feedId = searchParams.get("feed_id")

  const feedsQuery = useQuery({
    queryKey: queryKeys.feeds.list(),
    queryFn: () => apiGet<Feed[]>("/feeds"),
  })

  const markedReadIdRef = useRef<string | null>(null)

  const articlesQuery = useQuery({
    queryKey: queryKeys.articles.list(status),
    queryFn: () => {
      let url = `/articles?status_filter=${encodeURIComponent(status)}`
      if (feedId) url += `&feed_id=${encodeURIComponent(feedId)}`
      return apiGet<ArticleListItem[]>(url)
    },
  })

  const visibleArticles = (articlesQuery.data ?? []).filter((article) => {
    if (recommendation) {
      return article.reading_recommendation === recommendation
    }
    if (view === "today") {
      return isToday(article.published_at)
    }
    return true
  })

  const articleQuery = useQuery({
    queryKey: queryKeys.articles.detail(selectedId ?? ""),
    queryFn: () => apiGet<ArticleDetail>(`/articles/${selectedId}`),
    enabled: Boolean(selectedId) && !isMobile && !isFeedPanelOpen,
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
    if (isMobile || isFeedPanelOpen) return
    if (visibleArticles.length === 0) return
    if (selectedId && visibleArticles.some((article) => article.id === selectedId)) return

    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set("id", visibleArticles[0].id)
      return next
    })
  }, [isMobile, isFeedPanelOpen, visibleArticles, selectedId, setSearchParams])

  useEffect(() => {
    if (isMobile) return

    function handleKeyDown(event: KeyboardEvent) {
      if (isFeedPanelOpen) return
      if (visibleArticles.length === 0) return
      if (!selectedId) return

      const currentIndex = visibleArticles.findIndex((a) => a.id === selectedId)
      if (currentIndex === -1) return

      let nextIndex = currentIndex
      if (event.key === "ArrowDown") {
        nextIndex = Math.min(currentIndex + 1, visibleArticles.length - 1)
      } else if (event.key === "ArrowUp") {
        nextIndex = Math.max(currentIndex - 1, 0)
      } else {
        return
      }

      event.preventDefault()

      if (nextIndex === currentIndex) return

      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        next.set("id", visibleArticles[nextIndex].id)
        return next
      })
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [isMobile, isFeedPanelOpen, visibleArticles, selectedId, setSearchParams])

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

  function handleSelectFeed(nextFeedId: string | null) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete("id")
      if (nextFeedId === null) {
        next.delete("feed_id")
      } else if (prev.get("feed_id") === nextFeedId) {
        next.delete("feed_id")
      } else {
        next.set("feed_id", nextFeedId)
      }
      return next
    })
  }

  const selectedFeed = feedsQuery.data?.find((f) => f.id === feedId)
  const feedName = selectedFeed?.title ?? selectedFeed?.url ?? null

  function handleSelectView(nextView: ArticleView) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete("id")
      next.delete("status")
      if (nextView === "unread") {
        next.set("view", "unread")
        next.set("status", "unread")
      } else if (nextView === "today") {
        next.set("view", "today")
      } else {
        next.delete("view")
      }
      return next
    })
  }

  function handleSelectRecommendation(nextRecommendation: RecommendationView) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete("id")
      if (prev.get("recommendation") === nextRecommendation) {
        next.delete("recommendation")
      } else {
        next.set("recommendation", nextRecommendation)
      }
      return next
    })
  }

  if (isMobile) {
    if (isFeedPanelOpen) {
      return (
        <MobileFeedPanel onClose={() => setIsFeedPanelOpen(false)} />
      )
    }

    return (
      <div className="min-h-screen bg-background">
        <div className="flex items-center justify-between border-b px-4 py-2">
          <h1 className="text-sm font-semibold text-foreground">RSSWise</h1>
          <button
            type="button"
            onClick={() => setIsFeedPanelOpen(true)}
            aria-label="添加 Feed"
            className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <PlusIcon aria-hidden="true" className="size-4" />
          </button>
        </div>
        <ArticleListPanel
          articles={visibleArticles}
          selectedId={selectedId}
          onSelect={handleSelectArticle}
          view={view}
          recommendation={recommendation}
          onSelectView={handleSelectView}
          onSelectRecommendation={handleSelectRecommendation}
          feedName={feedName}
          isLoading={articlesQuery.isLoading}
          isError={articlesQuery.isError}
          errorMessage={articlesQuery.error?.message ?? "加载文章列表失败"}
        />
      </div>
    )
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <WorkbenchSidebar
        feeds={feedsQuery.data}
        feedId={feedId}
        onSelectFeed={handleSelectFeed}
        userEmail={appChrome.email}
        isLoggingOut={appChrome.isLoggingOut}
        onLogout={appChrome.onLogout}
        isFeedPanelOpen={isFeedPanelOpen}
        onToggleFeedPanel={() => setIsFeedPanelOpen((open) => !open)}
      />

      {isFeedPanelOpen ? (
        <FeedPanel onClose={() => setIsFeedPanelOpen(false)} />
      ) : (
        <>
          <ArticleListPanel
            articles={visibleArticles}
            selectedId={selectedId}
            onSelect={handleSelectArticle}
            view={view}
            recommendation={recommendation}
            onSelectView={handleSelectView}
            onSelectRecommendation={handleSelectRecommendation}
            feedName={feedName}
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
        </>
      )}
    </div>
  )
}
