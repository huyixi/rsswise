import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { MailIcon, SettingsIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Combobox,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
  ComboboxPopup,
} from "@/components/ui/combobox";
import {
  Dialog,
  DialogFooter,
  DialogHeader,
  DialogPanel,
  DialogPopup,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { toastManager } from "@/components/ui/toast";
import {
  apiGet,
  apiPost,
  apiPut,
  type EmailDigestSettings,
  type EmailDigestSettingsUpdate,
} from "@/lib/api";
import { queryClient } from "@/lib/query-client";
import { queryKeys } from "@/lib/query-keys";

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

const INTERVAL_VALUES = [1, 2, 3, 4, 5, 6, 7, 15, 30] as const;

const INTERVAL_ITEMS = INTERVAL_VALUES.map((v) => ({
  value: v,
  label: `${v} 天`,
}));

function calculateNextSendTime(
  lastRunDate: string | null,
  intervalDays: number,
  sendTime: string,
): string {
  const now = shanghaiNow();
  let nextDate = lastRunDate
    ? addDays(lastRunDate, intervalDays)
    : now.date;

  const stepDays = lastRunDate ? intervalDays : 1;
  while (`${nextDate} ${sendTime}` <= now.dateTime) {
    nextDate = addDays(nextDate, stepDays);
  }

  return `${nextDate} ${sendTime}`;
}

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const h = String(d.getHours()).padStart(2, "0");
  const m = String(d.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day} ${h}:${m}`;
}

function renderSendStatus(settings: EmailDigestSettings): string {
  const count = settings.last_sent_article_count;
  switch (settings.last_send_status) {
    case "success":
      return `\u2705 发送成功 \xb7 ${count} 篇`;
    case "failed":
      return "\u274c 发送失败";
    case "skipped_no_articles":
      return "\u23ed 无新增文章";
    case "skipped_disabled":
    case "skipped_missing_recipient":
    case "skipped_before_send_time":
    case "skipped_already_ran_today":
    case "skipped_interval_not_due":
      return "";
    default:
      return "";
  }
}

function addDays(dateString: string, days: number): string {
  const [year, month, day] = dateString.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day + days));
  return [
    date.getUTCFullYear(),
    String(date.getUTCMonth() + 1).padStart(2, "0"),
    String(date.getUTCDate()).padStart(2, "0"),
  ].join("-");
}

function shanghaiNow(): { date: string; dateTime: string } {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(new Date());
  const getPart = (type: string) =>
    parts.find((part) => part.type === type)?.value ?? "00";
  const date = `${getPart("year")}-${getPart("month")}-${getPart("day")}`;
  return {
    date,
    dateTime: `${date} ${getPart("hour")}:${getPart("minute")}`,
  };
}

function getErrorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "请求失败";
}

function isValidEmail(value: string): boolean {
  return EMAIL_RE.test(value.trim());
}

function payloadKey(payload: EmailDigestSettingsUpdate): string {
  return JSON.stringify(payload);
}

interface EmailDigestSettingsFormProps {
  settings: EmailDigestSettings;
  queryError: Error | null;
}

function EmailDigestSettingsForm({
  settings,
  queryError,
}: EmailDigestSettingsFormProps) {
  const [email, setEmail] = useState(settings.recipient_email ?? "");
  const [enabled, setEnabled] = useState(settings.enabled);
  const [sendInterval, setSendInterval] = useState(
    settings.send_interval_days,
  );
  const [sendTime, setSendTime] = useState(settings.send_time);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isDirty, setIsDirty] = useState(false);

  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dirtyRef = useRef(false);

  const emailRef = useRef(email);
  const enabledRef = useRef(enabled);
  const sendIntervalRef = useRef(sendInterval);
  const sendTimeRef = useRef(sendTime);
  const saveMutateRef = useRef<
    (payload: EmailDigestSettingsUpdate) => void
  >(() => undefined);

  useEffect(() => {
    emailRef.current = email;
    enabledRef.current = enabled;
    sendIntervalRef.current = sendInterval;
    sendTimeRef.current = sendTime;
  }, [email, enabled, sendInterval, sendTime]);

  function markDirty() {
    dirtyRef.current = true;
    setIsDirty(true);
  }

  function buildPayload(): EmailDigestSettingsUpdate {
    const trimmed = emailRef.current.trim();
    return {
      recipient_email: trimmed || null,
      enabled: enabledRef.current,
      send_interval_days: sendIntervalRef.current,
      send_time: sendTimeRef.current,
    };
  }

  function isCurrentPayloadValid() {
    const trimmed = emailRef.current.trim();
    return !(enabledRef.current && !trimmed) && !(trimmed && !isValidEmail(trimmed));
  }

  function clearSaveTimer() {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
  }

  const saveMutation = useMutation({
    mutationFn: (payload: EmailDigestSettingsUpdate) =>
      apiPut<EmailDigestSettings>("/settings/email-digest", payload),
    onSuccess: (data, payload) => {
      queryClient.setQueryData(queryKeys.settings.emailDigest(), data);
      setSaveError(null);
      if (payloadKey(payload) === payloadKey(buildPayload())) {
        dirtyRef.current = false;
        setIsDirty(false);
      }
    },
    onError: (err) => {
      const message = getErrorMessage(err);
      setSaveError(message);
      toastManager.add({
        id: "email-digest-save-error",
        type: "error",
        title: "保存失败",
        description: message,
      });
    },
  });

  useEffect(() => {
    saveMutateRef.current = saveMutation.mutate;
  }, [saveMutation.mutate]);

  useEffect(() => {
    if (!isDirty || !isCurrentPayloadValid()) return;

    saveTimerRef.current = setTimeout(() => {
      saveMutateRef.current(buildPayload());
    }, 400);
    return () => {
      clearSaveTimer();
    };
  }, [email, enabled, sendInterval, sendTime, isDirty]);

  const flushSave = useCallback(() => {
    clearSaveTimer();
    if (dirtyRef.current && isCurrentPayloadValid()) {
      saveMutateRef.current(buildPayload());
    }
  }, []);

  useEffect(() => {
    return flushSave;
  }, [flushSave]);

  const testMutation = useMutation({
    mutationFn: async () => {
      const trimmed = emailRef.current.trim();
      if (!trimmed) throw new Error("请先填写收件邮箱");
      if (!isValidEmail(trimmed)) throw new Error("邮箱格式不正确");

      clearSaveTimer();
      try {
        const saved = await apiPut<EmailDigestSettings>(
          "/settings/email-digest",
          buildPayload(),
        );
        queryClient.setQueryData(queryKeys.settings.emailDigest(), saved);
        setSaveError(null);
        dirtyRef.current = false;
        setIsDirty(false);
      } catch (err) {
        const message = getErrorMessage(err);
        setSaveError(message);
        toastManager.add({
          id: "email-digest-save-error",
          type: "error",
          title: "保存失败",
          description: message,
        });
        return { sent: false };
      }

      try {
        await apiPost("/settings/email-digest/test");
        return { sent: true };
      } catch (err) {
        // eslint-disable-next-line preserve-caught-error -- cause not available in es2020 target
        throw new Error(getErrorMessage(err));
      }
    },
    onSuccess: (result) => {
      if (!result.sent) return;
      toastManager.add({
        type: "success",
        title: "测试邮件已发送",
        description: `已发送至 ${emailRef.current.trim()}`,
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.settings.emailDigest(),
      });
    },
    onError: (err) => {
      toastManager.add({
        type: "error",
        title: "发送失败",
        description: err.message,
      });
    },
  });

  const emailError = (() => {
    if (enabled && !email.trim()) return "启用后需要填写收件邮箱";
    if (email.trim() && !isValidEmail(email)) return "邮箱格式不正确";
    return null;
  })();

  const error = saveError ?? queryError?.message ?? null;

  return (
    <>
      <DialogPanel className="flex flex-col gap-4">
        <Field>
          <FieldLabel htmlFor="email-digest-recipient">收件邮箱</FieldLabel>
          <Input
            id="email-digest-recipient"
            type="email"
            value={email}
            onChange={(event) => {
              emailRef.current = event.target.value;
              markDirty();
              setEmail(event.target.value);
            }}
            placeholder="reader@example.com"
          />
          {emailError ? (
            <p className="text-sm text-destructive-foreground">{emailError}</p>
          ) : null}
        </Field>

        <Field>
          <FieldLabel>发送间隔天数</FieldLabel>
          <Combobox
            items={INTERVAL_ITEMS}
            value={sendInterval}
            onValueChange={(value) => {
              sendIntervalRef.current = value as number;
              markDirty();
              setSendInterval(value as number);
            }}
          >
            <ComboboxInput
              id="email-digest-interval"
              placeholder="选择天数..."
              showClear={false}
            />
            <ComboboxPopup>
              <ComboboxEmpty>无匹配结果</ComboboxEmpty>
              <ComboboxList>
                {(item) => (
                  <ComboboxItem key={item.value} value={item.value}>
                    {item.label}
                  </ComboboxItem>
                )}
              </ComboboxList>
            </ComboboxPopup>
          </Combobox>
          <FieldDescription>
            每天在此时间检查，有新增文章即发送 EPUB 附件。
          </FieldDescription>
        </Field>

        <Field>
          <FieldLabel htmlFor="email-digest-send-time">发送时间</FieldLabel>
          <Input
            id="email-digest-send-time"
            type="time"
            value={sendTime}
            onChange={(event) => {
              sendTimeRef.current = event.target.value;
              markDirty();
              setSendTime(event.target.value);
            }}
          />
          <FieldDescription>使用 Asia/Shanghai 时区。</FieldDescription>
        </Field>

        <div className="flex items-center justify-between gap-4 rounded-lg border bg-card p-3">
          <div>
            <p className="text-sm font-medium text-foreground">
              启用文章推送
            </p>
            <p className="text-xs text-muted-foreground">
              开启后按设定的间隔和时间推送文章。
            </p>
          </div>
          <Switch
            aria-label="启用文章推送"
            checked={enabled}
            onCheckedChange={(checked) => {
              enabledRef.current = checked;
              markDirty();
              setEnabled(checked);
            }}
          />
        </div>

        <div className="flex items-start gap-2 rounded-lg border bg-card p-3 text-sm text-muted-foreground">
          <MailIcon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <div className="min-w-0 space-y-2">
            {settings.last_sent_at ? (
              <div>
                <p className="text-xs text-muted-foreground">上次发送</p>
                <p className="text-foreground">
                  {formatDateTime(settings.last_sent_at)}{" "}
                  {renderSendStatus(settings)}
                </p>
              </div>
            ) : (
              <p className="text-muted-foreground">暂无发送记录</p>
            )}
            {settings.last_send_error ? (
              <p className="break-all text-xs text-destructive-foreground">
                {settings.last_send_error}
              </p>
            ) : null}
            {enabled && email.trim() && isValidEmail(email) ? (
              <div>
                <p className="text-xs text-muted-foreground">下次预计</p>
                <p className="text-foreground">
                  {calculateNextSendTime(
                    settings.last_run_date,
                    sendInterval,
                    sendTime,
                  )}
                </p>
              </div>
            ) : null}
          </div>
        </div>

        {error ? (
          <p className="text-sm text-destructive-foreground">{error}</p>
        ) : null}
      </DialogPanel>
      <DialogFooter>
        <Button
          type="button"
          variant="outline"
          loading={testMutation.isPending}
          disabled={
            testMutation.isPending ||
            !email.trim() ||
            !isValidEmail(email)
          }
          onClick={() => testMutation.mutate()}
        >
          发送测试邮件
        </Button>
      </DialogFooter>
    </>
  );
}

export function EmailDigestSettingsDialog() {
  const [open, setOpen] = useState(false);
  const [formKey, setFormKey] = useState(0);

  const settingsQuery = useQuery({
    queryKey: queryKeys.settings.emailDigest(),
    queryFn: () => apiGet<EmailDigestSettings>("/settings/email-digest"),
    enabled: open,
  });
  const settings = settingsQuery.data;

  const handleOpenChange = useCallback((nextOpen: boolean) => {
    if (!nextOpen) {
      setFormKey((k) => k + 1);
    }
    setOpen(nextOpen);
  }, []);

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button aria-label="文章推送设置" size="icon" variant="ghost" />
        }
      >
        <SettingsIcon aria-hidden="true" />
      </DialogTrigger>
      <DialogPopup>
        <DialogHeader>
          <DialogTitle>文章推送</DialogTitle>
        </DialogHeader>
        {open && settings ? (
          <EmailDigestSettingsForm
            key={formKey}
            settings={settings}
            queryError={settingsQuery.error}
          />
        ) : (
          <DialogPanel>
            <p className="text-sm text-muted-foreground">
              {settingsQuery.error ? settingsQuery.error.message : "正在加载设置..."}
            </p>
          </DialogPanel>
        )}
      </DialogPopup>
    </Dialog>
  );
}
