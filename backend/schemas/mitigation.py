from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MitigationOptionType = Literal[
    "reroute", "alternate_supplier", "expedite", "accept_delay", "switch_compliant_supplier"
]
MitigationStatus = Literal["pending", "approved", "dismissed"]
RecipientType = Literal["supplier", "customer", "internal"]


class MitigationOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_type: MitigationOptionType
    description: str = Field(min_length=10, max_length=500)
    delta_cost: Decimal = Field(ge=0)
    delta_days: int
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=20, max_length=2000)


class MitigationOptionsBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    options: list[MitigationOption] = Field(min_length=2, max_length=4)


class MitigationOptionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    impact_report_id: uuid.UUID
    option_type: MitigationOptionType
    description: str
    delta_cost: Decimal
    delta_days: int
    confidence: float
    rationale: str
    status: MitigationStatus


class DraftCommunication(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_type: RecipientType
    recipient_contact: str
    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=20, max_length=5000)


class DraftCommunicationBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier: DraftCommunication
    customer: DraftCommunication
    internal: DraftCommunication


class DraftCommunicationRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    mitigation_id: uuid.UUID
    recipient_type: RecipientType
    recipient_contact: str
    subject: str
    body: str
    created_at: datetime
    sent_at: datetime | None

    @field_validator("sent_at")
    @classmethod
    def _never_sent(cls, v: datetime | None) -> datetime | None:
        if v is not None:
            raise ValueError("sent_at must be NULL — drafts are never sent")
        return v
