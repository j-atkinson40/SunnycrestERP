/**
 * Vitest setup — runs once before every test file.
 *
 * - Wires up @testing-library/jest-dom matchers (toBeInTheDocument,
 *   toHaveTextContent, etc.)
 * - Configures automatic cleanup after each test (testing-library v13+
 *   does this via the vitest plugin, but we pin it explicitly for clarity)
 */

import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});
