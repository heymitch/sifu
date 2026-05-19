# Classification report — Sifu

The actual product output. A workflow Sifu has watched, classified, and is teaching back to the user.

## Components
- `ReportHeader.jsx` — workflow ID, title, status, stamp
- `ReportSummary.jsx` — the teacher's lead paragraph + key metrics
- `Observations.jsx` — sparkline of when this happened, mono table
- `ClassifiedSteps.jsx` — the numbered steps Sifu inferred
- `Exceptions.jsx` — when the pattern doesn't apply
- `AgentPlan.jsx` — what Sifu would automate, with code reference
- `ReportFooter.jsx` — verified-by-Sifu seal, timestamps

## Index
`index.html` composes the full report — the document a user receives.
