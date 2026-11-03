/**
 * Payroll — the area shell.
 *
 * Deliberately empty of data. Payroll 1 ships the way IN: a signed-in user on
 * the area-limited `payroll` role reaches this page and, on the server, nothing
 * else. The weekly dues Focus and the report surfaces land in Payroll 2.
 *
 * ⚠️ NO DATA IS FETCHED HERE ON PURPOSE. The dues engine, the week model and the
 * report endpoints already exist (r220, /api/v1/payroll-reports/*), so it would
 * be one `useEffect` to put real numbers on this page — and the ruling for this
 * slice is that no payroll data loads until two-step sign-in exists for
 * payroll-limited users. Pay rates and hours should not sit behind a password
 * alone (James, 2026-11-03). Adding a fetch here would quietly cross that line.
 */
export default function PayrollHome() {
  return (
    <div className="space-y-6 p-6">
      <header className="space-y-1">
        <h1 className="text-h1 text-content-strong">Payroll</h1>
        <p className="text-body text-content-muted">
          Weekly union dues review
        </p>
      </header>

      <div className="max-w-reading rounded-base border border-border-subtle bg-surface-elevated p-6 shadow-level-1">
        <h2 className="text-h4 text-content-strong">Payroll review is coming</h2>
        <p className="mt-2 text-body text-content-muted">
          This is where the weekly dues review will live: the Payentry import,
          the per-member dues detail, the deduction register and the monthly
          remittance.
        </p>
        <p className="mt-3 text-body-sm text-content-subtle">
          Nothing is loaded yet. Your access is set up and limited to payroll —
          you will not see other parts of Bridgeable.
        </p>
      </div>
    </div>
  )
}
