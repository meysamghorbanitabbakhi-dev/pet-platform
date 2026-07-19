import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { listOrders } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { orderListPageFixture } from "@/test/fixtures/gate-fixtures";
import { OrderHistory } from "./order-history";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/orders",
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/api/client", () => ({
  listOrders: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("OrderHistory", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listOrders).mockResolvedValue(orderListPageFixture);
  });

  it("links each real order to its detail page with its backend status", async () => {
    renderWithQuery(<OrderHistory />);

    const link = await screen.findByRole("link", {
      name: /پرداخت تایید شده/,
    });
    expect(link).toHaveAttribute(
      "href",
      `/orders/${orderListPageFixture.items[0].id}`,
    );
  });

  it("filters the already-fetched list by status without a second network call", async () => {
    const user = userEvent.setup();
    renderWithQuery(<OrderHistory />);
    await screen.findByRole("link", { name: /پرداخت تایید شده/ });

    await user.click(screen.getByRole("button", { name: "تحویل‌شده" }));

    expect(
      screen.getByText("سفارشی با این وضعیت یافت نشد."),
    ).toBeInTheDocument();
    expect(listOrders).toHaveBeenCalledTimes(1);
  });

  it("shows an empty state, not an error, when there is no order history", async () => {
    vi.mocked(listOrders).mockResolvedValue({
      items: [],
      page: { has_more: false, limit: 25, offset: 0, total: 0 },
    });
    renderWithQuery(<OrderHistory />);

    expect(
      await screen.findByText("هنوز سفارشی ثبت نشده است"),
    ).toBeInTheDocument();
  });

  it("redirects to the session-expired screen on a 401", async () => {
    vi.mocked(listOrders).mockRejectedValue(new ApiError("expired", 401));
    renderWithQuery(<OrderHistory />);

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/auth/session-expired"),
    );
  });
});
