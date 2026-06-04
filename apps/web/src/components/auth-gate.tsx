import { useQuery } from "@tanstack/react-query"
import { Navigate, Outlet, useLocation } from "react-router-dom"

import { getCurrentUser } from "@/lib/auth"
import { queryKeys } from "@/lib/query-keys"

export function AuthGate() {
  const location = useLocation()
  const meQuery = useQuery({
    queryKey: queryKeys.auth.me,
    queryFn: getCurrentUser,
    retry: false,
  })

  if (meQuery.isLoading) {
    return (
      <main className="flex min-h-[50vh] items-center justify-center text-sm text-muted-foreground">
        加载中
      </main>
    )
  }

  if (meQuery.isError) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return <Outlet />
}
