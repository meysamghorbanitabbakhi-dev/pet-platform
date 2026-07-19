import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getBreedDetail, selectPetBreed } from "@/lib/api/client";
import { breedDetailFixture } from "@/test/fixtures/gate-fixtures";
import { BreedDetail } from "./breed-detail";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/breeds/persian",
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/api/client", () => ({
  getBreedDetail: vi.fn(),
  selectPetBreed: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("BreedDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getBreedDetail).mockResolvedValue(breedDetailFixture);
  });

  it("shows the veterinary-approved claim with its source, never an unattributed claim", async () => {
    renderWithQuery(<BreedDetail breedId="persian" />);

    expect(
      await screen.findByText(breedDetailFixture.claims[0].text_fa),
    ).toBeInTheDocument();
    expect(screen.getByText(/منبع: منبع تاییدشده/)).toBeInTheDocument();
  });

  it("does not show a select-breed action without a pet in context", async () => {
    renderWithQuery(<BreedDetail breedId="persian" />);
    await screen.findByText(breedDetailFixture.breed.name_fa);

    expect(
      screen.queryByRole("button", { name: "انتخاب این نژاد برای پت" }),
    ).not.toBeInTheDocument();
  });

  it("selects the breed for the given pet and navigates to its care page", async () => {
    vi.mocked(selectPetBreed).mockResolvedValue(undefined);
    const user = userEvent.setup();

    renderWithQuery(<BreedDetail breedId="persian" petId="pet-1" />);
    await user.click(
      await screen.findByRole("button", { name: "انتخاب این نژاد برای پت" }),
    );

    await waitFor(() =>
      expect(selectPetBreed).toHaveBeenCalledWith("pet-1", {
        breed_reference_id: "persian",
        identification_source: "owner_reported",
        selection_mode: "known",
      }),
    );
    await waitFor(() => expect(push).toHaveBeenCalledWith("/pets/pet-1/care"));
  });
});
