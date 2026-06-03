import { CheckCircle2Icon, ClockIcon, AlertCircleIcon, Loader2Icon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export type StepStatus = "pending" | "processing" | "success" | "failed"

export interface Step {
  id: string
  label: string
  description: string
  status: StepStatus
  failureMessage?: string
  onRetry?: () => void
  retryLabel?: string
}

const statusConfig = {
  pending: {
    icon: ClockIcon,
    iconClass: "text-slate-300",
    borderClass: "border-slate-200 bg-white",
    labelClass: "text-slate-400",
    connectorClass: "bg-slate-200",
  },
  processing: {
    icon: Loader2Icon,
    iconClass: "text-blue-500",
    borderClass: "border-blue-200 bg-blue-50",
    labelClass: "text-blue-700",
    connectorClass: "bg-blue-200",
  },
  success: {
    icon: CheckCircle2Icon,
    iconClass: "text-emerald-500",
    borderClass: "border-emerald-200 bg-emerald-50",
    labelClass: "text-emerald-700",
    connectorClass: "bg-emerald-200",
  },
  failed: {
    icon: AlertCircleIcon,
    iconClass: "text-red-500",
    borderClass: "border-red-200 bg-red-50",
    labelClass: "text-red-700",
    connectorClass: "bg-red-200",
  },
}

export function WorkflowStepper({ steps }: { steps: Step[] }) {
  return (
    <div className="space-y-0">
      {steps.map((step, i) => {
        const config = statusConfig[step.status]
        const Icon = config.icon
        const isLast = i === steps.length - 1

        return (
          <div key={step.id} className="relative flex gap-3 pb-8 last:pb-0">
            {!isLast && (
              <div
                className={cn(
                  "absolute left-[15px] top-8 h-full w-0.5",
                  config.connectorClass,
                )}
              />
            )}

            <div className="relative shrink-0">
              <div
                className={cn(
                  "flex size-8 items-center justify-center rounded-full border-2",
                  config.borderClass,
                )}
              >
                <Icon
                  className={cn(
                    "size-4",
                    config.iconClass,
                    step.status === "processing" && "animate-spin",
                  )}
                />
              </div>
            </div>

            <div className="min-w-0 flex-1 pt-1">
              <p className={cn("text-sm font-medium leading-tight", config.labelClass)}>
                {step.label}
              </p>
              <p className="mt-0.5 text-xs leading-relaxed text-slate-500">
                {step.description}
              </p>

              {step.status === "failed" && step.failureMessage && (
                <p className="mt-1 text-xs leading-relaxed text-red-600">
                  {step.failureMessage}
                </p>
              )}

              {step.status === "failed" && step.onRetry && (
                <Button
                  type="button"
                  variant="outline"
                  size="xs"
                  className="mt-2"
                  onClick={step.onRetry}
                >
                  {step.retryLabel || "重试"}
                </Button>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
