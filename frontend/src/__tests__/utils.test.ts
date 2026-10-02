import { describe, expect, it } from "vitest";
import { cn } from "../lib/utils";

describe("cn (className merge utility)", () => {
  it("merges multiple class names", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("handles conditional classes", () => {
    expect(cn("base", true && "included", false && "excluded")).toBe(
      "base included"
    );
  });

  it("handles undefined and null", () => {
    expect(cn("base", undefined, null, "end")).toBe("base end");
  });

  it("merges tailwind classes correctly", () => {
    // twMerge should handle conflicting tailwind classes
    expect(cn("px-2", "px-4")).toBe("px-4");
    expect(cn("text-red-500", "text-blue-500")).toBe("text-blue-500");
  });

  it("handles arrays", () => {
    expect(cn(["foo", "bar"])).toBe("foo bar");
  });

  it("handles objects", () => {
    expect(cn({ foo: true, bar: false, baz: true })).toBe("foo baz");
  });

  it("handles empty input", () => {
    expect(cn()).toBe("");
  });

  it("handles complex combinations", () => {
    expect(
      cn(
        "base-class",
        ["array-class"],
        { "conditional-true": true, "conditional-false": false },
        undefined,
        "final-class"
      )
    ).toBe("base-class array-class conditional-true final-class");
  });
});
