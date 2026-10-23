# Task 6 Report: Arabic RTL Design System

Status: DONE_WITH_CONCERNS

Commit SHA: the commit that adds this file, `feat: add the Arabic design system`. A report cannot hold its own SHA. Run `git log -1 --format=%H -- docs/superpowers/plans/task-6-report.md` to get it.

Test summary: `npm test -- --run` in `web/` gives 6 files and 45 tests passing. `tsc --noEmit` is clean and `vite build` succeeds.

## What was built

- `web/` is a Vite + React 18 + TypeScript project. Tests run on Vitest, jsdom and React Testing Library.
- Every visual component lives in `web/src/design-system/` and is exported from `index.ts`: AppShell, Button, TextField, Select, TextArea, FileField, FilterBar, DataTable, BulkActionBar, RowActions, StatusChip, Timeline, EmptyState, LoadingState and ErrorState. The module also exports `tokens`, `STATUS_LABELS` and `FILTER_QUERY_KEYS`.
- AppShell renders `dir="rtl"` and `lang="ar"`. The sidebar uses `#1a1814` with `#f3efe6` text, and the active item uses `#1e4a38` with `aria-current="page"`.
- The font is IBM Plex Sans Arabic from `@fontsource/ibm-plex-sans-arabic`, imported in `styles.css`. Vite bundles the woff and woff2 files, so there is no CDN.
- Tokens use the exact palette, the spacing scale 4/8/12/16/24/32/48, an input radius of 6, a panel radius of 10 and a 2px cedar focus ring.
- StatusChip gives each of the five labels its own tone. Unknown statuses render with a neutral tone.
- FilterBar accepts only the schema types search, select, date and date_range. It emits only the keys q, status, governorate, region, inspector, date_from, date_to, role and is_active. Empty values are dropped from the output, and date_range maps to date_from and date_to.
- DataTable takes columns, rows, getRowId, rowActions, bulkActions and pagination. When bulkActions is empty, it renders no BulkActionBar and no checkboxes.
- `web/src/pages/.gitkeep` exists. `tableGuard.test.ts` fails if any file under `src/pages` contains `<table`, or if a source file other than `design-system/DataTable.tsx` contains it. I checked this by adding a violating file temporarily and watching both tests fail.

## Concerns

- I did not check the visual result in a browser. The aesthetic comes from the CSS alone: ledger-style hairlines, warm paper, an ink sidebar with a copper edge, and cedar for authority and focus.
- `npm install` reported 6 audit advisories in dev tooling (vite 5 and vitest 2). I left them alone because fixing them needs major version upgrades.
- The esbuild postinstall script was skipped by npm's allowScripts policy. Vite and Vitest still work.
- `web/src/App.tsx` is a demo page with sample data that composes the design system. Replace it when real pages are added.
