import { createBrowserRouter } from "react-router-dom"
import { App } from "./App"
import { ArticleDetailPage } from "./routes/articles/detail"
import { ArticlesPage } from "./routes/articles/list"
import { FeedsPage } from "./routes/feeds/list"
import { HomePage } from "./routes/home"

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "articles", element: <ArticlesPage /> },
      { path: "articles/:id", element: <ArticleDetailPage /> },
      { path: "feeds", element: <FeedsPage /> },
    ],
  },
])
