import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { ReadingRecommendation } from "@/lib/api";

const labels: Record<ReadingRecommendation, string> = {
  deep_read: "值得精读",
  skim: "适合略读",
  skip: "可以跳过",
};

const variants: Record<ReadingRecommendation, BadgeProps["variant"]> = {
  deep_read: "success",
  skim: "secondary",
  skip: "warning",
};

export function RecommendationBadge({
  value,
}: {
  value: ReadingRecommendation;
}) {
  return (
    <Badge size="sm" variant={variants[value]}>
      {labels[value]}
    </Badge>
  );
}
