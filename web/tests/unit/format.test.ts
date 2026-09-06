import { describe, it, expect } from "vitest";
import { formatPoints } from "../../src/lib/format";

describe("formatPoints", () => {
  it("formats a normal value to one decimal place", () => {
    expect(formatPoints(21.44)).toBe("21.4");
  });

  it("rounds rather than truncates", () => {
    expect(formatPoints(21.46)).toBe("21.5");
  });

  it("renders an em dash for null", () => {
    expect(formatPoints(null)).toBe("—");
  });

  it("renders an em dash for undefined", () => {
    expect(formatPoints(undefined)).toBe("—");
  });

  it("renders an em dash for NaN", () => {
    expect(formatPoints(NaN)).toBe("—");
  });

  it("formats zero as a real value, not an absent one", () => {
    expect(formatPoints(0)).toBe("0.0");
  });
});
