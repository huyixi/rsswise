import { createBrowserRouter } from "react-router-dom"
import { App } from "./App"
import { AuthGate } from "./components/auth-gate"
import { FeedsPage } from "./routes/feeds/list"
import { HomePage } from "./routes/home"
import { ArticleWorkbenchPage } from "./routes/articles/workbench"
import { ArticleDetailPage } from "./routes/articles/detail"
import { LoginPage } from "./routes/login"
import { RegisterPage } from "./routes/register"

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  {
    element: <AuthGate />,
    children: [
      {
        path: "/",
        element: <App />,
        children: [
          { index: true, element: <HomePage /> },
          { path: "articles", element: <ArticleWorkbenchPage /> },
          { path: "articles/:id", element: <ArticleDetailPage /> },
          { path: "feeds", element: <FeedsPage /> },
        ],
      },
    ],
  },
])
