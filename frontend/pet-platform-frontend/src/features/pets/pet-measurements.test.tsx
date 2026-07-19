import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  getWeightTrend,
  listMeasurements,
  recordMeasurement,
} from "@/lib/api/client";
import {
  measurementFixture,
  weightTrendFixture,
} from "@/test/fixtures/gate-fixtures";
import { PetMeasurements } from "./pet-measurements";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/pets/pet-1/measurements",
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/api/client", () => ({
  getWeightTrend: vi.fn(),
  listMeasurements: vi.fn(),
  recordMeasurement: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("PetMeasurements", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(listMeasurements).mockResolvedValue([measurementFixture]);
    vi.mocked(getWeightTrend).mockResolvedValue(weightTrendFixture);
  });

  it("renders the real weight trend from the backend, not a client-computed number", async () => {
    renderWithQuery(<PetMeasurements petId="pet-1" />);

    expect(await screen.findByText("۱۲٫۴ کیلوگرم")).toBeInTheDocument();
  });

  it("renders measurement history with type and unit", async () => {
    renderWithQuery(<PetMeasurements petId="pet-1" />);

    expect(await screen.findByText(/وزن: ۱۲٫۴ kg/)).toBeInTheDocument();
  });

  it("records a new weight measurement through the real backend endpoint", async () => {
    vi.mocked(recordMeasurement).mockResolvedValue({
      id: "new-1",
      status: "active",
    });
    const user = userEvent.setup();

    renderWithQuery(<PetMeasurements petId="pet-1" />);
    await user.type(screen.getByLabelText("وزن (کیلوگرم)"), "13.2");
    await user.click(screen.getByRole("button", { name: "ثبت وزن" }));

    await waitFor(() =>
      expect(recordMeasurement).toHaveBeenCalledWith(
        "pet-1",
        expect.objectContaining({
          measurement_type: "weight",
          source: "owner_reported",
          unit: "kg",
          value: 13.2,
        }),
      ),
    );
  });

  it("shows an empty state, not an error, when no measurements exist yet", async () => {
    vi.mocked(listMeasurements).mockResolvedValue([]);
    renderWithQuery(<PetMeasurements petId="pet-1" />);

    expect(
      await screen.findByText("هنوز اندازه‌گیری ثبت نشده است"),
    ).toBeInTheDocument();
  });
});
