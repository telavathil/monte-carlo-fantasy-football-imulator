import { describe, it, expect } from "vitest";
import { buildAreaPath, bandBounds } from "../../src/lib/sparkline";

describe("buildAreaPath", () => {
  it("returns an empty path for no data", () => {
    expect(buildAreaPath([], 220, 56)).toBe("");
  });

  it("starts at the baseline and closes the shape", () => {
    const d = buildAreaPath([1, 4, 9, 4, 1], 100, 50);
    expect(d.startsWith("M0,50")).toBe(true);
    expect(d.endsWith("Z")).toBe(true);
  });

  it("puts the tallest bin at the top of the box", () => {
    const d = buildAreaPath([1, 10, 1], 100, 50);
    // The peak's y must be 0 (top); the baseline is height.
    expect(d).toContain(",0");
  });

  it("never emits a coordinate outside the box", () => {
    const d = buildAreaPath([3, 8, 2, 7], 220, 56);
    const coords = d.match(/-?\d+(\.\d+)?/g)!.map(Number);
    expect(Math.min(...coords)).toBeGreaterThanOrEqual(0);
    expect(Math.max(...coords)).toBeLessThanOrEqual(220);
  });

  it("survives an all-zero histogram without dividing by zero", () => {
    const d = buildAreaPath([0, 0, 0], 100, 50);
    expect(d).not.toContain("NaN");
  });
});

describe("bandBounds", () => {
  it("maps a percentile range onto the pixel box", () => {
    const { x1, x2 } = bandBounds([0, 10, 20, 30, 40], 10, 30, 200);
    expect(x1).toBeCloseTo(50);
    expect(x2).toBeCloseTo(150);
  });

  it("clamps a range that runs past the histogram", () => {
    const { x1, x2 } = bandBounds([0, 10, 20], -5, 999, 100);
    expect(x1).toBe(0);
    expect(x2).toBe(100);
  });

  it("returns a zero-width band for a degenerate axis", () => {
    const { x1, x2 } = bandBounds([5, 5], 1, 9, 100);
    expect(x1).toBe(0);
    expect(x2).toBe(0);
  });
});
