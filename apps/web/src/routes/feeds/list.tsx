import { useEffect, type FormEvent } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { RssIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { apiDelete, apiGet, apiPost, type Feed } from "@/lib/api"
import { queryClient } from "@/lib/query-client"
import { queryKeys } from "@/lib/query-keys"

function formatDate(value: string | null) {
  if (!value) return "尚未抓取"
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
}

function SkeletonCard() {
  return (
    <div className="flex flex-col gap-4 p-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0 flex-1 space-y-3">
        <div className="flex items-center gap-2">
          <div className="size-4 rounded bg-slate-200" />
          <div className="h-5 w-2/5 rounded bg-slate-200" />
        </div>
        <div className="h-4 w-3/5 rounded bg-slate-100" />
        <div className="h-4 w-2/5 rounded bg-slate-100" />
      </div>
      <div className="flex gap-2">
        <div className="h-7 w-14 rounded-lg bg-slate-200" />
        <div className="h-7 w-14 rounded-lg bg-slate-200" />
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

  const mutationError =
    addFeedMutation.error ?? refreshFeedMutation.error ?? deleteFeedMutation.error

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <RssIcon className="size-5 text-slate-400" />
        <h1 className="text-2xl font-semibold tracking-tight">Feed 管理</h1>
      </div>

      <form
        onSubmit={handleAddFeed}
        className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="min-w-0 flex-1">
            <label className="mb-1.5 block text-sm font-medium text-slate-700" htmlFor="url">
              Feed URL
            </label>
            <Input
              id="url"
              name="url"
              type="url"
              required
              nativeInput
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
        </div>
      </form>

      {mutationError ? (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <span className="size-1.5 rounded-full bg-red-500" />
          {mutationError.message}
        </div>
      ) : null}

      <div className="divide-y rounded-xl border border-slate-200 bg-white shadow-sm">
        {feedsQuery.isLoading ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : feedsQuery.isError ? (
          <div className="flex items-center gap-2 p-6 text-sm text-red-600">
            <span className="size-1.5 rounded-full bg-red-500" />
            {feedsQuery.error.message || "加载 Feed 失败"}
          </div>
        ) : feedsQuery.data?.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <RssIcon className="size-10 text-slate-300" />
            <p className="text-sm text-slate-500">暂无 Feed</p>
            <p className="text-xs text-slate-400">在上方输入 RSS 地址开始使用</p>
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
                className="flex flex-col gap-4 p-4 transition-colors hover:bg-slate-50 sm:flex-row sm:items-start sm:justify-between"
              >
                <div className="min-w-0 space-y-2">
                  <div className="flex items-center gap-2">
                    {feed.favicon_url ? (
                      <img
                        src={feed.favicon_url}
                        alt=""
                        className="size-4 rounded-sm"
                      />
                    ) : null}
                    <h2 className="font-medium text-slate-950">
                      {feed.title ?? feed.url}
                    </h2>
                  </div>
                  <p className="break-all text-sm text-slate-500">{feed.url}</p>
                  {feed.site_url ? (
                    <p className="break-all text-sm text-slate-500">
                      {feed.site_url}
                    </p>
                  ) : null}
                  <p className="text-sm text-slate-500">
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
