import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Reseeds the demo database once before the whole suite runs, so scenarios
 * that mutate state (resolving conflicts, feedback, sync, eval runs) always
 * start from the same known seed (326 docs, 6 conflicts, 46 agent runs...).
 *
 * Primary path: run the reset inside the already-running `api` compose
 * container. Fallback: run the seed script directly via uv from the backend
 * checkout (useful when compose exec isn't available, e.g. local non-docker
 * runs).
 */
const COMPOSE_ROOT = path.resolve(__dirname, "../../");

export default async function globalSetup(): Promise<void> {
  const dockerArgs = ["compose", "exec", "-T", "api", "python", "-m", "seeds.demo_data", "--reset"];
  try {
    execFileSync("docker", dockerArgs, {
      cwd: COMPOSE_ROOT,
      stdio: "inherit",
      timeout: 60_000,
    });
    return;
  } catch (error) {
    console.warn(
      `[global-setup] "docker ${dockerArgs.join(" ")}" failed, falling back to local uv run.\n${String(error)}`,
    );
  }

  execFileSync("uv", ["run", "python", "-m", "seeds.demo_data", "--reset"], {
    cwd: path.join(COMPOSE_ROOT, "backend"),
    stdio: "inherit",
    timeout: 60_000,
  });
}
