import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  getPolicies,
  getSmsPreference,
  updateSmsPreference,
} from "@/lib/api/client";
import { policyFixture } from "@/test/fixtures/gate-fixtures";
import { NotificationPreferences } from "./notification-preferences";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/account/notifications/preferences",
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/api/client", () => ({
  getPolicies: vi.fn(),
  getSmsPreference: vi.fn(),
  updateSmsPreference: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("NotificationPreferences", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a policy-hidden empty state, not a form, while late-credit is not customer-visible", async () => {
    vi.mocked(getPolicies).mockResolvedValue({
      ...policyFixture,
      late_credit_customer_visible: false,
    });
    renderWithQuery(<NotificationPreferences />);

    expect(
      await screen.findByText("این قابلیت در دسترس نیست"),
    ).toBeInTheDocument();
    expect(getSmsPreference).not.toHaveBeenCalled();
  });

  it("shows the real current sms-enabled state and quiet hours from the backend, not a blind form", async () => {
    vi.mocked(getPolicies).mockResolvedValue({
      ...policyFixture,
      late_credit_customer_visible: true,
    });
    vi.mocked(getSmsPreference).mockResolvedValue({
      event_key: "wallet.late_delivery_credit_granted",
      sms_enabled: false,
      quiet_hours_start: "22:30:00",
      quiet_hours_end: "07:00:00",
    });
    renderWithQuery(<NotificationPreferences />);

    const toggle = await screen.findByLabelText(
      "اعلان پیامکی جبران تأخیر تحویل فعال باشد",
    );
    expect(toggle).not.toBeChecked();
    expect(screen.getByLabelText("شروع بازه سکوت (اختیاری)")).toHaveValue(
      "22:30",
    );
    expect(screen.getByLabelText("پایان بازه سکوت (اختیاری)")).toHaveValue(
      "07:00",
    );
  });

  it("saves an overnight quiet-hours window (start after end) without rejecting it as invalid", async () => {
    vi.mocked(getPolicies).mockResolvedValue({
      ...policyFixture,
      late_credit_customer_visible: true,
    });
    vi.mocked(getSmsPreference).mockResolvedValue({
      event_key: "wallet.late_delivery_credit_granted",
      sms_enabled: true,
      quiet_hours_start: null,
      quiet_hours_end: null,
    });
    vi.mocked(updateSmsPreference).mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderWithQuery(<NotificationPreferences />);

    await screen.findByLabelText("اعلان پیامکی جبران تأخیر تحویل فعال باشد");
    await user.type(screen.getByLabelText("شروع بازه سکوت (اختیاری)"), "22:30");
    await user.type(
      screen.getByLabelText("پایان بازه سکوت (اختیاری)"),
      "07:00",
    );
    await user.click(screen.getByRole("button", { name: "ذخیره" }));

    await waitFor(() =>
      expect(updateSmsPreference).toHaveBeenCalledWith(
        "wallet.late_delivery_credit_granted",
        {
          enabled: true,
          quiet_start_local: "22:30:00",
          quiet_end_local: "07:00:00",
        },
      ),
    );
  });

  it("rejects saving only one side of the quiet-hours window client-side", async () => {
    vi.mocked(getPolicies).mockResolvedValue({
      ...policyFixture,
      late_credit_customer_visible: true,
    });
    vi.mocked(getSmsPreference).mockResolvedValue({
      event_key: "wallet.late_delivery_credit_granted",
      sms_enabled: true,
      quiet_hours_start: null,
      quiet_hours_end: null,
    });
    const user = userEvent.setup();
    renderWithQuery(<NotificationPreferences />);

    await screen.findByLabelText("اعلان پیامکی جبران تأخیر تحویل فعال باشد");
    await user.type(screen.getByLabelText("شروع بازه سکوت (اختیاری)"), "22:30");
    await user.click(screen.getByRole("button", { name: "ذخیره" }));

    expect(
      await screen.findByText(
        "برای بازه سکوت، هم زمان شروع و هم زمان پایان لازم است.",
      ),
    ).toBeInTheDocument();
    expect(updateSmsPreference).not.toHaveBeenCalled();
  });
});
