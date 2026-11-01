# Daily research updates and protected dashboard publication

The public site uses GitHub Pages' branch-based Jekyll build. Its canonical
presentation lives in `_layouts/dashboard.html`. `home.html` renders it to
`/index.html`; `dashboard.html` renders the same UI to `/dashboard.html`.
`_config.yml` deliberately excludes the **source** `index.html`. This prevents
an obsolete task copying a vertical-timeline export there from replacing the
actual homepage. Never add `.nojekyll` or remove that exclusion.

## Daily update contract

The existing cloud task runs at 21:00 Europe/Berlin, reads the current research
Page, and maintains the ten Google Sheets listed there. Its ONLY website write
target is `data/archive.json`. Drive and Library timeline exports are separate
destinations; their HTML must never be used as this site's template.

JSON structure:

```json
{"schemaVersion":1,"asOf":"2026-10-31","records":[["archive","YYYY-MM-DD","display date","record ID","actor","role/location","topic","summary","detail","quote","source URL","source status"]]}
```

Use exactly 12 values per row: strings, with null also allowed for an empty
source-status value in column 12. Valid archives: iran, us, israel, region,
pahlavi, opposition, meetings, trips, assassinations, developments. Preserve all
existing records and IDs (unique within each archive); revise a record in place
with its source/provenance rather than dropping it. `asOf` is the completed
research cutoff, not the latest future event date. Start the next pass from the
last successful coverage with the existing seven-day overlap.

Read the latest main/data before editing. Use its fresh SHA and a conditional
non-forced update. Do not modify HTML/layouts/scripts/configuration/workflows as
part of a research pass. If a tool cannot write JSON or confirm publication,
report the limitation; never fall back to overwriting HTML.

The dashboard loads this JSON once per visit without using a cached response.
Geographic matches, topics, dossier counts, solar months, source statistics,
date input limits, record counts and future flags are recomputed from it.
Invalid, older or truncated data retains the embedded snapshot and displays a
visible warning. The embedded snapshot also supports offline HTML exports.

## Checks

Run `node scripts/validate-site.mjs` before publication. The regression workflow
also replaces index.html with the legacy timeline **inside the temporary test
runner**, builds with Jekyll, then verifies that the built homepage still has
all seven dashboards, the map, dossiers, people and embedded Vazirmatn.
The workflow separately rejects record loss versus the preceding data version.

After Pages deploys, verify `/`, `/dashboard.html` and `/data/archive.json`;
compare record counts and research cutoff, then exercise all seven tabs, a
Rome map filter, a Promise dossier and a person sidebar. A committed file alone
does not prove that Pages has deployed it. Keep the prior successful site if
verification fails. The public legacy timeline remains at `/timeline.html`.

## Incident: 2026-11-01

The 2026-10-31 nightly commit c7e4ff6 replaced the repaired dashboard homepage
with the legacy timeline again. Its 793 records must be retained, including the
13 additions after the dashboard's 780-row embedded snapshot. Both the visible
research-Page publication paragraph and its Agent Instructions duplicated the
obsolete overwrite instruction; both were corrected on November 1. The hosted
task's saved prompt was also replaced through its existing task settings after
the user signed in. Readback confirmed the same automation ID, ten current
sheet links, a data-only website write target, and no legacy overwrite command.
No duplicate job was created; the enabled daily 21:00 Europe/Berlin schedule
was preserved. Its title is now "آرشیو ایران — به‌روزرسانی ده آرشیو و داده‌های داشبورد".

## Key-person deaths dossier

The requested UI extension adds a dedicated deaths hub and four dossiers:
all events and reactions, targeted attacks/assassinations, combat deaths and
accidental deaths. Categories follow each archive record's event title, with
reactions labelled separately. Counts are records, not victim totals or unique
events. The Raisi helicopter crash remains an accident, recorded once with its
companions in the existing details. The daily data-only publishing contract
continues to protect these dossiers.
