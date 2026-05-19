---
name: sifu-design
description: Use this skill to generate well-branded interfaces and assets for Sifu, either for production or throwaway prototypes/mocks/etc. Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping.
user-invocable: true
---

Read the README.md file within this skill, and explore the other available files.

If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out and create static HTML files for the user to view. If working on production code, you can copy assets and read the rules here to become an expert in designing with this brand.

If the user invokes this skill without any other guidance, ask them what they want to build or design, ask some questions, and act as an expert designer who outputs HTML artifacts _or_ production code, depending on the need.

## Quick orientation
- **Sifu** is a workflow classifier. It watches what you do, identifies patterns, and teaches you the system you didn't know you already had.
- **Vibe**: Japanese industrial design. MUJI lab notebook. Quiet product. Precision over personality. The brand is what gets removed, not added.
- **Voice**: Reads like a teacher's notebook — observational, low-noise. Never marketing-y. "I see you do X. Here's why. Here's when it doesn't work." Sentence case for everything.
- **Color**: Bone `#F2F0EB` background. Charcoal `#1F1F1F` ink. Indigo `#2D4A87` as the only accent. Stamp red `#C8202F` only for verified moments (<2% of any composition).
- **Type**: IBM Plex Sans (Light body, Medium headings) + JetBrains Mono (every label, ID, timestamp). Both on Google Fonts — `colors_and_type.css` imports them.
- **Surfaces**: hairline rules (1px pale-grey), no drop shadows ever, sharp corners by default, no gradients, no blur, no glass.

## Files
- `colors_and_type.css` — all tokens. Import once and you're in the system.
- `README.md` — full brand, voice, visual foundations, iconography rules.
- `assets/` — wordmark SVG, indigo seal (師), CLASSIFIED stamp, favicon.
- `preview/` — small spec cards for each token cluster.
- `ui_kits/marketing-site/` — one-page marketing site (Header, Hero, WhatItDoes, SamplePanel, CaseList, Pricing, Footer).
- `ui_kits/classification-report/` — the product output: a workflow Sifu has classified (ReportHeader, ReportSummary, Observations, ClassifiedSteps, Exceptions, AgentPlan, ReportFooter).

## Minimum viable artifact
```html
<link rel="stylesheet" href="colors_and_type.css" />
<body>
  <span class="eyebrow">Workflow · 0042</span>
  <h1>I see you do this 14 times a week.</h1>
  <p>Here's the pattern.</p>
  <span class="stamp">Classified</span>
</body>
```

## Hard rules (don't break these)
- No drop shadows. No gradients. No blur. No glassmorphism.
- No emoji, ever. Mono labels and the indigo seal do that work.
- One accent per composition. Indigo OR stamp red, not both prominent.
- No "AI-powered", "supercharge", "unleash", "revolutionize". Don't market — observe.
- No cherry blossoms, sakura, or aesthetic-Asia decoration. We are industrial design.
- No bouncy animations, no spring, no scale-on-press. Calm 200ms ease.
