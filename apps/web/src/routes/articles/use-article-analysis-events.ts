import { useEffect, useState } from "react"

import { openApiEventSource, type ArticleDetail } from "@/lib/api"
import { queryClient } from "@/lib/query-client"
import { queryKeys } from "@/lib/query-keys"

type AnalysisStreamState = {
  streamText: string
  isStreaming: boolean
  streamError: string | null
}

function parseEventData<T>(event: MessageEvent<string>): T | null {
  try {
    return JSON.parse(event.data) as T
  } catch {
    return null
  }
}

export function useArticleAnalysisEvents(article: ArticleDetail | undefined) {
  const [state, setState] = useState<AnalysisStreamState>({
    streamText: "",
    isStreaming: false,
    streamError: null,
  })

  useEffect(() => {
    if (!article) {
      setState({ streamText: "", isStreaming: false, streamError: null })
      return
    }

    if (
      article.analysis_status !== "pending" &&
      article.analysis_status !== "processing"
    ) {
      setState({ streamText: "", isStreaming: false, streamError: null })
      return
    }

    let hasReceivedChunk = false
    const source = openApiEventSource(
      `/articles/${encodeURIComponent(article.id)}/analysis/events`,
    )

    setState({ streamText: "", isStreaming: true, streamError: null })

    source.addEventListener("started", () => {
      setState((current) => ({
        ...current,
        isStreaming: true,
        streamError: null,
      }))
    })

    source.addEventListener("chunk", (event) => {
      const data = parseEventData<{ text?: string }>(
        event as MessageEvent<string>,
      )
      if (!data?.text) return
      hasReceivedChunk = true
      setState((current) => ({
        streamText: `${current.streamText}${data.text}`,
        isStreaming: true,
        streamError: null,
      }))
    })

    source.addEventListener("done", () => {
      source.close()
      setState((current) => ({
        ...current,
        isStreaming: false,
        streamError: null,
      }))
      queryClient.invalidateQueries({
        queryKey: queryKeys.articles.detail(article.id),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.articles.all,
      })
    })

    source.addEventListener("waiting_content", () => {
      source.close()
      setState({ streamText: "", isStreaming: false, streamError: null })
    })

    source.addEventListener("error", (event) => {
      if ("data" in event && typeof event.data === "string") {
        const data = parseEventData<{ message?: string }>(
          event as MessageEvent<string>,
        )
        source.close()
        setState({
          streamText: "",
          isStreaming: false,
          streamError: data?.message ?? "AI 分析失败",
        })
        queryClient.invalidateQueries({
          queryKey: queryKeys.articles.detail(article.id),
        })
        return
      }

      if (!hasReceivedChunk) {
        setState((current) => ({
          ...current,
          isStreaming: false,
          streamError: "AI 分析连接中断",
        }))
      }
    })

    return () => {
      source.close()
    }
  }, [article?.analysis_status, article?.id])

  return state
}
