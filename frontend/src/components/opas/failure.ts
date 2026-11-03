/**
 * What a failed request actually was, and what to say about it.
 *
 * Sweep item 2 (James, 2026-11-03): *"The 'did not reach the server' notice must name
 * what actually happened: network failure vs server error (status code) — never one
 * message for both. A 500 is 'Opas hit an error — your order is safe', not a connection
 * message."*
 *
 * ⚠️ THE OLD COPY WAS A FALLBACK NAMING THE WRONG CAUSE, which is the sweep item. One
 * `catch` said "The order did not reach the server" for every failure, and the failure
 * it reported on 2026-11-03 was a **deterministic HTTP 500** — the order had reached the
 * server, been understood, and crashed the serializer on the way back out. Every word of
 * that sentence was wrong except "the order".
 *
 * ⚠️ AND IT COST A DIAGNOSIS, NOT JUST A WORD. A connection message sends the reader to
 * the network; the fault was in a `read_state` serializer dereferencing a `None`. The
 * message is the first evidence anyone has, so a message that names the wrong layer is
 * the most expensive kind of wrong.
 *
 * ⚠️ WHICH IS WHY THE CLASSIFICATION ALSO DECIDES WHETHER TO RETRY. They are the same
 * question asked twice: a request that never arrived deserves another attempt, and a
 * request the server REFUSED (4xx) will be refused identically forever. Retrying a 400
 * three times is three ways of not listening.
 */

export type FailureKind = "network" | "server" | "refused"

export interface Failure {
  readonly kind: FailureKind
  /** Present only when the server answered. */
  readonly status?: number
  /** The one line the pane shows. */
  readonly notice: string
  /** Whether another attempt could plausibly succeed. */
  readonly retry: boolean
}

/** ⚠️ EVERY MESSAGE ENDS THE SAME WAY, because that is the director's real question and
 *  the old copy answered the opposite. Whatever broke, the order is on the server. */
const SAFE = "your order is safe"

/**
 * Classify an error from the capture service.
 *
 * ⚠️ `err.response` IS THE DISCRIMINATOR, and it is the only reliable one. Axios sets it
 * when the server answered — any status, including 500 — and leaves it undefined for a
 * DNS failure, a refused connection, a timeout, or a CORS rejection. Reading
 * `err.message` instead would be guessing from prose that differs per browser.
 *
 * ⚠️ AND A RESPONSE WITH NO STATUS IS TREATED AS NETWORK. A malformed error object is
 * not evidence the server answered, and the safe default is the one that retries.
 */
export function classifyFailure(err: unknown): Failure {
  const status = statusOf(err)

  if (status === undefined) {
    return {
      kind: "network",
      notice: `Reconnecting — ${SAFE}`,
      retry: true,
    }
  }

  // ⚠️ 4xx IS A REFUSAL AND DOES NOT RETRY. The server read the request and said no;
  // asking again unchanged gets the same no. 408 and 429 are the exceptions — both mean
  // "ask again" in so many words — so they fall through to the retrying branch.
  if (status >= 400 && status < 500 && status !== 408 && status !== 429) {
    return {
      kind: "refused",
      status,
      notice: `Opas could not accept that (${status}) — ${SAFE}`,
      retry: false,
    }
  }

  // ⚠️ THE STATUS IS IN THE TEXT ON PURPOSE. James read "did not reach the server" and
  // could not tell it from a connection drop; a number makes the layer unambiguous to
  // him and to whoever reads the report afterwards.
  return {
    kind: "server",
    status,
    notice: `Opas hit an error (${status}) — ${SAFE}`,
    retry: true,
  }
}

/** The HTTP status, or undefined when the server never answered. */
export function statusOf(err: unknown): number | undefined {
  if (typeof err !== "object" || err === null) return undefined
  const res = (err as { response?: unknown }).response
  if (typeof res !== "object" || res === null) return undefined
  const status = (res as { status?: unknown }).status
  return typeof status === "number" ? status : undefined
}

/**
 * The line to show once every attempt has failed.
 *
 * ⚠️ IT KEEPS THE CAUSE RATHER THAN COLLAPSING TO ONE SENTENCE, which is the whole
 * point of the sweep item. A settled network failure and a settled 500 are different
 * things to tell a director and different things to put in a bug report.
 */
export function stalledNotice(f: Failure): string {
  const tail = "The last words you typed have not been read yet."
  if (f.kind === "network") return `Still reconnecting — ${SAFE}. ${tail}`
  if (f.kind === "refused") return `${f.notice} ${tail}`
  return `Opas is still erroring (${f.status}) — ${SAFE}. ${tail}`
}
