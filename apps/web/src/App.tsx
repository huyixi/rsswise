import { Link, Outlet, useLocation } from "react-router-dom"

function navLinkClassName(active: boolean) {
  return active
    ? "rounded-md bg-accent px-2.5 py-1.5 text-sm font-medium text-foreground"
    : "rounded-md px-2.5 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
}

export function App() {
  const location = useLocation()
  const isWorkbench = location.pathname === "/articles"

  return (
    <>
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
        </nav>
      </header>
      {isWorkbench ? (
        <Outlet />
      ) : (
        <main className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-8 animate-fade-in md:px-6">
          <Outlet />
        </main>
      )}
    </>
  )
}
