"use client";

export const selectedPetStorageKey = "pet-platform.selected-pet-id";

export function clearSelectedPetId() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(selectedPetStorageKey);
}
