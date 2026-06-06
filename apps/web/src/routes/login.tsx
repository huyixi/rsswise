import { useEffect, useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"
import { Link, useLocation, useNavigate } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { login } from "@/lib/auth"
import { queryClient } from "@/lib/query-client"
import { queryKeys } from "@/lib/query-keys"

type LoginLocationState = {
  from?: unknown
}

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    document.title = "登录 - RSSWise"
  }, [])

  const loginMutation = useMutation({
    mutationFn: login,
    onSuccess: (user) => {
      const state = location.state as LoginLocationState | null
      queryClient.setQueryData(queryKeys.auth.me, user)
      navigate(typeof state?.from === "string" ? state.from : "/articles", {
        replace: true,
      })
    },
    onError: (err) => setError(err.message),
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    const formData = new FormData(event.currentTarget)
    loginMutation.mutate({
      email: String(formData.get("email") ?? ""),
      password: String(formData.get("password") ?? ""),
    })
  }

  function handleDemoLogin() {
    setError(null)
    loginMutation.mutate({
      email: "demo@huyixi.com",
      password: "demo@huyixi.com",
    })
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-sm flex-col justify-center gap-6 px-4">
      <div className="flex flex-col gap-2">
        <h1 className="text-xl font-semibold text-foreground">登录 RSSWise</h1>
        <p className="text-sm text-muted-foreground">使用邮箱和密码继续阅读。</p>
      </div>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4 rounded-lg border bg-card p-4">
        <Input name="email" type="email" placeholder="邮箱" required />
        <Input name="password" type="password" placeholder="密码" required minLength={8} />
        {error ? <p className="text-sm text-destructive-foreground">{error}</p> : null}
        <Button type="submit" loading={loginMutation.isPending}>
          登录
        </Button>
        <Button type="button" variant="outline" onClick={handleDemoLogin} loading={loginMutation.isPending}>
          立即体验
        </Button>
      </form>
      <p className="text-center text-sm text-muted-foreground">
        还没有账号？{" "}
        <Link className="font-medium text-foreground" to="/register">
          注册
        </Link>
      </p>
    </main>
  )
}
