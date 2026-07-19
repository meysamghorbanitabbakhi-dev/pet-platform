"use client";

const storageKey = "pet-platform.onboarding-progress";

export type OnboardingProgress = {
  challengeId?: string;
  mobile?: string;
  householdId?: string;
  petId?: string;
  addressId?: string;
};

function readAll(): OnboardingProgress {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(window.localStorage.getItem(storageKey) ?? "{}") as
      OnboardingProgress | Record<string, never>;
  } catch {
    return {};
  }
}

function writeAll(progress: OnboardingProgress) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(storageKey, JSON.stringify(progress));
}

export function getOnboardingProgress() {
  return readAll();
}

export function mergeOnboardingProgress(progress: OnboardingProgress) {
  writeAll({ ...readAll(), ...progress });
}

export function clearOnboardingProgress() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(storageKey);
}
