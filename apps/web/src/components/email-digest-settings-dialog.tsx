import { useState, type FormEvent } from "react";
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
  DialogDescription,
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
import {
  apiGet,
  apiPost,
  apiPut,
  type EmailDigestSettings,
  type EmailDigestSettingsUpdate,
} from "@/lib/api";
import { queryClient } from "@/lib/query-client";
import { queryKeys } from "@/lib/query-keys";

function statusLabel(status: string | null) {
  switch (status) {
    case "success":
      return "最近一次发送成功";
    case "failed":
      return "最近一次发送失败";
    case "skipped_no_articles":
      return "最近一次检查没有新增文章";
    case "skipped_disabled":
      return "邮件摘要已停用";
    case "skipped_missing_recipient":
      return "未配置收件邮箱";
    case "skipped_interval_not_due":
      return "未到下次发送间隔";
    default:
      return "暂无发送记录";
  }
}

const DEFAULT_SETTINGS: EmailDigestSettings = {
  recipient_email: null,
  enabled: false,
  send_interval_days: 1,
  send_time: "08:00",
  timezone: "Asia/Shanghai",
  last_run_date: null,
  last_sent_at: null,
  last_attempted_at: null,
  last_send_status: null,
  last_send_error: null,
  last_sent_article_count: 0,
};

const INTERVAL_VALUES = [1, 2, 3, 4, 5, 6, 7, 15, 30] as const;

const INTERVAL_ITEMS = INTERVAL_VALUES.map((v) => ({
  value: v,
  label: `${v} 天`,
}));

function settingsKey(settings: EmailDigestSettings) {
  return [
    settings.recipient_email ?? "",
    settings.enabled ? "1" : "0",
    settings.send_interval_days,
    settings.send_time,
    settings.last_send_status ?? "",
    settings.last_send_error ?? "",
  ].join("|");
}

function EmailDigestSettingsForm({
  settings,
  queryError,
}: {
  settings: EmailDigestSettings;
  queryError: Error | null;
}) {
  const [email, setEmail] = useState(settings.recipient_email ?? "");
  const [enabled, setEnabled] = useState(settings.enabled);
  const [sendIntervalDays, setSendIntervalDays] = useState(settings.send_interval_days);
  const [sendTime, setSendTime] = useState(settings.send_time);
  const [localError, setLocalError] = useState<string | null>(null);

  const saveMutation = useMutation({
    mutationFn: (payload: EmailDigestSettingsUpdate) =>
      apiPut<EmailDigestSettings>("/settings/email-digest", payload),
    onSuccess: (settings) => {
      queryClient.setQueryData(queryKeys.settings.emailDigest(), settings);
      queryClient.invalidateQueries({
        queryKey: queryKeys.settings.emailDigest(),
      });
    },
  });

  const testMutation = useMutation({
    mutationFn: () => apiPost("/settings/email-digest/test"),
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLocalError(null);
    const trimmedEmail = email.trim();
    if (enabled && !trimmedEmail) {
      setLocalError("启用邮件摘要前需要填写收件邮箱");
      return;
    }
    if (sendIntervalDays < 1 || sendIntervalDays > 30) {
      setLocalError("发送间隔需要在 1 到 30 天之间");
      return;
    }

    saveMutation.mutate({
      recipient_email: trimmedEmail || null,
      enabled,
      send_interval_days: sendIntervalDays,
      send_time: sendTime,
    });
  }

  const error =
    localError ??
    saveMutation.error?.message ??
    testMutation.error?.message ??
    queryError?.message ??
    null;

  const savedRecipientEmail =
    queryClient.getQueryData<EmailDigestSettings>(queryKeys.settings.emailDigest())
      ?.recipient_email ?? settings.recipient_email;

  return (
    <form className="contents" onSubmit={handleSubmit}>
      <DialogPanel className="flex flex-col gap-4">
        <Field>
          <FieldLabel htmlFor="email-digest-recipient">收件邮箱</FieldLabel>
          <Input
            id="email-digest-recipient"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="reader@example.com"
          />
        </Field>

        <Field>
          <FieldLabel>发送间隔天数</FieldLabel>
          <Combobox
            items={INTERVAL_ITEMS}
            value={sendIntervalDays}
            onValueChange={(value) => setSendIntervalDays(value as number)}
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
          <FieldDescription>1 表示每天发送，7 表示每周发送。</FieldDescription>
        </Field>

        <Field>
          <FieldLabel htmlFor="email-digest-send-time">发送时间</FieldLabel>
          <Input
            id="email-digest-send-time"
            type="time"
            value={sendTime}
            onChange={(event) => setSendTime(event.target.value)}
          />
          <FieldDescription>固定使用 Asia/Shanghai 时区。</FieldDescription>
        </Field>

        <div className="flex items-center justify-between gap-4 rounded-lg border bg-card p-3">
          <div>
            <p className="text-sm font-medium text-foreground">启用邮件摘要</p>
            <p className="text-xs text-muted-foreground">有新增文章时发送 EPUB 附件。</p>
          </div>
          <Switch
            aria-label="启用邮件摘要"
            checked={enabled}
            onCheckedChange={setEnabled}
          />
        </div>

        <div className="flex items-start gap-2 rounded-lg border bg-card p-3 text-sm text-muted-foreground">
          <MailIcon aria-hidden="true" className="mt-0.5 size-4" />
          <div>
            <p>{statusLabel(settings.last_send_status)}</p>
            {settings.last_send_error ? (
              <p className="mt-1 text-destructive-foreground">{settings.last_send_error}</p>
            ) : null}
          </div>
        </div>

        {error ? <p className="text-sm text-destructive-foreground">{error}</p> : null}
      </DialogPanel>
      <DialogFooter>
        <Button
          type="button"
          variant="outline"
          loading={testMutation.isPending}
          disabled={testMutation.isPending || !savedRecipientEmail}
          onClick={() => testMutation.mutate()}
        >
          发送测试邮件
        </Button>
        <Button
          type="submit"
          loading={saveMutation.isPending}
          disabled={saveMutation.isPending}
        >
          保存
        </Button>
      </DialogFooter>
    </form>
  );
}

export function EmailDigestSettingsDialog() {
  const [open, setOpen] = useState(false);
  const settingsQuery = useQuery({
    queryKey: queryKeys.settings.emailDigest(),
    queryFn: () => apiGet<EmailDigestSettings>("/settings/email-digest"),
    enabled: open,
  });
  const settings = settingsQuery.data ?? DEFAULT_SETTINGS;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={<Button aria-label="邮件摘要设置" size="icon" variant="ghost" />}
      >
        <SettingsIcon aria-hidden="true" />
      </DialogTrigger>
      <DialogPopup>
        <DialogHeader>
          <DialogTitle>邮件摘要</DialogTitle>
          <DialogDescription>设置收件邮箱、发送间隔和发送时间。</DialogDescription>
        </DialogHeader>
        <EmailDigestSettingsForm
          key={settingsKey(settings)}
          settings={settings}
          queryError={settingsQuery.error}
        />
      </DialogPopup>
    </Dialog>
  );
}
