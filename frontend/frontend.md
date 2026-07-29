# Frontend End-to-End Diagnostic Audit Report

This report presents a complete diagnostic audit of the frontend application against `frontend/UI.md` and `workstatus.md`. No source code modifications have been made.

---

## 1. Screen Inventory & Build Status

| Screen File | Route | Build Status | Notes / Observations |
|---|---|---|---|
| `src/app/_layout.tsx` | App Shell | **Complete** | ThemeProvider, Inter fonts loading via `@expo-google-fonts/inter`, splash screen management, and `SidebarLayout` wrapper. |
| `src/app/index.tsx` | `/` (Home Dashboard) | **Complete** | Hero card, 3 quick stat cards, Quick Workflows section with `DenseRow` items, System Health & LLM Status panel. |
| `src/app/cv-match.tsx` | `/cv-match` | **Complete** | Dual tab mode (Raw Text / File Upload), web file picker, LLM enrichment toggle, sub-score breakdown, mandatory fails, HR review modal trigger. |
| `src/app/vacancies.tsx` | `/vacancies` | **Complete** | Active vacancy directory, search filter, salary formatting (`₹ LPA` in `en-IN` locale), experience formatting, mandatory skills card, cache invalidation CTA. |
| `src/app/batch.tsx` | `/batch` | **Complete** | Candidate limit selector (5/10/20/30), WebSocket live pipeline progress bar, batch candidate results list with score badges. |
| `src/app/config.tsx` | `/config` | **Complete** | Engine thresholds, LLM weights, fast-track bypass margin/coverage thresholds, component score weights, live weight sum validation. |
| `src/app/candidates/index.tsx` | `/candidates` | **Basic / Complete** | Searchable candidate directory, filtering by filename/ID/department/job, `DenseRow` candidate list, page badges, `ScoreBadge`. |
| `src/app/candidates/[id].tsx` | `/candidates/[id]` | **Basic / Complete** | Detailed candidate profile, metadata banner, top match card with sub-scores & recommendation, text viewer with expand/collapse, `HrReviewModal` integration. |
| `src/app/explore.tsx` | `/explore` | **Dead Code** | Unused starter boilerplate code left over from original Expo template. Not included in `SidebarLayout` or linked anywhere. |

---

## 2. Design System Spec Drift (`UI.md` Section 1 Token Violations)

The following inline hardcoded colors, spacing deviations, and radius mismatches violate `UI.md` Section 1 tokens:

| File Name | Line Number | Quoted Code | Token It Should Be |
|---|---|---|---|
| `src/app/index.tsx` | L66 | `color="#FFFFFF"` | Token `text-text-inverse` / `surface` (`#FFFFFF`) |
| `src/app/index.tsx` | L80 | `className="flex-row gap-3"` | Section 1 Spacing token `gap-4` for section rhythm |
| `src/app/index.tsx` | L144 | `color="#4F46E5"` | Token `primary` (`#4F46E5`) |
| `src/app/index.tsx` | L154 | `color="#16A34A"` | Token `success` (`#16A34A`) |
| `src/app/index.tsx` | L164 | `color="#D97706"` | Token `warning` (`#D97706`) |
| `src/app/index.tsx` | L174 | `color="#2563EB"` | Token `info` (`#2563EB`) |
| `src/app/cv-match.tsx` | L104 | `className="gap-4 mb-8"` | Compact Section 2 Spacing rhythm (`mb-4` instead of spacious `mb-8`) |
| `src/app/cv-match.tsx` | L125, L142 | `color="#FFFFFF"`, `color="#9CA3AF"` | Tokens `text-text-inverse` and `text-text-faint` |
| `src/app/cv-match.tsx` | L224, L317, L367 | `color="#4F46E5"` | Token `primary` (`#4F46E5`) |
| `src/app/cv-match.tsx` | L248 | `color="#16A34A"` | Token `success` (`#16A34A`) |
| `src/app/cv-match.tsx` | L266 | `color="#DC2626"` | Token `danger` (`#DC2626`) |
| `src/app/vacancies.tsx` | L100, L137, L144 | `color="#6B7280"`, `color="#9CA3AF"` | Tokens `text-text-muted` and `text-text-faint` |
| `src/app/vacancies.tsx` | L112 | `rounded-sm` | Token `rounded-md` (8px standard card/badge radius) |
| `src/app/vacancies.tsx` | L178, L198 | `color="#16A34A"`, `color="#4F46E5"` | Tokens `success` and `primary` |
| `src/app/batch.tsx` | L127, L132, L158 | `color="#4F46E5"`, `color="#16A34A"` | Tokens `primary` and `success` |
| `src/app/config.tsx` | L104, L110 | `color="#4F46E5"`, `color="#16A34A"` | Tokens `primary` and `success` |
| `src/app/config.tsx` | L230 | `rounded-sm` | Token `rounded-md` (8px standard radius) |
| `src/app/candidates/index.tsx` | L89 | `color="#4F46E5"` | Token `primary` (`#4F46E5`) |
| `src/app/candidates/[id].tsx` | L40, L55, L73, L98 | `color="#4F46E5"` | Token `primary` (`#4F46E5`) |
| `src/app/candidates/[id].tsx` | L130 | `rounded-sm` | Token `rounded-md` (8px radius) |

---

## 3. Component Reuse Audit

| Screen | Custom / Reimplemented UI | Recommended Primitive |
|---|---|---|
| `src/app/index.tsx` | System Health rows (L197-L232) manually built with flex-row views. | `DenseRow` primitive for consistent system status rows. |
| `src/app/cv-match.tsx` | Mode Selector Tabs (L116-L150) manually built with custom pressables. | Segmented Control / Tab primitive. |
| `src/app/cv-match.tsx` | Match Analysis results cards manually formatted inside screen. | Reusable `MatchAnalysisCard` component. |
| `src/app/batch.tsx` | Candidate Limit Selector buttons (L85-L104) manually looped pressables. | Segmented Control / Toggle Group primitive. |
| `src/app/config.tsx` | Component Score Weight input rows (L227-L245) manually built. | `DenseRow` with embedded input or dedicated weight control component. |

---

## 4. Accessibility & Interaction Audit

| File Name | Line Number | Touchable Element | Missing Accessibility / Interaction Attributes |
|---|---|---|---|
| `src/app/cv-match.tsx` | L117, L134 | Mode Selector Tabs (`Pressable`) | Missing `hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}` and `accessibilityRole="button"`, `accessibilityLabel`. |
| `src/app/batch.tsx` | L86 | Candidate Limit buttons (`Pressable`) | Uses numeric `hitSlop={8}` instead of object `{ top: 8, bottom: 8, left: 8, right: 8 }`. Missing `accessibilityRole="button"` and `accessibilityLabel="Limit 5"`. |
| `src/app/config.tsx` | L230 | Component Weight item rows | Input row lacks `accessibilityLabel` for screen readers. |
| `src/app/SidebarLayout.tsx` | L63, L106 | Mobile Drawer close & Floating toggle (`Pressable`) | Missing `accessibilityLabel="Close sidebar"` and `accessibilityLabel="Open navigation menu"`. |

---

## 5. State Completeness Audit

| Screen | Loading State | Error State | Empty State | Status |
|---|---|---|---|---|
| `src/app/index.tsx` | `ActivityIndicator` / `healthLoading` | System offline status badge fallback | N/A (Fixed Dashboard Layout) | **Complete** |
| `src/app/cv-match.tsx` | Progress bar & status message | Error Card banner (`uploadError` / `textError`) | N/A (Form input view) | **Complete** |
| `src/app/vacancies.tsx` | `ActivityIndicator` spinner | Error Card + "Try Refreshing" button | `<EmptyState title="No job openings found" />` | **Complete** |
| `src/app/batch.tsx` | Live Progress Box + `ActivityIndicator` | Error Card banner | **MISSING** (No empty state when 0 matches returned or prior to starting) | **Incomplete** |
| `src/app/config.tsx` | `ActivityIndicator` spinner | Error Card banner | N/A (Config Form) | **Complete** |
| `src/app/candidates/index.tsx` | `ActivityIndicator` spinner | Error Card + "Try Again" button | `<EmptyState title="No candidates found" />` | **Complete** |
| `src/app/candidates/[id].tsx` | `ActivityIndicator` spinner | Error Card + "Back to Directory" button | Error Card fallback for missing record | **Complete** |

---

## 6. Data-Hook Health

| Hook File | Status | Wired Screen(s) | Health & Issues |
|---|---|---|---|
| `src/hooks/useJobs.ts` | **Healthy** | `index.tsx`, `vacancies.tsx` | Fetches active vacancies, handles loading & error states. |
| `src/hooks/useCvUpload.ts` | **Healthy** | `cv-match.tsx` | Polling loop up to 250 retries (12.5 min max), handles error & status. |
| `src/hooks/useMatchConfig.ts` | **Healthy** | `config.tsx` | Loads and updates match engine config settings. |
| `src/hooks/useBatchProgress.ts` | **Healthy** | `batch.tsx` | Connects to WebSocket progress stream & triggers batch processing. |
| `src/hooks/useCandidates.ts` | **Healthy** | `candidates/index.tsx` | Fetches candidates list with search query support. |
| `src/hooks/use-color-scheme.ts` | **Stale / Legacy** | None | Leftover Expo starter hook. NativeWind v4 handles themes via Tailwind `dark:` classes. |
| `src/hooks/use-theme.ts` | **Stale / Legacy** | `explore.tsx` (Dead Code) | Leftover Expo starter hook. Unused in NativeWind design system. |

---

## 7. Known Gap Confirmation

1. **Gap 1: Candidate List & Candidate Detail Screens**:
   - **Status**: **Basic Functional Version Built** (`src/app/candidates/index.tsx` & `src/app/candidates/[id].tsx`).
   - **Remaining Polish Needed**:
     - Department filter tabs/dropdown in list view.
     - Score classification filter (HIGH / MEDIUM / LOW).
     - Candidate deletion CTA.

2. **Gap 2: Home Dashboard Pending Panels**:
   - **Status**: **Still Missing**.
   - **Pending Items**:
     - *"Needs Attention"* panel (highlighting unreviewed candidates, OCR warning flags, or failed parsing jobs).
     - *"Recent Activity"* `DenseRow` feed (displaying real-time recently parsed candidates).
     - *"Top Vacancies"* breakdown card list.

---

## 8. Master Summary & Issue Remediation Table

Below is the consolidated table listing every screen, component issue, and fix size:

| Screen / Component | Diagnostic Issue Description | Fix Size |
|---|---|---|
| `src/app/explore.tsx` | Dead code leftover from Expo starter template. Should be deleted. | **Trivial** |
| `src/hooks/use-theme.ts` | Unused legacy theme hook from starter template. | **Trivial** |
| `src/hooks/use-color-scheme.ts` | Unused legacy color scheme hook. | **Trivial** |
| `src/app/index.tsx` | Raw hex colors used in icon props (`#FFFFFF`, `#4F46E5`, `#16A34A`, `#D97706`, `#2563EB`). Section gap `gap-3` instead of `gap-4`. | **Trivial** |
| `src/app/index.tsx` | Missing Dashboard panels: *"Needs Attention"* panel, *"Recent Activity"* feed, and *"Top Vacancies"* breakdown. | **Medium** |
| `src/app/cv-match.tsx` | Raw hex colors in icon props. Spacious section margin `mb-8` instead of `mb-4`. | **Trivial** |
| `src/app/cv-match.tsx` | Mode Selector Tabs missing `hitSlop` object and accessibility attributes. | **Trivial** |
| `src/app/cv-match.tsx` | Mode Selector Tabs and Match Analysis results could be extracted into reusable primitives. | **Small** |
| `src/app/vacancies.tsx` | Raw hex colors in icon props. Mandatory skills card uses `rounded-sm` instead of `rounded-md`. | **Trivial** |
| `src/app/batch.tsx` | Raw hex colors in icon props. Progress bar uses hardcoded `h-2`. | **Trivial** |
| `src/app/batch.tsx` | Limit selector `Pressable`s use scalar `hitSlop={8}` instead of object `{ top: 8, bottom: 8, left: 8, right: 8 }` and lack accessibility labels. | **Trivial** |
| `src/app/batch.tsx` | Missing empty state component when 0 batch matches are present prior to processing. | **Small** |
| `src/app/config.tsx` | Raw hex colors in icon props (`#4F46E5`, `#16A34A`). Weight items use `rounded-sm`. | **Trivial** |
| `src/app/config.tsx` | Weight item text inputs lack `accessibilityLabel` attributes. | **Trivial** |
| `src/app/candidates/index.tsx` | Raw hex color `#4F46E5` in icon props. | **Trivial** |
| `src/app/candidates/index.tsx` | Lacks classification filter (HIGH / MEDIUM / LOW) and department filter controls. | **Small** |
| `src/app/candidates/[id].tsx` | Raw hex colors in icon props (`#4F46E5`). Recommendation card uses `rounded-sm`. | **Trivial** |
| `src/components/ui/Sidebar/SidebarLayout.tsx` | Mobile menu close and floating toggle `Pressable`s missing explicit `accessibilityLabel`s. | **Trivial** |
