import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { RssIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  apiDelete,
  apiGet,
  apiPost,
  type Feed,
  type FeedImportCreateRequest,
  type FeedImportJob,
  type FeedImportItemStatus,
} from "@/lib/api"
import { queryClient } from "@/lib/query-client"
import { queryKeys } from "@/lib/query-keys"

const CURRENT_IMPORT_STORAGE_KEY = "rsswise.currentFeedImportId"

const itemStatusLabel: Record<FeedImportItemStatus, string> = {
  pending: "等待中",
  created: "新建",
  subscribed: "已订阅",
  skipped: "跳过",
  failed: "失败",
}

function formatDate(value: string | null) {
  if (!value) return "尚未抓取"
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
}

function SkeletonCard() {
  return (
    <div className="flex animate-pulse flex-col gap-4 p-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0 flex-1">
        <div className="flex flex-col gap-3">
          <div className="h-4 w-2/5 rounded bg-muted" />
          <div className="h-3.5 w-3/5 rounded bg-muted" />
          <div className="h-3.5 w-2/5 rounded bg-muted" />
        </div>
      </div>
      <div className="flex gap-2">
        <div className="h-7 w-14 rounded-md bg-muted" />
        <div className="h-7 w-14 rounded-md bg-muted" />
      </div>
    </div>
  )
}

export function FeedsPage() {
  useEffect(() => {
    document.title = "Feed 管理 - RSSWise"
  }, [])

  const feedsQuery = useQuery({
    queryKey: queryKeys.feeds.list(),
    queryFn: () => apiGet<Feed[]>("/feeds"),
  })

  const addFeedMutation = useMutation({
    mutationFn: (url: string) => apiPost("/feeds", { url }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.feeds.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.articles.all })
    },
  })

  const refreshFeedMutation = useMutation({
    mutationFn: (feedId: string) => apiPost(`/feeds/${feedId}/refresh`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.feeds.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.articles.all })
    },
  })

  const deleteFeedMutation = useMutation({
    mutationFn: (feedId: string) => apiDelete(`/feeds/${feedId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.feeds.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.articles.all })
    },
  })

  function handleAddFeed(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const formData = new FormData(form)
    const url = String(formData.get("url") ?? "").trim()
    if (!url) return

    addFeedMutation.mutate(url, {
      onSuccess: () => form.reset(),
    })
  }

  const [isImportOpen, setIsImportOpen] = useState(false)
  const [importMode, setImportMode] = useState<"urls" | "opml">("urls")
  const [urlsText, setUrlsText] = useState("")
  const [opmlXml, setOpmlXml] = useState("")
  const [currentImportId, setCurrentImportId] = useState<string | null>(() =>
    window.localStorage.getItem(CURRENT_IMPORT_STORAGE_KEY),
  )

  const importQuery = useQuery({
    queryKey: currentImportId
      ? queryKeys.feedImports.detail(currentImportId)
      : queryKeys.feedImports.all,
    queryFn: () => apiGet<FeedImportJob>(`/feeds/imports/${currentImportId}`),
    enabled: Boolean(currentImportId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === "pending" || status === "processing" ? 2000 : false
    },
  })

  useEffect(() => {
    if (importQuery.data?.status === "completed" || importQuery.data?.status === "failed") {
      queryClient.invalidateQueries({ queryKey: queryKeys.feeds.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.articles.all })
    }
  }, [importQuery.data?.status])

  const createImportMutation = useMutation({
    mutationFn: (payload: FeedImportCreateRequest) =>
      apiPost<FeedImportJob>("/feeds/imports", payload),
    onSuccess: (job) => {
      setCurrentImportId(job.id)
      window.localStorage.setItem(CURRENT_IMPORT_STORAGE_KEY, job.id)
      queryClient.setQueryData(queryKeys.feedImports.detail(job.id), job)
    },
  })

  function handleOpmlFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    file.text().then(setOpmlXml).catch(() => setOpmlXml(""))
  }

  function handleCreateImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const payload: FeedImportCreateRequest =
      importMode === "urls"
        ? { source_type: "urls", urls_text: urlsText.trim() }
        : { source_type: "opml", opml_xml: opmlXml.trim() }
    createImportMutation.mutate(payload)
  }

  function dismissImportResult() {
    setCurrentImportId(null)
    window.localStorage.removeItem(CURRENT_IMPORT_STORAGE_KEY)
  }

  const mutationError = useMemo(
    () =>
      addFeedMutation.error ??
      refreshFeedMutation.error ??
      deleteFeedMutation.error ??
      createImportMutation.error ??
      importQuery.error,
    [
      addFeedMutation.error,
      refreshFeedMutation.error,
      deleteFeedMutation.error,
      createImportMutation.error,
      importQuery.error,
    ],
  )

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-2">
        <RssIcon aria-hidden="true" className="size-4 text-muted-foreground" />
        <h1 className="text-xl font-semibold text-foreground">Feed 管理</h1>
      </div>

      <form
        onSubmit={handleAddFeed}
        className="rounded-lg border bg-card p-4"
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="min-w-0 flex-1">
            <label className="mb-1.5 block text-sm font-medium text-foreground" htmlFor="url">
              Feed URL
            </label>
            <Input
              id="url"
              name="url"
              type="url"
              required
              disabled={addFeedMutation.isPending}
              placeholder="https://example.com/feed.xml"
            />
          </div>
          <Button
            type="submit"
            className="sm:w-auto"
            loading={addFeedMutation.isPending}
            disabled={addFeedMutation.isPending}
          >
            添加 Feed
          </Button>
          <Button type="button" variant="outline" onClick={() => setIsImportOpen((open) => !open)}>
            批量导入
          </Button>
        </div>
      </form>

      {isImportOpen ? (
        <form onSubmit={handleCreateImport} className="rounded-lg border bg-card p-4">
          <div className="mb-4 flex gap-2" role="tablist" aria-label="导入方式">
            <Button
              type="button"
              variant={importMode === "urls" ? "default" : "outline"}
              role="tab"
              aria-selected={importMode === "urls"}
              onClick={() => setImportMode("urls")}
            >
              多行 URL
            </Button>
            <Button
              type="button"
              variant={importMode === "opml" ? "default" : "outline"}
              role="tab"
              aria-selected={importMode === "opml"}
              onClick={() => setImportMode("opml")}
            >
              OPML 文件
            </Button>
          </div>

          {importMode === "urls" ? (
            <div className="space-y-2">
              <label className="block text-sm font-medium text-foreground" htmlFor="feed-import-urls">
                Feed URL 列表
              </label>
              <textarea
                id="feed-import-urls"
                className="min-h-36 w-full rounded-md border bg-background px-3 py-2 text-sm"
                value={urlsText}
                onChange={(event) => setUrlsText(event.target.value)}
                placeholder="https://example.com/feed.xml"
              />
            </div>
          ) : (
            <div className="space-y-2">
              <label className="block text-sm font-medium text-foreground" htmlFor="feed-import-opml">
                OPML 文件
              </label>
              <Input
                id="feed-import-opml"
                type="file"
                accept=".opml,.xml,text/xml,application/xml"
                onChange={handleOpmlFileChange}
              />
            </div>
          )}

          <div className="mt-4 flex gap-2">
            <Button
              type="submit"
              loading={createImportMutation.isPending}
              disabled={
                createImportMutation.isPending ||
                (importMode === "urls" ? !urlsText.trim() : !opmlXml.trim())
              }
            >
              开始导入
            </Button>
          </div>
        </form>
      ) : null}

      {mutationError ? (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-sm text-destructive-foreground">
          <span aria-hidden="true" className="size-1.5 rounded-full bg-destructive" />
          {mutationError.message}
        </div>
      ) : null}

      {importQuery.data ? (
        <div className="rounded-lg border bg-card p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-medium text-foreground">导入结果</h2>
              <p className="text-sm text-muted-foreground">
                已处理 {importQuery.data.processed_count} / {importQuery.data.total_count}
              </p>
            </div>
            <Button type="button" variant="outline" size="sm" onClick={dismissImportResult}>
              关闭
            </Button>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-sm text-muted-foreground">
            <span>新建 {importQuery.data.created_count}</span>
            <span>已订阅 {importQuery.data.subscribed_count}</span>
            <span>跳过 {importQuery.data.skipped_count}</span>
            <span>失败 {importQuery.data.failed_count}</span>
          </div>
          {importQuery.data.items.length > 0 ? (
            <div className="mt-4 divide-y rounded-md border">
              {importQuery.data.items.map((item) => (
                <div key={item.id} className="flex flex-col gap-1 p-3 text-sm sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <p className="font-medium text-foreground">{item.source_title || item.normalized_url}</p>
                    <p className="break-all text-muted-foreground">{item.normalized_url}</p>
                    {item.message ? <p className="text-muted-foreground">{item.message}</p> : null}
                  </div>
                  <span className="shrink-0 rounded border px-2 py-0.5 text-xs text-muted-foreground">
                    {itemStatusLabel[item.status]}
                  </span>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="divide-y overflow-hidden rounded-lg border bg-card">
        {feedsQuery.isLoading ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : feedsQuery.isError ? (
          <div className="flex items-center gap-2 p-6 text-sm text-destructive-foreground">
            <span aria-hidden="true" className="size-1.5 rounded-full bg-destructive" />
            {feedsQuery.error.message || "加载 Feed 失败"}
          </div>
        ) : feedsQuery.data?.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <RssIcon aria-hidden="true" className="size-9 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">暂无 Feed</p>
            <p className="text-xs text-muted-foreground/70">在上方输入 RSS 地址开始使用</p>
          </div>
        ) : (
          feedsQuery.data?.map((feed) => {
            const isRefreshing =
              refreshFeedMutation.isPending &&
              refreshFeedMutation.variables === feed.id
            const isDeleting =
              deleteFeedMutation.isPending &&
              deleteFeedMutation.variables === feed.id

            return (
              <div
                key={feed.id}
                className="flex flex-col gap-4 p-4 transition-colors hover:bg-accent/50 sm:flex-row sm:items-start sm:justify-between"
              >
                <div className="flex min-w-0 flex-col gap-2">
                  <div className="flex items-center gap-2">
                    {feed.favicon_url ? (
                      <img
                        src={feed.favicon_url}
                        alt=""
                        className="size-4 rounded-sm"
                      />
                    ) : null}
                    <h2 className="font-medium text-foreground">
                      {feed.title ?? feed.url}
                    </h2>
                  </div>
                  <p className="break-all text-sm text-muted-foreground">{feed.url}</p>
                  {feed.site_url ? (
                    <p className="break-all text-sm text-muted-foreground">
                      {feed.site_url}
                    </p>
                  ) : null}
                  <p className="text-sm text-muted-foreground">
                    最后抓取时间：{formatDate(feed.last_fetched_at)}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2 sm:justify-end">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    loading={isRefreshing}
                    disabled={isRefreshing || isDeleting}
                    onClick={() => refreshFeedMutation.mutate(feed.id)}
                  >
                    刷新
                  </Button>
                  <Button
                    type="button"
                    variant="destructive-outline"
                    size="sm"
                    loading={isDeleting}
                    disabled={isRefreshing || isDeleting}
                    onClick={() => deleteFeedMutation.mutate(feed.id)}
                  >
                    删除
                  </Button>
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
