"""Hand-tuned fixture data for deterministic demo seeding.

Kept separate from seeding logic so you can edit the narrative text (reasoning
traces, mitigation rationales, draft emails) without touching the Python that
inserts them.

Two fixture sets:

- ACTIVE_SCENARIO_FIXTURES: 5 entries keyed by scenario id, matching the 5
  canonical demo scenarios. Used by seed_scenario.py — maps to the same
  scenarios as backend/scripts/scenarios/ so FK refs land on prime_chain
  shipments (SHP-PRIME-<SCENARIO[:4].upper()>-N).

- HISTORICAL_FIXTURES: 6 entries spread across past 30 days (resolved),
  mixed categories so the analytics aggregation by quarter/customer/sku has
  something to show. Used by seed_history.py — each pins to its own distinct
  SHP-PRIME-HIST-<slug>-N shipments via a lightweight prime-chain call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

# ── scenario fixture shape ───────────────────────────────────────────


@dataclass(frozen=True)
class DraftFixture:
    recipient_type: str  # supplier | customer | internal
    recipient_contact: str
    subject: str
    body: str


@dataclass(frozen=True)
class MitigationFixture:
    option_type: str
    description: str
    delta_cost: Decimal
    delta_days: int
    confidence: float
    rationale: str
    drafts: tuple[DraftFixture, ...] = ()


@dataclass(frozen=True)
class AffectedShipmentFixture:
    shipment_id: str  # must reference a real shipment (SHP-PRIME-*)
    exposure: Decimal
    days_to_sla_breach: int | None


@dataclass(frozen=True)
class SignalFixture:
    source_category: str
    source_name: str
    title: str
    summary: str
    region: str
    lat: float
    lng: float
    radius_km: float
    source_urls: tuple[str, ...]
    confidence: float
    hours_before_disruption: float  # relative offset (e.g. 4.0 = signal fired 4h before)


@dataclass(frozen=True)
class ScenarioFixture:
    total_exposure: Decimal
    units_at_risk: int
    cascade_depth: int
    signals: tuple[SignalFixture, ...]
    affected: tuple[AffectedShipmentFixture, ...]
    mitigations: tuple[MitigationFixture, ...]
    reasoning_trace: dict[str, Any] = field(default_factory=dict)


# ── helper to build a plausible reasoning_trace JSON ─────────────────


def _trace(
    *,
    region: str,
    lat: float,
    lng: float,
    radius_km: float,
    shipment_ids: list[str],
    exposure_rows: int,
    row_count: int,
    final_reasoning: str,
) -> dict[str, Any]:
    shipment_ids_json = ", ".join(repr(x) for x in shipment_ids[:3])
    return {
        "tool_calls": [
            {
                "tool_name": "shipments_touching_region",
                "args": {"center_lat": lat, "center_lng": lng, "radius_km": radius_km},
                "row_count": row_count,
                "synthesized_sql": (
                    "SELECT s.id, s.po_id, s.supplier_id, s.origin_port_id, "
                    "s.dest_port_id, s.status, s.value\n"
                    "FROM shipments s\n"
                    "JOIN ports op ON op.id = s.origin_port_id\n"
                    "WHERE s.status IN ('planned','in_transit')\n"
                    "  AND ST_DWithin(\n"
                    "    ST_MakePoint(op.lng, op.lat)::geography,\n"
                    f"    ST_MakePoint({lng}, {lat})::geography,\n"
                    f"    {int(radius_km * 1000)}\n"
                    "  )\n"
                    "ORDER BY s.eta ASC"
                ),
            },
            {
                "tool_name": "purchase_orders_for_skus",
                "args": {"shipment_ids": [shipment_ids_json]},
                "row_count": row_count,
                "synthesized_sql": (
                    "SELECT po.id, po.customer_id, po.sku_id, po.qty, po.revenue\n"
                    "FROM purchase_orders po\n"
                    "JOIN shipments s ON s.po_id = po.id\n"
                    "WHERE s.id IN (@shipment_ids)"
                ),
            },
            {
                "tool_name": "customers_by_po",
                "args": {"po_count": row_count},
                "row_count": max(1, row_count // 3),
                "synthesized_sql": (
                    "SELECT c.id, c.name, c.tier, c.sla_days\n"
                    "FROM customers c\n"
                    "JOIN purchase_orders po ON po.customer_id = c.id\n"
                    "WHERE po.id IN (@po_ids)"
                ),
            },
            {
                "tool_name": "exposure_aggregate",
                "args": {"region": region},
                "row_count": 1,
                "synthesized_sql": (
                    "SELECT SUM(s.value * po.qty) AS total_exposure,\n"
                    "       COUNT(*) AS units_at_risk\n"
                    "FROM shipments s\n"
                    "JOIN purchase_orders po ON po.id = s.po_id\n"
                    "WHERE s.id IN (@shipment_ids)"
                ),
            },
            {
                "tool_name": "sla_breach_projection",
                "args": {"delay_days": 5},
                "row_count": exposure_rows,
                "synthesized_sql": (
                    "SELECT s.id,\n"
                    "       (s.eta + INTERVAL '5 days') AS projected_eta,\n"
                    "       (po.due_date - (s.eta + INTERVAL '5 days')) AS slack_days\n"
                    "FROM shipments s\n"
                    "JOIN purchase_orders po ON po.id = s.po_id\n"
                    "WHERE s.id IN (@shipment_ids)\n"
                    "  AND po.due_date < (s.eta + INTERVAL '5 days')"
                ),
            },
        ],
        "final_reasoning": final_reasoning,
    }


# ── ACTIVE scenario fixtures (5 canonical demo ids) ──────────────────


def _scenario_shipment_ids(scenario_id: str) -> list[str]:
    """Match prime_chain.py: SHP-PRIME-<ID[:4].upper()>-{1,2,3}."""
    prefix = scenario_id[:4].upper()
    return [f"SHP-PRIME-{prefix}-{i}" for i in range(1, 4)]


ACTIVE_SCENARIO_FIXTURES: dict[str, ScenarioFixture] = {
    "typhoon_kaia": ScenarioFixture(
        total_exposure=Decimal("2310000"),
        units_at_risk=14,
        cascade_depth=2,
        signals=(
            SignalFixture(
                source_category="weather",
                source_name="open-meteo",
                title="Typhoon Kaia — Category 3 landfall near Shenzhen",
                summary="Sustained winds 185 km/h; eye tracked over Yantian approach at 06:40 HKT.",
                region="South China Sea",
                lat=22.54,
                lng=114.06,
                radius_km=500.0,
                source_urls=("https://open-meteo.com/en/cyclone/kaia",),
                confidence=0.94,
                hours_before_disruption=4.0,
            ),
            SignalFixture(
                source_category="news",
                source_name="tavily:scmp",
                title="Yantian and Shekou terminals halt operations for 36–48 hours",
                summary=(
                    "SCMP reports terminal operators preparing vessel holds through the weekend."
                ),
                region="Shenzhen",
                lat=22.61,
                lng=114.27,
                radius_km=120.0,
                source_urls=("https://www.scmp.com/business/article/typhoon-kaia-yantian",),
                confidence=0.88,
                hours_before_disruption=3.2,
            ),
            SignalFixture(
                source_category="logistics",
                source_name="tavily:freightwaves",
                title="Pearl River Delta corridor shipping advisory — 48h window",
                summary="MARDEP issued Tropical Cyclone Warning Signal No. 8 at 05:40 HKT.",
                region="Hong Kong",
                lat=22.39,
                lng=114.16,
                radius_km=200.0,
                source_urls=("https://www.freightwaves.com/news/typhoon-kaia-prd-advisory",),
                confidence=0.91,
                hours_before_disruption=2.8,
            ),
        ),
        affected=(
            AffectedShipmentFixture("SHP-PRIME-TYPH-1", Decimal("840000"), 1),
            AffectedShipmentFixture("SHP-PRIME-TYPH-2", Decimal("620000"), 2),
            AffectedShipmentFixture("SHP-PRIME-TYPH-3", Decimal("850000"), 3),
        ),
        mitigations=(
            MitigationFixture(
                option_type="reroute",
                description="Reroute fourteen shipments through Ho Chi Minh + rail to Shenzhen-alt",
                delta_cost=Decimal("180000"),
                delta_days=5,
                confidence=0.87,
                rationale="HCMC terminal has capacity in 3 of next 5 sailings; saves ~5 SLA days.",
                drafts=(
                    DraftFixture(
                        recipient_type="supplier",
                        recipient_contact="ops@primesupplier-typh.example.com",
                        subject="Reroute notice — Typhoon Kaia / HCMC corridor",
                        body=(
                            "Hi team,\n\nPlease prepare to divert the three in-transit "
                            "containers (PO-PRIME-TYPH-1..3) through Ho Chi Minh on the "
                            "next available sailing. We'll cover the $180K premium; "
                            "acknowledging receipt by 16:00 HKT."
                        ),
                    ),
                    DraftFixture(
                        recipient_type="customer",
                        recipient_contact="typhoon_kaia@example.com",
                        subject="Delivery update — 5d delay on three POs",
                        body=(
                            "Quick heads-up: Typhoon Kaia has closed Yantian/Shekou for "
                            "36–48h. We've rerouted your shipments via Ho Chi Minh and "
                            "are now targeting a 5-day slip on the committed delivery. "
                            "SLA credit owed — we'll reconcile at month-end."
                        ),
                    ),
                    DraftFixture(
                        recipient_type="internal",
                        recipient_contact="maya@suppl.ai",
                        subject="Approval packet — Typhoon Kaia reroute",
                        body=(
                            "One-click approval would flip three shipments to rerouting "
                            "status and book HCMC capacity. Exposure: $2.31M; cost delta: "
                            "+$180K; confidence 87%."
                        ),
                    ),
                ),
            ),
            MitigationFixture(
                option_type="alternate_supplier",
                description="Swap to backup supplier SUP-VN-0034 in Ho Chi Minh",
                delta_cost=Decimal("42000"),
                delta_days=0,
                confidence=0.71,
                rationale="Backup supplier pre-qualified; zero additional transit time.",
            ),
            MitigationFixture(
                option_type="expedite",
                description="Air-freight nine SLA-critical shipments via HKG → LAX",
                delta_cost=Decimal("1100000"),
                delta_days=8,
                confidence=0.64,
                rationale="Clears SLA breach window for 9 of 14 shipments; premium fuel surcharge.",
            ),
        ),
    ),
    "busan_strike": ScenarioFixture(
        total_exposure=Decimal("1820000"),
        units_at_risk=11,
        cascade_depth=2,
        signals=(
            SignalFixture(
                source_category="news",
                source_name="tavily:koreaherald",
                title="KPTU authorizes 72h strike at Busan New Port terminals",
                summary="Union cites stalled wage talks; work stops 06:00 Monday.",
                region="Busan",
                lat=35.1,
                lng=129.03,
                radius_km=80.0,
                source_urls=("https://koreaherald.com/busan-kptu-strike",),
                confidence=0.92,
                hours_before_disruption=6.0,
            ),
            SignalFixture(
                source_category="logistics",
                source_name="tavily:freightwaves",
                title="PNIT + HMM PSA chassis queue up 2x normal",
                summary=(
                    "Dwell time climbing fast at Busan New Port; vessels diverting to Pyeongtaek."
                ),
                region="Busan",
                lat=35.08,
                lng=128.95,
                radius_km=60.0,
                source_urls=("https://freightwaves.com/busan-dwell-spike",),
                confidence=0.85,
                hours_before_disruption=4.5,
            ),
        ),
        affected=(
            AffectedShipmentFixture("SHP-PRIME-BUSA-1", Decimal("610000"), 2),
            AffectedShipmentFixture("SHP-PRIME-BUSA-2", Decimal("540000"), 4),
            AffectedShipmentFixture("SHP-PRIME-BUSA-3", Decimal("670000"), 3),
        ),
        mitigations=(
            MitigationFixture(
                option_type="reroute",
                description="Shift Busan volume to Pyeongtaek + inland rail to Seoul hub",
                delta_cost=Decimal("95000"),
                delta_days=2,
                confidence=0.83,
                rationale=(
                    "Pyeongtaek has 4 of next 7 vessel slots available; rail to Seoul runs daily."
                ),
            ),
            MitigationFixture(
                option_type="hold",
                description="Hold in-transit vessels at anchor until strike resolves",
                delta_cost=Decimal("28000"),
                delta_days=4,
                confidence=0.58,
                rationale="Anchorage dues cheap relative to reroute; bet on 72h resolution.",
            ),
        ),
    ),
    "cbam_tariff": ScenarioFixture(
        total_exposure=Decimal("1470000"),
        units_at_risk=9,
        cascade_depth=2,
        signals=(
            SignalFixture(
                source_category="policy",
                source_name="tavily:ec-europa-eu",
                title="EU Commission publishes CBAM Q2 tariff schedule",
                summary="Steel and aluminum brackets shift up 3.2pp effective 1 May.",
                region="European Union",
                lat=50.85,
                lng=4.35,
                radius_km=1200.0,
                source_urls=("https://ec.europa.eu/cbam/q2-tariff-update",),
                confidence=0.97,
                hours_before_disruption=8.0,
            ),
            SignalFixture(
                source_category="news",
                source_name="tavily:reuters",
                title="EU steel importers scramble before 1 May CBAM step",
                summary="Several mills pull forward shipments to beat higher bracket.",
                region="European Union",
                lat=51.5,
                lng=10.0,
                radius_km=1500.0,
                source_urls=("https://reuters.com/cbam-may-rush",),
                confidence=0.88,
                hours_before_disruption=5.5,
            ),
        ),
        affected=(
            AffectedShipmentFixture("SHP-PRIME-CBAM-1", Decimal("520000"), 10),
            AffectedShipmentFixture("SHP-PRIME-CBAM-2", Decimal("490000"), 12),
            AffectedShipmentFixture("SHP-PRIME-CBAM-3", Decimal("460000"), 14),
        ),
        mitigations=(
            MitigationFixture(
                option_type="switch_compliant_supplier",
                description="Switch to CBAM-compliant mills in Turkey + Serbia",
                delta_cost=Decimal("62000"),
                delta_days=3,
                confidence=0.79,
                rationale=(
                    "Pre-qualified mills sit below the new threshold; cost pass-through manageable."
                ),
            ),
            MitigationFixture(
                option_type="accept_delay",
                description="Expedite current shipments to land before 1 May",
                delta_cost=Decimal("110000"),
                delta_days=-2,
                confidence=0.74,
                rationale="Avoids higher bracket entirely if we clear customs by 30 Apr.",
            ),
        ),
    ),
    "luxshare_fire": ScenarioFixture(
        total_exposure=Decimal("3240000"),
        units_at_risk=18,
        cascade_depth=3,
        signals=(
            SignalFixture(
                source_category="industrial",
                source_name="tavily:nikkei",
                title="Luxshare Kunshan plant fire — assembly line damage",
                summary=(
                    "Overnight fire localized to final-assembly wing; production paused 7-10 days."
                ),
                region="Kunshan",
                lat=31.39,
                lng=120.93,
                radius_km=20.0,
                source_urls=("https://nikkei.com/luxshare-kunshan-fire",),
                confidence=0.95,
                hours_before_disruption=12.0,
            ),
            SignalFixture(
                source_category="news",
                source_name="tavily:bloomberg",
                title="Apple AirPods supply chain watches Luxshare recovery timeline",
                summary=(
                    "Industry sources estimate 2-week production gap; no confirmation from Apple."
                ),
                region="China",
                lat=31.23,
                lng=121.47,
                radius_km=150.0,
                source_urls=("https://bloomberg.com/luxshare-airpods-watch",),
                confidence=0.82,
                hours_before_disruption=8.0,
            ),
        ),
        affected=(
            AffectedShipmentFixture("SHP-PRIME-LUXS-1", Decimal("1180000"), 5),
            AffectedShipmentFixture("SHP-PRIME-LUXS-2", Decimal("1060000"), 7),
            AffectedShipmentFixture("SHP-PRIME-LUXS-3", Decimal("1000000"), 8),
        ),
        mitigations=(
            MitigationFixture(
                option_type="alternate_supplier",
                description="Dual-source to Foxconn Zhengzhou for Q2 volume",
                delta_cost=Decimal("440000"),
                delta_days=4,
                confidence=0.81,
                rationale=(
                    "Foxconn has idle capacity on the matching line; already qualified as alt."
                ),
            ),
            MitigationFixture(
                option_type="expedite",
                description="Air-freight finished goods from Vietnam alt",
                delta_cost=Decimal("780000"),
                delta_days=12,
                confidence=0.69,
                rationale="Fastest path to keep shelves stocked for Q2 launch window.",
            ),
        ),
    ),
    "redsea_advisory": ScenarioFixture(
        total_exposure=Decimal("4120000"),
        units_at_risk=23,
        cascade_depth=2,
        signals=(
            SignalFixture(
                source_category="policy",
                source_name="tavily:ukmto",
                title="UKMTO extends Bab-el-Mandeb advisory through Q2",
                summary="Insurance underwriters expected to raise war-risk premiums another 80bps.",
                region="Bab-el-Mandeb",
                lat=12.58,
                lng=43.33,
                radius_km=350.0,
                source_urls=("https://ukmto.org/bab-el-mandeb-q2-extension",),
                confidence=0.94,
                hours_before_disruption=10.0,
            ),
            SignalFixture(
                source_category="logistics",
                source_name="tavily:lloydslist",
                title="Maersk + CMA re-route southbound Asia-Europe via Cape",
                summary="Rate surcharges of $1,200/FEU announced through 30 June.",
                region="Red Sea",
                lat=20.0,
                lng=38.0,
                radius_km=800.0,
                source_urls=("https://lloydslist.com/red-sea-cape-reroute",),
                confidence=0.89,
                hours_before_disruption=6.5,
            ),
        ),
        affected=(
            AffectedShipmentFixture("SHP-PRIME-REDS-1", Decimal("1500000"), 10),
            AffectedShipmentFixture("SHP-PRIME-REDS-2", Decimal("1320000"), 12),
            AffectedShipmentFixture("SHP-PRIME-REDS-3", Decimal("1300000"), 14),
        ),
        mitigations=(
            MitigationFixture(
                option_type="reroute",
                description="Accept Cape of Good Hope routing + $1,200/FEU surcharge",
                delta_cost=Decimal("640000"),
                delta_days=12,
                confidence=0.92,
                rationale=(
                    "Already underway on Maersk + CMA lanes; known quantity, stable carriers."
                ),
            ),
            MitigationFixture(
                option_type="alternate_supplier",
                description="Short-haul to Turkey + rail from Hamburg for priority SKUs",
                delta_cost=Decimal("220000"),
                delta_days=7,
                confidence=0.72,
                rationale="Keeps SLA for Tier-1 customers while Cape routing absorbs bulk.",
            ),
        ),
    ),
}


# Populate reasoning_traces from the computed data so we don't duplicate effort.
# This runs once at import time; ScenarioFixture is frozen so we replace entries.
def _build_traces() -> dict[str, ScenarioFixture]:
    out: dict[str, ScenarioFixture] = {}
    for sid, sc in ACTIVE_SCENARIO_FIXTURES.items():
        primary = sc.signals[0]
        trace = _trace(
            region=primary.region,
            lat=primary.lat,
            lng=primary.lng,
            radius_km=primary.radius_km,
            shipment_ids=[a.shipment_id for a in sc.affected],
            exposure_rows=max(2, sc.units_at_risk // 2),
            row_count=sc.units_at_risk,
            final_reasoning=(
                f"{primary.title}. "
                f"{sc.units_at_risk} in-transit shipments sit within the advisory radius, "
                f"totaling ~${sc.total_exposure:,} in exposure. "
                f"Recommend escalating the {sc.mitigations[0].option_type.replace('_', ' ')} "
                f"option first — confidence {int(sc.mitigations[0].confidence * 100)}%."
            ),
        )
        out[sid] = ScenarioFixture(
            total_exposure=sc.total_exposure,
            units_at_risk=sc.units_at_risk,
            cascade_depth=sc.cascade_depth,
            signals=sc.signals,
            affected=sc.affected,
            mitigations=sc.mitigations,
            reasoning_trace=trace,
        )
    return out


ACTIVE_SCENARIO_FIXTURES = _build_traces()


# ── HISTORICAL fixtures (6 resolved disruptions) ─────────────────────


@dataclass(frozen=True)
class HistoricalFixture:
    slug: str  # short id used to build SHP-PRIME-HIST-<SLUG>-N
    days_ago: int
    category: str
    title: str
    summary: str
    region: str
    lat: float
    lng: float
    radius_km: float
    severity: int
    total_exposure: Decimal
    units_at_risk: int
    source_signals: tuple[SignalFixture, ...]
    mitigations: tuple[MitigationFixture, ...]
    affected_count: int  # how many affected_shipments rows to emit (≤ 3)
    destination_name: str
    destination_lat: float
    destination_lng: float


HISTORICAL_FIXTURES: tuple[HistoricalFixture, ...] = (
    HistoricalFixture(
        slug="huan",
        days_ago=28,
        category="weather",
        title="Typhoon Huan — Shanghai port closure",
        summary=(
            "Cat 2 typhoon closed Yangshan container port 24h; residual dwell cleared within 72h."
        ),
        region="Shanghai",
        lat=31.23,
        lng=121.47,
        radius_km=400.0,
        severity=4,
        total_exposure=Decimal("1180000"),
        units_at_risk=8,
        source_signals=(
            SignalFixture(
                source_category="weather",
                source_name="open-meteo",
                title="Typhoon Huan approaches East China coast",
                summary="Cat 2 system tracking west, landfall expected at Yangshan within 36h.",
                region="Shanghai",
                lat=31.23,
                lng=121.47,
                radius_km=400.0,
                source_urls=("https://open-meteo.com/en/cyclone/huan",),
                confidence=0.9,
                hours_before_disruption=6.0,
            ),
        ),
        mitigations=(
            MitigationFixture(
                option_type="reroute",
                description="Temporarily divert Shanghai-bound vessels to Ningbo",
                delta_cost=Decimal("72000"),
                delta_days=3,
                confidence=0.85,
                rationale="Ningbo absorbed spillover cleanly during 2025 typhoon season.",
            ),
            MitigationFixture(
                option_type="hold",
                description="Hold two vessels at anchor; resume after port reopens",
                delta_cost=Decimal("18000"),
                delta_days=2,
                confidence=0.6,
                rationale="Short closure window makes anchorage hold cheaper than reroute.",
            ),
        ),
        affected_count=3,
        destination_name="Rotterdam",
        destination_lat=51.92,
        destination_lng=4.48,
    ),
    HistoricalFixture(
        slug="cbameu",
        days_ago=22,
        category="policy",
        title="EU CBAM steel — interim ruling released",
        summary="Adjustment bracket shifted +2.1pp for Class-B steel; affected Q2 EU imports.",
        region="European Union",
        lat=50.85,
        lng=4.35,
        radius_km=1200.0,
        severity=3,
        total_exposure=Decimal("680000"),
        units_at_risk=5,
        source_signals=(
            SignalFixture(
                source_category="policy",
                source_name="tavily:ec-europa-eu",
                title="EU publishes Q2 CBAM interim adjustment for Class-B steel",
                summary="+2.1pp bracket shift announced; effective 15 Apr 2026.",
                region="European Union",
                lat=50.85,
                lng=4.35,
                radius_km=1200.0,
                source_urls=("https://ec.europa.eu/cbam/q2-interim-ruling",),
                confidence=0.94,
                hours_before_disruption=12.0,
            ),
        ),
        mitigations=(
            MitigationFixture(
                option_type="switch_compliant_supplier",
                description="Move Q2 orders to Turkey + Serbia mills under the threshold",
                delta_cost=Decimal("32000"),
                delta_days=4,
                confidence=0.82,
                rationale="Pre-qualified mills sit below the new threshold for Class-B.",
            ),
        ),
        affected_count=2,
        destination_name="New York",
        destination_lat=40.71,
        destination_lng=-74.01,
    ),
    HistoricalFixture(
        slug="panama",
        days_ago=15,
        category="logistics",
        title="Panama Canal low-water — Neo-Panamax draft restrictions",
        summary=(
            "Gatun Lake hit 79.5 ft; restrictions forced 4-day transit delays on Asia-East Coast."
        ),
        region="Panama Canal",
        lat=9.08,
        lng=-79.68,
        radius_km=200.0,
        severity=4,
        total_exposure=Decimal("2780000"),
        units_at_risk=16,
        source_signals=(
            SignalFixture(
                source_category="logistics",
                source_name="tavily:acp",
                title="ACP announces Neo-Panamax draft cut to 44.5 ft",
                summary="Low water on Gatun; reduced daily slots; transit delays cascading.",
                region="Panama",
                lat=9.08,
                lng=-79.68,
                radius_km=200.0,
                source_urls=("https://pancanal.com/advisory/draft-restrictions",),
                confidence=0.95,
                hours_before_disruption=8.0,
            ),
            SignalFixture(
                source_category="news",
                source_name="tavily:gcaptain",
                title="Shippers consider Suez pivot as Panama wait times balloon",
                summary="Some carriers rerouting East Asia → US East Coast via Suez.",
                region="Global",
                lat=0.0,
                lng=0.0,
                radius_km=10000.0,
                source_urls=("https://gcaptain.com/panama-suez-pivot",),
                confidence=0.81,
                hours_before_disruption=4.0,
            ),
        ),
        mitigations=(
            MitigationFixture(
                option_type="reroute",
                description="Shift Asia-East Coast volume to all-water Suez + transshipment",
                delta_cost=Decimal("190000"),
                delta_days=7,
                confidence=0.79,
                rationale=(
                    "Suez routing stable; avoids 10+ day Panama queue at current draft limits."
                ),
            ),
            MitigationFixture(
                option_type="accept_delay",
                description="Accept 4-day Panama wait on lowest-priority SKUs",
                delta_cost=Decimal("0"),
                delta_days=4,
                confidence=0.6,
                rationale="Non-priority freight absorbs delay without SLA breach.",
            ),
        ),
        affected_count=3,
        destination_name="New York",
        destination_lat=40.71,
        destination_lng=-74.01,
    ),
    HistoricalFixture(
        slug="samsvn",
        days_ago=10,
        category="news",
        title="Samsung Vietnam — Q1 staffing shortfall at Bac Ninh",
        summary="Lunar New Year return rate 12pp below plan; Q1 memory output cut 8%.",
        region="Bac Ninh",
        lat=21.18,
        lng=106.06,
        radius_km=100.0,
        severity=2,
        total_exposure=Decimal("430000"),
        units_at_risk=4,
        source_signals=(
            SignalFixture(
                source_category="news",
                source_name="tavily:reuters",
                title="Samsung Bac Ninh reports post-Tet staffing shortfall",
                summary="Return rate below forecast; Q1 output guidance trimmed.",
                region="Bac Ninh",
                lat=21.18,
                lng=106.06,
                radius_km=100.0,
                source_urls=("https://reuters.com/samsung-bac-ninh-staffing",),
                confidence=0.78,
                hours_before_disruption=6.0,
            ),
        ),
        mitigations=(
            MitigationFixture(
                option_type="alternate_supplier",
                description="Pull Q1 shortfall from SK Hynix Icheon pre-qualified lot",
                delta_cost=Decimal("38000"),
                delta_days=2,
                confidence=0.83,
                rationale="Hynix lot pre-qualified; supply covers 90% of the shortfall.",
            ),
        ),
        affected_count=2,
        destination_name="Tokyo",
        destination_lat=35.65,
        destination_lng=139.75,
    ),
    HistoricalFixture(
        slug="tsmcfab",
        days_ago=6,
        category="industrial",
        title="TSMC Fab-15 utility incident — 6h line down",
        summary="Localized utility fault at Taichung Fab 15; tool recovery took 6h.",
        region="Taichung",
        lat=24.14,
        lng=120.68,
        radius_km=40.0,
        severity=3,
        total_exposure=Decimal("1120000"),
        units_at_risk=7,
        source_signals=(
            SignalFixture(
                source_category="industrial",
                source_name="tavily:digitimes",
                title="TSMC Fab 15 utility fault — brief line-down event",
                summary="Limited to Fab 15; no wafer loss; recovery within 6h.",
                region="Taichung",
                lat=24.14,
                lng=120.68,
                radius_km=40.0,
                source_urls=("https://digitimes.com/tsmc-fab15-utility-incident",),
                confidence=0.88,
                hours_before_disruption=2.5,
            ),
        ),
        mitigations=(
            MitigationFixture(
                option_type="expedite",
                description="Air-freight replacement wafers to Malaysia ATP",
                delta_cost=Decimal("180000"),
                delta_days=2,
                confidence=0.77,
                rationale="Downstream ATP line sensitive to wafer gap; air-freight covers.",
            ),
        ),
        affected_count=2,
        destination_name="Los Angeles",
        destination_lat=34.05,
        destination_lng=-118.24,
    ),
    HistoricalFixture(
        slug="thbaht",
        days_ago=2,
        category="macro",
        title="Thai baht — intraday 1.8% spike vs USD",
        summary=(
            "Policy rate announcement triggered rapid THB strength; "
            "FX cost uptick on Thailand landed cost."
        ),
        region="Thailand",
        lat=13.75,
        lng=100.5,
        radius_km=600.0,
        severity=1,
        total_exposure=Decimal("190000"),
        units_at_risk=3,
        source_signals=(
            SignalFixture(
                source_category="macro",
                source_name="tavily:bot-or-th",
                title="BoT surprises with 25bp hike; baht +1.8% vs USD intraday",
                summary="Unexpected tightening; THB strength expected to persist near-term.",
                region="Thailand",
                lat=13.75,
                lng=100.5,
                radius_km=600.0,
                source_urls=("https://bot.or.th/policy-rate-apr",),
                confidence=0.82,
                hours_before_disruption=3.0,
            ),
        ),
        mitigations=(
            MitigationFixture(
                option_type="accept_delay",
                description="Absorb FX hit on Q2 Thailand landed cost",
                delta_cost=Decimal("22000"),
                delta_days=0,
                confidence=0.7,
                rationale="Too small to justify reroute; absorb and re-forecast at month-end.",
            ),
        ),
        affected_count=1,
        destination_name="Tokyo",
        destination_lat=35.65,
        destination_lng=139.75,
    ),
)
