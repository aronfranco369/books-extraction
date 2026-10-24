# Biology Form Six: text-only import, PDF pages 1–40

These two user-supplied transcripts were imported into 40 independent JSONs in
`tie/output/acsee/biology/form six/`. Open them together through books2json's
ACSEE Biology Form Six catalogue. They are review drafts, not certified visual
extractions. No combined book JSON is generated.

- Source named by the transcripts: `acsee_biology_form_6.pdf`.
- Printed title/year reported by the transcripts: Biology for Advanced Level
  Secondary Schools Student's Book Form Six, 2019.
- Coverage: physical PDF pages 1–40; printed pages ii–vi and 1–33, plus two
  unnumbered opening pages.
- Original uploads are preserved byte-for-byte in the two `pages-*.txt` files.
- `source-blocks.json` preserves every parsed content block and its original
  wording before whitespace/markup normalization.
- `import-report.json` records source hashes, coverage and conversion counts.
- `pending-images.json` lists caption-derived figure IDs for later asset work.

## Draft representation

The existing book-pages content types and embedded registry are retained.
`status` is `partial`, page state is `transcribed`, and visual QA is `pending`.
The PDF itself was not supplied: PDF hash, total source page count, page size,
rotation and bounding boxes are explicitly null. Transcript hashes identify the
actual inputs; they are never represented as a PDF hash. These drafts are
viewer-compatible imports and do not pass the strict geometry/source-evidence
requirements for finished visual extraction. Do not run `checkpoint --verified`
on them without actually obtaining and checking the missing evidence.

Pending figure records have `asset_status: pending` and no asset file/hash or
geometry. The viewer displays an Image pending placeholder without requesting a
nonexistent file. Nineteen captions identify figures, but this is not a claim
that every visual object in the original PDF has been located.

## Normalization and review

Ordinary wrapped prose is joined without changing wording. Inline marker forms
and `[END_EXERCISE]` are supported. Flattened contents entries are split at the
surviving tab/page references. Lists are split on successive printed labels,
retaining internal references such as “steps (ii) to (iv)” within their item.
Bare TeX chemistry and numeric unit expressions from the first upload are wrapped
in inline math delimiters so the viewer can render them.

Table 1.1 on physical page 16 lost row separators. Its header and five data rows
were reconstructed from surviving tabs and text boundaries, preserving all words.
An open review note calls this out. Compare its row boundaries and scientific
wording with the PDF. No biological claims in the uploads were corrected.
Table 1.2 retains its supplied row/tab boundaries.

Validation checks page coverage, source marker accounting, payload fields,
reading order, IDs, group/caption references and table dimensions. A viewer
render check exercised all 40 pages and 19 placeholders without missing-object
or unknown-type errors. Neither check establishes PDF transcription accuracy.

## Reproduction and later images

From the repository root:

```sh
python tools/import_book_text.py
python -m unittest discover -s tools -p test_import_book_text.py
```

The importer is specific to these two files and the recoverable Table 1.1;
it rejects unexpected layouts rather than silently guessing. Re-running it
rewrites these draft outputs, so do not re-run after manual edits or attaching
images unless those changes have been incorporated into the conversion source.

When image files arrive, match them to the page and printed figure label in
`pending-images.json`, copy them into the indicated assets directory, populate
actual asset fields and hashes, and change the figure asset status. Text stays
readable before and after that step. Remaining provenance/geometry/visual-review
issues must be resolved separately before claiming full extraction completion.
