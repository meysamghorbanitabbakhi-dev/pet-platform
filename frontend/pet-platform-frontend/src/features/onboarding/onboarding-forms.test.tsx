import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createAddress,
  createHousehold,
  createPet,
  getMeContext,
  requestOtp,
  updatePetProfile,
  verifyOtp,
} from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import { mergeOnboardingProgress } from "@/lib/onboarding-progress";
import { meContextFixture } from "@/test/fixtures/gate-fixtures";
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
  getMeContext: vi.fn(),
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

  it("shows rate-limit as a warning, not an error, and does not advance", async () => {
    vi.mocked(requestOtp).mockRejectedValue(
      new ApiError("تعداد درخواست‌ها بیش از حد مجاز است.", 429),
    );
    const user = userEvent.setup();

    render(<AuthMobileForm />);
    await user.type(screen.getByLabelText("شماره موبایل"), "09121234567");
    await user.click(screen.getByRole("button", { name: "درخواست کد" }));

    const banner = await screen.findByText("تعداد درخواست‌ها بیش از حد مجاز است.");
    expect(banner.closest(".banner")).toHaveClass("banner--warning");
    expect(push).not.toHaveBeenCalled();
  });

  it.each([
    ["invalid", "کد وارد شده نادرست است"],
    ["expired", "این کد منقضی شده است"],
    ["consumed", "این کد قبلاً استفاده شده است"],
  ] as const)(
    "shows a distinct inline banner for OTP %s without exposing tokens",
    async (state, text) => {
      mergeOnboardingProgress({ challengeId: "challenge-1" });
      vi.mocked(verifyOtp).mockResolvedValue({
        attempts_remaining: 2,
        expires_in_seconds: 0,
        state,
      });
      const user = userEvent.setup();

      render(<AuthOtpForm />);
      await user.type(await screen.findByLabelText("کد تایید"), "123456");
      await user.click(screen.getByRole("button", { name: "تایید و ادامه" }));

      expect(await screen.findByText(new RegExp(text))).toBeInTheDocument();
      expect(push).not.toHaveBeenCalledWith("/onboarding/bootstrap");
    },
  );

  it("routes a locked OTP challenge to the dedicated lock screen", async () => {
    mergeOnboardingProgress({ challengeId: "challenge-1" });
    vi.mocked(verifyOtp).mockResolvedValue({
      attempts_remaining: 0,
      expires_in_seconds: 900,
      state: "locked",
    });
    const user = userEvent.setup();

    render(<AuthOtpForm />);
    await user.type(await screen.findByLabelText("کد تایید"), "123456");
    await user.click(screen.getByRole("button", { name: "تایید و ادامه" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/auth/locked"));
  });

  it("routes a not-found OTP challenge back to mobile entry", async () => {
    mergeOnboardingProgress({ challengeId: "challenge-1" });
    vi.mocked(verifyOtp).mockResolvedValue({
      attempts_remaining: 0,
      expires_in_seconds: 0,
      state: "not_found",
    });
    const user = userEvent.setup();

    render(<AuthOtpForm />);
    await user.type(await screen.findByLabelText("کد تایید"), "123456");
    await user.click(screen.getByRole("button", { name: "تایید و ادامه" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/auth/mobile"));
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
      screen.getByRole("button", { name: "ثبت آدرس و رفتن به امروز" }),
    );

    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/onboarding/bootstrap"),
    );
    expect(
      window.localStorage.getItem("pet-platform.onboarding-progress"),
    ).toContain("address-1");
  });

  it("recovers household context from MeContext when localStorage is empty", async () => {
    vi.mocked(getMeContext).mockResolvedValue({
      ...meContextFixture,
      onboarding: {
        needs_address: true,
        needs_household: false,
        needs_pet: true,
      },
      pets: [],
    });
    vi.mocked(createPet).mockResolvedValue({ id: "pet-from-context" });
    const user = userEvent.setup();

    render(<PetOnboardingForm />);
    await user.type(screen.getByLabelText("نام پت"), "بیشی");
    await user.click(screen.getByRole("button", { name: "ثبت پت" }));

    await waitFor(() =>
      expect(createPet).toHaveBeenCalledWith(
        meContextFixture.households[0].id,
        {
          name: "بیشی",
          species: "dog",
        },
      ),
    );
  });
});
