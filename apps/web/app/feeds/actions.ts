"use server";

import { revalidatePath } from "next/cache";

import { apiPost } from "@/lib/api";

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function addFeed(formData: FormData) {
  const url = String(formData.get("url") ?? "").trim();
  if (!url) return;

  const response = await fetch(`${apiBaseUrl}/feeds`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!response.ok) {
    throw new Error("add feed failed");
  }

  revalidatePath("/feeds");
  revalidatePath("/articles");
}

export async function refreshFeed(feedId: string) {
  await apiPost(`/feeds/${feedId}/refresh`);
  revalidatePath("/feeds");
}

export async function deleteFeed(feedId: string) {
  const response = await fetch(`${apiBaseUrl}/feeds/${feedId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error("delete feed failed");
  }

  revalidatePath("/feeds");
  revalidatePath("/articles");
}
