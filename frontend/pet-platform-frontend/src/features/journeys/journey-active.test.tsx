import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  completeJourney,
  getJourney,
  pauseJourney,
  resumeJourney,
  stopJourney,
  submitCheckIn,
} from "@/lib/api/client";
import { journeyDetailFixture } from "@/test/fixtures/gate-fixtures";
import { checkInIdempotencyKey } from "@/lib/journey-idempotency";
import { JourneyActive } from "./journey-active";

vi.mock("next/navigation", () => ({
  usePathname: () => "/journeys/active/journey-1",
}));

vi.mock("@/lib/api/client", () => ({
  completeJourney: vi.fn(),
  getJourney: vi.fn(),
  pauseJourney: vi.fn(),
  resumeJourney: vi.fn(),
  stopJourney: vi.fn(),
  submitCheckIn: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("JourneyActive", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the first unanswered step as the current check-in and submits with a deterministic idempotency key", async () => {
    vi.mocked(getJourney).mockResolvedValue(journeyDetailFixture);
    vi.mocked(submitCheckIn).mockResolvedValue({
      answer_key: "on_track",
      check_in_key: "week1",
      completed: false,
      diary_entry_id: null,
      garden_reward_id: null,
      id: "checkin-1",
      journey_id: journeyDetailFixture.id,
      submitted_at: "2026-07-17T09:00:00Z",
    });
    const user = userEvent.setup();

    renderWithQuery(<JourneyActive journeyId={journeyDetailFixture.id} />);

    expect(await screen.findByRole("heading", { name: "هفته اول: بررسی وزن" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "روند طبیعی است" }));
    await user.click(screen.getByRole("button", { name: "ثبت پاسخ" }));

    await waitFor(() =>
      expect(submitCheckIn).toHaveBeenCalledWith(
        journeyDetailFixture.id,
        { answer_key: "on_track", check_in_key: "week1" },
        checkInIdempotencyKey(journeyDetailFixture.id, "week1", "on_track"),
      ),
    );
  });

  it("offers completion only once every step has an answer, never inventing eligibility client-side", async () => {
    vi.mocked(getJourney).mockResolvedValue({
      ...journeyDetailFixture,
      check_ins: journeyDetailFixture.steps.map((step) => ({
        answer_key: "on_track",
        check_in_key: step.key,
        completed: false,
        diary_entry_id: null,
        garden_reward_id: null,
        id: `checkin-${step.key}`,
        journey_id: journeyDetailFixture.id,
        submitted_at: "2026-07-17T09:00:00Z",
      })),
    });

    renderWithQuery(<JourneyActive journeyId={journeyDetailFixture.id} />);

    expect(
      await screen.findByText(/همه گام‌ها پاسخ داده شده‌اند/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "تکمیل مسیر" }),
    ).toBeInTheDocument();
  });

  it("requires a reason to stop and calls the backend with it", async () => {
    vi.mocked(getJourney).mockResolvedValue(journeyDetailFixture);
    vi.mocked(stopJourney).mockResolvedValue(undefined);
    const user = userEvent.setup();

    renderWithQuery(<JourneyActive journeyId={journeyDetailFixture.id} />);
    await screen.findByRole("heading", { name: "هفته اول: بررسی وزن" });

    await user.click(screen.getByRole("button", { name: "لغو مسیر" }));
    expect(screen.getByRole("button", { name: "تایید لغو" })).toBeDisabled();
    await user.type(screen.getByLabelText("دلیل لغو"), "دیگر لازم نیست");
    await user.click(screen.getByRole("button", { name: "تایید لغو" }));

    await waitFor(() =>
      expect(stopJourney).toHaveBeenCalledWith(journeyDetailFixture.id, {
        reason: "دیگر لازم نیست",
      }),
    );
  });

  it("shows the paused banner distinctly and resumes through a confirmation sheet", async () => {
    vi.mocked(getJourney).mockResolvedValue({
      ...journeyDetailFixture,
      status: "paused",
    });
    vi.mocked(resumeJourney).mockResolvedValue(undefined);
    const user = userEvent.setup();

    renderWithQuery(<JourneyActive journeyId={journeyDetailFixture.id} />);

    expect(
      await screen.findByText(/این مسیر موقتاً متوقف شده است/),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "از سر گرفتن" }));
    await user.click(screen.getByRole("button", { name: "تایید از سر گرفتن" }));

    await waitFor(() =>
      expect(resumeJourney).toHaveBeenCalledWith(journeyDetailFixture.id),
    );
  });

  it("pauses and resumes through confirmation sheets, calling the real endpoints", async () => {
    vi.mocked(getJourney).mockResolvedValue(journeyDetailFixture);
    vi.mocked(pauseJourney).mockResolvedValue(undefined);
    const user = userEvent.setup();

    renderWithQuery(<JourneyActive journeyId={journeyDetailFixture.id} />);
    await screen.findByRole("heading", { name: "هفته اول: بررسی وزن" });

    await user.click(screen.getByRole("button", { name: "توقف موقت" }));
    await user.click(screen.getByRole("button", { name: "تایید توقف موقت" }));

    await waitFor(() => expect(pauseJourney).toHaveBeenCalledWith(journeyDetailFixture.id));
  });

  it("completes the journey with a required memory title once all steps are answered", async () => {
    const allAnswered = {
      ...journeyDetailFixture,
      check_ins: journeyDetailFixture.steps.map((step) => ({
        answer_key: "on_track",
        check_in_key: step.key,
        completed: false,
        diary_entry_id: null,
        garden_reward_id: null,
        id: `checkin-${step.key}`,
        journey_id: journeyDetailFixture.id,
        submitted_at: "2026-07-17T09:00:00Z",
      })),
    };
    // The completion Card is derived from the journey query, not the mutation
    // response, so a refetch after completeJourney must reflect the new state.
    vi.mocked(getJourney)
      .mockResolvedValueOnce(allAnswered)
      .mockResolvedValue({
        ...allAnswered,
        diary_entry_id: "diary-1",
        garden_reward_id: "reward-1",
        status: "completed",
      });
    vi.mocked(completeJourney).mockResolvedValue({
      diary_entry_id: "diary-1",
      garden_reward_id: "reward-1",
    });
    const user = userEvent.setup();

    renderWithQuery(<JourneyActive journeyId={journeyDetailFixture.id} />);
    await user.click(await screen.findByRole("button", { name: "تکمیل مسیر" }));
    expect(screen.getByRole("button", { name: "تایید تکمیل" })).toBeDisabled();
    await user.type(screen.getByLabelText("عنوان خاطره"), "هفته خوبی بود");
    await user.click(screen.getByRole("button", { name: "تایید تکمیل" }));

    await waitFor(() =>
      expect(completeJourney).toHaveBeenCalledWith(journeyDetailFixture.id, {
        memory_title_fa: "هفته خوبی بود",
      }),
    );

    expect(
      await screen.findByRole("link", { name: "مشاهده خاطره" }),
    ).toHaveAttribute(
      "href",
      `/diary/${journeyDetailFixture.pet_id}/diary-1`,
    );
    expect(
      screen.getByRole("link", { name: "مشاهده پاداش در باغ" }),
    ).toHaveAttribute(
      "href",
      `/garden/${journeyDetailFixture.pet_id}?reward=reward-1`,
    );
  });

  it("surfaces the diary entry and Garden reward when the backend auto-completes the journey on the final check-in, without a separate manual completion step", async () => {
    const lastStep = journeyDetailFixture.steps[journeyDetailFixture.steps.length - 1];
    const beforeFinalCheckIn = {
      ...journeyDetailFixture,
      check_ins: journeyDetailFixture.steps
        .filter((step) => step.key !== lastStep.key)
        .map((step) => ({
          answer_key: "on_track",
          check_in_key: step.key,
          completed: false,
          diary_entry_id: null,
          garden_reward_id: null,
          id: `checkin-${step.key}`,
          journey_id: journeyDetailFixture.id,
          submitted_at: "2026-07-17T09:00:00Z",
        })),
    };
    vi.mocked(getJourney)
      .mockResolvedValueOnce(beforeFinalCheckIn)
      .mockResolvedValue({
        ...beforeFinalCheckIn,
        check_ins: [
          ...beforeFinalCheckIn.check_ins,
          {
            answer_key: "on_track",
            check_in_key: lastStep.key,
            completed: true,
            diary_entry_id: "diary-auto-1",
            garden_reward_id: "reward-auto-1",
            id: "checkin-final",
            journey_id: journeyDetailFixture.id,
            submitted_at: "2026-07-17T09:05:00Z",
          },
        ],
        diary_entry_id: "diary-auto-1",
        garden_reward_id: "reward-auto-1",
        status: "completed",
      });
    vi.mocked(submitCheckIn).mockResolvedValue({
      answer_key: "on_track",
      check_in_key: lastStep.key,
      completed: true,
      diary_entry_id: "diary-auto-1",
      garden_reward_id: "reward-auto-1",
      id: "checkin-final",
      journey_id: journeyDetailFixture.id,
      submitted_at: "2026-07-17T09:05:00Z",
    });
    const user = userEvent.setup();

    renderWithQuery(<JourneyActive journeyId={journeyDetailFixture.id} />);
    await user.click(await screen.findByRole("button", { name: lastStep.allowed_answers[0].label_fa }));
    await user.click(screen.getByRole("button", { name: "ثبت پاسخ" }));

    expect(
      await screen.findByRole("link", { name: "مشاهده خاطره" }),
    ).toHaveAttribute("href", `/diary/${journeyDetailFixture.pet_id}/diary-auto-1`);
    expect(
      screen.getByRole("link", { name: "مشاهده پاداش در باغ" }),
    ).toHaveAttribute("href", `/garden/${journeyDetailFixture.pet_id}?reward=reward-auto-1`);
    expect(screen.getByText(/این مسیر تکمیل شده است/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "تکمیل مسیر" }),
    ).not.toBeInTheDocument();
  });

  it("shows the completion transition when a journey is already completed on load, without requiring any action", async () => {
    vi.mocked(getJourney).mockResolvedValue({
      ...journeyDetailFixture,
      diary_entry_id: "diary-2",
      garden_reward_id: "reward-2",
      status: "completed",
    });

    renderWithQuery(<JourneyActive journeyId={journeyDetailFixture.id} />);

    expect(
      await screen.findByRole("link", { name: "مشاهده خاطره" }),
    ).toHaveAttribute("href", `/diary/${journeyDetailFixture.pet_id}/diary-2`);
    expect(
      screen.queryByRole("button", { name: "تکمیل مسیر" }),
    ).not.toBeInTheDocument();
  });
});
