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
    # ── AI Feature Explanations ──
    {
        "explanation_key": "agent_alert_collections_draft",
        "trigger_context": "When a collections email draft alert appears for the first time",
        "headline": "What is this collections draft and what should I do with it?",
        "explanation": (
            "The system noticed that a customer has an invoice past a certain age threshold — typically 31, 45, "
            "or 60 days overdue — and drafted a collections email for you to review. The email is ready to send "
            "but has NOT been sent. Nothing goes out until you approve it.\n\n"
            "Before you send, check: do you have any recent context about this customer? A phone call, a payment "
            "promise, or a dispute? The system doesn't know about those conversations. If you have context that "
            "makes this email inappropriate right now, dismiss the alert and log a note explaining why.\n\n"
            "If the email looks right, you can edit it before sending. Change the tone, add personal context, or "
            "adjust the details. Then send. If you don't act on this draft, the system will eventually escalate "
            "to a firmer tone in the next step — so either send, edit and send, or dismiss with a reason."
        ),
    },
    {
        "explanation_key": "agent_alert_payment_unmatched",
        "trigger_context": "When an unmatched payment alert appears",
        "headline": "Why did the agent flag this payment and how do I resolve it?",
        "explanation": (
            "A payment came in that the system couldn't automatically match to an open invoice. This happens when "
            "the payment amount doesn't exactly match any single invoice, or when the payment date or customer "
            "reference doesn't line up clearly.\n\n"
            "Your job is to tell the system which invoice(s) this payment should apply to. Click 'Apply to Invoice' "
            "and you'll see all open invoices for this customer. Select the right one and the system handles the rest. "
            "If the payment covers multiple invoices, apply it to the oldest first.\n\n"
            "If you can't figure out what the payment is for, don't guess. Reach out to the customer or check the "
            "check stub for details. Applying a payment to the wrong invoice creates more problems than leaving it "
            "unmatched for a day while you investigate."
        ),
    },
    {
        "explanation_key": "agent_alert_po_discrepancy",
        "trigger_context": "When a three-way match discrepancy alert appears",
        "headline": "What is a three-way match discrepancy and why does it matter?",
        "explanation": (
            "Three-way match means the system compared three things: what you ordered (the PO), what you received "
            "(the receipt), and what the vendor is charging you (the bill). When all three agree, the bill is "
            "automatically cleared for payment. When they don't match, the system flags it for you.\n\n"
            "Common discrepancies include: the vendor charged a different price than the PO, the quantity on the "
            "bill doesn't match what was received, or freight charges were added that weren't on the PO. "
            "These are real money — a $5 price difference on 100 units is $500.\n\n"
            "Your job is to investigate: was this an agreed-upon price change? Did you receive less than ordered? "
            "Should the vendor issue a credit? Never approve a discrepancy without understanding it — that's how "
            "small overcharges accumulate into significant losses over time."
        ),
    },
    {
        "explanation_key": "agent_alert_transfer_pricing",
        "trigger_context": "When a transfer pricing review alert appears",
        "headline": "Why do I need to approve this pricing before the funeral home sees it?",
        "explanation": (
            "When a burial is transferred to a licensee in another area, they set their own price for the work. "
            "That price comes to you first — the funeral home never sees the inter-licensee cost directly. "
            "You decide whether to pass the cost through at the same amount or add a markup.\n\n"
            "This approval step exists because the funeral home's price is your business decision, not the area "
            "licensee's. You know your customer relationship, their price sensitivity, and what markup is "
            "appropriate for your market.\n\n"
            "Act on transfer pricing promptly — the funeral home is waiting for a final number, and service dates "
            "don't wait. If pricing hasn't been approved within 24 hours, the system will escalate the urgency. "
            "If the service date is within 7 days, the alert becomes critical."
        ),
    },
    {
        "explanation_key": "agent_alert_delivery_conflict",
        "trigger_context": "When a delivery capacity conflict alert appears",
        "headline": "Why is the agent flagging this delivery and what should I do now?",
        "explanation": (
            "The system predicted that funeral demand on a specific day may use most or all of your driver capacity, "
            "and you have a non-funeral delivery (wastewater, Redi-Rock, or Rosetta) scheduled on that same day. "
            "This doesn't mean the delivery is impossible — it means there's a risk of a scheduling conflict.\n\n"
            "The key number is 'days until delivery.' If you have 10+ days, you can have a conversation with the "
            "contractor about flexibility. If it's under 5 days, options are limited and you should contact them "
            "immediately. Waiting costs you the contractor's trust.\n\n"
            "You can accept the risk if you believe the funeral forecast is pessimistic or you have a backup plan. "
            "You can also mark it for rescheduling if you want to proactively move the delivery. The system will "
            "never cancel a delivery for you — that's always your call."
        ),
    },
    {
        "explanation_key": "agent_alert_cross_system",
        "trigger_context": "When a cross-system insight alert appears",
        "headline": "What is a cross-system insight and why is this one important?",
        "explanation": (
            "A cross-system insight means the platform connected information from different parts of your business "
            "to find something that no single report would show. For example: a customer who is overdue on payments "
            "AND just placed a new order — the AR system knows about the overdue balance and the order system knows "
            "about the new order, but only the cross-system insight connects the two.\n\n"
            "These insights are worth reading carefully because they surface genuine business risks or opportunities "
            "that are easy to miss when you're looking at one system at a time. The narrative explains the connection "
            "in plain English.\n\n"
            "Not every cross-system insight requires action — some are informational context. The severity level "
            "(critical, warning, info) tells you how urgent it is. Critical means act today. Warning means address "
            "this week. Info means be aware."
        ),
    },
    {
        "explanation_key": "agent_confidence_score",
        "trigger_context": "When a confidence percentage appears on any agent suggestion",
        "headline": "What does this confidence percentage mean and how much should I trust it?",
        "explanation": (
            "The confidence score tells you how certain the system is about its suggestion. 95% or higher means "
            "the match is very strong — amount, date, and details all align closely. You can usually approve these "
            "quickly after a glance. 75-94% means the system has a good suggestion but something isn't a perfect "
            "match — maybe the date is off by a few days or the amount is close but not exact. Use your judgment.\n\n"
            "Below 75% means the system is uncertain and you should look carefully before acting. The system surfaces "
            "these because you might see the connection it can't — but don't assume it's right just because it "
            "suggested something.\n\n"
            "The scores improve over time as the system learns from your decisions. When you confirm a match the "
            "system suggested, or override one it got wrong, that feedback makes future suggestions more accurate."
        ),
    },
    {
        "explanation_key": "agent_behavioral_insight",
        "trigger_context": "When a behavioral insight appears on the insights page or in the daily briefing",
        "headline": "How did the agent find this pattern and what should I do with it?",
        "explanation": (
            "Behavioral insights are patterns the system found by looking at your history over time. For example: "
            "'Johnson FH typically pays by day 12 — today is day 18 with no payment' or 'Heidelberg Materials "
            "prices have increased 8% over 6 months.' These are based on real data from your operations.\n\n"
            "The insight tells you something is different from the pattern. That doesn't automatically mean something "
            "is wrong — there could be a perfectly good reason. But patterns that break without explanation are "
            "worth investigating.\n\n"
            "You can dismiss insights you've already addressed or that aren't relevant. Dismissed insights won't "
            "reappear for 90 days. If an insight is helpful, clicking 'Acted On' helps the system learn what "
            "kinds of patterns matter to your business."
        ),
    },
    {
        "explanation_key": "agent_financial_health_drop",
        "trigger_context": "When the financial health grade drops or a negative factor appears",
        "headline": "Why did my financial health score change and should I be concerned?",
        "explanation": (
            "The financial health score is calculated daily from five dimensions: AR health, AP discipline, cash "
            "position, operational integrity, and growth trajectory. When the grade drops, something specific "
            "changed — it's never random.\n\n"
            "Click through to the health detail page to see the 'top negative factors.' These tell you exactly what "
            "drove the change. Common causes: a large invoice went overdue, a bank reconciliation became overdue, "
            "a vendor bill wasn't paid on time, or an accounting period wasn't closed.\n\n"
            "A one-day drop of a few points is usually one specific thing you can address quickly. A sustained "
            "decline over a week suggests a structural issue worth discussing with your manager. The score is a "
            "compass, not an alarm — use it to stay oriented, not to panic."
        ),
    },
    {
        "explanation_key": "agent_seasonal_readiness",
        "trigger_context": "When a seasonal readiness report appears",
        "headline": "What is the seasonal readiness report and how do I use it?",
        "explanation": (
            "The seasonal readiness report checks how prepared your business is for an upcoming busy period — "
            "typically spring burial season (March-May) or year-end. It scans your financial health, operational "
            "status, customer relationships, and vendor readiness to flag anything that could cause problems "
            "during the busiest time of year.\n\n"
            "Think of it as a pre-flight checklist. Each action item has an urgency level: 'immediate' means fix "
            "this now, 'soon' means address this week, 'monitor' means keep an eye on it. The report regenerates "
            "weekly during the preparation window, so action items you address will disappear from next week's report.\n\n"
            "Common findings include: credit limits that haven't been reviewed (peak months often double order "
            "volume), exemption certificates expiring during peak season, and vendor relationships with unresolved "
            "discrepancies. Addressing these before the rush prevents them from becoming crises during it."
        ),
    },
    {
        "explanation_key": "cemetery_equipment_settings",
        "trigger_context": "When viewing Settings → Cemeteries",
        "headline": "Why configure cemetery equipment settings?",
        "explanation": (
            "Every burial service involves equipment — a lowering device to place the vault, grass mats "
            "to keep the grave site clean, a tent for the graveside service, and chairs for the family. "
            "Some cemeteries own this equipment themselves and provide it at no charge. Others expect "
            "you to bring everything.\n\n"
            "If you charge a funeral home for a tent when the cemetery already provides one, the funeral "
            "home will push back — and they'll be right. Getting equipment wrong means inaccurate invoices, "
            "awkward conversations, and eroded trust.\n\n"
            "When you configure a cemetery's equipment settings here, every new order to that cemetery "
            "automatically pre-fills the correct equipment charges. The platform removes charges for "
            "equipment the cemetery provides and suggests what you need to bring. You set it once; "
            "every order gets it right automatically.\n\n"
            "The county setting matters too. Burial vaults are taxed at the rate of the county where "
            "the interment happens — not the funeral home's county. Oak Hill Cemetery in Cayuga County "
            "means Cayuga County tax applies, regardless of where the funeral home is located. "
            "Getting the county right here ensures every invoice has the correct tax amount."
        ),
    },
    {
        "explanation_key": "cemetery_shortlist",
        "trigger_context": "When selecting a cemetery on an order",
        "headline": "How does the cemetery shortlist work?",
        "explanation": (
            "Each funeral home tends to use the same cemeteries repeatedly — they serve specific "
            "geographic areas and build relationships with the cemeteries in their region.\n\n"
            "After you've taken three or more orders for a funeral home, the platform tracks which "
            "cemeteries they use most often and shows those at the top of the cemetery picker when "
            "you're taking a new order from that funeral home. This means less typing — you can select "
            "the cemetery in one click instead of searching for it.\n\n"
            "Until you've built up that history, the platform shows nearby cemeteries based on the "
            "funeral home's address. Either way, you can always search the full cemetery list or "
            "add a new cemetery inline if you encounter one that isn't in your system yet."
        ),
    },
]

SEED_PROCEDURES = [
    {
        "procedure_key": "managing_cemetery_settings",
        "title": "Configuring Cemetery Delivery Settings",
        "applicable_roles": ["inside_sales", "operations", "manager"],
        "category": "operations",
        "sort_order": 20,
        "overview": (
            "Cemetery delivery settings control what equipment appears on funeral orders and which "
            "tax rate applies. Keeping these settings accurate ensures every order is billed correctly "
            "without manual adjustments."
        ),
        "steps": [
            {
                "step_number": 1,
                "title": "Find Settings → Cemeteries",
                "instruction": (
                    "In the left navigation, open Settings (collapsed at the bottom) and click "
                    "'Cemeteries'. This page lists all the cemeteries you service. Click any cemetery "
                    "to open its full profile."
                ),
            },
            {
                "step_number": 2,
                "title": "Add a new cemetery",
                "instruction": (
                    "Click '+ Add Cemetery' in the top right. Enter the name (required), county, "
                    "city, and state. The county is the most important field — it determines which "
                    "tax rate applies to orders at this cemetery. Click 'Add Cemetery' to save and "
                    "open the profile page."
                ),
            },
            {
                "step_number": 3,
                "title": "Set equipment flags correctly",
                "instruction": (
                    "In the 'Delivery Settings' card, toggle on any equipment the cemetery provides "
                    "themselves. If Oak Hill Cemetery brings their own lowering device and grass mats, "
                    "toggle both on. The live preview below the toggles shows what you'll be prompted "
                    "to bring on orders — this is what appears on the order form."
                ),
            },
            {
                "step_number": 4,
                "title": "Understand the equipment preview",
                "instruction": (
                    "The preview reads: 'When selected on an order we suggest: [label]'. "
                    "'Full Equipment' means you provide everything. 'No equipment needed' means the "
                    "cemetery handles it all. 'Lowering Device & Grass' means you bring those two "
                    "items. This suggestion appears on the order form automatically when this cemetery "
                    "is selected."
                ),
            },
            {
                "step_number": 5,
                "title": "Confirm the county for tax",
                "instruction": (
                    "Set the County field to the county where this cemetery is located. Check the "
                    "'Confirmed for tax calculation' box once you've verified the county is correct. "
                    "Unconfirmed counties will prompt a reminder when the cemetery is selected on an "
                    "order. Getting this right means every invoice calculates tax at the correct "
                    "county rate."
                ),
            },
            {
                "step_number": 6,
                "title": "Link to a billing customer (if applicable)",
                "instruction": (
                    "Some cemeteries are also your customers — they pay for vault placements directly. "
                    "If this cemetery has an account with you, scroll to the 'Billing' card and either "
                    "link their existing customer record or create a new one. This connects their "
                    "billing account to their delivery settings in one place."
                ),
            },
            {
                "step_number": 7,
                "title": "Update settings when policy changes",
                "instruction": (
                    "Cemeteries sometimes change their equipment policies — they might purchase a "
                    "lowering device one year, or stop providing grass mats. When this happens, "
                    "return to Settings → Cemeteries, open the cemetery's profile, and update the "
                    "equipment toggles. Every future order to that cemetery will reflect the change "
                    "automatically."
                ),
            },
            {
                "step_number": 8,
                "title": "Check order history if settings seem wrong",
                "instruction": (
                    "If a funeral home calls about wrong equipment charges on an old order, open the "
                    "cemetery's profile and check the 'Order History' card. You can see recent orders "
                    "and verify when the settings last changed. If charges were wrong, the billing "
                    "adjustment can be made on the customer's account."
                ),
            },
        ],
        "related_procedure_keys": ["taking_a_funeral_order"],
        "related_feature_urls": ["/settings/cemeteries"],
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
