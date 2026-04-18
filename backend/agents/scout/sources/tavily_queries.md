# Scout Tavily Query Library

Judging artifact per PRD §13.3. These queries drive the four Tavily-backed
Scout source loops (`news.py`, `policy.py`, `logistics.py`, `macro.py`).
Weather is served by Open-Meteo and does not appear here.

Each query is run on its own cadence (see `scout/config.py`) with
`include_answer=false` and `max_results=10`, then fanned into the Scout
classifier. Re-running a query that returns a result already in the 72h
dedupe window is a cheap no-op thanks to the `signals.dedupe_hash` unique
constraint.

## News — cadence 60s

Focus: labor actions, industrial incidents, civil unrest, corporate events
that immediately affect factory output or port throughput.

| # | Query | Rationale |
|---|---|---|
| 1 | `("port strike" OR "dockworker walkout") ("2026" OR "this week")` | Labor action → logistics chokepoint within hours |
| 2 | `("ILWU" OR "ILA") strike authorization vote` | U.S. West/East coast port unions — direct trade-lane exposure |
| 3 | `"factory fire" (automotive OR semiconductor OR pharmaceutical) 2026` | Tier-2 supplier outages ripple to OEM allocations |
| 4 | `"refinery outage" OR "refinery shutdown" 2026` | Fuel cost shocks flow into freight rates within days |
| 5 | `"container ship" (collision OR grounding OR fire) 2026` | Single-vessel incidents that close lanes (Suez-style) |
| 6 | `"warehouse fire" logistics distribution center 2026` | Disrupts last-mile and tier-1 inventory pools |
| 7 | `"chemical leak" (plant OR facility) supply chain 2026` | Evacuation zones take suppliers offline |
| 8 | `"trucker strike" OR "haulier strike" Europe 2026` | Inland logistics shock — port backlog follows |
| 9 | `"power outage" industrial park ("Shenzhen" OR "Kaohsiung" OR "Chennai")` | Electronics/pharma hubs; grid is single-point-of-failure |
| 10 | `"earthquake" magnitude 6 industrial 2026` | High-severity low-probability — auto-escalates in rubric |
| 11 | `"pipeline rupture" oil gas supply chain 2026` | Feedstock hit for petchem, plastics, fertilizer |
| 12 | `"shipping lane" closed OR blocked OR diverted 2026` | Direct lane closure signal |
| 13 | `"air cargo" disruption OR suspension airline 2026` | Pharma / electronics expedite lanes |
| 14 | `"rail strike" freight operator 2026` | Intermodal ripple into port dwell times |
| 15 | `"bridge collapse" freight OR cargo 2026` | Rare but catastrophic (Baltimore-style) |
| 16 | `"cyberattack" logistics OR port OR shipping 2026` | Operational tech outages paralyze terminals |
| 17 | `"airport closure" cargo hub 2026` | HKG / MEM / FRA — impacts pharma / electronics |
| 18 | `"civil unrest" OR "protests" (port OR factory) 2026` | Site-level disruption in emerging markets |
| 19 | `"supplier bankruptcy" tier one automotive 2026` | Tier-1 collapse = OEM line stop |
| 20 | `"typhoon" OR "hurricane" port closure preemptive 2026` | News framing complements Open-Meteo weather signal |

## Policy — cadence 15min

Focus: government, regulator, and multilateral action that changes landed
cost, permissible origin, or carrier access.

| # | Query | Rationale |
|---|---|---|
| 1 | `"USTR" ("Section 301" OR tariff) determination 2026` | U.S. trade policy updates — high operator-impact |
| 2 | `"Section 232" national security tariff 2026` | Metals, semiconductors |
| 3 | `"OFAC" sanctions designation (entity OR vessel OR port) 2026` | Supplier compliance re-screens |
| 4 | `"EU" "Carbon Border Adjustment Mechanism" CBAM 2026` | Landed-cost impact for steel/aluminum/cement |
| 5 | `"export control" semiconductor advanced node 2026` | BIS Entity List / end-use restrictions |
| 6 | `"Forced Labor" "Withhold Release Order" CBP 2026` | U.S. import bans — immediate container hold |
| 7 | `"customs" inspection intensified region 2026` | Lane-level clearance delays |
| 8 | `"export ban" food commodity country 2026` | India rice, Russia wheat patterns |
| 9 | `"trade agreement" ratified signed 2026` | Rules-of-origin shifts |
| 10 | `"anti-dumping duty" product country 2026` | Per-SKU duty escalation |
| 11 | `"FDA" import alert 2026` | Pharma / medical device block |
| 12 | `"USDA" APHIS import suspension country 2026` | Food commodity flows |
| 13 | `"IMO" emissions regulation shipping compliance 2026` | Carrier fuel surcharges |
| 14 | `"OECD" critical minerals policy 2026` | Cobalt/lithium supply posture |
| 15 | `"UK" trade sanctions designation 2026` | Post-Brexit parallel regime |
| 16 | `"Japan" METI export license controls 2026` | EUV/photoresist parallels |
| 17 | `"China" MOFCOM export license rare earths 2026` | Supply-side choke |
| 18 | `"India" DGFT export notification 2026` | Rice, onion, pharma precursors |
| 19 | `"Brazil" tariff change industry 2026` | Agricultural commodity flows |
| 20 | `"WTO" dispute ruling tariff 2026` | Forward signal for tariff action |

## Logistics — cadence 10min

Focus: direct lane state, port throughput, carrier capacity, freight
pricing signals.

| # | Query | Rationale |
|---|---|---|
| 1 | `"Panama Canal" draft restriction transits 2026` | Gatun Lake levels — capacity throttle |
| 2 | `"Suez Canal" traffic security restrictions 2026` | Red Sea diversions persist |
| 3 | `"Cape of Good Hope" rerouting carriers Asia Europe 2026` | Transit-time shock signal |
| 4 | `"Shanghai" port congestion dwell time 2026` | China-US transpacific bellwether |
| 5 | `"Los Angeles" OR "Long Beach" port dwell 2026` | Pacific gateway to U.S. interior |
| 6 | `"Rotterdam" OR "Antwerp" terminal delays 2026` | Europe main gateway |
| 7 | `"drewry" world container index spike 2026` | Weekly spot-rate barometer |
| 8 | `"container spot rate" Asia US West Coast 2026` | Operator cost exposure |
| 9 | `"blank sailing" carrier alliance 2026` | Capacity withdrawal signal |
| 10 | `"empty container" imbalance region 2026` | Equipment availability crisis |
| 11 | `"rail ramp" intermodal dwell 2026` | Inland supply chain follow-through |
| 12 | `"truck capacity" tightness market 2026` | Drayage bottleneck |
| 13 | `"bunker fuel" IFO VLSFO price 2026` | Carrier fuel surcharge preview |
| 14 | `"ULCV" ultra-large container vessel redeploy 2026` | Capacity reshuffle indicator |
| 15 | `"Ningbo-Zhoushan" port closure typhoon fog 2026` | World's largest cargo port |
| 16 | `"Houston" port Gulf Coast closure 2026` | Petchem gateway |
| 17 | `"Chittagong" OR "Colombo" port strike closure 2026` | South Asia gateway |
| 18 | `"air freight" rate index pharmaceuticals 2026` | Expedited-lane cost |
| 19 | `"vessel sharing alliance" capacity adjustment 2026` | 2M / Ocean / THE patterns |
| 20 | `"ECDIS" navigational warning lane 2026` | Regulatory notice of lane hazard |

## Macro — cadence 30min

Focus: interest rates, FX, commodities, inflation prints that shift
landed cost and supplier financial health.

| # | Query | Rationale |
|---|---|---|
| 1 | `"Federal Reserve" rate decision FOMC 2026` | Financing cost for working capital |
| 2 | `"ECB" deposit rate decision 2026` | Euro-area supplier exposure |
| 3 | `"PBOC" ("MLF" OR "reserve ratio" OR "LPR") 2026` | China monetary stance |
| 4 | `"Bank of Japan" policy yield curve 2026` | JPY carry + exporter margin |
| 5 | `"CPI" inflation print United States 2026` | Rate-path driver |
| 6 | `"PPI" producer prices China 2026` | Landed-cost leading indicator |
| 7 | `"PMI" manufacturing global 2026` | Demand / supply activity pulse |
| 8 | `"Brent crude" price OPEC decision 2026` | Transport fuel and petchem feedstock |
| 9 | `"copper" LME price supply 2026` | Electronics / industrial metals |
| 10 | `"aluminum" LME price smelter curtailment 2026` | Packaging + transport |
| 11 | `"steel" HRC price tariff impact 2026` | Industrial + automotive |
| 12 | `"lithium carbonate" price 2026` | EV battery cost |
| 13 | `"semiconductor" WSTS book-to-bill 2026` | Electronics cycle |
| 14 | `"USD/CNY" OR "USD/JPY" move policy 2026` | Asia supplier FX exposure |
| 15 | `"USD/EUR" OR "USD/GBP" move policy 2026` | Europe supplier FX exposure |
| 16 | `"Baltic Dry Index" move 2026` | Bulk freight barometer |
| 17 | `"LNG" spot price JKM Europe 2026` | Industrial utility cost |
| 18 | `"urea" fertilizer price 2026` | Agricultural commodity input |
| 19 | `"cocoa" OR "coffee" price weather 2026` | Food commodity volatility |
| 20 | `"natural gas" TTF Henry Hub price 2026` | Chemical / glass / pharma utility cost |
