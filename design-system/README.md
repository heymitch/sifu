# Sifu Design System

> Sifu is a **workflow classifier** — it watches what you do, identifies the patterns, and teaches you the system you didn't know you already had.

The brand is what gets removed, not added. This system is the rulebook for that restraint.

---

## Sources

This design system was built **from a brand brief only** — no codebase, Figma file, or screenshots were attached. All visual decisions (logo, layout, components, iconography choices) were made from the written brief and the references it points to:

- MUJI product line photography (catalog pages — neutral product shots)
- Naoto Fukasawa industrial designs (CD player, kitchen tools)
- Kenya Hara design exhibition photography
- Sou Sou geometric textile patterns (texture only)
- Shigeru Ban architecture interiors (spatial restraint)
- IBM Plex Sans specimen page (type texture)

**If a real product codebase or Figma file exists, re-import it** and we'll align the kit to the source of truth — components here are an opinionated first pass, not a transcription.

---

## What's in this folder

```
README.md                  ← this file
SKILL.md                   ← Agent-Skill manifest (use this in Claude Code too)
colors_and_type.css        ← all tokens (color, type, spacing, motion, radii)
fonts/                     ← (Google Fonts — IBM Plex Sans + JetBrains Mono loaded by CSS)
assets/                    ← logo, seal, stamp, brand marks (SVG)
preview/                   ← design-system review cards (one HTML per concept)
ui_kits/
  marketing-site/          ← one-page marketing site
  classification-report/   ← the actual product output — workflow report
slides/                    ← (none — no template was provided)
```

---

## Product surfaces

Two surfaces are recreated as UI kits:

1. **Marketing site** — one-page, generous negative space. The index page of the brand.
2. **Workflow classification report** — the actual product output. A workflow Sifu has watched, classified, and is teaching back to you. This is where Sifu *is* the lab notebook.

Documentation, course materials, status badges, and Slack/Discord embeds reuse the components from these two kits.

---

## Visual foundations

The aesthetic is **Japanese industrial design via the MUJI lab notebook**: paper-stock backgrounds, ink-black text, a single indigo accent, and mono labels that read like a teacher's marginalia.

### Color
- **Bone white `#F2F0EB`** — primary background. Always. The page is paper.
- **Charcoal `#1F1F1F`** — primary text. Ink, with the warmth removed.
- **Pale grey `#C9C7C2`** — dividers and secondary surfaces. Hairlines do the work shadows would do elsewhere.
- **Warm grey `#5A5752`** — captions and secondary text.
- **Indigo `#2D4A87`** — the *only* functional accent. Links, the seal, status, focus rings. One per composition.
- **Stamp red `#C8202F`** — verified / approved moments. <2% of any composition. Used like a chop, not like a button.

No gradients between these. No tints other than the bone-deep / bone-soft derivatives (`#ECEAE3`, `#F7F5F1`) used to nest surfaces on themselves.

### Type
- **IBM Plex Sans** — Light (300) for body, Medium (500) for headings, Bold (700) sparingly for stamps and IDs. No serifs. No condensed cuts.
- **JetBrains Mono** — every label, every ID, every classification tag, every timestamp. Mono is the lab-notebook signature.
- **Eyebrow labels** are mono, 12px, uppercase, `0.12em` tracking, warm-grey. They appear above headings, on cards, on form labels — anywhere the system needs to *name a thing*.

### Spacing & layout
- 4px base. Generous use of the upper end (`64px`, `96px`, `128px`).
- Negative space is the primary compositional tool. A marketing section may be 70% empty.
- Hairline rules (`1px solid var(--rule)`) divide content. Cards are bordered, not shadowed.
- Max content width is conservative (`1080px`). Text columns are `64ch`.

### Backgrounds
- **Bone white**, full-bleed. Never gradient. Never patterned.
- Nested surfaces use `--bg-deep` (`#ECEAE3`) — one paper laid on another.
- No images as backgrounds. No textures. No noise. (The geometric Sou Sou patterns from the references are *texture studies* — they inform our restraint, not our decoration.)

### Cards & elevation
- **No drop shadows. Ever.**
- Cards = 1px hairline border on `--bg-deep` or `--surface`. That's it.
- The "elevation system" is `inset 0 0 0 1px var(--rule)`.
- Corners are sharp by default (`--r-0`). `--r-1` (2px) for inputs. `--r-2` (4px) for cards, max. `--r-pill` only for status pills.

### Motion
- Calm. `cubic-bezier(0.4, 0, 0.2, 1)`. 120–320ms.
- **No bounce. No spring. No parallax.**
- Hovers are instant tonal shifts. Press is a 60ms tint, not a scale.
- Page transitions are crossfades on opacity, never slides.

### Hover & press states
- **Hover**: `rgba(31,31,31,0.04)` tint on surfaces. Links shift to `#1F3766` (darker indigo, no purple). Underline thickness stays the same.
- **Press**: `rgba(31,31,31,0.06)` tint. **No scale, no shrink** — the page is paper, not rubber.
- **Focus**: 2px indigo outline, 2px offset. Always visible for keyboard.
- **Disabled**: 40% opacity, no other treatment.

### Borders & rules
- Hairlines (`1px`, `--rule`) are the primary separator.
- Doubled rules (`2px`) are reserved for major section breaks.
- The stamp uses `1.5px solid var(--stamp)` — slightly heavier, like an inked border.

### Transparency, blur, gradients
- **None.** No glass, no blur, no gradient. The brand is opaque paper on opaque paper.
- The only acceptable transparency is hover/press tints (4–6%) and the focus ring.

### Imagery
- B&W or extremely desaturated. Cool greys. No warmth.
- Product-shot framing: object centered, neutral background, no styling.
- Grain is acceptable; warmth is not.
- We mostly *don't* use imagery — the type and rules carry the page.

---

## Content fundamentals

The voice is a teacher's lab notebook: calm, observational, low-noise.

### Tone
- **Reads like a teacher's notebook**: *"I see you do X. Here's why X works. Here's when it doesn't."*
- Observational, not promotional. Sifu reports what it sees, then teaches what it means.
- Technical without jargon. Mono labels do the technical signaling.
- Quiet confidence. Never excited.

### Casing
- **Sentence case for everything** — headings, buttons, labels.
- `UPPERCASE` is reserved for mono eyebrow labels (`CLASSIFIED`, `WORKFLOW · 0042`) and stamps.
- Title case is **not used**. It feels marketing-y.

### Pronouns
- **"You" for the reader.** Always.
- **"Sifu" for the product**, named in third person — *"Sifu watches", "Sifu classifies"*. Not "we", not "our system".
- First-person ("I see you do X") is used **only** in classification-report copy, where Sifu is speaking back to a single user about their work. It's the teacher voice, not the brand voice.

### Don't say
- AI-powered, supercharge, unleash, revolutionary
- "Powered by", "next-gen", "10x"
- Any verb that ends in `-ify`

### Do say
- watches, classifies, teaches, observes
- "I see you do X." / "This is the pattern."
- "Here's when it works. Here's when it doesn't."

### Numbers, IDs, data
- Always mono. Always with a label.
- Workflows are numbered: `WORKFLOW · 0042`.
- Confidence is a percentage with one decimal: `94.2%`.
- Timestamps are ISO-ish, mono: `2026-04-28 · 14:32`.

### Examples

| Don't | Do |
|---|---|
| "Revolutionize your workflow with AI." | "Sifu watches what you do, then teaches you the system." |
| "Unleash your team's productivity!" | "I see you do this 14 times a week. Here's the pattern." |
| "Powered by next-gen AI." | "Classified · 94.2% confidence · 312 observations." |
| "Get started now →" | "Start watching" |
| "Premium plan" | "For teams" |

### Emoji
- **Never.** Mono labels and the indigo seal do the work emoji would do elsewhere.

### Unicode
- The middle dot `·` is the brand's punctuation. It separates ID segments, metadata, breadcrumbs.
- Em dash `—` for asides.
- Arrows are textual: `→` for forward, `↑` `↓` for trend. No emoji arrows.

---

## Iconography

**No icon font is bundled.** No icon set was attached, and the brand's restraint argues against importing one wholesale. The system uses three icon strategies, in order of preference:

1. **Type as icon** — the mono `·` separator, `→` arrow, `↑↓` trend, `✓ ×` confirm/deny. These are always present and zero-weight. **Preferred.**
2. **Geometric SVG primitives** — circle, square, diamond, line. Used for the seal, the workflow node, the stamp border. Drawn locally in `assets/`, never inline-bloated in components.
3. **Lucide icons (CDN)** — when a true icon is needed (search, copy, share, settings, play). Lucide's stroke style (`1.5px`, square caps, no fills) matches the brand's hairline-rule discipline. **Loaded from `https://unpkg.com/lucide@latest`.**

### Substitution flag
> Lucide is a substitution. If a real Sifu product exists with a chosen icon set (Phosphor, Heroicons, custom), please share it and we'll swap.

### Rules
- Icons render at `1em` next to text and align to the cap-height baseline.
- Icon stroke is always `1.5px`. Never filled. Never two-tone.
- Icon color is always `currentColor` — they inherit text color, never carry their own.
- **Emoji is never used as an icon.** Not in product, not in marketing, not in docs.
- Decorative icons are forbidden. If an icon doesn't communicate a verb, remove it.

### Brand marks
- **`assets/sifu-wordmark.svg`** — the wordmark. Plex Sans Medium, charcoal.
- **`assets/sifu-seal.svg`** — the indigo seal. A circle with `師` (sifu/master) inside, used as the favicon and the "classified by Sifu" mark.
- **`assets/sifu-stamp.svg`** — the red "CLASSIFIED" stamp. Used <2% of any composition, on completed workflow reports only.

---

## Index

| File | What it is |
|---|---|
| [`README.md`](./README.md) | This file. Brand, voice, visual system. |
| [`SKILL.md`](./SKILL.md) | Agent-Skill manifest. Drop-in for Claude Code. |
| [`colors_and_type.css`](./colors_and_type.css) | All tokens. Import once at the top of any artifact. |
| [`assets/`](./assets/) | Logo, seal, stamp, brand marks. |
| [`preview/`](./preview/) | Design-system review cards. |
| [`ui_kits/marketing-site/`](./ui_kits/marketing-site/) | One-page marketing site recreation. |
| [`ui_kits/classification-report/`](./ui_kits/classification-report/) | The product output — a workflow Sifu has classified. |

### UI kits at a glance

- **Marketing site** (`ui_kits/marketing-site/`) — one-page site. Components: `Header`, `Hero`, `WhatItDoes`, `SamplePanel`, `CaseList`, `Pricing`, `Footer`.
- **Classification report** (`ui_kits/classification-report/`) — the product output. Components: `ReportHeader`, `ReportSummary`, `Observations`, `ClassifiedSteps`, `Exceptions`, `AgentPlan`, `ReportFooter`.

### Preview cards

Each token cluster has a card under `preview/`: colors (primary, accents, semantic), type (display, body, mono), spacing, radii, elevation, buttons, inputs, status, card, voice, brand-wordmark, brand-marks, iconography. The Design System tab renders them all.

---

## How to use this in a new artifact

```html
<link rel="stylesheet" href="../colors_and_type.css" />
<body>
  <span class="eyebrow">Workflow · 0042</span>
  <h1>I see you do this 14 times a week.</h1>
  <p>Here's the pattern.</p>
  <span class="stamp">Classified</span>
</body>
```

That's the whole system, in one example.
