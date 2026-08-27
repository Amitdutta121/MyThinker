import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
  // Components now persist small bits of UI state (e.g. the composer draft) to
  // localStorage; clear it between tests so state can't leak across them.
  try {
    window.localStorage.clear();
  } catch {
    /* no storage in this environment */
  }
});
