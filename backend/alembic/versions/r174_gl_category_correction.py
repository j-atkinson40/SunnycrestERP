"""LEDGER-1 A-1 — correct 96 GL categorisations, then constrain the vocabulary.

⚠️ A DATA CORRECTION, NOT A RE-IMPORT. The corrections below are written out
explicitly rather than parsed from the source CSV at runtime, and that is
deliberate twice over. A migration that reads a file carries a dependency nobody
can see six months later; a migration whose input is a deliberately untracked
customer export cannot be rerun at all. Written out, a reviewer reads the actual
corrections instead of trusting a parse, and the migration is self-contained.

⚠️ EVERY ONE OF THE 96 IS TRACEABLE TO A CLASSIFIER DEFECT fixed in the commit
before this one. Nothing here is a judgement call about Sunnycrest's accounting
except the four operator rulings named at the bottom.

    other              -> cogs                 47   fuzzy matched no key at all
    other              -> delivery_cost        26   same
    current_liability  -> long_term_liability   8   "NON-" prefix invisible to a substring test
    cogs               -> revenue               8   "SALES" is a substring of "COST OF SALES"
    cogs               -> contra_revenue        5   same defect, different ruling
    other_income       -> other_expense         2   one Sage category holding both directions

The 8 liabilities are what you would fear: an officer note payable, a capital
lease, an operating lease liability, three vehicle notes, and BOTH deferred tax
liabilities — all reported as current. Current liabilities overstated, long-term
understated, working capital and the current ratio wrong in the direction a
lender reads.

The 73-row `other` bucket empties completely (47 + 26). After this migration no
Sunnycrest account is `other` or `unclassified`.

⚠️ SCOPED BY (account_number, current_category), NOT BY TENANT. Each UPDATE
matches only a row that currently holds the WRONG value at that account number,
so it is naturally idempotent — rerunning changes nothing — and cannot touch a
tenant whose chart is already correct. At the time of writing, production holds
224 mappings (all Sunnycrest), staging holds 0, and dev holds 2 (testco, account
numbers 1025 and 8801, neither in this set).

⚠️ THE DOWNGRADE RESTORES VALUES THAT WERE WRONG, AND THAT IS CORRECT. A reader
who runs it and sees revenue accounts return to `cogs` has not found a broken
reverse — a downgrade restores the prior state, and the prior state was
misclassified. Same discipline as r162's byte-exact restoration: reversibility
means returning to what was there, not to what should have been there.

## The constraint, in the same migration on purpose

`platform_category` has been `String(100)` with no enum, no FK and no CHECK
since it was created. That is why four vocabularies coexisted without a single
collision ever being detected, and why 211 of 224 production rows carried a
value no code defined. The constraint lands here rather than in a follow-up
because this is the only moment the vocabulary and the data are guaranteed to
agree — update first, constrain second, one transaction, no window.

`other_expense` is in the constrained set. It was added AFTER the vocabulary was
committed as complete: Sage's "OTHER INCOME & EXPENSES" holds both directions,
and two expense rows below the fold in an eighteen-account category is exactly
how a set gets declared complete before it is.

`other` and `unclassified` are both permitted and mean different things. `other`
means a human judged the account miscellaneous; `unclassified` means the
importer could not map it and somebody still has to look.

## Four operator rulings encoded here

  5150 / 5160 / 5165 / 5170 / 5410 -> contra_revenue, not revenue. Netting
  refunds, rebates and cash discounts into revenue makes the top line wrong in a
  way that still reconciles, which is the hardest kind to notice.

  5210 FREIGHT -> revenue. Sunnycrest's accountant already answered this in the
  chart: freight billed out sits in SALES, and 7500 FREIGHT IN sits separately
  in COST OF GOODS SOLD. The ambiguity was ours, not the data's.

  DELIVERY COSTS -> delivery_cost, its own category rather than folded into
  cogs. Licensees differ in whether hauling is outsourced or run in-house, and
  gross margin has to mean "what manufacturing earns" across all of them.

  9130 INTEREST EXPENSE / 9250 PENALTIES -> other_expense, below the operating
  line next to interest income where a reader compares the two.

STILL OPEN, deliberately untouched: 9400 SUSPENSE - MISC. remains `other_income`
pending a ruling on whether it is a live clearing account or dormant.
"""
from alembic import op
import sqlalchemy as sa

revision = "r174_gl_category_correction"
down_revision = "r173_gl_mapping_provenance"
branch_labels = None
depends_on = None

#: The constrained vocabulary. Mirrors
#: `data_migration_service.PLATFORM_ACCOUNT_CATEGORIES` — if you add a value
#: there, it needs a migration here or the write will be refused.
ALLOWED_CATEGORIES = (
    "current_asset",
    "fixed_asset",
    "current_liability",
    "long_term_liability",
    "equity",
    "revenue",
    "contra_revenue",
    "cogs",
    "delivery_cost",
    "expense",
    "tax_expense",
    "other_income",
    "other_expense",
    "other",
    "unclassified",
)

_CONSTRAINT = "ck_tenant_gl_mappings_platform_category"

#: (account_number, from_category, to_category, account_name, sage_category)
CORRECTIONS = (
    # account, from, to, name, sage_category
    ("4025", "current_liability", "long_term_liability", "NOTE PAYABLE - OFFICER", "NON-CURRENT LIABILITIES"),
    ("4035", "current_liability", "long_term_liability", "CAPITAL LEASE - L/T", "NON-CURRENT LIABILITIES"),
    ("4036", "current_liability", "long_term_liability", "OPERATING LEASE LIABILITY", "NON-CURRENT LIABILITIES"),
    ("4045", "current_liability", "long_term_liability", "NOTE PAYABLE - GM Fin. 2022 Chev Silv", "NON-CURRENT LIABILITIES"),
    ("4046", "current_liability", "long_term_liability", "LOAN PAYABLE-2025 SIERRA", "NON-CURRENT LIABILITIES"),
    ("4047", "current_liability", "long_term_liability", "NOTE PAYABLE-2016 FREIGHTLINER 7848", "NON-CURRENT LIABILITIES"),
    ("4200", "current_liability", "long_term_liability", "DEFERRED TAX LIABILITY - FED", "NON-CURRENT LIABILITIES"),
    ("4201", "current_liability", "long_term_liability", "DEFERRED TAX LIABILITY - NYS", "NON-CURRENT LIABILITIES"),
    ("5000", "cogs", "revenue", "REVENUE", "SALES"),
    ("5010", "cogs", "revenue", "PRECAST SALES", "SALES"),
    ("5012", "cogs", "revenue", "REDI-ROCK SALES", "SALES"),
    ("5014", "cogs", "revenue", "ROSETTA SALES", "SALES"),
    ("5020", "cogs", "revenue", "PRECAST-RESALE", "SALES"),
    ("5110", "cogs", "revenue", "FUNERAL SALES", "SALES"),
    ("5120", "cogs", "revenue", "FUNERAL-RESALE", "SALES"),
    ("5150", "cogs", "contra_revenue", "REFUNDS/RETURNS PRECAST", "SALES"),
    ("5160", "cogs", "contra_revenue", "REFUNDS/RETURNS FUNERAL", "SALES"),
    ("5165", "cogs", "contra_revenue", "FUNERAL REBATES", "SALES"),
    ("5170", "cogs", "contra_revenue", "DAMAGE OR DEFECTIVE RESALE", "SALES"),
    ("5210", "cogs", "revenue", "FREIGHT", "SALES"),
    ("5410", "cogs", "contra_revenue", "DISCOUNTS ALLOWED-CASH", "SALES"),
    ("6000", "other", "cogs", "COST OF SALES CLEARING", "COST OF GOODS SOLD"),
    ("6010", "other", "cogs", "CONCRETE", "COST OF GOODS SOLD"),
    ("6050", "other", "cogs", "CEMENT", "COST OF GOODS SOLD"),
    ("6100", "other", "cogs", "AGGREGATE HAULING", "COST OF GOODS SOLD"),
    ("6110", "other", "cogs", "AGGREGATE-MATERIAL", "COST OF GOODS SOLD"),
    ("6150", "other", "cogs", "COLOR ADDITIVES", "COST OF GOODS SOLD"),
    ("6180", "other", "cogs", "ADMIXTURES", "COST OF GOODS SOLD"),
    ("6210", "other", "cogs", "REINFORCING & LIFTING", "COST OF GOODS SOLD"),
    ("6260", "other", "cogs", "PURCHASE DISCOUNTS", "COST OF GOODS SOLD"),
    ("6300", "other", "cogs", "VAULT LINERS", "COST OF GOODS SOLD"),
    ("6330", "other", "cogs", "COATINGS & SEALER", "COST OF GOODS SOLD"),
    ("6350", "other", "cogs", "MISC. DIRECT MATERIALS", "COST OF GOODS SOLD"),
    ("6450", "other", "cogs", "DIRECT LABOR", "COST OF GOODS SOLD"),
    ("6510", "other", "cogs", "SUPERVISOR SALARIES", "COST OF GOODS SOLD"),
    ("6590", "other", "cogs", "INDIRECT PERSONNEL COSTS", "COST OF GOODS SOLD"),
    ("6600", "other", "cogs", "PAYROLL TAX EXPENSE-MFG", "COST OF GOODS SOLD"),
    ("6650", "other", "cogs", "HEALTH INSURANCE- MFG.", "COST OF GOODS SOLD"),
    ("6700", "other", "cogs", "COMP. & DBL INS. - MFG", "COST OF GOODS SOLD"),
    ("6740", "other", "cogs", "PACKAGING COSTS", "COST OF GOODS SOLD"),
    ("6750", "other", "cogs", "CLOTHING & PPE - MFG.", "COST OF GOODS SOLD"),
    ("6800", "other", "cogs", "SMALL TOOLS & EQUIPMENT", "COST OF GOODS SOLD"),
    ("6820", "other", "cogs", "EQUIPMENT RENTAL - MFG.", "COST OF GOODS SOLD"),
    ("6840", "other", "cogs", "SUBCONTRACT", "COST OF GOODS SOLD"),
    ("6850", "other", "cogs", "SUPPLIES - MFG", "COST OF GOODS SOLD"),
    ("6900", "other", "cogs", "UTILITIES EXPENSE", "COST OF GOODS SOLD"),
    ("6940", "other", "cogs", "RENT-SUNNYCREST BLDG", "COST OF GOODS SOLD"),
    ("6950", "other", "cogs", "EQUIPMENT MAINTENANCE - MFG.", "COST OF GOODS SOLD"),
    ("6960", "other", "cogs", "BUILDING REPAIRS", "COST OF GOODS SOLD"),
    ("6970", "other", "cogs", "REFUSE COLLECTION", "COST OF GOODS SOLD"),
    ("6980", "other", "cogs", "QUALITY CONTROL", "COST OF GOODS SOLD"),
    ("7000", "other", "cogs", "DEPRECIATION - MFG EQUIP", "COST OF GOODS SOLD"),
    ("7050", "other", "cogs", "INSURANCE-BUILDING/MFG.", "COST OF GOODS SOLD"),
    ("7100", "other", "cogs", "TAXES & INTEREST - MFG", "COST OF GOODS SOLD"),
    ("7110", "other", "cogs", "COGS MANUFACTURED CLEARING", "COST OF GOODS SOLD"),
    ("7150", "other", "cogs", "DAMAGED PRODUCT", "COST OF GOODS SOLD"),
    ("7240", "other", "cogs", "MATERIAL FOR RESALE", "COST OF GOODS SOLD"),
    ("7250", "other", "cogs", "VAULTS FOR RESALE", "COST OF GOODS SOLD"),
    ("7260", "other", "cogs", "VAULT TRANSFERS - OUT", "COST OF GOODS SOLD"),
    ("7270", "other", "cogs", "STEEL VAULTS", "COST OF GOODS SOLD"),
    ("7300", "other", "cogs", "PIPE FOR RESALE", "COST OF GOODS SOLD"),
    ("7320", "other", "cogs", "PRECAST ACCESS. FOR RESALE", "COST OF GOODS SOLD"),
    ("7350", "other", "cogs", "PRECAST FOR RESALE", "COST OF GOODS SOLD"),
    ("7370", "other", "cogs", "CREMATION PRODUCTS FOR RESALE", "COST OF GOODS SOLD"),
    ("7380", "other", "cogs", "MEMORIAL PRODUCTS FOR RESALE", "COST OF GOODS SOLD"),
    ("7400", "other", "cogs", "INVENTORY CHANGE", "COST OF GOODS SOLD"),
    ("7500", "other", "cogs", "FREIGHT IN", "COST OF GOODS SOLD"),
    ("7503", "other", "cogs", "CREDIT CARD FEES PROCESSED", "COST OF GOODS SOLD"),
    ("7530", "other", "delivery_cost", "DELIVERY COSTS", "DELIVERY COSTS"),
    ("7540", "other", "delivery_cost", "PERSONELL COSTS", "DELIVERY COSTS"),
    ("7550", "other", "delivery_cost", "DELIVERY LABOR", "DELIVERY COSTS"),
    ("7600", "other", "delivery_cost", "CEMETERY LABOR", "DELIVERY COSTS"),
    ("7650", "other", "delivery_cost", "PAYROLL TAX -DELIVERY", "DELIVERY COSTS"),
    ("7660", "other", "delivery_cost", "HEALTH INSURANCE - DELIVERY", "DELIVERY COSTS"),
    ("7700", "other", "delivery_cost", "COMP. & DBL INS. - DELIVERY", "DELIVERY COSTS"),
    ("7750", "other", "delivery_cost", "CLOTHING & PPE - DELIVERY", "DELIVERY COSTS"),
    ("7800", "other", "delivery_cost", "OTHER DELIVERY COSTS", "DELIVERY COSTS"),
    ("7850", "other", "delivery_cost", "GASOLINE & OIL", "DELIVERY COSTS"),
    ("7870", "other", "delivery_cost", "SUPPLIES - DELIVERY", "DELIVERY COSTS"),
    ("7920", "other", "delivery_cost", "LEASE MILEAGE", "DELIVERY COSTS"),
    ("7940", "other", "delivery_cost", "VEHICLE MAINTENANCE- PRECAST", "DELIVERY COSTS"),
    ("7950", "other", "delivery_cost", "VEHICLE MAINTENANCE-VAULT", "DELIVERY COSTS"),
    ("7960", "other", "delivery_cost", "LIABILITY INSURANCE", "DELIVERY COSTS"),
    ("8000", "other", "delivery_cost", "SMALL GRAVESIDE EQUIPMENT", "DELIVERY COSTS"),
    ("8010", "other", "delivery_cost", "PRODUCT HANDLING EQUIP. MAIN.", "DELIVERY COSTS"),
    ("8020", "other", "delivery_cost", "GRAVESIDE EQUIPMENT MAIN.", "DELIVERY COSTS"),
    ("8030", "other", "delivery_cost", "JOBSITE DAMAGE REPAIRS", "DELIVERY COSTS"),
    ("8050", "other", "delivery_cost", "INSURANCE - VEHICLE", "DELIVERY COSTS"),
    ("8100", "other", "delivery_cost", "DEPRECIATION - DELIVERY", "DELIVERY COSTS"),
    ("8150", "other", "delivery_cost", "TAXES & INTEREST - DELIVERY", "DELIVERY COSTS"),
    ("8180", "other", "delivery_cost", "HIRED TRUCKING", "DELIVERY COSTS"),
    ("8200", "other", "delivery_cost", "VEHICLE/TRAILER RENTAL", "DELIVERY COSTS"),
    ("8250", "other", "delivery_cost", "VEHICLE LEASE", "DELIVERY COSTS"),
    ("8255", "other", "delivery_cost", "EQUIPMENT LEASE", "DELIVERY COSTS"),
    ("9130", "other_income", "other_expense", "INTEREST EXPENSE", "OTHER INCOME & EXPENSES"),
    ("9250", "other_income", "other_expense", "PENALTIES", "OTHER INCOME & EXPENSES"),
)
# total: 96


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Correct the data FIRST. Scoped by (account_number, current value) so a
    #    row already holding the right answer is left alone — idempotent.
    for account_number, from_cat, to_cat, _name, _sage in CORRECTIONS:
        conn.execute(
            sa.text(
                "UPDATE tenant_gl_mappings SET platform_category = :to_cat "
                "WHERE account_number = :acct AND platform_category = :from_cat"
            ),
            {"to_cat": to_cat, "acct": account_number, "from_cat": from_cat},
        )

    # 2. THEN constrain. Same transaction, so there is no window in which the
    #    data is corrected but unprotected.
    op.create_check_constraint(
        _CONSTRAINT,
        "tenant_gl_mappings",
        sa.column("platform_category").in_(ALLOWED_CATEGORIES),
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Drop the constraint first — the restored values include `other`, which is
    # permitted, but the ordering matters if the allowed set is ever narrowed.
    op.drop_constraint(_CONSTRAINT, "tenant_gl_mappings", type_="check")

    # Restore the prior categorisation. These values are WRONG; restoring them
    # is what a downgrade means. See the module docstring.
    for account_number, from_cat, to_cat, _name, _sage in CORRECTIONS:
        conn.execute(
            sa.text(
                "UPDATE tenant_gl_mappings SET platform_category = :from_cat "
                "WHERE account_number = :acct AND platform_category = :to_cat"
            ),
            {"from_cat": from_cat, "acct": account_number, "to_cat": to_cat},
        )
