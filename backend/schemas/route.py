from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .disruption import DisruptionCategory

RouteMode = Literal["ocean", "air", "rail", "truck"]
RouteStatus = Literal["blocked", "watch", "good"]


class ActiveRoute(BaseModel):
    """One shipment lane tied to an active disruption.

    Frontend consumes this to render arcs on the globe. ``from_`` serializes
    to JSON ``from`` (keyword-reserved in Python); ``status`` is derived from
    the disruption severity server-side.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    disruption_id: uuid.UUID
    disruption_category: DisruptionCategory
    from_: tuple[float, float] = Field(alias="from")
    to: tuple[float, float]
    origin_name: str
    destination_name: str
    mode: RouteMode
    status: RouteStatus
    exposure: Decimal
    transit_days: int
    carrier: str
