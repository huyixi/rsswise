import { Link, Outlet } from "react-router-dom"

export function App() {
  return (
    <>
      <header className="border-b border-slate-200 bg-white shadow-xs">
        <nav className="mx-auto flex max-w-5xl items-center gap-6 px-4 py-3">
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
      <main className="mx-auto max-w-5xl px-4 py-6 animate-fade-in">
        <Outlet />
      </main>
    </>
  )
}
