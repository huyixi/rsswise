import type { ReactNode } from "react"
import { QueryClientProvider } from "@tanstack/react-query"
import { RouterProvider } from "react-router-dom"
import { queryClient } from "./lib/query-client"
import { router } from "./router"

export function Providers({ children }: { children?: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children ?? <RouterProvider router={router} />}
    </QueryClientProvider>
  )
}
