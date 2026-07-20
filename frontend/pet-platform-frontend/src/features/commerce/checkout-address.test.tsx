import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createAddress,
  createHousehold,
  getMeContext,
  listAddresses,
} from "@/lib/api/client";
import { addCartItem } from "@/lib/cart";
import {
  addressFixture,
  meContextFixture,
} from "@/test/fixtures/gate-fixtures";
import { CheckoutAddress } from "./checkout-address";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/checkout/address",
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/api/client", () => ({
  createAddress: vi.fn(),
  createHousehold: vi.fn(),
  getMeContext: vi.fn(),
  listAddresses: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("CheckoutAddress", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    addCartItem("offer-1");
    vi.mocked(getMeContext).mockResolvedValue(meContextFixture);
  });

  it("lists the household's real saved addresses from the backend", async () => {
    vi.mocked(listAddresses).mockResolvedValue([addressFixture]);

    renderWithQuery(<CheckoutAddress />);

    expect(await screen.findByText(addressFixture.label)).toBeInTheDocument();
    expect(listAddresses).toHaveBeenCalledWith(
      meContextFixture.default_household_id,
    );
  });

  it("selects an existing address and proceeds to review", async () => {
    vi.mocked(listAddresses).mockResolvedValue([addressFixture]);
    const user = userEvent.setup();

    renderWithQuery(<CheckoutAddress />);
    await user.click(
      await screen.findByRole("button", { name: "استفاده از این آدرس" }),
    );

    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/checkout/review"),
    );
  });

  it("submits a new address through the real backend and proceeds to review", async () => {
    vi.mocked(listAddresses).mockResolvedValue([]);
    vi.mocked(createAddress).mockResolvedValue(addressFixture);
    const user = userEvent.setup();

    renderWithQuery(<CheckoutAddress />);

    await user.type(
      await screen.findByLabelText("نام گیرنده"),
      "مالک خانه",
    );
    await user.type(screen.getByLabelText("موبایل گیرنده"), "09121234567");
    await user.type(screen.getByLabelText("استان"), "تهران");
    await user.type(screen.getByLabelText("شهر"), "تهران");
    await user.type(
      screen.getByLabelText("آدرس کامل"),
      "خیابان ولیعصر پلاک ۱۲",
    );
    await user.click(
      screen.getByRole("button", { name: "ثبت آدرس و بازبینی سفارش" }),
    );

    await waitFor(() =>
      expect(createAddress).toHaveBeenCalledWith(
        meContextFixture.default_household_id,
        expect.objectContaining({
          address_line: "خیابان ولیعصر پلاک ۱۲",
          city: "تهران",
          recipient_mobile: "09121234567",
          recipient_name: "مالک خانه",
        }),
      ),
    );
    expect(createHousehold).not.toHaveBeenCalled();
    await waitFor(() => expect(push).toHaveBeenCalledWith("/checkout/review"));
  });

  it("shows an empty-cart state instead of an address form when the cart has no items", async () => {
    localStorage.clear();

    renderWithQuery(<CheckoutAddress />);

    expect(screen.getByText("سبد خرید خالی است")).toBeInTheDocument();
    expect(listAddresses).not.toHaveBeenCalled();
  });
});
