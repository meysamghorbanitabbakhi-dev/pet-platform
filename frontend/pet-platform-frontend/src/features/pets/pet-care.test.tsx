import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  getPetCareGuidance,
  getPetKnowledge,
  setGuidancePreference,
} from "@/lib/api/client";
import {
  careGuidanceFixture,
  petKnowledgeFixture,
} from "@/test/fixtures/gate-fixtures";
import { PetCare } from "./pet-care";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/pets/pet-1/care",
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/api/client", () => ({
  getPetCareGuidance: vi.fn(),
  getPetKnowledge: vi.fn(),
  setGuidancePreference: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("PetCare", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getPetKnowledge).mockResolvedValue(petKnowledgeFixture);
    vi.mocked(getPetCareGuidance).mockResolvedValue(careGuidanceFixture);
  });

  it("shows a breed-selection prompt, not an error, when the pet has no recorded breed", async () => {
    vi.mocked(getPetKnowledge).mockResolvedValue({
      claims: [],
      disclaimer_fa: "این اطلاعات عمومی است و جایگزین نظر دامپزشک نیست.",
      pet_id: "pet-1",
      status: "breed_not_recorded",
    });
    renderWithQuery(<PetCare petId="pet-1" />);

    expect(
      await screen.findByText("نژاد این پت ثبت نشده است"),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "انتخاب نژاد" })).toHaveAttribute(
      "href",
      "/breeds?petId=pet-1",
    );
  });

  it("renders approved guidance and dismisses it through the real backend endpoint", async () => {
    vi.mocked(setGuidancePreference).mockResolvedValue(undefined);
    const user = userEvent.setup();

    renderWithQuery(<PetCare petId="pet-1" />);
    expect(
      await screen.findByText(careGuidanceFixture.items[0].text_fa),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "نیازی ندارم" }));

    await waitFor(() =>
      expect(setGuidancePreference).toHaveBeenCalledWith(
        "pet-1",
        careGuidanceFixture.items[0].id,
        { action: "dismiss", snoozed_until: null },
      ),
    );
    expect(await screen.findByText("این راهنما پنهان شد.")).toBeInTheDocument();
  });

  it("shows a breed-unavailable empty state, not an error, when there is no breed-specific guidance", async () => {
    vi.mocked(getPetCareGuidance).mockResolvedValue({
      disclaimer_fa: "راهنماهای عمومی جایگزین توصیه اختصاصی دامپزشک نیستند.",
      items: [],
      state: "breed_specific_guidance_unavailable",
    });
    renderWithQuery(<PetCare petId="pet-1" />);

    expect(
      await screen.findByText("راهنمای اختصاصی نژاد در دسترس نیست"),
    ).toBeInTheDocument();
  });
});
