import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { listCustomerRequests } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { customerRequestFixture, customerRequestPageFixture } from "@/test/fixtures/gate-fixtures";
import { ConciergeRequestList } from "./concierge-request-list";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/support",
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/api/client", () => ({
  listCustomerRequests: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("ConciergeRequestList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("links each real request to its own detail page with a customer-safe status label", async () => {
    vi.mocked(listCustomerRequests).mockResolvedValue(customerRequestPageFixture);
    renderWithQuery(<ConciergeRequestList />);

    const link = await screen.findByRole("link", { name: /پشتیبانی/ });
    expect(link).toHaveAttribute("href", `/support/${customerRequestFixture.id}`);
    expect(screen.getByText("ثبت‌شده")).toBeInTheDocument();
  });

  it("shows an empty state, not an error, when there is no request history", async () => {
    vi.mocked(listCustomerRequests).mockResolvedValue({
      items: [],
      page: { has_more: false, limit: 25, offset: 0, total: 0 },
    });
    renderWithQuery(<ConciergeRequestList />);

    expect(
      await screen.findByText("هنوز درخواستی ثبت نشده است"),
    ).toBeInTheDocument();
  });

  it("redirects to the session-expired screen on a 401", async () => {
    vi.mocked(listCustomerRequests).mockRejectedValue(new ApiError("expired", 401));
    renderWithQuery(<ConciergeRequestList />);

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/auth/session-expired"),
    );
  });
});
