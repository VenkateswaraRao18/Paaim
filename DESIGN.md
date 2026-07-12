# PAAIM Design System — "Field Ops / Pine & Amber"

This file is the single source of truth for how PAAIM looks and is structured.
**Every new component must follow it.** Do not drift back to generic Tailwind
blues, drop shadows, or gray-on-gray. If something isn't covered here, extend
this file first, then build.

The product is a **factory decision system for plant managers and lead
operators**. The design goal is not "pretty" — it is **clarity under pressure**:
a stressed manager must know, on every screen, *what is happening, why, and what
to do next*, in under five seconds.

---

## 1. Core principles (the "why", not just the "look")

1. **One screen, one question.** Every screen answers exactly one management
   question stated at the top (e.g. "Can we safely restart Line 3?"). If a
   screen answers two questions, split it.
2. **What → Why → What next.** Every meaningful element shows the fact, the
   reason behind it, and the resulting action. Never a number with no meaning.
3. **Plain language over jargon.** `0x4F3` is always paired with "Station C3
   interlock / torque fault." Machine codes get translated, never shown raw
   alone.
4. **Colour means something.** Most of the screen is calm and neutral. Colour is
   a signal — amber = attention, coral = danger. If everything is coloured,
   nothing is.
5. **Evidence, not assertion.** Every recommendation links to its source. The UI
   should feel auditable: "here's the data behind this," not "trust me."
6. **Calm, executive, operational.** No excessive charts, no dashboard vomit.
   White space is a feature.

---

## 2. Colour palette

The concept: a calm natural base (deep pine green on warm paper) with a single
hot signal colour (amber) reserved for attention, and coral strictly for danger.
**The discipline is what makes it look designed — most colours do nothing; two
colours do all the talking.**

```css
:root {
  --pine:   #123A2E;  /* darkest green — big numbers, strongest text accents */
  --pine-2: #1B5443;  /* primary brand — buttons, progress fills, links, headings */
  --moss:   #7FA893;  /* soft green — success hints, hover borders, subtle labels */
  --paper:  #F3F5F2;  /* page background — warm off-white with a green cast */
  --card:   #FFFFFF;  /* surface — cards sit on paper */
  --ink:    #17211C;  /* body text — near-black with green undertone, not pure #000 */
  --dim:    #5E6B64;  /* secondary text — captions, hints, labels */
  --amber:  #E8A13D;  /* THE signal colour — "now", warnings, highlights */
  --coral:  #D8492B;  /* danger only — faults, missed targets, destructive actions */
  --line:   #DDE4DF;  /* borders and dividers — tinted toward the palette, not gray */
}
```

### State surfaces are TINTS, never new colours
- success surface → `#EDF4EF` (pine at ~8%)
- warning surface → `#FBF3E3` (amber tint)
- danger surface  → `#FBEAE5` (coral tint)

### Rules that keep it cohesive
- **Amber appears in exactly one place per screen** where possible — the single
  most important "look here."
- Every neutral (borders, dim text, page bg) carries a slight green undertone, so
  even the "grays" belong to the family. Never use pure `#000`, `#808080`, or
  Tailwind's default slate/gray.
- Coral is **danger only**. A red button that isn't destructive is a bug.

---

## 3. Typography

Two voices: a **system sans** for reading, and **monospace for anything numeric
or machine-like** — counters, KPIs, timestamps, codes, nav labels. The
mono-for-data choice is what gives PAAIM its "mission control / logbook"
character.

```css
body:   -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
--mono: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
```

### The signature detail — eyebrows
Small uppercase labels above every section title:
- mono, 10–11px, `text-transform: uppercase`, `letter-spacing: .08–.18em`
- colour `--pine-2` (or `--dim` when secondary)

### Headings
- tight: `letter-spacing: -.02em`
- one word may be tinted via an `.accent` span (`--pine-2` or `--amber`)

### The section stack (use on EVERY section)
```
EYEBROW           ← mono uppercase, --pine-2
Title             ← sans, tight, large
Sub / one-liner   ← --dim, states the question this section answers
```

---

## 4. UI patterns

- **Card-on-paper:** white cards, `1px solid var(--line)`, `border-radius: 10px`,
  on the tinted paper background. **No drop shadows** — borders do the
  separation. A subtle shadow is allowed only on a single focal element (e.g. the
  decision banner).
- **Layout width:** the guided story / decision views use a focused centred
  column (~`max-width: 960px`). Data-dense views (audit table, live feed) may go
  wider, but stay on the card-on-paper grid.
- **Eyebrow → Title → Sub** header stack on every section (see §3).
- **Signal-state components:** progress bars, table cells, and status pills
  change class by threshold — `ok / warn / bad / over` — so colour always means
  something. A cell is never coloured decoratively.
- **Left-border alert pattern:** `border-left: 4px solid` + tinted background.
  Amber for warning, coral for critical, pine for informational.
- **KPI tile:** mono value (large, `--pine`), eyebrow label above, one-line
  meaning below in `--dim`. Never a bare number.
- **Evidence row:** every claim renders as `fact → source → interpretation`, with
  the source clickable to a snippet. This is the trust primitive.
- **Steppers over inputs** for any counter (−/+ buttons), not text fields.
- **Read-only OT banner:** a persistent, calm strip on operational screens —
  "Read-only OT mode: no PLC write-back, no autonomous restart." Uses pine
  informational styling, never alarming.

---

## 5. Architecture patterns (front-end)

- **Design tokens live in `globals.css`** as the CSS variables above, and are
  mirrored into `tailwind.config.ts` so classes like `bg-paper`, `text-pine`,
  `border-line`, `text-amber` exist. Prefer the tokens over hex literals.
- **Reusable primitives** (build these once, use everywhere):
  `Eyebrow`, `SectionHeader`, `Card`, `KpiTile`, `SignalPill`, `AlertBar`,
  `EvidenceRow`, `AgentCard`, `DecisionBanner`. New screens compose primitives;
  they do not re-style from scratch.
- **Data-driven UI:** cards, KPIs, agent rows, and evidence come from plain
  arrays/objects; render functions map over them. Adding content = adding a data
  item, never touching markup.
- **State clarity:** each page owns a small, explicit state object; interactions
  mutate it and re-render. Keep it debuggable.

---

## 6. Voice & copy

- Address the operator/manager directly and plainly.
- Lead with the decision, then the reason: **"Do not restart yet — active
  interlock + elevated torque + camera anomaly."**
- Always translate machine language: code → meaning → safe action.
- No hype, no emoji in product UI, no vague "AI-powered" language. State facts.

---

## 7. One-paragraph brief (for handing to a code assistant)

> Use the Pine & Amber palette (`--pine-2 #1B5443` primary on `--paper #F3F5F2`,
> `--amber #E8A13D` as the sole attention colour, `--coral #D8492B` for danger
> only, tinted borders `--line #DDE4DF`, never pure gray/black). System sans for
> body, monospace for all numbers/codes/labels and uppercase eyebrows. Bordered
> white cards, no drop shadows, calm executive layout. Every screen answers one
> management question with an eyebrow→title→sub header; every fact shows
> what→why→what-next; every recommendation links to its evidence source. Compose
> screens from shared primitives (Card, KpiTile, SignalPill, AlertBar,
> EvidenceRow, AgentCard, DecisionBanner). Colour always means a state; amber
> appears once per screen.
