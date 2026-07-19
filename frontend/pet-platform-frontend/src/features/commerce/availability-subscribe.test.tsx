import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  cancelAvailabilitySubscription,
  listAvailabilitySubscriptions,
  subscribeAvailability,
} from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import {
  availabilitySubscriptionFixture,
  availabilitySubscriptionPageFixture,
} from "@/test/fixtures/gate-fixtures";
import { AvailabilitySubscribe } from "./availability-subscribe";

vi.mock("@/lib/api/client", () => ({
  cancelAvailabilitySubscription: vi.fn(),
  listAvailabilitySubscriptions: vi.fn(),
  subscribeAvailability: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("AvailabilitySubscribe", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("subscribes to restock notification through the real backend endpoint", async () => {
    vi.mocked(listAvailabilitySubscriptions).mockResolvedValue(
      availabilitySubscriptionPageFixture,
    );
    vi.mocked(subscribeAvailability).mockResolvedValue(
      availabilitySubscriptionFixture,
    );
    const user = userEvent.setup();

    renderWithQuery(<AvailabilitySubscribe offerId={availabilitySubscriptionFixture.offer_id} />);

    const button = await screen.findByRole("button", {
      name: "اطلاع بده وقتی موجود شد",
    });
    await user.click(button);

    await waitFor(() =>
      expect(subscribeAvailability).toHaveBeenCalledWith(
        availabilitySubscriptionFixture.offer_id,
      ),
    );
  });

  it("shows the active subscription and cancels it through the real backend endpoint", async () => {
    vi.mocked(listAvailabilitySubscriptions).mockResolvedValue({
      items: [availabilitySubscriptionFixture],
      page: { has_more: false, limit: 25, offset: 0, total: 1 },
    });
    vi.mocked(cancelAvailabilitySubscription).mockResolvedValue({
      ...availabilitySubscriptionFixture,
      status: "cancelled",
    });
    const user = userEvent.setup();

    renderWithQuery(
      <AvailabilitySubscribe offerId={availabilitySubscriptionFixture.offer_id} />,
    );

    expect(
      await screen.findByText(/به شما اطلاع داده می‌شود/),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "لغو اطلاع‌رسانی" }));

    await waitFor(() =>
      expect(cancelAvailabilitySubscription).toHaveBeenCalledWith(
        availabilitySubscriptionFixture.offer_id,
      ),
    );
  });

  it("shows a policy-disabled message on 409, not a generic error", async () => {
    vi.mocked(listAvailabilitySubscriptions).mockResolvedValue(
      availabilitySubscriptionPageFixture,
    );
    vi.mocked(subscribeAvailability).mockRejectedValue(
      new ApiError("خطا", 409),
    );
    const user = userEvent.setup();

    renderWithQuery(
      <AvailabilitySubscribe offerId={availabilitySubscriptionFixture.offer_id} />,
    );
    await user.click(
      await screen.findByRole("button", { name: "اطلاع بده وقتی موجود شد" }),
    );

    expect(
      await screen.findByText("اطلاع‌رسانی موجودی فعلاً در دسترس نیست."),
    ).toBeInTheDocument();
  });
});
