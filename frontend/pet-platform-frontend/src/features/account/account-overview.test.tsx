import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  getMeContext,
  listAddresses,
  listHouseholdPets,
  logout,
} from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { addressFixture, meContextFixture } from "@/test/fixtures/gate-fixtures";
import { AccountOverview } from "./account-overview";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/account",
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/api/client", () => ({
  getMeContext: vi.fn(),
  listAddresses: vi.fn(),
  listHouseholdPets: vi.fn(),
  logout: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("AccountOverview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getMeContext).mockResolvedValue(meContextFixture);
    vi.mocked(listHouseholdPets).mockResolvedValue(meContextFixture.pets);
    vi.mocked(listAddresses).mockResolvedValue([addressFixture]);
  });

  it("shows the household's real pets and addresses, not fixtures invented by the client", async () => {
    renderWithQuery(<AccountOverview />);

    expect(await screen.findByText(meContextFixture.pets[0].name)).toBeInTheDocument();
    expect(await screen.findByText(addressFixture.label)).toBeInTheDocument();
    expect(listHouseholdPets).toHaveBeenCalledWith(
      meContextFixture.default_household_id,
    );
  });

  it("confirms before logging out and clears the session on confirm", async () => {
    vi.mocked(logout).mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderWithQuery(<AccountOverview />);

    await screen.findByText(meContextFixture.pets[0].name);
    await user.click(screen.getByRole("button", { name: "خروج از حساب" }));
    expect(logout).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "خروج" }));

    await waitFor(() => expect(logout).toHaveBeenCalled());
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/auth/mobile"));
  });

  it("redirects to the session-expired screen on a 401, not a generic error", async () => {
    vi.mocked(getMeContext).mockRejectedValue(new ApiError("expired", 401));
    renderWithQuery(<AccountOverview />);

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/auth/session-expired"),
    );
  });
});
