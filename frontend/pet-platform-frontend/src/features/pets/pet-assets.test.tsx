import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createBodyAssessment,
  deletePetAsset,
  getPolicies,
  grantPetConsent,
  listBodyAssessments,
  listPetAssets,
  listPetConsents,
  uploadPetAsset,
  withdrawPetConsent,
} from "@/lib/api/client";
import {
  bodyAssessmentFixture,
  petAssetFixture,
  petConsentFixture,
  policyFixture,
} from "@/test/fixtures/gate-fixtures";
import { PetAssets } from "./pet-assets";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/pets/pet-1/assets",
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/api/client", () => ({
  createBodyAssessment: vi.fn(),
  deletePetAsset: vi.fn(),
  getPolicies: vi.fn(),
  grantPetConsent: vi.fn(),
  listBodyAssessments: vi.fn(),
  listPetAssets: vi.fn(),
  listPetConsents: vi.fn(),
  petAssetUrl: (petId: string, assetId: string) =>
    `/api/bff/pets/${petId}/assets/${assetId}`,
  uploadPetAsset: vi.fn(),
  withdrawPetConsent: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("PetAssets", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listPetAssets).mockResolvedValue([petAssetFixture]);
    vi.mocked(listBodyAssessments).mockResolvedValue([bodyAssessmentFixture]);
    vi.mocked(getPolicies).mockResolvedValue(policyFixture);
    vi.mocked(listPetConsents).mockResolvedValue([]);
  });

  it("shows an empty gallery state, not an error, when no assets exist yet", async () => {
    vi.mocked(listPetAssets).mockResolvedValue([]);
    renderWithQuery(<PetAssets petId="pet-1" />);

    expect(
      await screen.findByText("هنوز فایلی آپلود نشده است"),
    ).toBeInTheDocument();
  });

  it("requires an explicit, distinct consent step before any upload is possible, never granting consent as a side effect of the upload click", async () => {
    vi.mocked(grantPetConsent).mockResolvedValue(petConsentFixture);
    const user = userEvent.setup();

    renderWithQuery(<PetAssets petId="pet-1" />);
    await screen.findByAltText(petAssetFixture.filename);

    expect(screen.getByTestId("consent-gate")).toBeInTheDocument();
    expect(
      screen.queryByLabelText("فایل (jpg، png یا pdf)"),
    ).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "موافقم و رضایت می‌دهم" }),
    );

    await waitFor(() =>
      expect(grantPetConsent).toHaveBeenCalledWith("pet-1", {
        policy_version: policyFixture.pet_health_consent_policy_version,
        purpose: "body_photographs",
      }),
    );
  });

  it("uploads directly, without re-asking for consent, once a matching valid consent already exists", async () => {
    vi.mocked(listPetConsents).mockResolvedValue([petConsentFixture]);
    vi.mocked(uploadPetAsset).mockResolvedValue({
      id: "asset-2",
      status: "active",
    });
    const user = userEvent.setup();
    const file = new File(["fake-bytes"], "photo.jpg", { type: "image/jpeg" });

    renderWithQuery(<PetAssets petId="pet-1" />);
    const input = await screen.findByLabelText("فایل (jpg، png یا pdf)");
    expect(screen.queryByTestId("consent-gate")).not.toBeInTheDocument();

    await user.upload(input, file);
    await user.click(screen.getByRole("button", { name: "آپلود" }));

    expect(grantPetConsent).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(uploadPetAsset).toHaveBeenCalledWith("pet-1", file, {
        category: "body_top",
        consentId: petConsentFixture.id,
      }),
    );
  });

  it("requires withdrawing a stale consent before a new policy version can be granted", async () => {
    vi.mocked(listPetConsents).mockResolvedValue([
      { ...petConsentFixture, policy_version: "0.9" },
    ]);
    vi.mocked(withdrawPetConsent).mockResolvedValue(undefined);
    const user = userEvent.setup();

    renderWithQuery(<PetAssets petId="pet-1" />);
    await screen.findByAltText(petAssetFixture.filename);

    expect(
      screen.getByRole("button", { name: "لغو رضایت قبلی" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "موافقم و رضایت می‌دهم" }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "لغو رضایت قبلی" }));

    await waitFor(() =>
      expect(withdrawPetConsent).toHaveBeenCalledWith(
        "pet-1",
        petConsentFixture.id,
      ),
    );
  });

  it("supports withdrawing an active consent", async () => {
    vi.mocked(listPetConsents).mockResolvedValue([petConsentFixture]);
    vi.mocked(withdrawPetConsent).mockResolvedValue(undefined);
    const user = userEvent.setup();

    renderWithQuery(<PetAssets petId="pet-1" />);
    await screen.findByLabelText("فایل (jpg، png یا pdf)");

    await user.click(screen.getByRole("button", { name: "لغو رضایت" }));

    await waitFor(() =>
      expect(withdrawPetConsent).toHaveBeenCalledWith(
        "pet-1",
        petConsentFixture.id,
      ),
    );
  });

  it("deletes an asset through the real backend endpoint", async () => {
    vi.mocked(deletePetAsset).mockResolvedValue(undefined);
    const user = userEvent.setup();

    renderWithQuery(<PetAssets petId="pet-1" />);
    await user.click(await screen.findByRole("button", { name: "حذف" }));

    await waitFor(() =>
      expect(deletePetAsset).toHaveBeenCalledWith("pet-1", petAssetFixture.id),
    );
  });

  it("shows whether a body assessment has been professionally confirmed, distinct from owner-only entries", async () => {
    renderWithQuery(<PetAssets petId="pet-1" />);

    expect(await screen.findByText("ثبت‌شده توسط مالک")).toBeInTheDocument();
  });

  it("submits a new body-condition assessment through the real backend endpoint", async () => {
    vi.mocked(createBodyAssessment).mockResolvedValue({
      assessment_source: "owner_reported",
      id: "assessment-2",
    });
    const user = userEvent.setup();

    renderWithQuery(<PetAssets petId="pet-1" />);
    await screen.findByAltText(petAssetFixture.filename);
    await user.click(screen.getByRole("button", { name: "ثبت" }));

    await waitFor(() =>
      expect(createBodyAssessment).toHaveBeenCalledWith(
        "pet-1",
        expect.objectContaining({
          answers: {},
          bcs_scale: 9,
          bcs_score: 5,
          muscle_condition: "normal",
        }),
      ),
    );
  });
});
