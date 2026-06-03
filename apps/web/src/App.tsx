import { Link, Outlet, useLocation } from "react-router-dom"

export function App() {
  const location = useLocation()
  const isWorkbench = location.pathname === "/articles"

  return (
    <>
      <header className="border-b border-slate-200 bg-white shadow-xs">
        <nav className="flex items-center gap-6 px-5 py-3">
          <Link to="/articles" className="text-lg font-bold tracking-tight text-slate-900">
            RSSWise
          </Link>
          <div className="flex gap-1">
            <Link
              to="/articles"
              className="rounded-md px-3 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
            >
              文章
            </Link>
            <Link
              to="/feeds"
              className="rounded-md px-3 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
            >
              Feed
            </Link>
          </div>
        </nav>
      </header>
      {isWorkbench ? (
        <Outlet />
      ) : (
        <main className="mx-auto max-w-5xl px-4 py-6 animate-fade-in">
          <Outlet />
        </main>
      )}
    </>
  )
}
