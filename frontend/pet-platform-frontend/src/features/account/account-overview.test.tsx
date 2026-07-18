import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  deleteAddress,
  getMeContext,
  getWallet,
  listAddresses,
  listHouseholdPets,
  logout,
  updateAddress,
} from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import {
  addressFixture,
  meContextFixture,
  walletFixture,
} from "@/test/fixtures/gate-fixtures";
import { AccountOverview } from "./account-overview";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/account",
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/api/client", () => ({
  deleteAddress: vi.fn(),
  getMeContext: vi.fn(),
  getWallet: vi.fn(),
  listAddresses: vi.fn(),
  listHouseholdPets: vi.fn(),
  logout: vi.fn(),
  updateAddress: vi.fn(),
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
    vi.mocked(getWallet).mockResolvedValue(walletFixture);
  });

  it("shows the household's real pets and addresses, not fixtures invented by the client", async () => {
    renderWithQuery(<AccountOverview />);

    expect(
      await screen.findByText(meContextFixture.pets[0].name),
    ).toBeInTheDocument();
    expect(await screen.findByText(addressFixture.label)).toBeInTheDocument();
    expect(listHouseholdPets).toHaveBeenCalledWith(
      meContextFixture.default_household_id,
    );
  });

  it("shows the real wallet balance from the backend", async () => {
    renderWithQuery(<AccountOverview />);

    await screen.findByText(meContextFixture.pets[0].name);
    expect(getWallet).toHaveBeenCalledWith(
      meContextFixture.default_household_id,
    );
    expect(await screen.findByText("۰ تومان")).toBeInTheDocument();
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

  it("edits an address and refreshes the list from the real update response", async () => {
    vi.mocked(updateAddress).mockResolvedValue({
      ...addressFixture,
      label: "محل کار",
    });
    const user = userEvent.setup();
    renderWithQuery(<AccountOverview />);

    await screen.findByText(addressFixture.label);
    await user.click(screen.getByRole("button", { name: "ویرایش" }));

    const labelInput = screen.getByLabelText("برچسب");
    await user.clear(labelInput);
    await user.type(labelInput, "محل کار");
    await user.click(screen.getByRole("button", { name: "ذخیره" }));

    await waitFor(() =>
      expect(updateAddress).toHaveBeenCalledWith(
        meContextFixture.default_household_id,
        addressFixture.id,
        expect.objectContaining({ label: "محل کار" }),
      ),
    );
    expect(screen.queryByText("ویرایش آدرس")).not.toBeInTheDocument();
  });

  it("deletes an address after explicit confirmation, not on the first click", async () => {
    vi.mocked(deleteAddress).mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderWithQuery(<AccountOverview />);

    await screen.findByText(addressFixture.label);
    await user.click(screen.getByRole("button", { name: "حذف" }));
    expect(deleteAddress).not.toHaveBeenCalled();

    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "حذف" }));

    await waitFor(() =>
      expect(deleteAddress).toHaveBeenCalledWith(
        meContextFixture.default_household_id,
        addressFixture.id,
      ),
    );
  });
});
