import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ShopLoading from "./loading";

vi.mock("next/navigation", () => ({
  usePathname: () => "/shop",
}));

describe("ShopLoading", () => {
  it("renders an instant skeleton fallback for the shop page, not a blank screen", () => {
    render(<ShopLoading />);

    expect(screen.getByText("کشف محصول")).toBeInTheDocument();
    expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
  });
});
