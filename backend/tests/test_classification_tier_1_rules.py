"""Phase R-6.1a — Tier 1 rule evaluation."""

from __future__ import annotations

from tests._classification_fixtures import (  # noqa: F401
    db,
    make_email_account,
    make_inbound_email,
    make_rule,
    make_workflow,
    tenant_pair,
)
from app.services.classification import tier_1_rules


def test_match_empty_dict_matches_anything(db, tenant_pair):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    msg = make_inbound_email(db, tenant=a, account=acct)
    assert tier_1_rules.match({}, msg) is True


def test_sender_email_in_match(db, tenant_pair):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    msg = make_inbound_email(
        db, tenant=a, account=acct, sender_email="fh@hopkins.example.com"
    )
    assert tier_1_rules.match(
        {"sender_email_in": ["fh@hopkins.example.com"]}, msg
    )
    assert not tier_1_rules.match(
        {"sender_email_in": ["other@elsewhere.test"]}, msg
    )


def test_sender_domain_in_match(db, tenant_pair):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    msg = make_inbound_email(
        db, tenant=a, account=acct, sender_email="fh@hopkins.example.com"
    )
    assert tier_1_rules.match(
        {"sender_domain_in": ["hopkins.example.com"]}, msg
    )
    # Tolerates leading @
    assert tier_1_rules.match(
        {"sender_domain_in": ["@hopkins.example.com"]}, msg
    )
    assert not tier_1_rules.match(
        {"sender_domain_in": ["other.test"]}, msg
    )


def test_subject_contains_any_case_insensitive(db, tenant_pair):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    msg = make_inbound_email(
        db,
        tenant=a,
        account=acct,
        subject="Disinterment for Smith family",
    )
    assert tier_1_rules.match(
        {"subject_contains_any": ["disinterment"]}, msg
    )
    assert tier_1_rules.match(
        {"subject_contains_any": ["DISINTERMENT", "removal"]}, msg
    )
    assert not tier_1_rules.match(
        {"subject_contains_any": ["invoice", "pricing"]}, msg
    )


def test_body_contains_any(db, tenant_pair):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    msg = make_inbound_email(
        db,
        tenant=a,
        account=acct,
        body_text="Please process the disinterment release form.",
    )
    assert tier_1_rules.match(
        {"body_contains_any": ["RELEASE FORM"]}, msg
    )
    assert not tier_1_rules.match(
        {"body_contains_any": ["unrelated"]}, msg
    )


def test_thread_label_in_against_message_payload(db, tenant_pair):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    msg = make_inbound_email(
        db,
        tenant=a,
        account=acct,
        message_payload={"labels": ["IMPORTANT", "INBOX"]},
    )
    assert tier_1_rules.match(
        {"thread_label_in": ["IMPORTANT"]}, msg
    )
    msg2 = make_inbound_email(
        db, tenant=a, account=acct, message_payload={"categories": ["billing"]}
    )
    assert tier_1_rules.match(
        {"thread_label_in": ["billing"]}, msg2
    )
    assert not tier_1_rules.match(
        {"thread_label_in": ["other"]}, msg
    )


def test_match_AND_across_operators(db, tenant_pair):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    msg = make_inbound_email(
        db,
        tenant=a,
        account=acct,
        sender_email="fh@hopkins.example.com",
        subject="Disinterment",
    )
    # Sender matches, subject matches → True.
    assert tier_1_rules.match(
        {
            "sender_domain_in": ["hopkins.example.com"],
            "subject_contains_any": ["disinterment"],
        },
        msg,
    )
    # Sender matches, subject does NOT → False.
    assert not tier_1_rules.match(
        {
            "sender_domain_in": ["hopkins.example.com"],
            "subject_contains_any": ["pricing"],
        },
        msg,
    )


def test_evaluate_first_priority_wins(db, tenant_pair):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    wf = make_workflow(db, a)

    rule_high = make_rule(
        db,
        a,
        priority=10,
        name="Catch-all",
        match_conditions={},
        fire_workflow_id=wf.id,
    )
    rule_low = make_rule(
        db,
        a,
        priority=0,
        name="Disinterment",
        match_conditions={"subject_contains_any": ["disinterment"]},
        fire_workflow_id=wf.id,
    )

    msg = make_inbound_email(
        db, tenant=a, account=acct, subject="Disinterment for Smith"
    )
    matched = tier_1_rules.evaluate(db, msg)
    assert matched is not None
    assert matched.id == rule_low.id  # priority 0 wins over 10


def test_evaluate_skips_inactive(db, tenant_pair):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    wf = make_workflow(db, a)

    rule = make_rule(
        db,
        a,
        priority=0,
        name="Inactive rule",
        match_conditions={},
        fire_workflow_id=wf.id,
        is_active=False,
    )
    msg = make_inbound_email(db, tenant=a, account=acct)
    assert tier_1_rules.evaluate(db, msg) is None
    assert rule.id  # silence unused


def test_evaluate_tenant_scoped(db, tenant_pair):
    a, b = tenant_pair
    acct_a = make_email_account(db, a)
    wf_a = make_workflow(db, a)
    make_rule(
        db,
        a,
        priority=0,
        name="A's rule",
        match_conditions={},
        fire_workflow_id=wf_a.id,
    )

    # B's message; A's rule should NOT match against it (tenant
    # scoping is at list_active_rules level).
    acct_b = make_email_account(db, b)
    msg_b = make_inbound_email(db, tenant=b, account=acct_b)
    assert tier_1_rules.evaluate(db, msg_b) is None
