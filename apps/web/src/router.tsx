import { createBrowserRouter, Navigate } from "react-router-dom"
import { App } from "./App"
import { FeedsPage } from "./routes/feeds/list"
import { HomePage } from "./routes/home"
import { ArticleWorkbenchPage } from "./routes/articles/workbench"

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "articles", element: <ArticleWorkbenchPage /> },
      { path: "articles/:id", element: <Navigate to="/articles" replace /> },
      { path: "feeds", element: <FeedsPage /> },
    ],
  },
])
