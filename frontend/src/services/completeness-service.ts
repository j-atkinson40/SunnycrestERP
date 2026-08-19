/**
 * The completeness review + the nil-claim pattern. CR-2 A-3.
 *
 * ⚠️ TWO AUDIENCES, ONE SERVICE. `getReview` is the accountant's bounded
 * decision; `getMyObligations` is the SAME data filtered to the caller's role.
 * That filter is the whole "prompted, not remembered" mechanism — a quiet day
 * produces no reason to open anything, so the obligation has to arrive at the
 * person rather than wait on a page they chose to visit.
 */
// DEFAULT import — `api-client.ts` has no named `apiClient` export, and every
// other service in this directory imports it this way. The named form typechecks
// nowhere and fails the rollup build outright.
import apiClient from "@/lib/api-client";

/** Satisfied and quiet. */
export type Verdict =
  | "arrived"
  | "partial"
  | "missing"
  | "not_yet_due"
  /** Someone holding the obligation signed a statement that nothing happened. */
  | "reported_none"
  | "declined"
  /**
   * The tenant declined this obligation and evidence arrived anyway. Either the
   * declination is wrong or something unexpected happened; the verdict names the
   * relationship and refuses to pick which.
   */
  | "contradicted"
  /** The check could not run. NOT the same as a clean period. */
  | "unknown";

/**
 * Consecutive periods of one obligation sharing a verdict, as ONE row.
 * Six consecutive missing days is one condition; six rows would describe
 * incidents that do not exist.
 */
export interface CompletenessRun {
  key: string;
  label: string;
  role_slug: string;
  verdict: Verdict;
  actionable: boolean;
  first: string;
  last: string;
  periods: number;
  detail: string;
}

export interface CompletenessResult {
  rows: CompletenessRun[];
  /** The quiet obligations, counted not enumerated. Silence reads as an
   *  assumption; "3 obligations current" is a statement. */
  quiet_summary: string;
  actionable_count: number;
}

export interface MyObligations extends CompletenessResult {
  role_slug: string | null;
}

/** A tenant's recorded "we don't do that", with who said it and why. */
export interface Declination {
  id: string;
  declined_on: string;
  reason: string;
  /** Snapshotted at write time — who answered THEN, not what they hold now. */
  declined_by_name: string;
  declined_by_role_slug: string;
}

/**
 * One declared obligation and its current state.
 *
 * ⚠️ THIS IS NOT A REVIEW ROW AND MUST NOT BE DERIVED FROM ONE. `/review` is
 * exception-shaped — `summarise` drops everything that is fine into a count — so
 * a control built from review rows could only ever decline obligations that were
 * already red. Declining is a standing decision about the business, not an
 * answer to a red row, and the data shape is where that distinction starts.
 */
export interface Obligation {
  key: string;
  label: string;
  role_slug: string;
  cadence: string;
  matters_because: string;
  declination: Declination | null;
}

export interface ObligationList {
  obligations: Obligation[];
}

/**
 * ⚠️ THERE IS NO `may_decline` FLAG, AND ITS ABSENCE IS THE DESIGN.
 *
 * D-2 shipped one, because a control that renders and then 403s invites the
 * click it cannot honour. Then `/obligations` was gated to the same accounting
 * roles that may decline — so the flag became structurally always `true`, which
 * is a field that reads as a permission check and checks nothing. This codebase
 * already carries two of those (`AUTO_COMMIT_THRESHOLD` referenced nowhere,
 * `suggested_count` hardcoded to 0) and both produced wrong conclusions when
 * someone reasoned from them.
 *
 * So the permission is expressed once, at the endpoint: reaching this data at
 * all means the server admitted you, and it admits exactly the roles that may
 * write. Re-deriving the role list on the client would be the same defect from
 * the other side.
 */

export const completenessService = {
  async getReview(asOf?: string): Promise<CompletenessResult> {
    const { data } = await apiClient.get<CompletenessResult>("/completeness/review", {
      params: asOf ? { as_of: asOf } : {},
    });
    return data;
  },

  async getMyObligations(asOf?: string): Promise<MyObligations> {
    const { data } = await apiClient.get<MyObligations>("/completeness/my-obligations", {
      params: asOf ? { as_of: asOf } : {},
    });
    return data;
  },

  async getObligations(): Promise<ObligationList> {
    const { data } = await apiClient.get<ObligationList>(
      "/completeness/obligations",
    );
    return data;
  },

  /**
   * "We don't do that", recorded — CR-3 D-2.
   *
   * No effective date parameter, deliberately. A back-dated declination would
   * erase periods that were genuinely missed, which is the retroactive rewrite
   * D-3 was spent removing handed back as an argument.
   */
  async decline(input: {
    expectation_key: string;
    reason: string;
  }): Promise<{ status: string; declined_by: string; role_slug: string }> {
    const { data } = await apiClient.post("/completeness/decline", input);
    return data;
  },

  /** "We do this again". NOT a delete — the episode keeps its dates, so the
   *  months the tenant was not doing it still read as `declined` rather than
   *  turning back into gaps. */
  async revokeDeclination(
    declinationId: string,
    reason: string,
  ): Promise<{ status: string; revoked_by: string; role_slug: string }> {
    const { data } = await apiClient.post(
      `/completeness/declinations/${declinationId}/revoke`,
      { reason },
    );
    return data;
  },

  /**
   * State that nothing happened, signed.
   *
   * The server rejects this with 403 unless the caller holds the obligation's
   * role — this is the one place assertion substitutes for evidence, and what
   * makes it worth anything is that a named person who OWES it stood behind it.
   */
  async fileNilClaim(input: {
    expectation_key: string;
    period_start: string;
    period_end: string;
    note?: string;
  }): Promise<{ status: string; claimed_by: string; role_slug: string }> {
    const { data } = await apiClient.post("/completeness/nil-claim", input);
    return data;
  },
};
