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
  getPolicies,
  grantPetConsent,
  listBodyAssessments,
  listPetAssets,
  listPetConsents,
  petAssetUrl,
  uploadPetAsset,
  withdrawPetConsent,
} from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { formatPersianNumber } from "@/lib/format";
import { useSessionExpiryRedirect } from "@/lib/session/use-session-expiry";

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

const categoryPurpose: Record<string, "body_photographs" | "medical_records"> =
  {
    body_side: "body_photographs",
    body_top: "body_photographs",
    lab_result: "medical_records",
    medical_document: "medical_records",
    other_medical: "medical_records",
  };

// Explanation copy is derived from the approved product decisions in
// backend/docs/architecture/pet-health-assets.md (purpose-limited use,
// household-only access, versioned and revocable consent). Exact legal
// wording is pending product/legal sign-off before this ships broadly.
const purposeExplanationFa: Record<
  "body_photographs" | "medical_records",
  string
> = {
  body_photographs:
    "تصاویر بدن پت فقط برای پیگیری شخصی وضعیت بدنی او در طول زمان استفاده می‌شود و فقط برای اعضای همین خانوار قابل مشاهده است.",
  medical_records:
    "مدارک پزشکی فقط برای نگهداری شخصی سوابق پت استفاده می‌شود و فقط برای اعضای همین خانوار قابل مشاهده است.",
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
  const [category, setCategory] =
    useState<keyof typeof categoryLabels>("body_top");
  const [file, setFile] = useState<File | null>(null);
  // Bumped on a successful upload to remount the native file input --
  // otherwise its displayed filename stays stale even after `file` is reset
  // to null, and re-selecting the same file would not fire onChange again.
  const [fileInputResetKey, setFileInputResetKey] = useState(0);
  const purpose = categoryPurpose[category];

  const policyQuery = useQuery({ queryKey: ["policy"], queryFn: getPolicies });
  const consentsQuery = useQuery({
    queryKey: ["pet-life", "consents", petId],
    queryFn: () => listPetConsents(petId),
    enabled: Boolean(petId),
  });

  async function invalidateConsents() {
    await queryClient.invalidateQueries({
      queryKey: ["pet-life", "consents", petId],
    });
  }

  const currentPolicyVersion =
    policyQuery.data?.pet_health_consent_policy_version;
  const grantedForPurpose = consentsQuery.data?.find(
    (item) => item.purpose === purpose && item.status === "granted",
  );
  const activeConsent =
    grantedForPurpose &&
    grantedForPurpose.policy_version === currentPolicyVersion
      ? grantedForPurpose
      : undefined;
  // Granted under an older policy_version: the backend requires an explicit
  // withdrawal before a fresh consent can be granted (it never silently
  // reinterprets an old grant as covering a new policy version).
  const staleConsent =
    grantedForPurpose && !activeConsent ? grantedForPurpose : undefined;

  const consentMutation = useMutation({
    mutationFn: () => {
      if (!currentPolicyVersion) throw new Error("policy not loaded");
      return grantPetConsent(petId, {
        policy_version: currentPolicyVersion,
        purpose,
      });
    },
    onSuccess: invalidateConsents,
  });

  const withdrawMutation = useMutation({
    mutationFn: (consentId: string) => withdrawPetConsent(petId, consentId),
    onSuccess: async () => {
      await invalidateConsents();
      await queryClient.invalidateQueries({
        queryKey: ["pet-life", "assets", petId],
      });
    },
  });

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!file || !activeConsent)
        throw new Error("no file selected or consent missing");
      return uploadPetAsset(petId, file, {
        category,
        consentId: activeConsent.id,
      });
    },
    onSuccess: async () => {
      setFile(null);
      setFileInputResetKey((key) => key + 1);
      await queryClient.invalidateQueries({
        queryKey: ["pet-life", "assets", petId],
      });
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

      {policyQuery.isLoading || consentsQuery.isLoading ? (
        <Skeleton />
      ) : !activeConsent ? (
        <div className="stack" data-testid="consent-gate">
          <div className="eyebrow">رضایت لازم است</div>
          <p className="caption">{purposeExplanationFa[purpose]}</p>
          <p className="caption">
            رضایت شما نسخه‌دار است؛ در صورت تغییر نسخه سیاست، دوباره از شما
            پرسیده می‌شود. می‌توانید هر زمان آن را لغو کنید؛ لغو رضایت، دسترسی
            به فایل‌های آپلودشده را فوراً غیرفعال می‌کند.
          </p>
          {consentMutation.isError ? (
            <Banner tone="error">{errorText(consentMutation.error)}</Banner>
          ) : null}
          {withdrawMutation.isError ? (
            <Banner tone="error">{errorText(withdrawMutation.error)}</Banner>
          ) : null}
          {staleConsent ? (
            <>
              <p className="caption">
                رضایت قبلی شما با نسخه فعلی سیاست همخوانی ندارد. برای ادامه،
                ابتدا رضایت قبلی را لغو کنید.
              </p>
              <Button
                variant="secondary"
                loading={withdrawMutation.isPending}
                onClick={() => withdrawMutation.mutate(staleConsent.id)}
              >
                لغو رضایت قبلی
              </Button>
            </>
          ) : (
            <Button
              disabled={!currentPolicyVersion}
              loading={consentMutation.isPending}
              onClick={() => consentMutation.mutate()}
            >
              موافقم و رضایت می‌دهم
            </Button>
          )}
        </div>
      ) : (
        <>
          <div className="field">
            <label htmlFor="asset-file">فایل (jpg، png یا pdf)</label>
            <input
              id="asset-file"
              key={fileInputResetKey}
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
          <Button
            variant="ghost"
            loading={withdrawMutation.isPending}
            onClick={() => withdrawMutation.mutate(activeConsent.id)}
          >
            لغو رضایت
          </Button>
        </>
      )}
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
          onChange={(event) =>
            setBcsScore(Number.parseInt(event.target.value, 10))
          }
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
      <Button
        loading={submitMutation.isPending}
        onClick={() => submitMutation.mutate()}
      >
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
      await queryClient.invalidateQueries({
        queryKey: ["pet-life", "assets", petId],
      });
    },
  });

  const sessionExpired = useSessionExpiryRedirect(
    assetsQuery.error,
    assessmentsQuery.error,
  );

  if (sessionExpired) {
    return (
      <AppShell>
        <Skeleton />
      </AppShell>
    );
  }

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
                <Button
                  variant="secondary"
                  onClick={() => void assetsQuery.refetch()}
                >
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
          {assessmentsQuery.isLoading ? <Skeleton /> : null}
          {assessmentsQuery.isError ? (
            <ErrorState
              title="تاریخچه وضعیت بدنی در دسترس نیست"
              action={
                <Button
                  variant="secondary"
                  onClick={() => void assessmentsQuery.refetch()}
                >
                  تلاش دوباره
                </Button>
              }
            />
          ) : null}
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
                    {muscleConditionLabels[item.muscle_condition] ??
                      item.muscle_condition}
                  </span>
                  <StatusChip
                    tone={item.veterinarian_confirmed_at ? "positive" : "muted"}
                  >
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
