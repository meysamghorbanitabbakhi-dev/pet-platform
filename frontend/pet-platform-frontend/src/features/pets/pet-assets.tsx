"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { AppShell } from "@/components/app-shell";
import {
  Banner,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Skeleton,
  StatusChip,
} from "@/components/primitives";
import {
  createBodyAssessment,
  deletePetAsset,
  grantPetConsent,
  listBodyAssessments,
  listPetAssets,
  petAssetUrl,
  uploadPetAsset,
} from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { formatPersianNumber } from "@/lib/format";

// A policy_version accompanies every consent grant per the backend contract
// (ConsentBody.policy_version). It must stay stable: changing it would force
// every existing consent to be withdrawn and re-granted.
const CONSENT_POLICY_VERSION = "1.0";

function errorText(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "خطا در ارتباط با سرویس.";
}

const categoryLabels: Record<string, string> = {
  body_side: "عکس بدن (نمای پهلو)",
  body_top: "عکس بدن (نمای بالا)",
  lab_result: "نتیجه آزمایش",
  medical_document: "مدرک پزشکی",
  other_medical: "سایر مدارک پزشکی",
};

const categoryPurpose: Record<string, "body_photographs" | "medical_records"> = {
  body_side: "body_photographs",
  body_top: "body_photographs",
  lab_result: "medical_records",
  medical_document: "medical_records",
  other_medical: "medical_records",
};

const muscleConditionLabels: Record<string, string> = {
  mild_loss: "کاهش خفیف",
  moderate_loss: "کاهش متوسط",
  normal: "طبیعی",
  severe_loss: "کاهش شدید",
  unknown: "نامشخص",
};

function UploadForm({ petId }: { petId: string }) {
  const queryClient = useQueryClient();
  const [category, setCategory] = useState<keyof typeof categoryLabels>("body_top");
  const [file, setFile] = useState<File | null>(null);

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("no file selected");
      const consent = await grantPetConsent(petId, {
        policy_version: CONSENT_POLICY_VERSION,
        purpose: categoryPurpose[category],
      });
      return uploadPetAsset(petId, file, { category, consentId: consent.id });
    },
    onSuccess: async () => {
      setFile(null);
      await queryClient.invalidateQueries({ queryKey: ["pet-life", "assets", petId] });
    },
  });

  return (
    <Card className="stack">
      <h2 className="title">آپلود خصوصی</h2>
      <p className="caption">
        فایل‌ها فقط برای شما و از طریق دسترسی خصوصی نمایش داده می‌شوند.
      </p>
      <div className="cluster" role="radiogroup" aria-label="دسته فایل">
        {Object.entries(categoryLabels).map(([value, label]) => (
          <Button
            key={value}
            type="button"
            variant={category === value ? "selection" : "secondary"}
            aria-pressed={category === value}
            onClick={() => setCategory(value as keyof typeof categoryLabels)}
          >
            {label}
          </Button>
        ))}
      </div>
      <div className="field">
        <label htmlFor="asset-file">فایل (jpg، png یا pdf)</label>
        <input
          id="asset-file"
          accept="image/jpeg,image/png,application/pdf"
          className="input"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          type="file"
        />
      </div>
      {uploadMutation.isError ? (
        <Banner tone="error">{errorText(uploadMutation.error)}</Banner>
      ) : null}
      <Button
        disabled={!file || uploadMutation.isPending}
        loading={uploadMutation.isPending}
        onClick={() => uploadMutation.mutate()}
      >
        آپلود
      </Button>
    </Card>
  );
}

function AssessmentForm({ petId }: { petId: string }) {
  const queryClient = useQueryClient();
  const [bcsScore, setBcsScore] = useState(5);
  const [muscleCondition, setMuscleCondition] =
    useState<keyof typeof muscleConditionLabels>("normal");

  const submitMutation = useMutation({
    mutationFn: () =>
      createBodyAssessment(petId, {
        answers: {},
        assessed_at: new Date().toISOString(),
        bcs_scale: 9,
        bcs_score: bcsScore,
        muscle_condition: muscleCondition,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["pet-life", "body-assessments", petId],
      });
    },
  });

  return (
    <Card className="stack">
      <h2 className="title">ثبت وضعیت بدنی</h2>
      <p className="caption">
        این عدد فقط یک برآورد شخصی است و جایگزین معاینه دامپزشک نیست.
      </p>
      <div className="field">
        <label htmlFor="bcs-score">امتیاز وضعیت بدنی (۱ تا ۹)</label>
        <input
          id="bcs-score"
          className="input"
          max={9}
          min={1}
          onChange={(event) => setBcsScore(Number.parseInt(event.target.value, 10))}
          type="number"
          value={bcsScore}
        />
      </div>
      <div className="cluster" role="radiogroup" aria-label="وضعیت عضلانی">
        {Object.entries(muscleConditionLabels).map(([value, label]) => (
          <Button
            key={value}
            type="button"
            variant={muscleCondition === value ? "selection" : "secondary"}
            aria-pressed={muscleCondition === value}
            onClick={() =>
              setMuscleCondition(value as keyof typeof muscleConditionLabels)
            }
          >
            {label}
          </Button>
        ))}
      </div>
      {submitMutation.isError ? (
        <Banner tone="error">{errorText(submitMutation.error)}</Banner>
      ) : null}
      <Button loading={submitMutation.isPending} onClick={() => submitMutation.mutate()}>
        ثبت
      </Button>
    </Card>
  );
}

export function PetAssets({ petId }: { petId: string }) {
  const queryClient = useQueryClient();
  const assetsQuery = useQuery({
    queryKey: ["pet-life", "assets", petId],
    queryFn: () => listPetAssets(petId),
    enabled: Boolean(petId),
  });
  const assessmentsQuery = useQuery({
    queryKey: ["pet-life", "body-assessments", petId],
    queryFn: () => listBodyAssessments(petId),
    enabled: Boolean(petId),
  });

  const deleteMutation = useMutation({
    mutationFn: (assetId: string) => deletePetAsset(petId, assetId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["pet-life", "assets", petId] });
    },
  });

  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">پت</div>
          <h1 className="display">تصاویر و اسناد</h1>
        </div>

        <UploadForm petId={petId} />

        <Card className="stack">
          <h2 className="title">گالری خصوصی</h2>
          {assetsQuery.isLoading ? <Skeleton /> : null}
          {assetsQuery.isError ? (
            <ErrorState
              title="گالری در دسترس نیست"
              action={
                <Button variant="secondary" onClick={() => void assetsQuery.refetch()}>
                  تلاش دوباره
                </Button>
              }
            />
          ) : null}
          {assetsQuery.data?.length === 0 ? (
            <EmptyState
              title="هنوز فایلی آپلود نشده است"
              body="عکس یا مدرک آپلودشده اینجا نمایش داده می‌شود."
            />
          ) : null}
          {assetsQuery.data?.length ? (
            <div className="grid grid--two" aria-label="فهرست فایل‌ها">
              {assetsQuery.data.map((asset) => (
                <div className="stack" key={asset.id}>
                  {asset.media_type.startsWith("image/") ? (
                    // Private, authenticated media proxied through the BFF; never a
                    // direct storage URL.
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      alt={asset.filename}
                      className="product-media"
                      src={petAssetUrl(petId, asset.id)}
                    />
                  ) : (
                    <a
                      className="button button--secondary"
                      href={petAssetUrl(petId, asset.id)}
                    >
                      دانلود سند
                    </a>
                  )}
                  <span className="caption">
                    {categoryLabels[asset.category] ?? asset.category}
                  </span>
                  <Button
                    variant="ghost"
                    loading={deleteMutation.isPending}
                    onClick={() => deleteMutation.mutate(asset.id)}
                  >
                    حذف
                  </Button>
                </div>
              ))}
            </div>
          ) : null}
        </Card>

        <AssessmentForm petId={petId} />

        <Card className="stack">
          <h2 className="title">تاریخچه وضعیت بدنی</h2>
          {assessmentsQuery.data?.length === 0 ? (
            <p className="caption">هنوز ارزیابی ثبت نشده است.</p>
          ) : null}
          {assessmentsQuery.data?.length ? (
            <ul className="stack" aria-label="فهرست ارزیابی‌های بدنی">
              {assessmentsQuery.data.map((item) => (
                <li className="split" key={item.id}>
                  <span>
                    امتیاز {formatPersianNumber(item.bcs_score)} از{" "}
                    {formatPersianNumber(item.bcs_scale)} -{" "}
                    {muscleConditionLabels[item.muscle_condition] ?? item.muscle_condition}
                  </span>
                  <StatusChip tone={item.veterinarian_confirmed_at ? "positive" : "muted"}>
                    {item.veterinarian_confirmed_at
                      ? "تاییدشده توسط دامپزشک"
                      : "ثبت‌شده توسط مالک"}
                  </StatusChip>
                </li>
              ))}
            </ul>
          ) : null}
        </Card>
      </div>
    </AppShell>
  );
}
