/**
 * Custom Playwright reporter that logs test failures as platform_incidents.
 *
 * Intercepts failed/timed-out tests and POSTs them to the Bridgeable backend
 * incident endpoint. This wires Playwright CI failures into the self-repair
 * system so they appear in the platform operator dashboard.
 *
 * Env vars:
 *   BACKEND_URL     — backend API base (default: staging)
 *   INTERNAL_API_KEY — auth key for /api/platform/incidents
 *   TEST_ENV        — environment tag (default: 'staging')
 */
import type {
  Reporter,
  TestCase,
  TestResult,
  FullConfig,
  Suite,
  FullResult,
} from "@playwright/test/reporter";

interface FailedTest {
  testTitle: string;
  testFile: string;
  error: string;
  stack: string;
  duration: number;
  tenantId: string | null;
}

class IncidentReporter implements Reporter {
  private backendUrl: string = "";
  private failedTests: FailedTest[] = [];

  onBegin(config: FullConfig, suite: Suite) {
    this.backendUrl =
      process.env.BACKEND_URL ||
      "https://sunnycresterp-staging.up.railway.app";
  }

  onTestEnd(test: TestCase, result: TestResult) {
    if (result.status !== "failed" && result.status !== "timedOut") return;

    const error = result.errors[0];
    const errorMessage = error?.message || "Test failed with no error message";
    const stack = error?.stack || "";

    // Extract tenant_id from test title or file path.
    // Tests named with @tenant:sunnycrest or file paths containing
    // tenant_<slug> will map to that tenant.
    const titlePath = test.titlePath().join("/");
    const tenantMatch =
      test.title.match(/@tenant:(\S+)/) ||
      titlePath.match(/@tenant:(\S+)/) ||
      titlePath.match(/tenant[_-]([a-z0-9]+)/i);
    const tenantId = tenantMatch ? tenantMatch[1] : null;

    // Verify extraction works for tagged tests
    if (titlePath.includes("@tenant:") && !tenantId) {
      console.error(
        `[IncidentReporter] BUG: @tenant tag found in titlePath but extraction failed: ${titlePath}`
      );
    }

    this.failedTests.push({
      testTitle: test.title,
      testFile: test.location.file.split("tests/e2e/")[1] || test.location.file,
      error: errorMessage.slice(0, 500),
      stack: stack.slice(0, 2000),
      duration: result.duration,
      tenantId,
    });
  }

  async onEnd(result: FullResult) {
    if (this.failedTests.length === 0) return;

    const apiKey = process.env.INTERNAL_API_KEY || "";
    if (!apiKey) {
      console.warn(
        "[IncidentReporter] INTERNAL_API_KEY not set — skipping incident logging"
      );
      return;
    }

    let logged = 0;
    for (const failure of this.failedTests) {
      const severity = this.deriveSeverity(failure.testTitle, failure.error);

      try {
        const resp = await fetch(
          `${this.backendUrl}/api/platform/incidents`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Internal-Key": apiKey,
            },
            body: JSON.stringify({
              category: "api_contract",
              severity,
              source: "playwright",
              tenant_id: failure.tenantId,
              error_message:
                `[${failure.testFile}] ${failure.testTitle}: ${failure.error}`,
              stack_trace: failure.stack,
              context: {
                test_file: failure.testFile,
                test_title: failure.testTitle,
                duration_ms: failure.duration,
                environment: process.env.TEST_ENV || "staging",
              },
            }),
          }
        );
        if (resp.ok) {
          logged++;
        } else {
          console.warn(
            `[IncidentReporter] POST failed (${resp.status}):`,
            failure.testTitle
          );
        }
      } catch (e) {
        // Never let reporter failures block the test run
        console.warn(
          "[IncidentReporter] Failed to log:",
          failure.testTitle,
          e
        );
      }
    }

    console.log(
      `[IncidentReporter] Logged ${logged}/${this.failedTests.length} incident(s) to platform_incidents`
    );
  }

  private deriveSeverity(title: string, error: string): string {
    const t = title.toLowerCase();
    const e = error.toLowerCase();

    // Critical: auth or core business flow failures
    if (
      t.includes("login") ||
      t.includes("auth") ||
      t.includes("order") ||
      t.includes("invoice")
    )
      return "high";

    // RBAC or navigation failures
    if (
      t.includes("rbac") ||
      t.includes("permission") ||
      t.includes("redirect")
    )
      return "medium";

    // Timeout always high
    if (e.includes("timeout") || e.includes("timed out")) return "high";

    return "medium";
  }
}

export default IncidentReporter;
