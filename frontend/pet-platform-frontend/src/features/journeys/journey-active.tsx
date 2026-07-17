"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { AppShell } from "@/components/app-shell";
import {
  Banner,
  Button,
  Card,
  ErrorState,
  Sheet,
  Skeleton,
  StatusChip,
} from "@/components/primitives";
import type { JourneyStepResponse } from "@/lib/api-types";
import {
  completeJourney,
  getJourney,
  pauseJourney,
  resumeJourney,
  stopJourney,
  submitCheckIn,
} from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { formatIranDateTime } from "@/lib/format";
import { checkInIdempotencyKey } from "@/lib/journey-idempotency";

function errorText(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "خطا در ارتباط با سرویس.";
}

const statusLabelFa: Record<string, string> = {
  active: "فعال",
  completed: "تکمیل‌شده",
  paused: "متوقف‌شده موقت",
  stopped: "لغوشده",
};

const statusTone: Record<
  string,
  "positive" | "info" | "warning" | "error" | "muted"
> = {
  active: "info",
  completed: "positive",
  paused: "warning",
  stopped: "muted",
};

function CheckInForm({
  step,
  submitting,
  submitError,
  onSubmit,
}: {
  step: JourneyStepResponse;
  submitting: boolean;
  submitError: string | null;
  onSubmit: (answerKey: string) => void;
}) {
  const [answerKey, setAnswerKey] = useState<string | null>(null);

  return (
    <Card className="stack">
      <div className="eyebrow">گام جاری</div>
      <h2 className="title">{step.title_fa}</h2>
      <p className="caption">{step.body_fa}</p>
      <div className="stack" role="radiogroup" aria-label={step.title_fa}>
        {step.allowed_answers.map((answer) => (
          <Button
            key={answer.key}
            type="button"
            variant={answerKey === answer.key ? "selection" : "secondary"}
            aria-pressed={answerKey === answer.key}
            onClick={() => setAnswerKey(answer.key)}
          >
            {answer.label_fa}
          </Button>
        ))}
      </div>
      {submitError ? <Banner tone="error">{submitError}</Banner> : null}
      <Button
        disabled={!answerKey || submitting}
        loading={submitting}
        onClick={() => answerKey && onSubmit(answerKey)}
      >
        ثبت پاسخ
      </Button>
    </Card>
  );
}

export function JourneyActive({ journeyId }: { journeyId: string }) {
  const queryClient = useQueryClient();
  const [sheet, setSheet] = useState<"pause" | "resume" | "stop" | "complete" | null>(
    null,
  );
  const [stopReason, setStopReason] = useState("");
  const [memoryTitle, setMemoryTitle] = useState("");

  const journeyQuery = useQuery({
    queryKey: ["pet-life", "journeys", journeyId],
    queryFn: () => getJourney(journeyId),
    enabled: Boolean(journeyId),
  });

  async function invalidateJourney() {
    await queryClient.invalidateQueries({
      queryKey: ["pet-life", "journeys", journeyId],
    });
    await queryClient.invalidateQueries({ queryKey: ["pet-life", "today"] });
  }

  const checkInMutation = useMutation({
    mutationFn: (variables: { checkInKey: string; answerKey: string }) =>
      submitCheckIn(
        journeyId,
        { answer_key: variables.answerKey, check_in_key: variables.checkInKey },
        checkInIdempotencyKey(
          journeyId,
          variables.checkInKey,
          variables.answerKey,
        ),
      ),
    onSuccess: () => invalidateJourney(),
  });

  const pauseMutation = useMutation({
    mutationFn: () => pauseJourney(journeyId),
    onSuccess: async () => {
      setSheet(null);
      await invalidateJourney();
    },
  });

  const resumeMutation = useMutation({
    mutationFn: () => resumeJourney(journeyId),
    onSuccess: async () => {
      setSheet(null);
      await invalidateJourney();
    },
  });

  const stopMutation = useMutation({
    mutationFn: () => stopJourney(journeyId, { reason: stopReason }),
    onSuccess: async () => {
      setSheet(null);
      await invalidateJourney();
    },
  });

  const completeMutation = useMutation({
    mutationFn: () =>
      completeJourney(journeyId, { memory_title_fa: memoryTitle }),
    onSuccess: async () => {
      setSheet(null);
      await invalidateJourney();
    },
  });

  if (journeyQuery.isLoading) {
    return (
      <AppShell>
        <Card className="stack">
          <Skeleton />
          <Skeleton />
          <Skeleton />
        </Card>
      </AppShell>
    );
  }

  if (journeyQuery.isError || !journeyQuery.data) {
    return (
      <AppShell>
        <ErrorState
          title="این مسیر مراقبتی در دسترس نیست"
          action={
            <Button
              variant="secondary"
              onClick={() => void journeyQuery.refetch()}
            >
              تلاش دوباره
            </Button>
          }
        />
      </AppShell>
    );
  }

  const journey = journeyQuery.data;
  const answeredKeys = new Set(journey.check_ins.map((c) => c.check_in_key));
  const currentStep = journey.steps.find((step) => !answeredKeys.has(step.key));
  const allStepsAnswered = !currentStep;

  return (
    <AppShell>
      <div className="stack">
        <div className="split">
          <div>
            <div className="eyebrow">مسیر مراقبتی</div>
            <h1 className="display">{journey.title_fa}</h1>
          </div>
          <StatusChip tone={statusTone[journey.status] ?? "muted"}>
            {statusLabelFa[journey.status] ?? journey.status}
          </StatusChip>
        </div>

        <Card className="stack">
          <div className="eyebrow">گام‌ها</div>
          <ol className="stack">
            {journey.steps.map((step) => (
              <li className="split" key={step.key}>
                <span>{step.title_fa}</span>
                <StatusChip tone={answeredKeys.has(step.key) ? "positive" : "muted"}>
                  {answeredKeys.has(step.key) ? "پاسخ ثبت شد" : "در انتظار"}
                </StatusChip>
              </li>
            ))}
          </ol>
        </Card>

        {journey.status === "active" && currentStep ? (
          <CheckInForm
            step={currentStep}
            submitting={checkInMutation.isPending}
            submitError={
              checkInMutation.isError ? errorText(checkInMutation.error) : null
            }
            onSubmit={(answerKey) =>
              checkInMutation.mutate({ answerKey, checkInKey: currentStep.key })
            }
          />
        ) : null}

        {journey.status === "active" && allStepsAnswered ? (
          <Banner tone="info">
            همه گام‌ها پاسخ داده شده‌اند. حالا می‌توانید مسیر را تکمیل کنید.
          </Banner>
        ) : null}

        {journey.status === "paused" ? (
          <Banner tone="warning">
            این مسیر موقتاً متوقف شده است. برای ادامه، آن را از سر بگیرید.
          </Banner>
        ) : null}

        {journey.status === "stopped" ? (
          <Banner tone="info">این مسیر لغو شده است.</Banner>
        ) : null}

        {journey.status === "completed" ? (
          <Banner tone="info">
            این مسیر تکمیل شده است. خاطره و پاداش باغ آن ثبت شده است.
          </Banner>
        ) : null}

        {journey.status === "active" || journey.status === "paused" ? (
          <div className="cluster">
            {journey.status === "active" ? (
              <Button variant="secondary" onClick={() => setSheet("pause")}>
                توقف موقت
              </Button>
            ) : (
              <Button variant="secondary" onClick={() => setSheet("resume")}>
                از سر گرفتن
              </Button>
            )}
            <Button variant="ghost" onClick={() => setSheet("stop")}>
              لغو مسیر
            </Button>
            {journey.status === "active" && allStepsAnswered ? (
              <Button onClick={() => setSheet("complete")}>تکمیل مسیر</Button>
            ) : null}
          </div>
        ) : null}

        {sheet === "pause" ? (
          <Sheet title="توقف موقت مسیر" onClose={() => setSheet(null)}>
            <div className="stack">
              <p className="caption">
                مسیر موقتاً متوقف می‌شود و می‌توانید بعداً آن را از سر بگیرید.
              </p>
              {pauseMutation.isError ? (
                <Banner tone="error">{errorText(pauseMutation.error)}</Banner>
              ) : null}
              <div className="cluster">
                <Button
                  loading={pauseMutation.isPending}
                  onClick={() => pauseMutation.mutate()}
                >
                  تایید توقف موقت
                </Button>
                <Button variant="ghost" onClick={() => setSheet(null)}>
                  انصراف
                </Button>
              </div>
            </div>
          </Sheet>
        ) : null}

        {sheet === "resume" ? (
          <Sheet title="از سر گرفتن مسیر" onClose={() => setSheet(null)}>
            <div className="stack">
              {resumeMutation.isError ? (
                <Banner tone="error">{errorText(resumeMutation.error)}</Banner>
              ) : null}
              <div className="cluster">
                <Button
                  loading={resumeMutation.isPending}
                  onClick={() => resumeMutation.mutate()}
                >
                  تایید از سر گرفتن
                </Button>
                <Button variant="ghost" onClick={() => setSheet(null)}>
                  انصراف
                </Button>
              </div>
            </div>
          </Sheet>
        ) : null}

        {sheet === "stop" ? (
          <Sheet title="لغو مسیر مراقبتی" onClose={() => setSheet(null)}>
            <div className="stack">
              <p className="caption">
                لغو این مسیر قابل بازگشت نیست. لطفاً دلیل لغو را بنویسید.
              </p>
              <div className="field">
                <label htmlFor="stop-reason">دلیل لغو</label>
                <textarea
                  id="stop-reason"
                  className="input"
                  value={stopReason}
                  onChange={(event) => setStopReason(event.target.value)}
                />
              </div>
              {stopMutation.isError ? (
                <Banner tone="error">{errorText(stopMutation.error)}</Banner>
              ) : null}
              <div className="cluster">
                <Button
                  loading={stopMutation.isPending}
                  disabled={stopReason.trim().length === 0}
                  onClick={() => stopMutation.mutate()}
                >
                  تایید لغو
                </Button>
                <Button variant="ghost" onClick={() => setSheet(null)}>
                  انصراف
                </Button>
              </div>
            </div>
          </Sheet>
        ) : null}

        {sheet === "complete" ? (
          <Sheet title="تکمیل مسیر مراقبتی" onClose={() => setSheet(null)}>
            <div className="stack">
              <p className="caption">
                یک عنوان کوتاه برای این خاطره بنویسید تا در دفترچه پت ثبت شود.
              </p>
              <div className="field">
                <label htmlFor="memory-title">عنوان خاطره</label>
                <input
                  id="memory-title"
                  className="input"
                  value={memoryTitle}
                  onChange={(event) => setMemoryTitle(event.target.value)}
                />
              </div>
              {completeMutation.isError ? (
                <Banner tone="error">{errorText(completeMutation.error)}</Banner>
              ) : null}
              <div className="cluster">
                <Button
                  loading={completeMutation.isPending}
                  disabled={memoryTitle.trim().length === 0}
                  onClick={() => completeMutation.mutate()}
                >
                  تایید تکمیل
                </Button>
                <Button variant="ghost" onClick={() => setSheet(null)}>
                  انصراف
                </Button>
              </div>
            </div>
          </Sheet>
        ) : null}

        <p className="caption ltr-data">
          {formatIranDateTime(journey.started_at)}
        </p>
      </div>
    </AppShell>
  );
}
