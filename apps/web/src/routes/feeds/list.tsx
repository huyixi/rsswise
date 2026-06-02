import { useEffect, type FormEvent } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
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
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">Feed 管理</h1>
      </div>

      <form
        onSubmit={handleAddFeed}
        className="flex flex-col gap-2 rounded border border-slate-200 bg-white p-4 sm:flex-row"
      >
        <label className="sr-only" htmlFor="url">
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
        <Button
          type="submit"
          className="sm:w-auto"
          loading={addFeedMutation.isPending}
          disabled={addFeedMutation.isPending}
        >
          添加 Feed
        </Button>
      </form>

      {mutationError ? (
        <p className="text-sm text-red-600">{mutationError.message}</p>
      ) : null}

      <div className="divide-y rounded border border-slate-200 bg-white">
        {feedsQuery.isLoading ? (
          <div className="flex items-center gap-2 p-6 text-sm text-slate-500">
            <Spinner />
            <span>加载 Feed 中</span>
          </div>
        ) : feedsQuery.isError ? (
          <div className="p-6 text-sm text-red-600">
            {feedsQuery.error.message || "加载 Feed 失败"}
          </div>
        ) : feedsQuery.data?.length === 0 ? (
          <div className="p-6 text-sm text-slate-500">暂无 Feed</div>
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
                className="flex flex-col gap-4 p-4 sm:flex-row sm:items-start sm:justify-between"
              >
                <div className="min-w-0 space-y-2">
                  <div className="flex items-center gap-2">
                    {feed.favicon_url ? (
                      <img
                        src={feed.favicon_url}
                        alt=""
                        className="h-4 w-4 rounded-sm"
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
