import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { getPoliciesServer, listOffersServer } from "@/lib/api/server";
import { offersFixture, policyFixture } from "@/test/fixtures/gate-fixtures";
import ShopPage from "./page";

vi.mock("next/navigation", () => ({
  usePathname: () => "/shop",
}));

vi.mock("@/lib/api/server", () => ({
  getPoliciesServer: vi.fn(),
  listOffersServer: vi.fn(),
}));

describe("ShopPage", () => {
  it("renders offers loaded from the real backend-backed server call", async () => {
    vi.mocked(listOffersServer).mockResolvedValue(offersFixture);
    vi.mocked(getPoliciesServer).mockResolvedValue(policyFixture);

    render(await ShopPage());

    expect(
      await screen.findByText(offersFixture[0].title_fa),
    ).toBeInTheDocument();
    expect(listOffersServer).toHaveBeenCalled();
    expect(getPoliciesServer).toHaveBeenCalled();
  });

  it("shows a distinct error state, not a blank page, when the offer list fails to load", async () => {
    vi.mocked(listOffersServer).mockRejectedValue(new Error("network"));
    vi.mocked(getPoliciesServer).mockResolvedValue(policyFixture);

    render(await ShopPage());

    expect(
      await screen.findByText("فروشگاه در دسترس نیست"),
    ).toBeInTheDocument();
  });
});
