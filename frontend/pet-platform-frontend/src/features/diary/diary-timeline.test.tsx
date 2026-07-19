import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getMeContext, listDiary } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { diaryListFixture, meContextFixture } from "@/test/fixtures/gate-fixtures";
import { DiaryTimeline } from "./diary-timeline";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/diary",
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/api/client", () => ({
  getMeContext: vi.fn(),
  listDiary: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("DiaryTimeline", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    vi.mocked(getMeContext).mockResolvedValue(meContextFixture);
  });

  it("links each real diary entry to its pet-scoped detail route", async () => {
    vi.mocked(listDiary).mockResolvedValue(diaryListFixture);
    renderWithQuery(<DiaryTimeline />);

    const link = await screen.findByRole("link", {
      name: new RegExp(diaryListFixture[0].title_fa),
    });
    expect(link).toHaveAttribute(
      "href",
      `/diary/${meContextFixture.pets[0].id}/${diaryListFixture[0].id}`,
    );
    expect(listDiary).toHaveBeenCalledWith(meContextFixture.pets[0].id);
  });

  it("shows an empty state, not an error, when the pet has no diary entries yet", async () => {
    vi.mocked(listDiary).mockResolvedValue([]);
    renderWithQuery(<DiaryTimeline />);

    expect(
      await screen.findByText("هنوز خاطره‌ای ثبت نشده است"),
    ).toBeInTheDocument();
  });

  it("redirects to the session-expired screen on a 401", async () => {
    vi.mocked(getMeContext).mockRejectedValue(new ApiError("expired", 401));
    renderWithQuery(<DiaryTimeline />);

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/auth/session-expired"),
    );
  });
});
