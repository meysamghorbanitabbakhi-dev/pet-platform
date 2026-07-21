import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { listBreeds, searchBreeds } from "@/lib/api/client";
import {
  breedListFixture,
  breedSearchFixture,
} from "@/test/fixtures/gate-fixtures";
import { BreedSearch } from "./breed-search";

vi.mock("next/navigation", () => ({
  usePathname: () => "/breeds",
}));

vi.mock("@/lib/api/client", () => ({
  listBreeds: vi.fn(),
  searchBreeds: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("BreedSearch", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listBreeds).mockResolvedValue(breedListFixture);
    vi.mocked(searchBreeds).mockResolvedValue(breedSearchFixture);
  });

  it("lists breeds by default and preserves petId in the detail link", async () => {
    renderWithQuery(<BreedSearch petId="pet-1" />);

    const link = await screen.findByRole("link", { name: /پرشین/ });
    expect(link).toHaveAttribute(
      "href",
      `/breeds/${breedListFixture.items[0].id}?petId=pet-1`,
    );
  });

  it("searches instead of listing once a query is typed", async () => {
    const user = userEvent.setup();
    renderWithQuery(<BreedSearch />);

    await user.type(screen.getByLabelText("جستجو"), "پرشین");

    await waitFor(() =>
      expect(searchBreeds).toHaveBeenCalledWith("پرشین", undefined),
    );
  });
});
