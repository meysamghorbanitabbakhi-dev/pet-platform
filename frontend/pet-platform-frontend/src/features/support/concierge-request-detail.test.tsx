import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getCustomerRequest } from "@/lib/api/client";
import { customerRequestFixture } from "@/test/fixtures/gate-fixtures";
import { ConciergeRequestDetail } from "./concierge-request-detail";

vi.mock("next/navigation", () => ({
  usePathname: () => "/support/request-1",
}));

vi.mock("@/lib/api/client", () => ({
  getCustomerRequest: vi.fn(),
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
  });
});
