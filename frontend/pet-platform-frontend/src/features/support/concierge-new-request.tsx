"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { AppShell } from "@/components/app-shell";
import {
  Banner,
  Button,
  Card,
  EmptyState,
  Skeleton,
} from "@/components/primitives";
import {
  createCustomerRequest,
  getMeContext,
  getPolicies,
} from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { enabled } from "@/lib/policy";
import { useSessionExpiryRedirect } from "@/lib/session/use-session-expiry";

const requestSchema = z.object({
  contactPreference: z.enum(["in_app", "sms"]),
  message: z.string().min(1, "متن پیام لازم است").max(2000),
  requestType: z.enum(["support", "concierge_sourcing"]),
});

function errorText(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "خطا در ارتباط با سرویس. دوباره تلاش کنید.";
}

export function ConciergeNewRequest() {
  const router = useRouter();
  const contextQuery = useQuery({
    queryKey: ["me", "context"],
    queryFn: getMeContext,
  });
  const policyQuery = useQuery({ queryKey: ["policy"], queryFn: getPolicies });

  const [requestType, setRequestType] = useState<
    "support" | "concierge_sourcing"
  >("support");
  const [contactPreference, setContactPreference] = useState<"in_app" | "sms">(
    "in_app",
  );
  const form = useForm<z.infer<typeof requestSchema>>({
    resolver: zodResolver(requestSchema),
    defaultValues: {
      contactPreference: "in_app",
      message: "",
      requestType: "support",
    },
  });

  const submitMutation = useMutation({
    mutationFn: (values: z.infer<typeof requestSchema>) => {
      const householdId =
        contextQuery.data?.default_household_id ??
        contextQuery.data?.households[0]?.id;
      if (!householdId) throw new Error("household missing");
      return createCustomerRequest(
        {
          contact_preference: values.contactPreference,
          household_id: householdId,
          message_fa: values.message,
          request_type: values.requestType,
        },
        crypto.randomUUID(),
      );
    },
    onSuccess: (result) => {
      router.push(`/support/${result.id}`);
    },
  });

  const sessionExpired = useSessionExpiryRedirect(contextQuery.error);

  if (sessionExpired) {
    return (
      <AppShell>
        <Skeleton />
      </AppShell>
    );
  }

  if (contextQuery.isLoading || policyQuery.isLoading) {
    return (
      <AppShell>
        <Card className="stack">
          <Skeleton />
          <Skeleton />
        </Card>
      </AppShell>
    );
  }

  if (
    !policyQuery.data ||
    !enabled(policyQuery.data, "concierge_requests_enabled")
  ) {
    return (
      <AppShell>
        <EmptyState
          title="این قابلیت در دسترس نیست"
          body="درخواست پشتیبانی و تامین فعلاً برای حساب شما فعال نشده است."
        />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">پشتیبانی</div>
          <h1 className="display">درخواست جدید</h1>
        </div>

        <Card>
          <form
            className="stack"
            onSubmit={form.handleSubmit((values) =>
              submitMutation.mutate(values),
            )}
          >
            <div className="cluster" role="radiogroup" aria-label="نوع درخواست">
              {(
                [
                  ["support", "پشتیبانی"],
                  ["concierge_sourcing", "درخواست تامین محصول"],
                ] as const
              ).map(([value, label]) => (
                <Button
                  key={value}
                  type="button"
                  variant={requestType === value ? "selection" : "secondary"}
                  aria-pressed={requestType === value}
                  onClick={() => {
                    setRequestType(value);
                    form.setValue("requestType", value);
                  }}
                >
                  {label}
                </Button>
              ))}
            </div>

            <div className="field">
              <label htmlFor="message">پیام شما</label>
              <textarea
                id="message"
                className="input"
                {...form.register("message")}
              />
              {form.formState.errors.message ? (
                <div className="inline-error">
                  {form.formState.errors.message.message}
                </div>
              ) : null}
            </div>

            <div className="cluster" role="radiogroup" aria-label="روش پاسخ">
              {(
                [
                  ["in_app", "داخل برنامه"],
                  ["sms", "پیامک"],
                ] as const
              ).map(([value, label]) => (
                <Button
                  key={value}
                  type="button"
                  variant={
                    contactPreference === value ? "selection" : "secondary"
                  }
                  aria-pressed={contactPreference === value}
                  onClick={() => {
                    setContactPreference(value);
                    form.setValue("contactPreference", value);
                  }}
                >
                  {label}
                </Button>
              ))}
            </div>

            <Banner tone="info">
              {policyQuery.data.customer_request_acknowledgement_fa}
            </Banner>

            {submitMutation.isError ? (
              <Banner tone="error">{errorText(submitMutation.error)}</Banner>
            ) : null}

            <Button
              type="submit"
              loading={submitMutation.isPending}
              disabled={submitMutation.isPending}
            >
              ثبت درخواست
            </Button>
          </form>
        </Card>
      </div>
    </AppShell>
  );
}
