import { useEffect, useState, type FormEvent } from "react"
import { useMutation } from "@tanstack/react-query"
import { Link, useNavigate } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { register } from "@/lib/auth"
import { queryClient } from "@/lib/query-client"
import { queryKeys } from "@/lib/query-keys"

export function RegisterPage() {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    document.title = "注册 - RSSWise"
  }, [])

  const registerMutation = useMutation({
    mutationFn: register,
    onSuccess: (user) => {
      queryClient.setQueryData(queryKeys.auth.me, user)
      navigate("/articles", { replace: true })
    },
    onError: (err) => setError(err.message),
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    const formData = new FormData(event.currentTarget)
    registerMutation.mutate({
      email: String(formData.get("email") ?? ""),
      password: String(formData.get("password") ?? ""),
    })
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-sm flex-col justify-center gap-6 px-4">
      <div className="flex flex-col gap-2">
        <h1 className="text-xl font-semibold text-foreground">注册 RSSWise</h1>
        <p className="text-sm text-muted-foreground">创建账号后直接开始订阅 Feed。</p>
      </div>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4 rounded-lg border bg-card p-4">
        <Input name="email" type="email" placeholder="邮箱" required />
        <Input name="password" type="password" placeholder="密码" required minLength={8} />
        {error ? <p className="text-sm text-destructive-foreground">{error}</p> : null}
        <Button type="submit" loading={registerMutation.isPending}>
          注册
        </Button>
      </form>
      <p className="text-center text-sm text-muted-foreground">
        已有账号？{" "}
        <Link className="font-medium text-foreground" to="/login">
          登录
        </Link>
      </p>
    </main>
  )
}
