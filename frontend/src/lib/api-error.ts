/**
 * Extract a human-readable error message from an Axios error.
 *
 * FastAPI returns `detail` as a **string** for business logic errors (400/401/403/404),
 * but as an **array of objects** for pydantic validation errors (422).
 * Passing the raw array into React state and rendering it crashes the app
 * because objects aren't valid React children.
 *
 * This helper normalises both shapes into a single string.
 */
export function getApiErrorMessage(
  err: unknown,
  fallback = "An unexpected error occurred"
): string {
  const detail = (
    err as { response?: { data?: { detail?: unknown } } }
  ).response?.data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((e: { msg?: string }) => e.msg ?? "")
      .filter(Boolean)
      .join(", ");
  }

  return fallback;
}
