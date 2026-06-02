import { cn } from "@/lib/utils";
import type { ReadingRecommendation } from "@/lib/api";

const labels: Record<ReadingRecommendation, string> = {
  deep_read: "值得精读",
  skim: "适合略读",
  skip: "可以跳过",
};

const styles: Record<ReadingRecommendation, string> = {
  deep_read:
    "border-emerald-200 bg-emerald-50 text-emerald-700",
  skim:
    "border-blue-200 bg-blue-50 text-blue-700",
  skip:
    "border-amber-200 bg-amber-50 text-amber-700",
};

export function RecommendationBadge({
  value,
}: {
  value: ReadingRecommendation;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        styles[value],
      )}
    >
      {labels[value]}
    </span>
  );
}
