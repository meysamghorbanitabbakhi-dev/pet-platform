import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getMeContext, listHouseholdInventory } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import {
  inventoryListFixture,
  meContextFixture,
} from "@/test/fixtures/gate-fixtures";
import { InventoryList } from "./inventory-list";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/inventory",
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/api/client", () => ({
  getMeContext: vi.fn(),
  listHouseholdInventory: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("InventoryList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getMeContext).mockResolvedValue(meContextFixture);
  });

  it("renders the household's real inventory units with their backend state", async () => {
    vi.mocked(listHouseholdInventory).mockResolvedValue(inventoryListFixture);
    renderWithQuery(<InventoryList />);

    expect(
      await screen.findByText(inventoryListFixture[0].label),
    ).toBeInTheDocument();
    expect(listHouseholdInventory).toHaveBeenCalledWith(
      meContextFixture.default_household_id,
    );
  });

  it("shows an empty state, not an error, when the household has no inventory yet", async () => {
    vi.mocked(listHouseholdInventory).mockResolvedValue([]);
    renderWithQuery(<InventoryList />);

    expect(
      await screen.findByText("هنوز واحد انباری ثبت نشده است"),
    ).toBeInTheDocument();
  });

  it("shows a distinct empty state, not a blank screen, when the household itself hasn't been created yet", async () => {
    vi.mocked(getMeContext).mockResolvedValue({
      ...meContextFixture,
      default_household_id: null,
      households: [],
      onboarding: { ...meContextFixture.onboarding, needs_household: true },
    });

    renderWithQuery(<InventoryList />);

    expect(
      await screen.findByText("هنوز خانواری ثبت نشده است"),
    ).toBeInTheDocument();
    expect(listHouseholdInventory).not.toHaveBeenCalled();
  });

  it("redirects to the session-expired screen on a 401", async () => {
    vi.mocked(getMeContext).mockRejectedValue(new ApiError("expired", 401));
    renderWithQuery(<InventoryList />);

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/auth/session-expired"),
    );
  });
});
