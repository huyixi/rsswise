import { useMutation, useQuery } from "@tanstack/react-query"
import { LogOutIcon } from "lucide-react"
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom"

import { EmailDigestSettingsDialog } from "@/components/email-digest-settings-dialog"
import { Button } from "@/components/ui/button"
import { getCurrentUser, logout } from "@/lib/auth"
import { queryClient } from "@/lib/query-client"
import { queryKeys } from "@/lib/query-keys"

function navLinkClassName(active: boolean) {
  return active
    ? "rounded-md bg-accent px-2.5 py-1.5 text-sm font-medium text-foreground"
    : "rounded-md px-2.5 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
}

function AppHeader({
  email,
  isLoggingOut,
  onLogout,
}: {
  email: string | undefined
  isLoggingOut: boolean
  onLogout: () => void
}) {
  const location = useLocation()

  return (
    <header className="border-b bg-background">
      <nav className="flex h-12 items-center gap-6 px-4 md:px-6">
        <Link to="/articles" className="text-sm font-semibold text-foreground">
          RSSWise
        </Link>
        <div className="flex items-center gap-1">
          <Link
            to="/articles"
            aria-current={location.pathname === "/articles" ? "page" : undefined}
            className={navLinkClassName(location.pathname === "/articles")}
          >
            文章
          </Link>
          <Link
            to="/feeds"
            aria-current={location.pathname === "/feeds" ? "page" : undefined}
            className={navLinkClassName(location.pathname === "/feeds")}
          >
            Feed
          </Link>
        </div>
        <div className="ml-auto flex min-w-0 items-center gap-2">
          <span className="hidden truncate text-sm text-muted-foreground sm:block">
            {email}
          </span>
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
      </nav>
    </header>
  )
}

export function App() {
  const navigate = useNavigate()
  const location = useLocation()
  const isWorkbench = location.pathname === "/articles"
  const meQuery = useQuery({
    queryKey: queryKeys.auth.me,
    queryFn: getCurrentUser,
    retry: false,
  })
  const logoutMutation = useMutation({
    mutationFn: logout,
    onSettled: () => {
      queryClient.clear()
      navigate("/login", { replace: true })
    },
  })

  return (
    <>
      {!isWorkbench ? (
        <AppHeader
          email={meQuery.data?.email}
          isLoggingOut={logoutMutation.isPending}
          onLogout={() => logoutMutation.mutate()}
        />
      ) : null}
      {isWorkbench ? (
        <Outlet
          context={{
            email: meQuery.data?.email,
            isLoggingOut: logoutMutation.isPending,
            onLogout: () => logoutMutation.mutate(),
          }}
        />
      ) : (
        <main className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-8 animate-fade-in md:px-6">
          <Outlet />
        </main>
      )}
    </>
  )
}