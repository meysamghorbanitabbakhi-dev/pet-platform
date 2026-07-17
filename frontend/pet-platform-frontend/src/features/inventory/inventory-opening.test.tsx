import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getInventoryDetail, openInventory } from "@/lib/api/client";
import { inventoryDetailFixture } from "@/test/fixtures/gate-fixtures";
import { InventoryOpening } from "./inventory-opening";

vi.mock("next/navigation", () => ({
  usePathname: () => "/inventory/unit-1",
}));

vi.mock("@/lib/api/client", () => ({
  getInventoryDetail: vi.fn(),
  openInventory: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("InventoryOpening", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches inventory detail by route unit id and opens the same real id", async () => {
    vi.mocked(getInventoryDetail).mockResolvedValue({
      ...inventoryDetailFixture,
      id: "unit-real-1",
      opened_at: null,
      state: "delivered",
    });
    vi.mocked(openInventory).mockResolvedValue({
      basis: {},
      confidence: "unknown",
      id: "estimate-1",
      inventory_unit_id: "unit-real-1",
      provenance: [],
      scope: "household",
    });
    const user = userEvent.setup();

    renderWithQuery(<InventoryOpening unitId="unit-real-1" />);

    expect(await screen.findByText("unit-real-1")).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "تایید باز شدن بسته" }),
    );

    await waitFor(() =>
      expect(openInventory).toHaveBeenCalledWith("unit-real-1", {
        feeding_context: "unknown",
        remaining: null,
        remaining_grams: null,
      }),
    );
    expect(screen.getByText(/باز شدن بسته ثبت شد/)).toBeInTheDocument();
  });

  it("renders already-opened inventory without submitting another open mutation", async () => {
    vi.mocked(getInventoryDetail).mockResolvedValue({
      ...inventoryDetailFixture,
      opened_at: "2026-07-17T10:00:00Z",
      state: "opened",
    });

    renderWithQuery(<InventoryOpening unitId="unit-opened" />);

    expect(await screen.findByText(/قبلاً ثبت شده/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "تایید باز شدن بسته" }),
    ).not.toBeInTheDocument();
  });
});
