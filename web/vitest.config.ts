import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // tests/e2e belongs to Playwright; never let the two runners collide.
    include: ["tests/unit/**/*.test.ts"],
    environment: "node",
  },
});
