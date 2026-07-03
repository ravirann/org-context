#!/usr/bin/env node
/**
 * Runs `vitest run <args>`, dropping any literal "--" separator.
 *
 * Why: `pnpm test -- --coverage` (used by the Makefile) forwards the "--"
 * itself, and vitest would then treat "--coverage" as a test-name filter and
 * silently skip coverage. This wrapper makes both `pnpm test --coverage` and
 * `pnpm test -- --coverage` behave identically.
 */
import { spawnSync } from "node:child_process";

const args = process.argv.slice(2).filter((arg) => arg !== "--");
const result = spawnSync("vitest", ["run", ...args], { stdio: "inherit" });
process.exit(result.status ?? 1);
