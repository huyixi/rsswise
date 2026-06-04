import { apiGet, apiPost } from "@/lib/api"

export type CurrentUser = {
  id: string
  email: string
}

export type AuthPayload = {
  email: string
  password: string
}

export function getCurrentUser() {
  return apiGet<CurrentUser>("/auth/me")
}

export function login(payload: AuthPayload) {
  return apiPost<CurrentUser>("/auth/login", payload)
}

export function register(payload: AuthPayload) {
  return apiPost<CurrentUser>("/auth/register", payload)
}

export function logout() {
  return apiPost<void>("/auth/logout")
}
