"""R-1.6.10 — Update Hopkins/St. Mary demo seed emails from .test to .example.com.

Pydantic's EmailStr (via the email-validator library) rejects RFC 6761
reserved-for-testing TLDs like `.test`, breaking direct login flows
(POST /api/v1/auth/login → 422). `.example.com` is RFC 2606
reserved-for-documentation and accepted by email-validator.

The matching code change in seed_fh_demo.py + e2e _shared.ts ensures fresh
seeds use the new TLD; this migration retrofits any rows that were created
by pre-R-1.6.10 deploys (Hopkins FH on staging in particular).

Idempotent — REPLACE() with a precise LIKE filter is a no-op when no rows
match. Safe on production where no Hopkins/St. Mary's demo data exists.

Revision ID: r48_fh_demo_email_tld_fix
Revises: r87_dashboard_layouts
Create Date: 2026-05-07
"""
from alembic import op


revision = "r48_fh_demo_email_tld_fix"
down_revision = "r87_dashboard_layouts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Hopkins FH demo users: admin/director1/director2/office.
    op.execute(
        """
        UPDATE users
        SET email = REPLACE(email, '@hopkinsfh.test', '@hopkinsfh.example.com')
        WHERE email LIKE '%@hopkinsfh.test'
        """
    )
    # St. Mary's Cemetery demo users.
    op.execute(
        """
        UPDATE users
        SET email = REPLACE(email, '@stmarys.test', '@stmarys.example.com')
        WHERE email LIKE '%@stmarys.test'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE users
        SET email = REPLACE(email, '@hopkinsfh.example.com', '@hopkinsfh.test')
        WHERE email LIKE '%@hopkinsfh.example.com'
        """
    )
    op.execute(
        """
        UPDATE users
        SET email = REPLACE(email, '@stmarys.example.com', '@stmarys.test')
        WHERE email LIKE '%@stmarys.example.com'
        """
    )
