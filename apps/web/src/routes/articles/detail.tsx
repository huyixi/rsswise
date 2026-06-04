import { useEffect, useRef } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { Link, Navigate, useParams } from "react-router-dom"
import { ArrowLeftIcon } from "lucide-react"

import { Spinner } from "@/components/ui/spinner"
import { useIsMobile } from "@/hooks/use-media-query"
import { apiGet, apiPost, type ArticleDetail } from "@/lib/api"
import { queryClient } from "@/lib/query-client"
import { queryKeys } from "@/lib/query-keys"
import { ArticleAiSummary, ArticleBody, ArticleHeader } from "./components"

function MobileArticleDetailContent({ id }: { id: string }) {
  const markedReadIdRef = useRef<string | null>(null)

  const articleQuery = useQuery({
    queryKey: queryKeys.articles.detail(id),
    queryFn: () => apiGet<ArticleDetail>(`/articles/${id}`),
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
    if (markedReadIdRef.current === id) return
    markedReadIdRef.current = id
    markReadMutation.mutate(id)
  }, [id, markReadMutation])

  useEffect(() => {
    document.title = articleQuery.data?.title
      ? `${articleQuery.data.title} - RSSWise`
      : "文章详情 - RSSWise"
  }, [articleQuery.data?.title])

  if (articleQuery.isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-20 text-sm text-muted-foreground">
        <Spinner />
        <span>加载文章中</span>
      </div>
    )
  }

  if (articleQuery.isError) {
    return (
      <div className="py-8 text-sm text-destructive-foreground">
        {articleQuery.error.message || "加载文章失败"}
      </div>
    )
  }

  const article = articleQuery.data
  if (!article) return null

  return (
    <article className="flex flex-col gap-6 py-5">
      <Link
        to="/articles"
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeftIcon aria-hidden="true" className="size-4" />
        返回文章列表
      </Link>

      <ArticleHeader article={article} titleClassName="text-2xl" />
      <ArticleAiSummary article={article} />
      <ArticleBody contentMarkdown={article.content_markdown} className="pt-5" />
    </article>
  )
}

export function ArticleDetailPage() {
  const { id } = useParams<{ id: string }>()
  const isMobile = useIsMobile()

  if (!id) {
    return <div className="text-sm text-destructive-foreground">文章 ID 无效</div>
  }

  if (!isMobile) {
    return <Navigate to={`/articles?id=${encodeURIComponent(id)}`} replace />
  }

  return <MobileArticleDetailContent id={id} />
}
