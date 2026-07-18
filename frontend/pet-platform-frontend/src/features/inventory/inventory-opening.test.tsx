import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  assessReorder,
  correctEstimate,
  exhaustInventory,
  getInventoryDetail,
  getPolicies,
  openInventory,
  snoozeReorder,
} from "@/lib/api/client";
import {
  inventoryDetailFixture,
  policyFixture,
  reorderAssessmentFixture,
} from "@/test/fixtures/gate-fixtures";
import { InventoryOpening } from "./inventory-opening";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/inventory/unit-1",
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/api/client", () => ({
  assessReorder: vi.fn(),
  correctEstimate: vi.fn(),
  exhaustInventory: vi.fn(),
  getInventoryDetail: vi.fn(),
  getPolicies: vi.fn(),
  openInventory: vi.fn(),
  snoozeReorder: vi.fn(),
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
    vi.mocked(getPolicies).mockResolvedValue(policyFixture);
  });

  it("submits an unknown-share opening when no amount is provided", async () => {
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
    await user.click(screen.getByRole("button", { name: "ثبت" }));

    await waitFor(() =>
      expect(openInventory).toHaveBeenCalledWith("unit-real-1", {
        feeding_context: "unknown",
        remaining: null,
        remaining_grams: null,
      }),
    );
    expect(screen.getByText(/باز شدن بسته ثبت شد/)).toBeInTheDocument();
  });

  it("submits an exact-grams opening, never computing the number client-side", async () => {
    vi.mocked(getInventoryDetail).mockResolvedValue({
      ...inventoryDetailFixture,
      opened_at: null,
      state: "delivered",
    });
    vi.mocked(openInventory).mockResolvedValue({
      basis: {},
      confidence: "high",
      id: "estimate-1",
      inventory_unit_id: inventoryDetailFixture.id,
      provenance: [],
      scope: "household",
    });
    const user = userEvent.setup();

    renderWithQuery(<InventoryOpening unitId={inventoryDetailFixture.id} />);
    await screen.findByText(inventoryDetailFixture.id);

    await user.click(
      screen.getByRole("button", { name: "دقیقاً می‌دانم (گرم)" }),
    );
    await user.type(screen.getByLabelText("گرم باقی‌مانده"), "900");
    await user.click(screen.getByRole("button", { name: "ثبت" }));

    await waitFor(() =>
      expect(openInventory).toHaveBeenCalledWith(inventoryDetailFixture.id, {
        feeding_context: "unknown",
        remaining: { mode: "grams", grams: 900 },
      }),
    );
  });

  it("submits a semantic level opening only when the policy allows it", async () => {
    vi.mocked(getInventoryDetail).mockResolvedValue({
      ...inventoryDetailFixture,
      opened_at: null,
      state: "delivered",
    });
    vi.mocked(openInventory).mockResolvedValue({
      basis: {},
      confidence: "mid",
      id: "estimate-1",
      inventory_unit_id: inventoryDetailFixture.id,
      provenance: [],
      scope: "household",
    });
    const user = userEvent.setup();

    renderWithQuery(<InventoryOpening unitId={inventoryDetailFixture.id} />);
    await screen.findByText(inventoryDetailFixture.id);

    await user.click(
      screen.getByRole("button", { name: "تقریباً می‌دانم (سطح)" }),
    );
    await user.click(
      screen.getByRole("button", { name: "بیشتر از نصف (۵۰ تا ۷۵٪)" }),
    );
    await user.click(screen.getByRole("button", { name: "ثبت" }));

    await waitFor(() =>
      expect(openInventory).toHaveBeenCalledWith(inventoryDetailFixture.id, {
        feeding_context: "unknown",
        remaining: { mode: "level", level: "more_than_half" },
      }),
    );
  });

  it("hides the level option entirely when semantic level estimation is policy-disabled", async () => {
    vi.mocked(getPolicies).mockResolvedValue({
      ...policyFixture,
      semantic_level_estimation_enabled: false,
    });
    vi.mocked(getInventoryDetail).mockResolvedValue({
      ...inventoryDetailFixture,
      opened_at: null,
      state: "delivered",
    });

    renderWithQuery(<InventoryOpening unitId={inventoryDetailFixture.id} />);
    await screen.findByText(inventoryDetailFixture.id);

    expect(
      screen.queryByRole("button", { name: "تقریباً می‌دانم (سطح)" }),
    ).not.toBeInTheDocument();
  });

  it("renders already-opened inventory without submitting another open mutation", async () => {
    vi.mocked(getInventoryDetail).mockResolvedValue({
      ...inventoryDetailFixture,
      opened_at: "2026-07-17T10:00:00Z",
      state: "opened",
    });

    renderWithQuery(<InventoryOpening unitId="unit-opened" />);

    expect(await screen.findByText(/قبلاً ثبت شده/)).toBeInTheDocument();
    expect(screen.queryByLabelText("گرم باقی‌مانده")).not.toBeInTheDocument();
    expect(openInventory).not.toHaveBeenCalled();
  });

  it("shows unknown household share without a per-pet number when assignments have no known basis points", async () => {
    vi.mocked(getInventoryDetail).mockResolvedValue({
      ...inventoryDetailFixture,
      opened_at: "2026-07-17T10:00:00Z",
      shares_known: false,
      state: "opened",
    });

    renderWithQuery(<InventoryOpening unitId={inventoryDetailFixture.id} />);

    expect(await screen.findByText("سهم نامشخص")).toBeInTheDocument();
  });

  it("lets an opened unit be marked exhausted and invalidates inventory after", async () => {
    vi.mocked(getInventoryDetail).mockResolvedValue({
      ...inventoryDetailFixture,
      opened_at: "2026-07-17T10:00:00Z",
      state: "opened",
    });
    vi.mocked(exhaustInventory).mockResolvedValue(undefined);
    const user = userEvent.setup();

    renderWithQuery(<InventoryOpening unitId={inventoryDetailFixture.id} />);
    await screen.findByText(/قبلاً ثبت شده/);

    await user.click(
      screen.getByRole("button", { name: "این واحد تمام شده است" }),
    );

    await waitFor(() =>
      expect(exhaustInventory).toHaveBeenCalledWith(inventoryDetailFixture.id),
    );
  });

  it("lets an opened unit's estimate be corrected with a new exact-grams reading", async () => {
    vi.mocked(getInventoryDetail).mockResolvedValue({
      ...inventoryDetailFixture,
      opened_at: "2026-07-17T10:00:00Z",
      state: "opened",
    });
    vi.mocked(correctEstimate).mockResolvedValue({
      basis: {},
      confidence: "high",
      id: "estimate-2",
      inventory_unit_id: inventoryDetailFixture.id,
      provenance: [],
      scope: "household",
    });
    const user = userEvent.setup();

    renderWithQuery(<InventoryOpening unitId={inventoryDetailFixture.id} />);
    await screen.findByText(/قبلاً ثبت شده/);

    await user.click(
      screen.getByRole("button", { name: "دقیقاً می‌دانم (گرم)" }),
    );
    await user.type(screen.getByLabelText("گرم باقی‌مانده"), "450");
    await user.click(screen.getByRole("button", { name: "ثبت" }));

    await waitFor(() =>
      expect(correctEstimate).toHaveBeenCalledWith(inventoryDetailFixture.id, {
        feeding_context: "unknown",
        remaining: { mode: "grams", grams: 450 },
      }),
    );
    expect(
      await screen.findByText("تخمین به‌روزرسانی شد."),
    ).toBeInTheDocument();
  });

  it("shows the backend reorder outcome and offers a snooze, never inventing eligibility client-side", async () => {
    vi.mocked(getInventoryDetail).mockResolvedValue({
      ...inventoryDetailFixture,
      opened_at: "2026-07-17T10:00:00Z",
      state: "opened",
    });
    vi.mocked(assessReorder).mockResolvedValue(reorderAssessmentFixture);
    vi.mocked(snoozeReorder).mockResolvedValue(undefined);
    const user = userEvent.setup();

    renderWithQuery(<InventoryOpening unitId={inventoryDetailFixture.id} />);
    await screen.findByText(/قبلاً ثبت شده/);

    await user.click(screen.getByRole("button", { name: "بررسی وضعیت" }));

    expect(
      await screen.findByText("موجودی فعلی هنوز کافی است."),
    ).toBeInTheDocument();
    expect(screen.getByText(/۱۲ تا ۱۸ روز/)).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "به‌خواب بردن تا ۷۲ ساعت" }),
    );
    await user.click(
      screen.getByRole("button", { name: "تایید به‌خواب بردن" }),
    );

    await waitFor(() =>
      expect(snoozeReorder).toHaveBeenCalledWith(inventoryDetailFixture.id, {
        hours: 72,
      }),
    );
  });
});
