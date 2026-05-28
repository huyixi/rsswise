import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiGet } from "@/lib/api";
import { addFeed, deleteFeed, refreshFeed } from "./actions";

export const dynamic = "force-dynamic";

type Feed = {
  id: string;
  title: string;
  url: string;
  site_url: string | null;
  favicon_url: string | null;
  last_fetched_at: string | null;
};

function formatDate(value: string | null) {
  if (!value) return "尚未抓取";
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default async function FeedsPage() {
  const feeds = await apiGet<Feed[]>("/feeds");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">Feed 管理</h1>
      </div>

      <form
        action={addFeed}
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
          placeholder="https://example.com/feed.xml"
        />
        <Button type="submit" className="sm:w-auto">
          添加 Feed
        </Button>
      </form>

      <div className="divide-y rounded border border-slate-200 bg-white">
        {feeds.length === 0 ? (
          <div className="p-6 text-sm text-slate-500">暂无 Feed</div>
        ) : (
          feeds.map((feed) => (
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
                  <h2 className="font-medium text-slate-950">{feed.title}</h2>
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
                <form action={refreshFeed.bind(null, feed.id)}>
                  <Button type="submit" variant="outline" size="sm">
                    刷新
                  </Button>
                </form>
                <form action={deleteFeed.bind(null, feed.id)}>
                  <Button type="submit" variant="destructive-outline" size="sm">
                    删除
                  </Button>
                </form>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
