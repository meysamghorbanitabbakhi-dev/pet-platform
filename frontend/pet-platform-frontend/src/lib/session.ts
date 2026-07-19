export const csrfHeaderName = "x-csrf-token";
const csrfCookieNames = ["__Host-pet_csrf", "pet_csrf"];

export function csrfHeaders(): HeadersInit {
  if (typeof document === "undefined") return {};
  const csrf = document.cookie
    .split("; ")
    .find((entry) =>
      csrfCookieNames.some((name) => entry.startsWith(`${name}=`)),
    )
    ?.split("=")[1];
  return csrf ? { [csrfHeaderName]: decodeURIComponent(csrf) } : {};
}
