import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createAddress,
  createHousehold,
  createPet,
  requestOtp,
  updatePetProfile,
  verifyOtp,
} from "@/lib/api/client";
import { mergeOnboardingProgress } from "@/lib/onboarding-progress";
import {
  AddressOnboardingForm,
  AuthMobileForm,
  AuthOtpForm,
  HouseholdOnboardingForm,
  PetBirthDateForm,
  PetOnboardingForm,
} from "./onboarding-forms";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/auth/mobile",
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/api/client", () => ({
  createAddress: vi.fn(),
  createHousehold: vi.fn(),
  createPet: vi.fn(),
  requestOtp: vi.fn(),
  updatePetProfile: vi.fn(),
  verifyOtp: vi.fn(),
}));

describe("canonical T8 onboarding forms", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("requests OTP and routes to /auth/otp with the server challenge id persisted", async () => {
    vi.mocked(requestOtp).mockResolvedValue({
      challenge_id: "challenge-1",
      expires_in_seconds: 90,
    });
    const user = userEvent.setup();

    render(<AuthMobileForm />);
    await user.type(screen.getByLabelText("شماره موبایل"), "09121234567");
    await user.click(screen.getByRole("button", { name: "درخواست کد" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/auth/otp"));
    expect(
      window.localStorage.getItem("pet-platform.onboarding-progress"),
    ).toContain("challenge-1");
  });

  it.each([
    ["invalid", "کد وارد شده معتبر نیست"],
    ["expired", "این کد قابل استفاده نیست"],
    ["consumed", "این کد قابل استفاده نیست"],
    ["not_found", "این کد قابل استفاده نیست"],
    ["locked", "قفل شده است"],
  ] as const)("shows OTP %s without exposing tokens", async (state, text) => {
    mergeOnboardingProgress({ challengeId: "challenge-1" });
    vi.mocked(verifyOtp).mockResolvedValue({
      attempts_remaining: state === "invalid" ? 2 : 0,
      expires_in_seconds: state === "locked" ? 900 : 0,
      state,
    });
    const user = userEvent.setup();

    render(<AuthOtpForm />);
    await user.type(await screen.findByLabelText("کد تایید"), "123456");
    await user.click(screen.getByRole("button", { name: "تایید و ادامه" }));

    expect(await screen.findByText(new RegExp(text))).toBeInTheDocument();
    expect(push).not.toHaveBeenCalledWith("/onboarding/bootstrap");
  });

  it("routes verified OTP to bootstrap", async () => {
    mergeOnboardingProgress({ challengeId: "challenge-1" });
    vi.mocked(verifyOtp).mockResolvedValue({
      identity_id: "identity-1",
      state: "verified",
    });
    const user = userEvent.setup();

    render(<AuthOtpForm />);
    await user.type(await screen.findByLabelText("کد تایید"), "123456");
    await user.click(screen.getByRole("button", { name: "تایید و ادامه" }));

    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/onboarding/bootstrap"),
    );
  });

  it("creates required household, pet and address IDs across canonical screens", async () => {
    vi.mocked(createHousehold).mockResolvedValue({ id: "household-1" });
    vi.mocked(createPet).mockResolvedValue({ id: "pet-1" });
    vi.mocked(createAddress).mockResolvedValue({ id: "address-1" });
    const user = userEvent.setup();

    const { rerender } = render(<HouseholdOnboardingForm />);
    await user.type(screen.getByLabelText("نام خانوار"), "خانه بیشی");
    await user.click(screen.getByRole("button", { name: "ثبت خانوار" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/onboarding/pet"));

    rerender(<PetOnboardingForm />);
    await user.type(screen.getByLabelText("نام پت"), "بیشی");
    await user.click(screen.getByRole("button", { name: "ثبت پت" }));
    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/onboarding/pet/birth-date"),
    );

    rerender(<PetBirthDateForm />);
    await user.click(screen.getByRole("button", { name: "رد کردن" }));
    expect(updatePetProfile).not.toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith("/onboarding/address");

    rerender(<AddressOnboardingForm />);
    await user.type(screen.getByLabelText("نام گیرنده"), "مالک خانه");
    await user.type(screen.getByLabelText("موبایل گیرنده"), "09121234567");
    await user.type(screen.getByLabelText("استان"), "تهران");
    await user.type(screen.getByLabelText("شهر"), "تهران");
    await user.type(
      screen.getByLabelText("آدرس کامل"),
      "خیابان ولیعصر پلاک ۱۲",
    );
    await user.click(
      screen.getByRole("button", { name: "ثبت آدرس و رفتن به Today" }),
    );

    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/onboarding/bootstrap"),
    );
    expect(
      window.localStorage.getItem("pet-platform.onboarding-progress"),
    ).toContain("address-1");
  });
});
