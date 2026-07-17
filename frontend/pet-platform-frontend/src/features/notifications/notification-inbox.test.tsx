import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getPolicies, listNotifications, markNotificationRead } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import {
  notificationPageFixture,
  policyFixture,
} from "@/test/fixtures/gate-fixtures";
import { NotificationInbox } from "./notification-inbox";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/notifications",
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/api/client", () => ({
  getPolicies: vi.fn(),
  listNotifications: vi.fn(),
  markNotificationRead: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("NotificationInbox", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getPolicies).mockResolvedValue(policyFixture);
  });

  it("renders a real notification with a translated label and marks it read through the backend", async () => {
    vi.mocked(listNotifications).mockResolvedValue(notificationPageFixture);
    vi.mocked(markNotificationRead).mockResolvedValue(undefined);
    const user = userEvent.setup();

    renderWithQuery(<NotificationInbox />);

    expect(
      await screen.findByText("محصولی که منتظرش بودید موجود شد"),
    ).toBeInTheDocument();
    expect(screen.getByText("خوانده‌نشده")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "علامت‌گذاری به‌عنوان خوانده‌شده" }),
    );

    await waitFor(() =>
      expect(markNotificationRead).toHaveBeenCalledWith(
        notificationPageFixture.items[0].id,
      ),
    );
  });

  it("shows a push-disabled banner when the policy has push notifications off", async () => {
    vi.mocked(listNotifications).mockResolvedValue({
      items: [],
      page: { has_more: false, limit: 25, offset: 0, total: 0 },
    });
    renderWithQuery(<NotificationInbox />);

    expect(
      await screen.findByText(/اعلان‌های فوری \(push\) در حال حاضر فعال نیست/),
    ).toBeInTheDocument();
  });

  it("shows an empty state, not an error, for an empty inbox", async () => {
    vi.mocked(listNotifications).mockResolvedValue({
      items: [],
      page: { has_more: false, limit: 25, offset: 0, total: 0 },
    });
    renderWithQuery(<NotificationInbox />);

    expect(
      await screen.findByText("صندوق اعلان‌ها خالی است"),
    ).toBeInTheDocument();
  });

  it("redirects to the session-expired screen on a 401", async () => {
    vi.mocked(listNotifications).mockRejectedValue(new ApiError("expired", 401));
    renderWithQuery(<NotificationInbox />);

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/auth/session-expired"),
    );
  });
});
