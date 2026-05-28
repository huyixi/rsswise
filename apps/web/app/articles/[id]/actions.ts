"use server";

import { revalidatePath } from "next/cache";

import { apiPost } from "@/lib/api";

export async function markUnread(articleId: string) {
  await apiPost(`/articles/${articleId}/unread`);
  revalidatePath(`/articles/${articleId}`);
  revalidatePath("/articles");
}

export async function reanalyze(articleId: string) {
  await apiPost(`/articles/${articleId}/reanalyze`);
  revalidatePath(`/articles/${articleId}`);
}
