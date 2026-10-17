# Compact contract and reusable writer

Canonical output remains `book-pages-1.1`, with the exact embedded registry and source hash. No schema change. The writer accepts only agent-supplied visual transcription; it never reads text layers, performs OCR, guesses captions or decides hierarchy. Read detailed schema/notation references only for encountered content requiring them.

## Single-page input

Save UTF-8 input containing exactly one physical page, then run against the standalone page JSON returned by book_sequence.py next. Multi-page input and range-sized transcription targets are rejected:

```powershell
python "$skillDir/scripts/book_batch.py" --book $pagePath --input $batchJson --root $bookRoot
python "$skillDir/scripts/book_batch.py" --book $pagePath --describe paragraph,heading,list,table
```

`--describe names` lists supported types/group kinds. Other values return exact required/optional fields and closed subtypes from the partial's embedded registry. Inspect a new kind before using it; new types/subtypes/group kinds still need explicit user approval.

```json
{
  "book_id":"<session book_id>", "source_sha256":"<session source hash>",
  "pages":[{
    "pdf_page":14, "transcribed":true,
    "surfaces":[{
      "printed_page":"8", "render_size_px":[2223,3128],
      "elements":[
        {"key":"heading14","type":"heading","bbox":[280,270,1000,335],"text":"Exact printed heading","payload":{"level":3,"role":"subsection"}},
        {"key":"prose14","type":"paragraph","bbox":[280,350,1080,620],"text":"Exact visually transcribed text."},
        {"key":"figure14","type":"figure","bbox":[290,680,1060,1190],"crop":{"kind":"photo","dpi":150,"printed_label":"Figure 1.5","description":"Sources of carbohydrates"}},
        {"key":"caption14","type":"caption","bbox":[350,1220,1030,1280],"text":"**Figure 1.5:** Sources of carbohydrates","payload":{"target_refs":["@figure14"]}},
        {"key":"number14","type":"page_number","bbox":[240,2920,310,3000],"text":"8"}
      ]
    }]
  }],
  "groups":[{"key":"section14","kind":"subsection","title":"Exact printed heading","element_refs":["@heading14","@prose14","@figure14","@caption14"]}],
  "relations":[], "review":[], "exclusions":[]
}
```

This example demonstrates mechanics, not complete source content. Include every visible header/footer, caption, number and educational region from the real images.

## Coordinates, ownership and references

- `bbox` is `[x0,y0,x1,y1]` in displayed-page PDF points by default. With `render_size_px`, all supplied boxes—including nested list-item boxes—use that **full physical page render's actual pixel dimensions**. If viewing a resized image, use its actual displayed dimensions and matching coordinates. No guessed DPI scaling or quadrant boundaries. Measured multi-up surfaces need separate `bbox` and printed number values.
- `printed_page` is an exact string or null. Nullable pages specify `printed_page_status: not_printed|illegible` and `printed_page_system: none|roman|arabic|other` as observed. Printed numbers also need explicit `page_number` elements.
- Surface IDs default to `s-p0014-01`; element IDs use page/surface plus a stable supplied `key`. Keys are unique within a batch. Use semantic keys rather than renumbering on edits. Existing content is appended, never replaced; conflicts and verified-page edits are rejected. A matching pending surface may be reused by its exact ID.
- `@key` references resolve only in reference fields. Links to previous batches use their canonical IDs. Raw printed text remains untouched even if it begins with `@`.
- Group membership may be supplied as group `element_refs` or element `groups`. The writer adds matching reverse links. Supply `parent_ref` when hierarchy is observed; the writer checks cycles, not meaning.
- Caption `target_refs` generate `caption_of` relations. Supply semantic continuation/reference relations explicitly; the writer does not infer them. Relations use `kind`, `from_ref`, `to_ref`, `resolution`, `printed_text`; observed external targets require the exact out-of-range page as in schema.md.
- `crop` invokes the existing PDF crop helper using the measured element box. Photo/map uses JPEG; other diagrams PNG. Labels stay in the crop and captions stay separate. Crop QA starts pending; visually inspect every saved crop before setting `crop_check`. For deskew/trim/advanced assets, read notation-assets.md.
- Every canonical type accepts `payload` with the exact registry fields. `text` is shorthand for `payload.text`. Lists use `style` and `items:[{label_printed,text,bbox?,items?}]`. Tables use `columns`, `header_rows`, `rows:[[cell,...]]`; each cell has `text`, optional spans/header/blank/figure_ref/blocks. Covered merged positions are omitted. Read notation guidance for tables/formulas/chemistry.
- Legibility defaults clear; supply `partial|illegible`, evidence and review where required. Uncertainty markers are `[[?word]]` or `[[illegible]]`. No reconstruction of unavailable text. Keep source defects distinct from unfinished extraction; do not weaken completion gates by renaming blocking issues.

## Checkpoint and completion

Token cost is a first-class requirement. Follow the strict per-page call budget in workflow.md: a page without a figure takes **5 tool calls, exactly one of them an image read**; a page with a figure takes **7 tool calls, exactly two image reads**. Read the prep render once, take every coordinate from `measure.py`, and do not add exploratory calls, extra renders, overlay images, repeated reads or viewer tours. Quality comes from accurate calls, not more of them.

The writer/checkpoint checks payloads, runs, IDs, boxes, membership, references, table grids and registry fingerprint. It skips external file integrity work, saves only on success and returns compact stats. On its own it never sets QA passed or completes a range; `checkpoint --verified` does so only because you explicitly assert that you made the brief check. `transcribed:true` only records the agent's assertion that that page's visible content has been transcribed.

After one brief visual sanity check of the current page, finish in one step with `checkpoint --verified` (or plain `checkpoint` when recording an open issue honestly). Its completion gates still reject missing/unknown content. Full build/validate, browser tours and repeated source/asset comparisons are not routine requirements; use them only when requested or a specific problem justifies them. Report coverage and remaining issues without claiming an intensive audit.

For sequential range extraction, finish/save/validate this page before opening the next for transcription. Follow workflow.md for next/resume, temporary work and finished-page promotion; compilation is manual. Retain every standalone page JSON; never compile them automatically.

Current output policy: finished individual page JSONs go in the matching form folder; unfinished pages/session records/backups/scratch work go in the subject temp folder. Compilation is exclusively manual by the user.
