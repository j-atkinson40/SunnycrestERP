"""Seed contextual explanations with default content — no AI call needed."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.training import ContextualExplanation

logger = logging.getLogger(__name__)

SEED_EXPLANATIONS = [
    {
        "explanation_key": "ar_aging_buckets",
        "trigger_context": "When viewing AR aging",
        "headline": "What do the aging buckets mean for our business?",
        "explanation": (
            "The aging buckets show how long your customers have owed you money. "
            "'Current' means the invoice isn't due yet — this is normal. "
            "'1-30 days' means it's slightly past due, which happens often and usually resolves quickly.\n\n"
            "'31-60 days' is where you should start paying attention. At this point, a friendly reminder "
            "is appropriate. '61-90 days' is a concern — the longer money sits unpaid, the harder it is to collect. "
            "'90+ days' is serious and may require escalation or a credit hold.\n\n"
            "For a vault manufacturer, most funeral homes pay on 30-day terms. If you see a lot of money "
            "in the 31-60 bucket, it usually means statements went out late or a payment got lost. "
            "The 90+ bucket is where you risk write-offs — money you may never collect."
        ),
    },
    {
        "explanation_key": "journal_entry_purpose",
        "trigger_context": "When creating a journal entry",
        "headline": "What is a journal entry and when do we use them?",
        "explanation": (
            "A journal entry is a manual adjustment to your books. Most transactions — invoices, payments, "
            "bills — create accounting entries automatically. Journal entries are for everything else: "
            "recording depreciation, correcting mistakes, accruing expenses, or making year-end adjustments.\n\n"
            "Every journal entry must balance — the total debits must equal the total credits. This is the "
            "foundation of double-entry accounting and ensures your books stay accurate.\n\n"
            "Common examples in a vault manufacturing business: monthly depreciation on your delivery trucks, "
            "accruing wages at month-end, recording insurance prepayments, or correcting an invoice that "
            "was posted to the wrong GL account."
        ),
    },
    {
        "explanation_key": "statement_vs_invoice",
        "trigger_context": "When generating statements",
        "headline": "What is the difference between a statement and an invoice?",
        "explanation": (
            "An invoice is a bill for a specific order — 'You bought a Monticello vault on March 5th, "
            "here's what you owe for that order.' A statement is a summary of everything — all invoices, "
            "all payments, and the total balance for the month.\n\n"
            "Most funeral homes receive individual invoices when each order ships, then a monthly statement "
            "that summarizes their entire account activity. The statement is what they typically pay from — "
            "it shows their opening balance, new charges, payments received, and closing balance.\n\n"
            "Statements are important because they catch anything that slipped through. A funeral home might "
            "miss a single invoice email, but the monthly statement shows everything in one place."
        ),
    },
    {
        "explanation_key": "finance_charge_posting",
        "trigger_context": "When posting finance charges",
        "headline": "Why do we charge finance charges?",
        "explanation": (
            "Finance charges incentivize customers to pay on time. When a funeral home carries a balance "
            "past their payment terms, the finance charge compensates you for the cost of carrying that debt — "
            "you've delivered the product but haven't been paid yet.\n\n"
            "The charge is typically 1-2% per month on the overdue balance. It's standard practice in the "
            "industry and most funeral homes expect it. The key is consistency — charge everyone the same way, "
            "and forgive strategically when there's a good reason (like a payment arrangement or a dispute).\n\n"
            "Finance charges post as revenue to your books and appear on the customer's next statement. "
            "They should be calculated and posted before you generate month-end statements."
        ),
    },
    {
        "explanation_key": "early_payment_discount_apply",
        "trigger_context": "When applying an early payment discount",
        "headline": "Why do we offer early payment discounts?",
        "explanation": (
            "Early payment discounts reward funeral homes for paying quickly. A typical discount is 2% "
            "if paid by the 15th of the month — so on a $1,000 statement, they save $20 by paying early.\n\n"
            "This benefits you because faster payment improves your cash flow and reduces the risk of "
            "non-payment. It's much cheaper to give a 2% discount than to chase a 90-day overdue account "
            "through collections.\n\n"
            "When you apply the discount, a journal entry is created automatically — debiting Sales Discounts "
            "(reducing your revenue slightly) and crediting Accounts Receivable (closing the customer's balance). "
            "The customer's invoice is marked as paid in full even though they paid slightly less."
        ),
    },
    {
        "explanation_key": "three_way_match",
        "trigger_context": "When reviewing a PO match discrepancy",
        "headline": "What is three-way match and why does it matter?",
        "explanation": (
            "Three-way match compares three documents: the purchase order (what you ordered), the receiving "
            "record (what you received), and the vendor's invoice (what they're charging you). All three "
            "should agree on quantities and prices.\n\n"
            "When they don't match, it means something went wrong — you were charged for items you didn't "
            "receive, the price changed without notice, or there was a data entry error. Catching these "
            "discrepancies before paying prevents overpayment.\n\n"
            "In a vault plant, common discrepancies include cement price adjustments, freight charges not "
            "on the PO, or short deliveries where you received fewer bags than ordered. Always resolve "
            "the discrepancy before approving payment."
        ),
    },
    {
        "explanation_key": "period_close",
        "trigger_context": "When closing an accounting period",
        "headline": "Why do we close accounting periods?",
        "explanation": (
            "Closing an accounting period means locking down the books for that month so no new transactions "
            "can be posted to it accidentally. Once March is closed, anyone trying to post something to March "
            "will get a warning (or be blocked entirely).\n\n"
            "This matters because your financial reports for a closed month should never change. If you gave "
            "your accountant the March income statement, and then someone posts an invoice to March later, "
            "the numbers won't match what you reported.\n\n"
            "Best practice is to close the prior month within 15 days of the new month starting. So close "
            "March by April 15th at the latest. The platform will remind you if you forget."
        ),
    },
    {
        "explanation_key": "credit_limit_enforcement",
        "trigger_context": "When a credit limit warning appears",
        "headline": "Why do we set credit limits for funeral homes?",
        "explanation": (
            "Credit limits protect you from extending too much credit to any one customer. If a funeral home "
            "keeps ordering but doesn't pay, their balance grows — and the larger the balance, the harder "
            "it is to collect if something goes wrong.\n\n"
            "A credit limit says 'we trust this customer up to $X.' Beyond that, we need to talk about "
            "their outstanding balance before shipping more product. It's not about distrust — it's about "
            "healthy business practice.\n\n"
            "When a customer hits 90% of their limit, you'll get a warning. When they exceed it, new orders "
            "are held for manager approval. This gives you a chance to reach out about their balance before "
            "extending more credit."
        ),
    },
    {
        "explanation_key": "collections_sequence",
        "trigger_context": "When reviewing a collections draft",
        "headline": "How does our collections process work and why?",
        "explanation": (
            "Collections is the process of following up on overdue payments. The platform generates email "
            "drafts for you — you review and send them. It's always a human decision to contact a customer.\n\n"
            "The sequence has three steps: a friendly reminder at 31 days (assumes good faith — maybe they "
            "forgot), a firmer notice at 45 days, and a final notice at 59 days warning about a potential "
            "credit hold. Each step gives the customer a chance to respond before escalation.\n\n"
            "The key is consistency and professionalism. These are long-term business relationships — the "
            "goal is to get paid while maintaining the relationship. Always review the draft before sending "
            "and adjust the tone if you know something about the customer's situation."
        ),
    },
    {
        "explanation_key": "bank_reconciliation_purpose",
        "trigger_context": "When starting reconciliation",
        "headline": "Why do we reconcile our bank accounts?",
        "explanation": (
            "Bank reconciliation compares your platform's records to your actual bank statement to make sure "
            "they match. If you recorded a payment in the platform but it never appeared in the bank, "
            "something is wrong — maybe the check bounced or was never deposited.\n\n"
            "Reconciling monthly catches errors, fraud, and missing transactions before they compound. "
            "It's one of the most important internal controls a business can have.\n\n"
            "The platform does most of the matching automatically — it finds transactions in your bank "
            "statement that match payments and bills in the system. You only need to handle the exceptions: "
            "bank fees, unmatched deposits, and outstanding checks."
        ),
    },
    {
        "explanation_key": "transfer_workflow",
        "trigger_context": "When initiating a licensee transfer",
        "headline": "How does an out-of-area transfer work?",
        "explanation": (
            "When a funeral home orders a burial in a cemetery outside your service territory, you can't "
            "deliver there yourself. Instead, you transfer the order to the Wilbert licensee who serves "
            "that area — they fulfill the delivery, and you handle the billing back to the funeral home.\n\n"
            "The transfer creates a chain: the area licensee charges you their price, and you charge the "
            "funeral home your price (usually the same or with a small markup). The platform handles the "
            "cross-tenant billing automatically.\n\n"
            "Transfers are common and expected in the Wilbert network. The key is prompt communication — "
            "the area licensee needs enough lead time to schedule their driver, and the funeral home needs "
            "to know the pricing before the service."
        ),
    },
    {
        "explanation_key": "tax_exemption_importance",
        "trigger_context": "When a tax exemption warning appears",
        "headline": "Why do we track funeral home tax exemption certificates?",
        "explanation": (
            "Many funeral homes are tax-exempt on purchases they resell to families. But you can only "
            "honor that exemption if you have a valid exemption certificate on file. Without it, you're "
            "liable for the uncollected tax if you're audited.\n\n"
            "Certificates expire — typically every few years. When one expires and isn't renewed, the "
            "platform automatically starts charging tax on that customer's invoices. This protects you "
            "from audit liability.\n\n"
            "When you see an expiration warning, reach out to the funeral home and ask them to send a "
            "renewed certificate. It's a routine request they're used to handling."
        ),
    },
    {
        "explanation_key": "vendor_w9_requirement",
        "trigger_context": "When a W-9 warning appears",
        "headline": "Why do we need W-9s from vendors?",
        "explanation": (
            "If you pay a vendor more than $600 in a year, the IRS requires you to file a 1099 form "
            "reporting those payments. To file the 1099, you need the vendor's tax ID — which comes "
            "from their W-9 form.\n\n"
            "The platform tracks vendor payments year-to-date and warns you when a vendor approaches "
            "the $600 threshold without a W-9 on file. Getting the W-9 early avoids a scramble at "
            "year-end when everyone is trying to file 1099s.\n\n"
            "This applies to contractors and individuals — not to corporations, who are generally exempt "
            "from 1099 reporting."
        ),
    },
    {
        "explanation_key": "charge_account_basics",
        "trigger_context": "When setting up a new customer charge account",
        "headline": "How do funeral home charge accounts work?",
        "explanation": (
            "A charge account means the funeral home doesn't pay at delivery — they order throughout the "
            "month and receive a consolidated statement at month-end. This is standard in the vault industry "
            "because funeral homes order frequently and it's impractical to pay per delivery.\n\n"
            "When you set up a charge account, you're extending credit. You set payment terms (typically "
            "Net 30), a credit limit, and whether they receive monthly statements. The platform tracks "
            "everything — orders, invoices, payments, aging — so you always know where each account stands.\n\n"
            "Not every customer needs a charge account. Walk-in purchases, one-time orders, and contractors "
            "may be better suited to COD (cash on delivery) or invoice-on-order billing."
        ),
    },
    {
        "explanation_key": "po_purpose",
        "trigger_context": "When creating a purchase order",
        "headline": "Why do we use purchase orders?",
        "explanation": (
            "A purchase order is your formal authorization to buy something. It documents what you're ordering, "
            "from whom, at what price, and when you expect delivery. Without POs, you're relying on verbal "
            "agreements and handshakes — which leads to disputes when the invoice doesn't match expectations.\n\n"
            "POs also create accountability. When a vendor sends an invoice, you can match it against the PO "
            "to verify you're being charged correctly (three-way match). This catches pricing errors and "
            "unauthorized charges before you pay them.\n\n"
            "For a vault plant, common POs include cement, aggregates, admixtures, and equipment maintenance. "
            "The platform can require manager approval for POs above a certain amount — giving you cost "
            "control without slowing down routine purchases."
        ),
    },
]


def seed_explanations(db: Session, tenant_id: str) -> int:
    """Seed all contextual explanations for a tenant. Returns count created."""
    created = 0
    for item in SEED_EXPLANATIONS:
        existing = (
            db.query(ContextualExplanation)
            .filter(
                ContextualExplanation.tenant_id == tenant_id,
                ContextualExplanation.explanation_key == item["explanation_key"],
            )
            .first()
        )
        if existing:
            continue

        explanation = ContextualExplanation(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            explanation_key=item["explanation_key"],
            trigger_context=item["trigger_context"],
            headline=item["headline"],
            explanation=item["explanation"],
            content_generated=True,
            content_generated_at=datetime.now(timezone.utc),
            is_active=True,
        )
        db.add(explanation)
        created += 1

    db.commit()
    return created
