import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FirstOwnerFlow } from "./first-owner-flow";

function fakeApi(state: "verified" | "invalid" | "locked" = "verified") {
  return {
    requestOtp: vi.fn(async () => ({
      challenge_id: "66666666-6666-4666-8666-666666666666",
      expires_in_seconds: 90,
    })),
    verifyOtp: vi.fn(async () =>
      state === "verified"
        ? {
            state,
            access_token: "token",
            refresh_token: "refresh",
            identity_id: "identity",
            token_type: "bearer" as const,
          }
        : {
            state,
            attempts_remaining: state === "invalid" ? 2 : 0,
            expires_in_seconds: state === "locked" ? 900 : 60,
          },
    ),
  };
}

describe("FirstOwnerFlow OTP states", () => {
  it("walks from mobile OTP to optional pet onboarding", async () => {
    const user = userEvent.setup();
    const api = fakeApi("verified");
    render(<FirstOwnerFlow api={api} />);

    await user.click(screen.getByRole("button", { name: "درخواست کد" }));
    expect(await screen.findByText("تأیید شماره موبایل")).toBeInTheDocument();

    await user.type(screen.getByLabelText("کد تایید"), "123456");
    await user.click(screen.getByRole("button", { name: "تأیید و ادامه" }));

    expect(
      await screen.findByText("پروفایل پت اختیاری است"),
    ).toBeInTheDocument();
  });

  it("shows invalid OTP without leaving OTP screen", async () => {
    const user = userEvent.setup();
    render(<FirstOwnerFlow api={fakeApi("invalid")} />);

    await user.click(screen.getByRole("button", { name: "درخواست کد" }));
    await user.type(await screen.findByLabelText("کد تایید"), "000000");
    await user.click(screen.getByRole("button", { name: "تأیید و ادامه" }));

    expect(
      await screen.findByText("کد وارد شده معتبر نیست"),
    ).toBeInTheDocument();
    expect(screen.getByText("تأیید شماره موبایل")).toBeInTheDocument();
  });

  it("locks OTP confirmation after backend lock state", async () => {
    const user = userEvent.setup();
    render(<FirstOwnerFlow api={fakeApi("locked")} />);

    await user.click(screen.getByRole("button", { name: "درخواست کد" }));
    await user.type(await screen.findByLabelText("کد تایید"), "999999");
    await user.click(screen.getByRole("button", { name: "تأیید و ادامه" }));

    expect(await screen.findByText(/قفل شده است/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "تأیید و ادامه" }),
    ).toBeDisabled();
  });

  it("keeps commerce usable when pet onboarding is skipped", async () => {
    const user = userEvent.setup();
    render(<FirstOwnerFlow api={fakeApi("verified")} />);

    await user.click(screen.getByRole("button", { name: "درخواست کد" }));
    await user.type(await screen.findByLabelText("کد تایید"), "123456");
    await user.click(screen.getByRole("button", { name: "تأیید و ادامه" }));
    await user.click(
      await screen.findByRole("button", { name: "رد کردن و رفتن به فروشگاه" }),
    );

    expect(await screen.findByText("فروشگاه در دسترس است")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "مشاهده فروشگاه" }),
    ).toHaveAttribute("href", "/shop");
  });
});
