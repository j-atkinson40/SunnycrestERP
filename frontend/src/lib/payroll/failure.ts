/**
 * What a failed payroll write is allowed to CLAIM, and how to find out.
 *
 * ⚠️ **EXTRACTED FROM `payroll-setup.tsx` ON 2026-11-17 BECAUSE THE SAME
 * DEFECT WAS IN THREE OTHER PLACES.** The setup page was fixed first; the
 * weekly Focus still told Susan "Nothing has been changed" on a register
 * upload, an hour correction and a week answer — three writes, three claims
 * that cannot be made when no reply arrives.
 *
 * Behaviour is unchanged by the move. The tests that pinned these two
 * functions were written against the setup page and now import them here.
 */

/**
 * What a request said when it failed.
 *
 * ⚠️ **"NOTHING HAS BEEN CHANGED" USED TO BE THE FALLBACK HERE, AND IT WAS A
 * CLAIM THIS FUNCTION CANNOT MAKE.** Measured on production 2026-11-17: the
 * register upload answered **422 in 41 ms**, and this function printed "The
 * request did not go through. Nothing has been changed." Both halves were
 * wrong. The request went through; the server replied; and whether anything
 * changed is not knowable from an error object.
 *
 * Two failures were being collapsed into one sentence:
 *
 *   `err.response` PRESENT   the server answered. Its words are the answer,
 *                            and a generic line hides them.
 *   `err.response` ABSENT    no reply reached the browser. The work may have
 *                            completed anyway — a CORS rejection, a timeout or
 *                            a reset on the RETURN leg all look like this — so
 *                            the only honest line says the state is unknown
 *                            and goes and looks.
 *
 * ⚠️ **AND FastAPI's 422 DETAIL IS A LIST**, not a string and not an object
 * with `message`. The old code read only those two shapes, so every validation
 * refusal — including the one that actually happened — fell through to the
 * generic sentence and the server's own account was discarded.
 */
export function failureText(err: unknown): string {
  const response = (err as { response?: { status?: number; data?: unknown } })
    ?.response

  if (!response) {
    // ⚠️ **THIS SENTENCE NO LONGER PROMISES A CHECK, AND THAT IS THE FIX.**
    // It used to end "…this page will check what was saved" — a promise made
    // by a SHARED helper and kept by only one of its callers. On 2026-11-17 the
    // roster card showed exactly that sentence and then went silent, because
    // `RosterCard` had no follow-up at all.
    //
    // A shared message cannot promise per-caller behaviour. So this states only
    // what is true everywhere — the outcome is unknown — and a caller that
    // really does look appends `CHECKING_SUFFIX` itself. The promise is now
    // only expressible by code in a position to keep it.
    return "No reply from the server, so whether it completed is unknown."
  }

  const data = response.data as { detail?: unknown } | undefined
  const detail = data?.detail

  if (typeof detail === "string") return detail
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{loc, msg, type}, ...]. Rendered with the
    // field, because "field required" without saying WHICH field is the same
    // uselessness as the generic sentence this replaced.
    const parts = detail
      .map((d) => {
        const e = d as { loc?: unknown[]; msg?: unknown }
        const where = Array.isArray(e.loc)
          ? e.loc.filter((x) => x !== "body").join(".")
          : ""
        const msg = typeof e.msg === "string" ? e.msg : "invalid"
        return where ? `${where}: ${msg}` : msg
      })
      .filter(Boolean)
    if (parts.length > 0) {
      return `The server rejected the request (${response.status}): ${parts.join("; ")}`
    }
  }
  if (detail && typeof detail === "object") {
    const msg = (detail as { message?: unknown }).message
    if (typeof msg === "string") return msg
  }
  return `The server refused the request (${response.status}).`
}

/** True when no reply reached the browser, so the server's state is unknown
 *  and must be read rather than assumed. */
export function gotNoReply(err: unknown): boolean {
  return !(err as { response?: unknown })?.response
}


/** What a follow-up check concluded about a write whose reply never arrived. */
export type LandedVerdict = "landed" | "did-not-land" | "unknown"

/**
 * Ask the SERVER whether a write landed, when the client's own account is
 * worth nothing.
 *
 * ⚠️ **THE THREE OUTCOMES ARE NOT TWO.** A failed check is not "did not land";
 * it is "still unknown", and collapsing it is how "nothing has been changed"
 * gets back in by a side door. `unknown` exists so a caller must write a
 * sentence for it.
 *
 * ⚠️ **`read` IS THE SERVER'S RECORD, NEVER A CACHE OR A LOCAL FLAG.** A CORS
 * rejection, a timeout or a reset on the RETURN leg produces a client error
 * for work the server may have committed — so the only account worth having
 * comes from the thing the request arrived at.
 */
export async function didWriteLand<T>(
  read: () => Promise<T>,
  present: (value: T) => boolean,
): Promise<LandedVerdict> {
  try {
    return present(await read()) ? "landed" : "did-not-land"
  } catch {
    return "unknown"
  }
}

/**
 * Appended by a caller that is ABOUT TO perform the check — never by
 * `failureText`, which cannot know whether its caller will.
 */
export const CHECKING_SUFFIX = " Checking what was saved…"
