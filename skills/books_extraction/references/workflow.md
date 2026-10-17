# Sequential individual pages; manual compilation

Set `$skillDir`, `$bookTool`, and `$bookRoot` to the actual skill/helper/shared root. In this repository (from the repo root):

```bash
export TETEA_ROOT="$PWD"; bookRoot="$TETEA_ROOT"
skillDir="$TETEA_ROOT/skills/books_extraction"; bookTool="$skillDir/scripts/book_tools.py"
```
 The invocation remains level, subject, form and physical PDF range:

```powershell
python $bookTool session csee biology 4m2 6-15 --root $bookRoot
python "$skillDir/scripts/book_sequence.py" next --book $sessionPath --root $bookRoot --prep --measure
```

Session prints the PDF, source/book identity and `book` path; assign this temporary range record to `$sessionPath`. It lives in `tie/output/<level>/<subject>/temp/<book-slug>__pages-0006-0015.json` and contains pending coverage only. It is not a compiled book. `next` returns the first unfinished page's `page_json`; assign it to `$pagePath`. Render/transcribe only that one physical page and all its logical surfaces. No OCR, PDF text APIs or cached text hints. Minimal neighboring context is read-only, never a multi-page transcription batch.

## Per-page call budget (strict)

Token cost is a first-class requirement. **Do not exceed the budget below**, and do not add exploratory calls "to be safe" — quality comes from the accuracy of these calls, not from making more of them.

A page **without a figure: 5 tool calls, exactly one an image read**. A page **with a figure: 7 tool calls, exactly two image reads**. The complete sequence is (steps 5–6 are figure-only):

| # | Call | Notes |
|---|------|-------|
| 1 | `book_sequence.py next --prep --measure` | selects the page, renders it, prints geometry |
| 2 | read the prep render (`page-00NN.png`, 150 dpi) | image read #1 |
| 3 | write the one-page input JSON | |
| 4 | `book_batch.py --book $pagePath --input $json --root $bookRoot` | applies + crops |
| 5 | *(figure pages only)* `measure.py --shrink <asset> --out <preview>` | |
| 6 | *(figure pages only)* read that preview | image read #2, the last one |
| 7 | `book_tools.py checkpoint --book $pagePath --root $bookRoot --verified` | asserts the one brief check, promotes |

Permitted additions — each **at most once per page**, and only when a real defect exists:

- one `--describe <type>` call for a genuinely unknown content type;
- one extra small crop read when a measured edge is genuinely ambiguous;
- one reset-and-re-apply when a crop is clipped.

Everything else is forbidden: re-rendering at 300 dpi, generating overlay/grid images to measure by eye, reading any image twice, re-reading an asset whose crop already measured cleanly, opening the viewer, running full `build`/`validate` per page, or re-measuring a page already measured. If a page genuinely needs more than the budget, stop and say why instead of silently spending it.

## Working files and finished files

- `temp/<book-slug>__page-0006.json`: unfinished page, saved immediately and after edits so interruption loses no prior pages.
- `<form-folder>/<book-slug>__page-0006.json`: finished independent page JSON only. Literal form folders are `form one` through `form six`.
- Subject `temp/`: session records, unfinished pages, `.bak`, atomic `.tmp` files, input snippets, logs, ad hoc scripts and other scratch work. Do not leave these files in form folders. Create folders only on demand.
- Source renders and permanent referenced assets retain their existing `pages/books` and `assets/books` locations; never move/delete assets needed by finished pages as scratch cleanup.

## Measure with numbers, not repeated image reads

Image reads dominate token cost, so keep them to **one per page**. Read only the small prep render (`pages/books/<book-id>/page-00NN.png`, 150 dpi) to understand layout and wording. Take every coordinate from the measurement helper instead of eyeballing renders or overlay grids. `next --prep --measure` renders the page and prints the table in the same call:

```powershell
python "$skillDir/scripts/book_sequence.py" next --book $sessionPath --root $bookRoot --prep --measure
```

For a two-column page restrict the scan to one column at a time with `--x0`/`--x1` (prep px), or call the helper directly:

```powershell
python "$skillDir/scripts/measure.py" --page-json $pagePath --root $bookRoot [--x0 90 --x1 335]
```

It prints, in `render_size_px` coordinates ready to paste into the input snippet:

- `text_lines` — grouped ink bands `[x0,y0,x1,y1]` (headings, paragraphs, list lines, captions, labels).
- `h_lines` / `v_lines` — long horizontal/vertical rules, i.e. figure-box tops/bottoms and sides.
- `banners` — coloured bands (e.g. the activity/experiment header) with hex colour.
- `watermark` — the top-band light-grey watermark, for the `exclusions` block.

Rules of thumb: figure crop bounds come from `h_lines`/`v_lines` (or the enclosing `text_lines` span when a figure has no box); the activity banner comes from `banners`; the watermark `bbox_pt` is the reported region multiplied by `width_pt/654`. Only open a small crop when a measured edge is genuinely ambiguous (e.g. a figure whose labels sit outside the ruled box); shrink a large asset with `measure.py --shrink <asset> --out <preview>` before reading it, and never re-read a finished asset to "confirm" a crop that already measured cleanly.

## Extract, save, then advance

1. Read the current page image directly. Capture its visible educational content, printed numbers, headings, order and measured regions using the registered types. Essential front metadata is in scope only for page 1.
2. Automatically crop visual objects; retain labels and transcribe notation/tables using notation-assets. Give crops a quick glance for obvious clipping/readability, fixing an obvious issue once when practical.
3. Save input snippets in the subject temp folder. Use the writer against the current working page JSON:

```powershell
python "$skillDir/scripts/book_batch.py" --book $pagePath --input $inputJson --root $bookRoot
```

Exactly one physical page is allowed. Within-page edits are allowed. Unknown content types still require explicit user permission; preserve that region/page as partial meanwhile.

4. Make one brief sanity check for obvious omissions, wrong page numbers and unreadable crops. No repeated sentence/layout audit or mandatory viewer/full integrity checks. Record state/QA/status honestly: `verified` records this brief page check; use complete or complete_with_issues only when completion gates pass. Finish in one step with `--verified`, which asserts that check, marks the pages `verified`/QA `passed` and the crops `ok`, then validates and promotes:

```powershell
python $bookTool checkpoint --book $pagePath --root $bookRoot --verified
```

Omit `--verified` (plain `checkpoint`) when the page has an open issue you are recording honestly; it then stays in temp with your state/QA. Never pass `--verified` to assert a check you did not make.

The helper automatically puts a finished `__page-...json` into its form folder and reports its new `book` path. Its unfinished work and backups remain in temp. Use the returned path if opening the page afterwards; the old working path no longer exists after promotion. Failed structural checks leave the existing checkpoint intact. These checks never certify an intensive audit.

5. Call `next` again using the same `$sessionPath`. It skips matching completed pages, resumes an unfinished temp page, or initializes the next missing page. Finish/save page 6 before extracting page 7 and continue ascending. Every finished page remains independently usable. External references to other physical pages remain external; no neighbor JSON is required. Keep local groups and page-qualified stable IDs.

6. When `next` reports `all_pages_saved: true`, report the individual page paths/coverage and stop. **Do not compile pages, create a combined range/book JSON, invoke a merge tool or concatenate the files. The user compiles manually.** Existing older combined outputs may be retained in temp as historical/reference material; do not silently discard or split them during ordinary extraction.

## Resume and view

Resume only matching source/scope/schema. Do not re-extract or overwrite completed pages. Preserve uncertainties and unresolved types; an unfinished page remains in temp and is returned for resume. Older session records that contain extraction content need explicit migration before this workflow; keep the content intact.

The viewer lists finished pages in form folders and excludes subject temp folders from its normal catalogue. A working page can still be opened explicitly for a focused check. Viewer use and full build/validate are optional when requested or a concrete issue justifies them. The viewer (`books2json/serve.py`) is not part of this repository. Report coverage, page paths and remaining issues without implying compilation or an intensive audit.
