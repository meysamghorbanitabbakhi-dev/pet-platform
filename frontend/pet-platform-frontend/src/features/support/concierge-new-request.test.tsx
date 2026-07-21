import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createCustomerRequest,
  getMeContext,
  getPolicies,
} from "@/lib/api/client";
import {
  customerRequestFixture,
  meContextFixture,
  policyFixture,
} from "@/test/fixtures/gate-fixtures";
import { ConciergeNewRequest } from "./concierge-new-request";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/support/new",
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/api/client", () => ({
  createCustomerRequest: vi.fn(),
  getMeContext: vi.fn(),
  getPolicies: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("ConciergeNewRequest", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getMeContext).mockResolvedValue(meContextFixture);
    vi.mocked(getPolicies).mockResolvedValue(policyFixture);
  });

  it("shows the backend's own no-guarantee acknowledgement text before submission", async () => {
    renderWithQuery(<ConciergeNewRequest />);
    expect(
      await screen.findByText(
        policyFixture.customer_request_acknowledgement_fa,
      ),
    ).toBeInTheDocument();
  });

  it("shows a policy-hidden empty state, not a form, when concierge requests are disabled", async () => {
    vi.mocked(getPolicies).mockResolvedValue({
      ...policyFixture,
      concierge_requests_enabled: false,
    });
    renderWithQuery(<ConciergeNewRequest />);

    expect(
      await screen.findByText("این قابلیت در دسترس نیست"),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("پیام شما")).not.toBeInTheDocument();
  });

  it("submits the request scoped to the household and navigates to its detail page", async () => {
    vi.mocked(createCustomerRequest).mockResolvedValue(customerRequestFixture);
    const user = userEvent.setup();

    renderWithQuery(<ConciergeNewRequest />);
    await user.click(
      await screen.findByRole("button", { name: "درخواست تامین محصول" }),
    );
    await user.type(
      screen.getByLabelText("پیام شما"),
      "آیا این محصول برای نژاد پرشین مناسب است؟",
    );
    await user.click(screen.getByRole("button", { name: "پیامک" }));
    await user.click(screen.getByRole("button", { name: "ثبت درخواست" }));

    await waitFor(() =>
      expect(createCustomerRequest).toHaveBeenCalledWith(
        {
          contact_preference: "sms",
          household_id: meContextFixture.default_household_id,
          message_fa: "آیا این محصول برای نژاد پرشین مناسب است؟",
          request_type: "concierge_sourcing",
        },
        expect.any(String),
      ),
    );
    await waitFor(() =>
      expect(push).toHaveBeenCalledWith(
        `/support/${customerRequestFixture.id}`,
      ),
    );
  });
});
