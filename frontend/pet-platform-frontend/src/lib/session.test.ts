import { afterEach, describe, expect, it } from "vitest";
import { csrfHeaders, csrfHeaderName } from "./session";

describe("browser session boundary", () => {
  afterEach(() => {
    document.cookie = "pet_csrf=; Max-Age=0; path=/";
  });

  it("adds CSRF from the non-HttpOnly CSRF cookie for browser mutations", () => {
    document.cookie = "pet_csrf=csrf-value; path=/";

    expect(csrfHeaders()).toEqual({ [csrfHeaderName]: "csrf-value" });
  });
});
