import { describe, it, expect } from "vitest";
import { toUserMessage } from "../../src/api/errors";

describe("toUserMessage", () => {
  it("explains an auth failure in terms of the fix", () => {
    expect(toUserMessage(401, {})).toMatch(/token/i);
  });

  it("reports insufficient history with the real reason", () => {
    const body = { detail: { error: "insufficient_history", message: "Only 2 career games" } };
    expect(toUserMessage(422, body)).toBe("Only 2 career games");
  });

  it("explains unsupported positions", () => {
    const body = { detail: { error: "not_supported_mvp", message: "K/DEF not supported" } };
    expect(toUserMessage(422, body)).toMatch(/Kickers and defenses/i);
  });

  it("explains a missing projection", () => {
    expect(toUserMessage(404, { detail: "no projection for player" }))
      .toMatch(/No projection imported/i);
  });

  it("never leaks a raw stringified object", () => {
    expect(toUserMessage(500, { detail: { deep: { nested: true } } }))
      .not.toContain("[object Object]");
  });
});
