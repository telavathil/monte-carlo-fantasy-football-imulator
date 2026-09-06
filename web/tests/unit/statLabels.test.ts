import { describe, it, expect } from "vitest";
import { statLabel } from "../../src/lib/statLabels";

describe("statLabel", () => {
  it("humanizes known canonical stat keys", () => {
    expect(statLabel("receiving_yards")).toBe("Receiving yards");
    expect(statLabel("passing_tds")).toBe("Passing TDs");
    expect(statLabel("rushing_fumbles_lost")).toBe("Fumbles lost");
    expect(statLabel("receptions")).toBe("Receptions");
  });

  it("falls back to a readable form for unknown keys", () => {
    expect(statLabel("some_new_stat")).toBe("Some new stat");
  });
});
