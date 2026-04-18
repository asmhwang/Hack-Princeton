from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class StateSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mitigation_id: uuid.UUID
    shipment_ids_flipped: list[str]
    total_exposure_avoided: Decimal
    drafts_saved: list[uuid.UUID]


class ApprovalRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    mitigation_id: uuid.UUID
    approved_by: str
    approved_at: datetime
    state_snapshot: StateSnapshot


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval: ApprovalRecord
    shipments_flipped: int
    drafts_saved: int
