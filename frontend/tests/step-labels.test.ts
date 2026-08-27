import { describe, expect, it } from "vitest";
import { stepLabel } from "@/lib/step-labels";

describe("stepLabel", () => {
  it("maps known tool names to plain language", () => {
    expect(stepLabel("web_search")).toBe("Searching the web");
    expect(stepLabel("commit_proposed_direction")).toBe("Committing the direction");
    expect(stepLabel("save_evidence")).toBe("Saving evidence");
  });

  it("humanizes an unknown tool name instead of showing the identifier", () => {
    expect(stepLabel("some_new_tool")).toBe("Some new tool");
    expect(stepLabel("plain")).toBe("Plain");
  });

  it("falls back to the raw value when there is nothing to humanize", () => {
    expect(stepLabel("")).toBe("");
  });
});
