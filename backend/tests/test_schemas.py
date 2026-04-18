"""Tests for backend.schemas — contract invariants consumed by Plan A + Plan B."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from backend.schemas import (
    ApprovalRecord,
    ApprovalRequest,
    DisruptionDraft,
    DisruptionRecord,
    DraftCommunication,
    DraftCommunicationBundle,
    DraftCommunicationRecord,
    ImpactReport,
    ImpactReportRecord,
    MitigationOption,
    MitigationOptionRecord,
    MitigationOptionsBundle,
    ReasoningTrace,
    SignalClassification,
    SignalRecord,
    ToolInvocation,
)

# ---------------------------------------------------------------------------
# Helpers / minimal valid kwargs
# ---------------------------------------------------------------------------

_SIGNAL_CLS_KWARGS: dict[str, Any] = {
    "source_category": "news",
    "title": "Port closure",
    "summary": "The port of Shanghai closed due to typhoon.",
    "severity": 3,
    "confidence": 0.8,
    "dedupe_keywords": ["shanghai", "typhoon"],
}

_DISRUPTION_DRAFT_KWARGS: dict[str, Any] = {
    "title": "Typhoon disruption",
    "category": "weather",
    "severity": 4,
    "confidence": 0.9,
    "source_signal_ids": [],
}

_MITIGATION_OPTION_KWARGS: dict[str, Any] = {
    "option_type": "reroute",
    "description": "Reroute via Busan port instead of Shanghai.",
    "delta_cost": Decimal("5000"),
    "delta_days": 3,
    "confidence": 0.75,
    "rationale": "Busan has available berths and the detour adds only 3 days transit time.",
}

_DRAFT_COMM_KWARGS: dict[str, Any] = {
    "recipient_type": "supplier",
    "recipient_contact": "supplier@example.com",
    "subject": "Supply chain alert",
    "body": "Please be advised that a disruption has been detected affecting your shipments.",
}

_MITIGATION_BUNDLE_OPTION_KWARGS: list[dict[str, Any]] = [
    {
        "option_type": "reroute",
        "description": "Reroute via Busan port.",
        "delta_cost": Decimal("5000"),
        "delta_days": 3,
        "confidence": 0.75,
        "rationale": "Busan has available berths and the detour adds only 3 days transit time.",
    },
    {
        "option_type": "expedite",
        "description": "Expedite via air freight from Tokyo.",
        "delta_cost": Decimal("15000"),
        "delta_days": -2,
        "confidence": 0.65,
        "rationale": "Air freight is available and eliminates the delay at minimal SLA risk.",
    },
]

_APPROVAL_RECORD_KWARGS: dict[str, Any] = {
    "id": uuid.uuid4(),
    "mitigation_id": uuid.uuid4(),
    "approved_by": "user@example.com",
    "approved_at": datetime(2026, 4, 18, 12, 0, 0),
    "state_snapshot": {
        "mitigation_id": str(uuid.uuid4()),
        "shipment_ids_flipped": ["SHP-001"],
        "total_exposure_avoided": Decimal("50000"),
        "drafts_saved": [],
    },
}


# ---------------------------------------------------------------------------
# 1. extra="forbid" rejects unknown keys — parametrized across LLM output models
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model_cls, valid_kwargs",
    [
        (SignalClassification, _SIGNAL_CLS_KWARGS),
        (DisruptionDraft, _DISRUPTION_DRAFT_KWARGS),
        (MitigationOption, _MITIGATION_OPTION_KWARGS),
        (MitigationOptionsBundle, {"options": _MITIGATION_BUNDLE_OPTION_KWARGS}),
        (DraftCommunication, _DRAFT_COMM_KWARGS),
        (
            DraftCommunicationBundle,
            {
                "supplier": _DRAFT_COMM_KWARGS,
                "customer": {**_DRAFT_COMM_KWARGS, "recipient_type": "customer"},
                "internal": {**_DRAFT_COMM_KWARGS, "recipient_type": "internal"},
            },
        ),
        (ApprovalRequest, {}),
    ],
)
def test_extra_forbid_rejects_unknown_key(
    model_cls: type[Any], valid_kwargs: dict[str, Any]
) -> None:
    """extra='forbid' must raise ValidationError when an unknown field is present."""
    # Confirm valid kwargs construct without error.
    model_cls(**valid_kwargs)
    # Unknown key must be rejected.
    with pytest.raises(ValidationError):
        model_cls(**valid_kwargs, _unknown_field_xyz="boom")


# ---------------------------------------------------------------------------
# 2. Validator edge cases
# ---------------------------------------------------------------------------


def test_signal_severity_rejects_zero() -> None:
    with pytest.raises(ValidationError):
        SignalClassification(**{**_SIGNAL_CLS_KWARGS, "severity": 0})


def test_signal_severity_rejects_six() -> None:
    with pytest.raises(ValidationError):
        SignalClassification(**{**_SIGNAL_CLS_KWARGS, "severity": 6})


def test_signal_confidence_rejects_negative() -> None:
    with pytest.raises(ValidationError):
        SignalClassification(**{**_SIGNAL_CLS_KWARGS, "confidence": -0.1})


def test_signal_confidence_rejects_over_one() -> None:
    with pytest.raises(ValidationError):
        SignalClassification(**{**_SIGNAL_CLS_KWARGS, "confidence": 1.1})


def test_mitigation_option_delta_cost_rejects_negative() -> None:
    with pytest.raises(ValidationError):
        MitigationOption(**{**_MITIGATION_OPTION_KWARGS, "delta_cost": Decimal("-1")})


def test_mitigation_bundle_rejects_single_option() -> None:
    with pytest.raises(ValidationError):
        MitigationOptionsBundle(options=[MitigationOption(**_MITIGATION_OPTION_KWARGS)])


def test_mitigation_bundle_rejects_five_options() -> None:
    opt = MitigationOption(**_MITIGATION_OPTION_KWARGS)
    with pytest.raises(ValidationError):
        MitigationOptionsBundle(options=[opt, opt, opt, opt, opt])


def test_draft_communication_bundle_rejects_missing_supplier() -> None:
    with pytest.raises(ValidationError):
        DraftCommunicationBundle.model_validate(
            {
                "customer": {**_DRAFT_COMM_KWARGS, "recipient_type": "customer"},
                "internal": {**_DRAFT_COMM_KWARGS, "recipient_type": "internal"},
            }
        )


def test_draft_communication_bundle_rejects_missing_customer() -> None:
    with pytest.raises(ValidationError):
        DraftCommunicationBundle.model_validate(
            {
                "supplier": _DRAFT_COMM_KWARGS,
                "internal": {**_DRAFT_COMM_KWARGS, "recipient_type": "internal"},
            }
        )


def test_draft_communication_bundle_rejects_missing_internal() -> None:
    with pytest.raises(ValidationError):
        DraftCommunicationBundle.model_validate(
            {
                "supplier": _DRAFT_COMM_KWARGS,
                "customer": {**_DRAFT_COMM_KWARGS, "recipient_type": "customer"},
            }
        )


def test_impact_report_rejects_empty_affected_shipments() -> None:
    trace = ReasoningTrace(
        tool_calls=[
            ToolInvocation(
                tool_name="run_sql",
                args={"query": "SELECT 1"},
                row_count=1,
                synthesized_sql="SELECT 1",
            )
        ],
        final_reasoning="Analysis complete.",
    )
    with pytest.raises(ValidationError):
        ImpactReport(
            disruption_id=uuid.uuid4(),
            total_exposure=Decimal("100000"),
            units_at_risk=50,
            cascade_depth=2,
            sql_executed="SELECT 1",
            reasoning_trace=trace,
            affected_shipments=[],
        )


# ---------------------------------------------------------------------------
# 3. from_attributes=True round-trip smoke tests
# ---------------------------------------------------------------------------


def test_signal_record_from_attributes() -> None:
    ns = SimpleNamespace(
        id=uuid.uuid4(),
        source_category="news",
        source_name="Reuters",
        title="Port closure alert",
        summary="Shanghai port closed.",
        region="APAC",
        lat=31.2304,
        lng=121.4737,
        radius_km=Decimal("50"),
        source_urls=["https://reuters.com/article"],
        confidence=Decimal("0.9"),
        first_seen_at=datetime(2026, 4, 18, 10, 0, 0),
        promoted_to_disruption_id=None,
    )
    record = SignalRecord.model_validate(ns)
    assert record.source_category == "news"
    assert record.confidence == Decimal("0.9")


def test_disruption_record_from_attributes() -> None:
    ns = SimpleNamespace(
        id=uuid.uuid4(),
        title="Typhoon Wilma",
        summary=None,
        category="weather",
        severity=4,
        region="APAC",
        lat=31.0,
        lng=121.0,
        radius_km=Decimal("200"),
        source_signal_ids=[uuid.uuid4()],
        confidence=Decimal("0.85"),
        first_seen_at=datetime(2026, 4, 18, 8, 0, 0),
        last_seen_at=datetime(2026, 4, 18, 12, 0, 0),
        status="active",
    )
    record = DisruptionRecord.model_validate(ns)
    assert record.status == "active"
    assert record.confidence == Decimal("0.85")


def test_impact_report_record_from_attributes() -> None:
    trace_dict: dict[str, object] = {
        "tool_calls": [
            {
                "tool_name": "run_sql",
                "args": {"query": "SELECT 1"},
                "row_count": 1,
                "synthesized_sql": "SELECT 1",
            }
        ],
        "final_reasoning": "Done.",
    }
    ns = SimpleNamespace(
        id=uuid.uuid4(),
        disruption_id=uuid.uuid4(),
        total_exposure=Decimal("75000"),
        units_at_risk=30,
        cascade_depth=2,
        sql_executed="SELECT 1",
        reasoning_trace=trace_dict,
        generated_at=datetime(2026, 4, 18, 11, 0, 0),
    )
    _EXPECTED_UNITS_AT_RISK = 30
    record = ImpactReportRecord.model_validate(ns)
    assert record.units_at_risk == _EXPECTED_UNITS_AT_RISK
    assert record.reasoning_trace.final_reasoning == "Done."


def test_mitigation_option_record_from_attributes() -> None:
    ns = SimpleNamespace(
        id=uuid.uuid4(),
        impact_report_id=uuid.uuid4(),
        option_type="reroute",
        description="Reroute via Busan port instead of Shanghai.",
        delta_cost=Decimal("5000"),
        delta_days=3,
        confidence=Decimal("0.75"),
        rationale="Busan has available berths and the detour adds only 3 days transit time.",
        status="pending",
    )
    record = MitigationOptionRecord.model_validate(ns)
    assert record.status == "pending"
    assert record.option_type == "reroute"


def test_draft_communication_record_from_attributes() -> None:
    ns = SimpleNamespace(
        id=uuid.uuid4(),
        mitigation_id=uuid.uuid4(),
        recipient_type="supplier",
        recipient_contact="supplier@example.com",
        subject="Supply chain alert",
        body="Please be advised that a disruption has been detected affecting your shipments.",
        created_at=datetime(2026, 4, 18, 10, 0, 0),
        sent_at=None,
    )
    record = DraftCommunicationRecord.model_validate(ns)
    assert record.sent_at is None


def test_approval_record_from_attributes() -> None:
    snapshot_dict: dict[str, object] = {
        "mitigation_id": str(uuid.uuid4()),
        "shipment_ids_flipped": ["SHP-001", "SHP-002"],
        "total_exposure_avoided": Decimal("50000"),
        "drafts_saved": [],
    }
    ns = SimpleNamespace(
        id=uuid.uuid4(),
        mitigation_id=uuid.uuid4(),
        approved_by="user@example.com",
        approved_at=datetime(2026, 4, 18, 12, 0, 0),
        state_snapshot=snapshot_dict,
    )
    record = ApprovalRecord.model_validate(ns)
    assert record.approved_by == "user@example.com"
    assert record.state_snapshot.shipment_ids_flipped == ["SHP-001", "SHP-002"]


# ---------------------------------------------------------------------------
# 4. sent_at never-sent invariant
# ---------------------------------------------------------------------------


def test_draft_communication_record_rejects_non_null_sent_at() -> None:
    with pytest.raises(ValidationError, match="sent_at must be NULL"):
        DraftCommunicationRecord(
            id=uuid.uuid4(),
            mitigation_id=uuid.uuid4(),
            recipient_type="supplier",
            recipient_contact="supplier@example.com",
            subject="Supply chain alert",
            body="Please be advised that a disruption has been detected affecting your shipments.",
            created_at=datetime(2026, 4, 18, 10, 0, 0),
            sent_at=datetime(2026, 4, 18, 11, 0, 0),
        )


def test_draft_communication_record_accepts_null_sent_at() -> None:
    record = DraftCommunicationRecord(
        id=uuid.uuid4(),
        mitigation_id=uuid.uuid4(),
        recipient_type="customer",
        recipient_contact="customer@example.com",
        subject="Order update",
        body="Please be advised that a disruption has been detected affecting your shipments.",
        created_at=datetime(2026, 4, 18, 10, 0, 0),
        sent_at=None,
    )
    assert record.sent_at is None
