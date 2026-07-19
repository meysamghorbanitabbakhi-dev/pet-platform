import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getDiaryEntry } from "@/lib/api/client";
import { diaryEntryDetailFixture } from "@/test/fixtures/gate-fixtures";
import { DiaryEntryDetail } from "./diary-entry-detail";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/diary/pet-1/entry-1",
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/api/client", () => ({
  getDiaryEntry: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("DiaryEntryDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the backend note and links to the garden when a reward is linked", async () => {
    vi.mocked(getDiaryEntry).mockResolvedValue(diaryEntryDetailFixture);
    renderWithQuery(<DiaryEntryDetail entryId="entry-1" petId="pet-1" />);

    expect(
      await screen.findByText(diaryEntryDetailFixture.note_fa!),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "مشاهده باغ" })).toHaveAttribute(
      "href",
      "/garden/pet-1",
    );
    expect(getDiaryEntry).toHaveBeenCalledWith("pet-1", "entry-1");
  });

  it("does not render a garden link when no reward is linked to the entry", async () => {
    vi.mocked(getDiaryEntry).mockResolvedValue({
      ...diaryEntryDetailFixture,
      linked_garden_object: null,
    });
    renderWithQuery(<DiaryEntryDetail entryId="entry-1" petId="pet-1" />);

    await screen.findByText(diaryEntryDetailFixture.title_fa);
    expect(
      screen.queryByRole("link", { name: "مشاهده باغ" }),
    ).not.toBeInTheDocument();
  });
});
