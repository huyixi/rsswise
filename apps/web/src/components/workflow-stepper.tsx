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
    iconClass: "text-muted-foreground/50",
    borderClass: "border-border bg-background",
    labelClass: "text-muted-foreground",
    connectorClass: "bg-border",
  },
  processing: {
    icon: Loader2Icon,
    iconClass: "text-info-foreground",
    borderClass: "border-info/20 bg-info/5",
    labelClass: "text-foreground",
    connectorClass: "bg-info/20",
  },
  success: {
    icon: CheckCircle2Icon,
    iconClass: "text-success-foreground",
    borderClass: "border-success/20 bg-success/5",
    labelClass: "text-foreground",
    connectorClass: "bg-success/20",
  },
  failed: {
    icon: AlertCircleIcon,
    iconClass: "text-destructive-foreground",
    borderClass: "border-destructive/20 bg-destructive/5",
    labelClass: "text-destructive-foreground",
    connectorClass: "bg-destructive/20",
  },
}

export function WorkflowStepper({ steps }: { steps: Step[] }) {
  return (
    <div className="flex flex-col gap-0">
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
              <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                {step.description}
              </p>

              {step.status === "failed" && step.failureMessage && (
                <p className="mt-1 text-xs leading-relaxed text-destructive-foreground">
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
