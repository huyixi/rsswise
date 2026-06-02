import { Link, Outlet } from "react-router-dom"

export function App() {
  return (
    <>
      <header className="border-b bg-white">
        <nav className="mx-auto flex max-w-5xl gap-4 px-4 py-3">
          <Link to="/articles" className="font-semibold">
            RSSWise
          </Link>
          <Link to="/articles">文章</Link>
          <Link to="/feeds">Feed</Link>
        </nav>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <Outlet />
      </main>
    </>
  )
}
