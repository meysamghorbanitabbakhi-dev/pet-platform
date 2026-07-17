import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  getJourneyDefinition,
  getMeContext,
  startJourney,
} from "@/lib/api/client";
import {
  journeyDefinitionFixture,
  meContextFixture,
} from "@/test/fixtures/gate-fixtures";
import { JourneyDefinitionDetail } from "./journey-definition-detail";

const push = vi.fn();
const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/journeys/def-1",
  useRouter: () => ({ push, replace }),
}));

vi.mock("@/lib/api/client", () => ({
  getJourneyDefinition: vi.fn(),
  getMeContext: vi.fn(),
  startJourney: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("JourneyDefinitionDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    vi.mocked(getJourneyDefinition).mockResolvedValue(journeyDefinitionFixture);
    vi.mocked(getMeContext).mockResolvedValue(meContextFixture);
  });

  it("renders the non-diagnostic disclaimer the backend provides, never inventing clinical copy", async () => {
    renderWithQuery(<JourneyDefinitionDetail definitionId="def-1" />);

    expect(
      await screen.findByText(
        journeyDefinitionFixture.content.exception_behavior.message_fa!,
      ),
    ).toBeInTheDocument();
  });

  it("renders every step from the typed content, not a client-invented list", async () => {
    renderWithQuery(<JourneyDefinitionDetail definitionId="def-1" />);

    for (const step of journeyDefinitionFixture.content.steps) {
      expect(await screen.findByText(step.title_fa)).toBeInTheDocument();
    }
  });

  it("starts the journey for the active pet and navigates to the active journey page", async () => {
    vi.mocked(startJourney).mockResolvedValue({ id: "journey-1" });
    const user = userEvent.setup();
    renderWithQuery(<JourneyDefinitionDetail definitionId="def-1" />);

    await user.click(
      await screen.findByRole("button", {
        name: `شروع مسیر برای ${meContextFixture.pets[0].name}`,
      }),
    );
    await user.click(screen.getByRole("button", { name: "تایید شروع" }));

    await waitFor(() =>
      expect(startJourney).toHaveBeenCalledWith(meContextFixture.pets[0].id, {
        definition_id: journeyDefinitionFixture.id,
      }),
    );
    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/journeys/active/journey-1"),
    );
  });
});
