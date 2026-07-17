import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createBodyAssessment,
  deletePetAsset,
  grantPetConsent,
  listBodyAssessments,
  listPetAssets,
  uploadPetAsset,
} from "@/lib/api/client";
import { bodyAssessmentFixture, petAssetFixture } from "@/test/fixtures/gate-fixtures";
import { PetAssets } from "./pet-assets";

vi.mock("next/navigation", () => ({
  usePathname: () => "/pets/pet-1/assets",
}));

vi.mock("@/lib/api/client", () => ({
  createBodyAssessment: vi.fn(),
  deletePetAsset: vi.fn(),
  grantPetConsent: vi.fn(),
  listBodyAssessments: vi.fn(),
  listPetAssets: vi.fn(),
  petAssetUrl: (petId: string, assetId: string) =>
    `/api/bff/pets/${petId}/assets/${assetId}`,
  uploadPetAsset: vi.fn(),
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
  });

  it("shows an empty gallery state, not an error, when no assets exist yet", async () => {
    vi.mocked(listPetAssets).mockResolvedValue([]);
    renderWithQuery(<PetAssets petId="pet-1" />);

    expect(
      await screen.findByText("هنوز فایلی آپلود نشده است"),
    ).toBeInTheDocument();
  });

  it("grants consent before uploading, and uploads with the granted consent id", async () => {
    vi.mocked(grantPetConsent).mockResolvedValue({ id: "consent-1", status: "granted" });
    vi.mocked(uploadPetAsset).mockResolvedValue({ id: "asset-2", status: "active" });
    const user = userEvent.setup();
    const file = new File(["fake-bytes"], "photo.jpg", { type: "image/jpeg" });

    renderWithQuery(<PetAssets petId="pet-1" />);
    await screen.findByAltText(petAssetFixture.filename);

    const input = screen.getByLabelText("فایل (jpg، png یا pdf)");
    await user.upload(input, file);
    await user.click(screen.getByRole("button", { name: "آپلود" }));

    await waitFor(() =>
      expect(grantPetConsent).toHaveBeenCalledWith("pet-1", {
        policy_version: "1.0",
        purpose: "body_photographs",
      }),
    );
    await waitFor(() =>
      expect(uploadPetAsset).toHaveBeenCalledWith("pet-1", file, {
        category: "body_top",
        consentId: "consent-1",
      }),
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
