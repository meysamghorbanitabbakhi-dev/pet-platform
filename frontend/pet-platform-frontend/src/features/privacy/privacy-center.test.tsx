import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { exportMyData, requestPrivacyAction } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { privacyExportFixture, privacyRequestFixture } from "@/test/fixtures/gate-fixtures";
import { PrivacyCenter } from "./privacy-center";

vi.mock("@/lib/api/client", () => ({
  exportMyData: vi.fn(),
  requestPrivacyAction: vi.fn(),
}));

function renderWithQuery(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("PrivacyCenter", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    URL.createObjectURL = vi.fn(() => "blob:mock");
    URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  });

  it("downloads a real export from the backend, not a client-fabricated file", async () => {
    vi.mocked(exportMyData).mockResolvedValue(privacyExportFixture);
    const user = userEvent.setup();

    renderWithQuery(<PrivacyCenter />);
    await user.click(screen.getByRole("button", { name: "دانلود اطلاعات من" }));

    await waitFor(() => expect(exportMyData).toHaveBeenCalled());
    expect(URL.createObjectURL).toHaveBeenCalled();
  });

  it("requires confirmation before submitting an irreversible disable request", async () => {
    vi.mocked(requestPrivacyAction).mockResolvedValue(privacyRequestFixture);
    const user = userEvent.setup();

    renderWithQuery(<PrivacyCenter />);
    await user.click(
      screen.getByRole("button", { name: "درخواست غیرفعال‌سازی حساب" }),
    );
    expect(requestPrivacyAction).not.toHaveBeenCalled();

    expect(
      screen.getByText(/این اقدام غیرقابل بازگشت است/),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "تایید و ثبت درخواست" }),
    );

    await waitFor(() =>
      expect(requestPrivacyAction).toHaveBeenCalledWith({
        reason: null,
        request_type: "disable",
      }),
    );
    expect(
      await screen.findByText(new RegExp(privacyRequestFixture.id)),
    ).toBeInTheDocument();
  });

  it("submits an anonymize request distinctly from disable", async () => {
    vi.mocked(requestPrivacyAction).mockResolvedValue(privacyRequestFixture);
    const user = userEvent.setup();

    renderWithQuery(<PrivacyCenter />);
    await user.click(
      screen.getByRole("button", { name: "درخواست ناشناس‌سازی داده‌ها" }),
    );
    await user.click(
      screen.getByRole("button", { name: "تایید و ثبت درخواست" }),
    );

    await waitFor(() =>
      expect(requestPrivacyAction).toHaveBeenCalledWith({
        reason: null,
        request_type: "anonymize",
      }),
    );
  });

  it("shows a real backend error, not a silent failure, when the request fails", async () => {
    vi.mocked(requestPrivacyAction).mockRejectedValue(
      new ApiError("خطا در ثبت درخواست", 500),
    );
    const user = userEvent.setup();

    renderWithQuery(<PrivacyCenter />);
    await user.click(
      screen.getByRole("button", { name: "درخواست غیرفعال‌سازی حساب" }),
    );
    await user.click(
      screen.getByRole("button", { name: "تایید و ثبت درخواست" }),
    );

    expect(await screen.findByText("خطا در ثبت درخواست")).toBeInTheDocument();
  });
});
