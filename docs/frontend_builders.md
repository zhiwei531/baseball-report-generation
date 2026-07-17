# Static Report Builders

The repository uses static HTML/Python builders, not React. The canonical
template is the latest Git-tracked
`reports/pitching_bryan_coach/index.html`. Its frozen Stage 9 SHA and DOM shape
are validated before migration decisions.

The combined builder validates ReportData subject/sections, then retains
legacy CSV binding and the final polish compatibility pass to preserve layout,
copy, scores, assets, PDF, and PPTX behavior. Asset paths are relative and
copied through a scoped asset manager. No biomechanics calculation belongs in
HTML/CSS; remaining legacy binding is tracked in `docs/stage9_reporting.md`.
