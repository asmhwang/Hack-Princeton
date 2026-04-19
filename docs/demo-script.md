# suppl.ai — Two-minute demo script

**Total:** 2:00 (120 seconds). Problem 25s · Solution 17s · Tech 13s · Live demo 65s. Memorize the opening hook and the closing line; everything in between is narrated over clicks.

---

## 0:00 – 0:25 · Problem (25s, ~80 words)

When a supply chain disruption hits, like the war on Iran blocking the Strait of Hormuz, managers face a chaotic, multi-hour scramble. They’re frantically cross-referencing breaking news, spreadsheets, and emails just to figure out what's at risk. By the time they calculate the financial hit and decide their best course of action, it’s already too late.

---

## 0:25 – 0:42 · Solution (17s, ~50 words)

suppl.ai compresses those five hours into sixty seconds with an automated AI agent pipeline that streamlines the process from beginning to end. Three agents run continuously on three separate dedalus VMs. The first agent Scout watches the world for news, weather events, new policy, etc. The second agent Analyst waits for Scout to detect an anomoloy, and calculates the total exposure from the event, and what damages come out of it. Lastly, the third agent Strategist drafts reroutes, finds alternative solutions, and drafts emails to customers, shippers, and of course your boss.

---

## 0:42 – 0:55 · Tech stack (13s, ~45 words)

For the tech stack, we used dedalus to have our 3 agents running asyncronously and concurrently, 

---

## 0:55 – 2:00 · Live demo (65s)

> *Dashboard live on screen. `pnpm dev` running, agents up, offline-cache primed.*

### Beat 1 · 0:55 – 0:58 (3s)
> *Gesture at the empty dashboard.*
>
> "Here's Maya's war room. Calm. Zero active disruptions, zero dollars at risk."

### Beat 2 · 0:58 – 1:03 (5s)
> *Click `+ Simulate event` in the top bar. Select `Typhoon Kaia — Shenzhen`.*
>
> "I'm simulating a Category-3 typhoon making landfall near Shenzhen. In production Scout picks this up from Tavily and Open-Meteo automatically — here I'm triggering it on demand for time."

### Beat 3 · 1:03 – 1:11 (8s)
> *New signal card slides in from the left rail. Map pin appears with a radius ring. Top bar `$` counter starts.*
>
> "Scout classified the raw signal. Two seconds later it promoted to a disruption — that's the cone on the map. Fourteen shipments in transit just lit up as affected."

### Beat 4 · 1:11 – 1:26 (15s)
> *Analyst is working. Affected-shipments table populates. `$2.3M` appears in the top bar.*
>
> "Analyst is running right now — a tool-calling loop over seven parameterized reads against Postgres. Look at the top bar: two-point-three million dollars in exposure just appeared. Fourteen shipments of microcontrollers and power-management ICs, all destined for ACME Corp in Tokyo. None of this was hard-coded; it came out of the database."

### Beat 5 · 1:26 – 1:38 (12s)
> *Three mitigation cards appear in the right rail with spring animation.*
>
> "And here are the mitigations. Option one: reroute the fourteen shipments through Ho Chi Minh — plus one-hundred-eighty-K, saves five days, eighty-seven-percent confidence. Option two: switch to a backup supplier in Vietnam — forty-two-K, zero delay. Option three: expedite air — one-point-one million, saves eight days."

### Beat 6 · 1:38 – 1:46 (8s)
> *Click `Why this recommendation?` — explainability drawer slides in from the right.*
>
> "Why this recommendation? Here's the receipt. Trigger signals. The synthesized SQL that produced the impact report. The full reasoning trace — every tool call the Analyst made, every row it read. No black box."

### Beat 7 · 1:46 – 1:58 (12s)
> *Close drawer. Click `Approve` on the reroute option. Button collapses → checkmark → card morphs into the approvals log via `layoutId`.*
>
> "One click. Fourteen shipments flip to 'rerouting'. Three emails drafted — to the supplier in Vietnam, to ACME, to Maya's boss — saved to the database, never sent. Approval logged to the audit table with a full state snapshot."

### Beat 8 · 1:58 – 2:00 (2s — the money line)
> *Hold. Let the approvals log entry settle.*
>
> "Sixty seconds. Five hours compressed. **That's the pitch.**"

---

## Stage notes

### The Hormuz framing
If the Gulf situation has cooled by judging day (unlikely given the escalation timeline), swap in whichever supply shock is currently active — Red Sea, Panama Canal drought, any Asia typhoon. Keep the opening visceral and present-tense: "right now" is the whole lift.

### What NOT to linger on
- **Don't spend more than 13 seconds on the tech stack.** Judges see stack claims all day; the memorable beat is the approval moment ("it actually does something"), not the dep list.
- **Don't apologize for the simulate trigger.** It's a demo — everyone simulates. Frame it as "time compression", not "this is fake".
- **Don't narrate what the user can already see.** Let the animations do work. The card appearing, the number counting up, the drawer sliding — those read at a glance.

### Fallbacks
| Failure | Fallback |
|---|---|
| Simulate click doesn't fire the cascade within 10s | Click it a second time — `POST /api/dev/simulate` is idempotent (each call creates a fresh signal with a UUID dedupe key) |
| Signal appears but Analyst stalls | Keep narrating over the empty state; agents have offline cache and will resume; if >20s, cut to: "and here's the result from a run we did this morning" and swap to `docs/demo-backup.mp4` |
| WebSocket drops | Refresh the page; state restores from the DB on mount. Don't apologize — just do it while saying the next line |
| Complete system failure | Open `docs/demo-backup.mp4`. The script works as voiceover for the recording |

### Rehearsal checklist (do 3× on Sunday morning)
- [ ] Full fresh-boot run: `alembic upgrade head && python -m backend.scripts.seed && pnpm dev` + all 3 agents systemctl-started
- [ ] Offline cache primed for `typhoon_kaia` (one live run yesterday, cache artifact committed)
- [ ] Browser at 110 % zoom so the activity feed reads from the back row
- [ ] Dark mode, display mirroring off (don't show the MacBook display separately)
- [ ] Phone on silent, Slack/email/notifications muted
- [ ] Second laptop queued to `docs/demo-backup.mp4` as insurance
- [ ] Clock visible in peripheral vision (Apple Watch works)

### If asked questions during or after
- **"How do you prevent SQL injection?"** → Analyst never emits raw SQL. Gemini picks from a fixed set of seven parameterized read-only tools. Defense-in-depth: any synthesized SQL string is passed through `sql_guard` which rejects non-SELECT, forbidden keywords, and DoS functions at the token level. Twenty-two tests cover it.
- **"What happens if Gemini hallucinates?"** → Every LLM response is bound to a Pydantic `response_schema`. Invalid output triggers one retry with the validation error appended to the prompt; second failure falls back to a rules-based template keyed on disruption category.
- **"How do the three agents coordinate?"** → They don't talk to each other. They write to Postgres and listen for NOTIFY events on five channels. If the bus connection drops, the `EventBus` reconnects with exponential backoff and resubscribes. It's the same pattern Linear uses for realtime.
- **"Why not Kafka / Redis / Temporal?"** → Three reasons. One: everything is already in Postgres — adding a broker doubles the infra to fail during a live demo. Two: `LISTEN/NOTIFY` is built-in and gives us at-most-once delivery, which combined with agent idempotency (`ON CONFLICT DO NOTHING`, content-hash dedupe) is enough. Three: we built this in 36 hours.
- **"Are the emails actually sent?"** → Never. `draft_communications.sent_at` is always NULL, enforced by a Pydantic validator. Zero SMTP libraries in our dependency graph — `grep -r smtplib backend/` returns empty. It's a quality gate on every commit.
- **"What about Eragon / OpenClaw?"** → Strategist's entire mutation path runs through OpenClaw Actions — supplier lookup, draft-comms write, shipment status flip, audit log entry. That's what makes the approval click do real work. It's not chat.

---

## Word count audit

| Section | Words | Target s @ 180 wpm | Actual s |
|---|---:|---:|---:|
| Problem | 80 | 26.7 | 25 |
| Solution | 51 | 17.0 | 17 |
| Tech stack | 44 | 14.7 | 13 |
| Demo voiceover | ~195 | 65.0 | 65 |
| Close | 9 | 3.0 | 2 |
| **Total** | **~379** | **126.4** | **122** |

Runs slightly hot at 180 wpm — aim for 175–180 wpm delivery, crisp consonants, no filler. Practice the Hormuz opening until you can say it on autopilot; that's the one line nobody's allowed to stumble on.
