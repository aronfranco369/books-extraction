# Physics Form One — latest supplied transcript import

Imported from the user-approved file
`physics-form-one__pages-1-240__complete_text-v3 (1).txt`.
`source-transcript.txt` preserves those uploaded bytes unchanged.

## Coverage

The user confirmed that the actual book ends at physical PDF page 232. All pages
1–232 have one standalone JSON in `tie/output/csee/physics/form one/`. The
filename/header's 1–240 range is stale; pages 233–240 are not counted as missing.
Printed pages iii–vi and 1–226 are retained, along with two unnumbered pages.
The supplied page total is recorded as user-confirmed, not independently measured.

## Review status

The user authorized publishing this latest supplied text. These JSONs remain
`partial`, with visual QA `pending`: the original PDF and images were not supplied.
The PDF hash and page/element geometry are unknown. The book ID identifies the
transcript hash, never a fabricated PDF hash. They display in books2json before
image assets are available, using 164 pending image placeholders.

Source discrepancies remain visible in review notes:

- The contents list Chapter Eight as Linear motion and Chapter Nine as Work,
  energy and power, but later headings introduce Work as Chapter Eight, followed
  by Light, Magnetism, Electricity and Chapter Twelve revision material.
- Glossary/index/end-of-book material on pages 196–200 precedes resumed Work
  content at page 201 and further end matter from page 219.
- Some table widths/merges and group delimiters still disagree internally.

Supplied words and numbering are retained. Import does not certify that another
model's extraction accurately represents the original PDF or correct scientific
answers. These issues require source comparison, not arbitrary relabeling.

## Conversion

Header commentary is treated as provenance, not textbook content. Literal marker
examples in that commentary are not interpreted as actual page markers.
Identifiable broken TeX escapes were repaired, and trailing solution prose was
separated from equations. Original tokens are in `source-blocks.json`; repair
locations and review counts are in `import-report.json`.

Text types use the existing embedded registry. MATERIALS renders as instruction;
NOTE and SUMMARY groups use section memberships while preserving printed text.
Inconsistent table grids retain all supplied cell text with review notes rather
than applying unverifiable merged-cell spans. No original words, equations or
missing page content were invented.

`pending-images.json` lists figure labels, page numbers and asset destinations
for later image attachment. Captions alone may not identify every original visual.

## Validation

- 232 unique ordered page files; no duplicate or missing pages within 1–232.
- 2,526 content elements and 164 image placeholders.
- Parsed content-marker accounting, payload fields, table grids, IDs and group/
  caption references checked by regression tests.
- Ten regression tests pass across Physics and Biology importers.
- All 232 pages exercised through the viewer renderer.
- 946 math expressions checked with KaTeX: zero parse errors.

These checks are conversion/render checks, not PDF visual QA.

From the repository root:

```sh
python tools/import_physics_form_one_text.py
python -m unittest discover -s tools -p 'test*import*.py'
```

Regeneration overwrites draft JSONs. Incorporate manual corrections and image
attachments into the conversion source before re-running.
