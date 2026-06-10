import { useEffect, useRef } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { Link, useNavigate, useOutletContext, useSearchParams } from "react-router-dom"
import {
  BookOpenIcon,
  InboxIcon,
  LogOutIcon,
  PlusIcon,
  RssIcon,
  UserIcon,
} from "lucide-react"

import { EmailDigestSettingsDialog } from "@/components/email-digest-settings-dialog"
import { Button } from "@/components/ui/button"

import { Spinner } from "@/components/ui/spinner"
import { useIsMobile } from "@/hooks/use-media-query"
import { cn } from "@/lib/utils"
import { apiGet, apiPost, type ArticleDetail, type ArticleListItem } from "@/lib/api"
import { queryClient } from "@/lib/query-client"
import { queryKeys } from "@/lib/query-keys"
import {
  ArticleAiSummary,
  ArticleBody,
  ArticleMetadata,
} from "./components"

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

function streamTitle(view: ArticleView, recommendation: RecommendationView | null) {
  if (recommendation) {
    return recommendationNavItems.find((item) => item.recommendation === recommendation)?.label ?? "AI"
  }
  return primaryNavItems.find((item) => item.view === view)?.label ?? "All Articles"
}

function WorkbenchSidebar({
  view,
  recommendation,
  userEmail,
  isLoggingOut,
  onLogout,
  onSelectView,
  onSelectRecommendation,
}: {
  view: ArticleView
  recommendation: RecommendationView | null
  userEmail: string | undefined
  isLoggingOut: boolean
  onLogout: () => void
  onSelectView: (view: ArticleView) => void
  onSelectRecommendation: (recommendation: RecommendationView) => void
}) {
  return (
    <aside className="flex w-[220px] shrink-0 flex-col border-r bg-background px-3 py-3">
      <div className="flex items-center gap-2">
        <h1 className="min-w-0 flex-1 truncate text-base font-semibold text-foreground">
          RSSWise
        </h1>
        <Link
          to="/feeds"
          aria-label="添加 Feed"
          className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <PlusIcon aria-hidden="true" className="size-4" />
        </Link>
        <div
          aria-label="当前用户"
          title={userEmail}
          className="inline-flex size-8 items-center justify-center rounded-full border bg-card text-muted-foreground"
        >
          <UserIcon aria-hidden="true" className="size-4" />
        </div>
      </div>

      <nav className="mt-5 flex flex-1 flex-col gap-5" aria-label="文章导航">
        <div className="flex flex-col gap-1">
          {primaryNavItems.map((item) => (
            <button
              key={item.view}
              type="button"
              className={navButtonClassName(!recommendation && view === item.view)}
              onClick={() => onSelectView(item.view)}
            >
              <span>{item.label}</span>
            </button>
          ))}
        </div>

        <div className="flex flex-col gap-1">
          <div className="px-2.5 text-xs font-medium text-muted-foreground">AI</div>
          {recommendationNavItems.map((item) => (
            <button
              key={item.recommendation}
              type="button"
              className={navButtonClassName(recommendation === item.recommendation)}
              onClick={() => onSelectRecommendation(item.recommendation)}
            >
              <span>{item.label}</span>
            </button>
          ))}
        </div>

        <div className="mt-auto flex flex-col gap-1">
          <Link
            to="/feeds"
            className="flex items-center gap-2 rounded-md px-2.5 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent/70 hover:text-foreground"
          >
            <RssIcon aria-hidden="true" className="size-4" />
            Feeds
          </Link>
        </div>
      </nav>

      <div className="mt-3 border-t pt-3">
        <div className="truncate px-2.5 text-xs text-muted-foreground">
          {userEmail ?? "当前用户"}
        </div>
        <div className="mt-2 flex items-center gap-1">
          <EmailDigestSettingsDialog />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="退出登录"
            loading={isLoggingOut}
            onClick={onLogout}
          >
            <LogOutIcon aria-hidden="true" className="size-4" />
          </Button>
        </div>
      </div>
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
  title,
  isLoading,
  isError,
  errorMessage,
}: {
  articles: ArticleListItem[] | undefined
  selectedId: string | null
  onSelect: (id: string) => void
  title: string
  isLoading: boolean
  isError: boolean
  errorMessage: string
}) {
  return (
    <aside className="flex w-[320px] shrink-0 flex-col border-r bg-background max-lg:w-full max-lg:border-r-0 max-lg:border-b">
      <div className="border-b px-4 py-3">
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
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

export function ArticleWorkbenchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedId = searchParams.get("id")
  const view = normalizeView(searchParams.get("view"))
  const recommendation = normalizeRecommendation(searchParams.get("recommendation"))
  const status = view === "unread" ? "unread" : normalizeStatus(searchParams.get("status"))
  const navigate = useNavigate()
  const isMobile = useIsMobile()

  const appChrome = useOutletContext<AppChromeContext>()

  const markedReadIdRef = useRef<string | null>(null)

  const articlesQuery = useQuery({
    queryKey: queryKeys.articles.list(status),
    queryFn: () =>
      apiGet<ArticleListItem[]>(
        `/articles?status_filter=${encodeURIComponent(status)}`,
      ),
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
    if (visibleArticles.length === 0) return
    if (selectedId && visibleArticles.some((article) => article.id === selectedId)) return

    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set("id", visibleArticles[0].id)
      return next
    })
  }, [isMobile, visibleArticles, selectedId, setSearchParams])

  useEffect(() => {
    if (isMobile) return

    function handleKeyDown(event: KeyboardEvent) {
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
  }, [isMobile, visibleArticles, selectedId, setSearchParams])

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

  function handleSelectView(nextView: ArticleView) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete("id")
      next.delete("recommendation")
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
      next.delete("view")
      next.delete("status")
      next.set("recommendation", nextRecommendation)
      return next
    })
  }

  if (isMobile) {
    return (
      <div className="min-h-[calc(100vh-49px)] bg-background">
        <ArticleListPanel
          articles={visibleArticles}
          selectedId={selectedId}
          onSelect={handleSelectArticle}
          title={streamTitle(view, recommendation)}
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
        view={view}
        recommendation={recommendation}
        userEmail={appChrome.email}
        isLoggingOut={appChrome.isLoggingOut}
        onLogout={appChrome.onLogout}
        onSelectView={handleSelectView}
        onSelectRecommendation={handleSelectRecommendation}
      />

      <ArticleListPanel
        articles={visibleArticles}
        selectedId={selectedId}
        onSelect={handleSelectArticle}
        title={streamTitle(view, recommendation)}
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
    </div>
  )
}
