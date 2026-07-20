import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  acceptConciergeOffer,
  declineConciergeOffer,
  getCustomerRequest,
  getPolicies,
  listAddresses,
  listConciergeOffers,
  refreshConciergeOffer,
} from "@/lib/api/client";
import {
  addressFixture,
  conciergeCustomerRequestFixture,
  conciergeOfferFixture,
  customerRequestFixture,
  policyDisabledFixture,
  policyFixture,
} from "@/test/fixtures/gate-fixtures";
import { ConciergeRequestDetail } from "./concierge-request-detail";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/support/request-1",
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/api/client", () => ({
  acceptConciergeOffer: vi.fn(),
  declineConciergeOffer: vi.fn(),
  getCustomerRequest: vi.fn(),
  getPolicies: vi.fn(),
  listAddresses: vi.fn(),
  listConciergeOffers: vi.fn(),
  refreshConciergeOffer: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("ConciergeRequestDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getPolicies).mockResolvedValue(policyDisabledFixture);
  });

  it("never exposes internal operator notes, only the customer-facing acknowledgement and unmet promises", async () => {
    vi.mocked(getCustomerRequest).mockResolvedValue(customerRequestFixture);
    renderWithQuery(<ConciergeRequestDetail requestId="request-1" />);

    expect(
      await screen.findByText(customerRequestFixture.acknowledgement_fa),
    ).toBeInTheDocument();
    expect(
      screen.getByText("این درخواست تضمین موجودی نیست."),
    ).toBeInTheDocument();
    expect(getCustomerRequest).toHaveBeenCalledWith("request-1");
    expect(listConciergeOffers).not.toHaveBeenCalled();
  });

  it("does not render the concierge offer section while the policy leaves it disabled", async () => {
    vi.mocked(getCustomerRequest).mockResolvedValue(
      conciergeCustomerRequestFixture,
    );
    renderWithQuery(
      <ConciergeRequestDetail requestId={conciergeCustomerRequestFixture.id} />,
    );

    expect(
      await screen.findByText(conciergeCustomerRequestFixture.message_fa),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("concierge-offer-card"),
    ).not.toBeInTheDocument();
    expect(listConciergeOffers).not.toHaveBeenCalled();
  });

  it("shows a presented concierge offer and lets the customer accept it with a chosen address", async () => {
    vi.mocked(getPolicies).mockResolvedValue({
      ...policyFixture,
      concierge_offers_enabled: true,
    });
    vi.mocked(getCustomerRequest).mockResolvedValue(
      conciergeCustomerRequestFixture,
    );
    vi.mocked(listConciergeOffers).mockResolvedValue([conciergeOfferFixture]);
    vi.mocked(listAddresses).mockResolvedValue([addressFixture]);
    vi.mocked(acceptConciergeOffer).mockResolvedValue({
      ...conciergeOfferFixture,
      status: "accepted",
      resulting_order_id: "order-from-concierge",
    });
    const user = userEvent.setup();

    renderWithQuery(
      <ConciergeRequestDetail requestId={conciergeCustomerRequestFixture.id} />,
    );
    expect(
      await screen.findByTestId("concierge-offer-card"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(conciergeOfferFixture.title_fa ?? ""),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "پذیرش پیشنهاد" }));
    await user.click(
      await screen.findByRole("button", {
        name: `${addressFixture.label} · ${addressFixture.recipient_name}`,
      }),
    );

    await waitFor(() =>
      expect(acceptConciergeOffer).toHaveBeenCalledWith(
        conciergeOfferFixture.id,
        { address_id: addressFixture.id },
      ),
    );
  });

  it("lets the customer decline a presented concierge offer with a reason", async () => {
    vi.mocked(getPolicies).mockResolvedValue({
      ...policyFixture,
      concierge_offers_enabled: true,
    });
    vi.mocked(getCustomerRequest).mockResolvedValue(
      conciergeCustomerRequestFixture,
    );
    vi.mocked(listConciergeOffers).mockResolvedValue([conciergeOfferFixture]);
    vi.mocked(declineConciergeOffer).mockResolvedValue({
      ...conciergeOfferFixture,
      status: "declined",
    });
    const user = userEvent.setup();

    renderWithQuery(
      <ConciergeRequestDetail requestId={conciergeCustomerRequestFixture.id} />,
    );
    await screen.findByTestId("concierge-offer-card");

    await user.click(screen.getByRole("button", { name: "رد پیشنهاد" }));
    await user.type(
      screen.getByLabelText("دلیل رد (اختیاری)"),
      "دیگر لازم نیست",
    );
    await user.click(screen.getByRole("button", { name: "تایید رد پیشنهاد" }));

    await waitFor(() =>
      expect(declineConciergeOffer).toHaveBeenCalledWith(
        conciergeOfferFixture.id,
        { reason: "دیگر لازم نیست" },
      ),
    );
  });

  it("lets the customer request a refresh of an expired concierge offer", async () => {
    vi.mocked(getPolicies).mockResolvedValue({
      ...policyFixture,
      concierge_offers_enabled: true,
    });
    vi.mocked(getCustomerRequest).mockResolvedValue(
      conciergeCustomerRequestFixture,
    );
    vi.mocked(listConciergeOffers).mockResolvedValue([
      { ...conciergeOfferFixture, status: "expired" },
    ]);
    vi.mocked(refreshConciergeOffer).mockResolvedValue({
      ...conciergeOfferFixture,
      id: "refreshed-offer",
      status: "refresh_requested",
      refreshed_from_offer_id: conciergeOfferFixture.id,
    });
    const user = userEvent.setup();

    renderWithQuery(
      <ConciergeRequestDetail requestId={conciergeCustomerRequestFixture.id} />,
    );
    await screen.findByTestId("concierge-offer-card");

    await user.click(
      screen.getByRole("button", { name: "درخواست بررسی دوباره" }),
    );

    await waitFor(() =>
      expect(refreshConciergeOffer).toHaveBeenCalledWith(
        conciergeOfferFixture.id,
      ),
    );
  });
});
