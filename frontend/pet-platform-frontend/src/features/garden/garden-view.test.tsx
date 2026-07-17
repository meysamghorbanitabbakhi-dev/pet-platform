import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getGarden, placeGardenObject, returnGardenObject } from "@/lib/api/client";
import { gardenStateFixture } from "@/test/fixtures/gate-fixtures";
import { GardenView } from "./garden-view";

vi.mock("next/navigation", () => ({
  usePathname: () => "/garden/pet-1",
}));

vi.mock("@/lib/api/client", () => ({
  getGarden: vi.fn(),
  placeGardenObject: vi.fn(),
  returnGardenObject: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("GardenView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows an empty garden state without inventing a purchase or streak reward", async () => {
    vi.mocked(getGarden).mockResolvedValue({
      ...gardenStateFixture,
      objects: [],
    });
    renderWithQuery(<GardenView petId="pet-1" />);

    expect(await screen.findByText("باغ هنوز خالی است")).toBeInTheDocument();
  });

  it("places a revealed reward through the real backend endpoint, never a client-only success", async () => {
    vi.mocked(getGarden).mockResolvedValue(gardenStateFixture);
    vi.mocked(placeGardenObject).mockResolvedValue(undefined);
    const user = userEvent.setup();

    renderWithQuery(<GardenView petId="pet-1" />);
    await user.click(await screen.findByRole("button", { name: "watering_can" }));
    await user.click(screen.getByRole("button", { name: "وسط وسط" }));

    await waitFor(() =>
      expect(placeGardenObject).toHaveBeenCalledWith(
        gardenStateFixture.objects[0].id,
        { position_x: 500, position_y: 500, quadrant: 1 },
      ),
    );
  });

  it("returns a placed object to storage through the real backend endpoint", async () => {
    vi.mocked(getGarden).mockResolvedValue({
      ...gardenStateFixture,
      objects: [{ ...gardenStateFixture.objects[0], state: "placed" }],
    });
    vi.mocked(returnGardenObject).mockResolvedValue(undefined);
    const user = userEvent.setup();

    renderWithQuery(<GardenView petId="pet-1" />);
    await user.click(await screen.findByRole("button", { name: "watering_can" }));
    await user.click(
      screen.getByRole("button", { name: "بازگرداندن به انبار" }),
    );

    await waitFor(() =>
      expect(returnGardenObject).toHaveBeenCalledWith(
        gardenStateFixture.objects[0].id,
      ),
    );
  });

  it("moves a placed object to a new spot in one step, without first returning it", async () => {
    vi.mocked(getGarden).mockResolvedValue({
      ...gardenStateFixture,
      objects: [{ ...gardenStateFixture.objects[0], state: "placed" }],
    });
    vi.mocked(placeGardenObject).mockResolvedValue(undefined);
    const user = userEvent.setup();

    renderWithQuery(<GardenView petId="pet-1" />);
    await user.click(await screen.findByRole("button", { name: "watering_can" }));
    await user.click(screen.getByRole("button", { name: "جابه‌جایی" }));
    await user.click(screen.getByRole("button", { name: "پایین چپ" }));

    await waitFor(() =>
      expect(placeGardenObject).toHaveBeenCalledWith(
        gardenStateFixture.objects[0].id,
        { position_x: 250, position_y: 750, quadrant: 1 },
      ),
    );
    expect(returnGardenObject).not.toHaveBeenCalled();
  });

  it("highlights the reward named by the completion link", async () => {
    vi.mocked(getGarden).mockResolvedValue(gardenStateFixture);
    renderWithQuery(
      <GardenView
        highlightedRewardId={gardenStateFixture.objects[0].id}
        petId="pet-1"
      />,
    );

    expect(await screen.findByText("پاداش جدید شما")).toBeInTheDocument();
  });
});
