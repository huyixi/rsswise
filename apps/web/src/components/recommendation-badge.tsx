import { Badge } from "@/components/ui/badge";
import type { ReadingRecommendation } from "@/lib/api";

const labels: Record<ReadingRecommendation, string> = {
  deep_read: "值得精读",
  skim: "适合略读",
  skip: "可以跳过",
};

const variants: Record<
  ReadingRecommendation,
  "success" | "info" | "warning"
> = {
  deep_read: "success",
  skim: "info",
  skip: "warning",
};

export function RecommendationBadge({
  value,
}: {
  value: ReadingRecommendation;
}) {
  return (
    <Badge size="lg" variant={variants[value]}>
      {labels[value]}
    </Badge>
  );
}
