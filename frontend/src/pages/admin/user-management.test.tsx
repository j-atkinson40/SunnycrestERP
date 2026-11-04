/**
 * Resend and Cancel invite — the row decisions, both branches of each.
 *
 * ⚠️ **A TEST PER BRANCH, BECAUSE THAT IS THE DISCIPLINE CLAUDE.md ASKS FOR BY
 * NAME.** DotNav's `spaces.length === 0 → return null` early return survived
 * fourteen months with an inline comment describing behaviour the code never
 * implemented, because the populated path was the only one any fixture
 * exercised. A conditional render gets a test for each side, including the
 * absent and unknown cases a happy-path fixture skips straight over.
 *
 * The functions under test are the ones the render calls — the page holds no
 * second copy of the condition. A test against a duplicated predicate would be
 * a fixture modelled on the implementation, agreeing with it by construction.
 */
import { describe, expect, it } from "vitest"

import {
  cancelOutcome,
  resendOutcome,
  userRowState,
} from "./user-management"

describe("userRowState", () => {
  it("offers Resend and Cancel to someone who has not signed in", () => {
    const s = userRowState({ is_active: true, has_outstanding_invite: true })
    expect(s.status).toBe("invited")
    expect(s.offersInviteActions).toBe(true)
  })

  it("says 'Invited' rather than 'Active' for a pending invitee", () => {
    // ⚠️ She IS `is_active: true`. Reporting her as Active is the one thing
    // that is false about her — she has never signed in, and an admin reading
    // "Active" has no reason to look for a Resend button.
    expect(userRowState({ is_active: true, has_outstanding_invite: true }).status)
      .toBe("invited")
  })

  it("offers neither to a colleague who has signed in", () => {
    const s = userRowState({ is_active: true, has_outstanding_invite: false })
    expect(s.status).toBe("active")
    expect(s.offersInviteActions).toBe(false)
  })

  it("reports an inactive user as inactive, not as invited", () => {
    const s = userRowState({ is_active: false, has_outstanding_invite: false })
    expect(s.status).toBe("inactive")
    expect(s.offersInviteActions).toBe(false)
  })

  it("treats an ABSENT flag as 'not known' and offers nothing", () => {
    // The branch a happy-path fixture never reaches: older payloads and the
    // auth /me shape carry no such field. Nothing is offered, because nothing
    // is known — not because there is no invite.
    const s = userRowState({ is_active: true })
    expect(s.offersInviteActions).toBe(false)
    expect(s.status).toBe("active")
  })

  it("is not satisfied by a truthy non-boolean", () => {
    // ⚠️ `=== true`, not truthiness. A server sending the string "false" must
    // not light up invite actions on an account that has a password.
    const s = userRowState({
      is_active: true,
      has_outstanding_invite: "false" as unknown as boolean,
    })
    expect(s.offersInviteActions).toBe(false)
  })
})

describe("resendOutcome", () => {
  it("reports success when the email went out", () => {
    const o = resendOutcome({ email_sent: true }, "Sue", "sue@example.com")
    expect(o.level).toBe("success")
    expect(o.message).toContain("sue@example.com")
  })

  it("reports an ERROR when the email did not send, not a partial success", () => {
    // ⚠️ The whole point. A resend that minted a token nobody received is
    // worse than not resending, because the old link is dead too — so she now
    // has no way in at all. One outcome, and it is the error.
    const o = resendOutcome({ email_sent: false }, "Sue", "sue@example.com")
    expect(o.level).toBe("error")
    expect(o.message).toContain("no way in")
    expect(o.message).not.toContain("New invitation sent")
  })

  it("does not cry wolf when the field is absent", () => {
    // An older server that omits `email_sent` has not reported failure.
    expect(resendOutcome({}, "Sue", "s@e.com").level).toBe("success")
    expect(resendOutcome(undefined, "Sue", "s@e.com").level).toBe("success")
  })
})

describe("cancelOutcome", () => {
  it("confirms a cancelled invitation", () => {
    const o = cancelOutcome({ cancelled: true }, "Sue", "sue@example.com")
    expect(o.level).toBe("success")
    expect(o.message).toContain("cancelled")
  })

  it("explains rather than erroring when she had already signed in", () => {
    // ⚠️ This is the branch that proves Cancel cannot delete a real user: the
    // server refused, and the UI says her account is untouched instead of
    // showing a failure the admin would retry.
    const o = cancelOutcome({ cancelled: false }, "Sue", "sue@example.com")
    expect(o.level).toBe("info")
    expect(o.message).toContain("already signed in")
    expect(o.message).toContain("untouched")
  })

  it("treats an absent field as 'nothing was cancelled', not as success", () => {
    // ⚠️ The asymmetry is deliberate and opposite to `resendOutcome`'s. There,
    // absence must not claim failure; here, absence must not claim a deletion
    // happened. In both cases the unknown answer is the one that does not
    // assert the consequential thing.
    expect(cancelOutcome({}, "Sue", "s@e.com").level).toBe("info")
    expect(cancelOutcome(undefined, "Sue", "s@e.com").level).toBe("info")
  })
})
