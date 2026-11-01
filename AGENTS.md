# Iran Archives website

Read DEPLOYMENT.md before publishing.

Daily research updates MUST change only `data/archive.json` in this repository.
Preserve all ten archive groups, existing IDs, rows, source links and provenance.
Never copy the Drive/Library vertical timeline HTML into this site's UI.

The canonical UI is `_layouts/dashboard.html`, used by `home.html` and
`dashboard.html`. `index.html` is excluded by Jekyll intentionally. Do not remove
that exclusion, add `.nojekyll`, change these entry points, or replace the layout
as part of a data refresh. UI changes require a separate explicit user request.

Before publication run `node scripts/validate-site.mjs`. Compare the new record
IDs with the previous data file; do not silently drop records. Read the fresh
branch SHA and use a conditional, non-forced update. Verify the public JSON and
all seven dashboard tabs after Pages finishes deploying.
