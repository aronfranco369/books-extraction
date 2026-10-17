# Page-session contract additions (1.1)

The canonical current root is produced by `book_tools.py session`. Each range embeds `schema: {registry: <full content-types object>, sha256: <fingerprint>}`. Fingerprint is SHA-256 of UTF-8 JSON serialized with sorted keys, ensure_ascii=False, and separators (",", ":"). No sibling registry file is needed. The validator also reads legacy file-based snapshots for older extracts.

Metadata is limited to `{level, subject, form, title_printed, language, edition_year_printed}`. Level/subject/form come from routing; nullable printed fields require observed evidence. Omit the old publication_statements/catalogue/evidence metadata collection. `extraction.front_details_in_scope` is true only when requested pages begin at 1. Source provenance, geometry, element boxes and asset evidence remain required.

The partial's requested physical page range defines completion. Its groups and memberships contain only local IDs. Relations may use `resolution: external`, `to_ref: null` and `external_target: {book_id, pdf_page, printed_page: string|null, label_printed: string|null}` for an observed target outside this range in the same source. External links do not require another JSON to render; unresolved targets remain unresolved. Local links retain the contract below. Prefer page-qualified stable IDs across partials. Output paths and scope follow SKILL.md/workflow.md; do not use the legacy book.json destination shown by older extracts.

# Book-pages JSON contract

Version: `book-pages-1.1`. Registry: `content-types.json`. This is an extraction record, not a reader-layout specification. The helper performs structural/semantic checks; visual fidelity is checked separately.

## Root

```json
{
  "schema_version":"book-pages-1.1",
  "book_id":"sample-012345abcdef",
  "status":"partial",
  "schema":{"registry": {},"sha256":"<actual snapshot hash>"},
  "metadata":{"level":"csee","subject":"biology","form":2,"title_printed":null,"language":null,"edition_year_printed":null},
  "source":{"pdf":"tie/books/.../book.pdf","sha256":"<actual PDF hash>","pdf_page_count":20,"completeness":"unchecked"},
  "extraction":{"prompt_version":"books-extraction-1.1","method":"visual","requested_pdf_pages":[1,2],"front_details_in_scope":true,"runs":[]},
  "pages":[],"groups":[],"relations":[],"figures":[],"exclusions":[],"review":[],"stats":{}
}
```

`status`: partial, complete, complete_with_issues, failed. A complete extraction is relative to the explicit requested pages; it need not mean the PDF contains a complete printed book. `source.completeness`: unchecked, apparently_complete, incomplete. Record missing-source evidence in review, not fabricated content. Never infer publication/revision/syllabus facts from a filename; bibliographic evidence includes page/surface/element IDs. Catalogue assertions remain separate from printed metadata.

`source.pdf` is relative to the supplied root where possible; an absolute path is permitted for a user-selected external PDF. Hash all input bytes. Each book stores an exact registry snapshot and digest. The validator loads that snapshot and checks the version; permission-controlled changes do not retroactively change older contracts.

## Pages and logical surfaces

```json
{
  "pdf_page":7,"width_pt":595,"height_pt":842,"rotation":0,
  "state":"transcribed","visual_qa":"pending",
  "surfaces":[
    {
      "id":"s-p0007-01","order":0,"bbox_pt":[0,0,595,842],
      "printed_page":"1","printed_page_system":"arabic",
      "printed_page_status":"observed","elements":[]
    }
  ]
}
```

Page `state`: pending, transcribed, validated, verified. `visual_qa`: pending, passed, flagged. Surface `printed_page_system`: arabic, roman, other, none. `printed_page_status`: observed, not_printed, illegible. With not_printed/illegible use null instead of inferring a number. `order` is 0-based reading order within its parent array. Multiple surfaces represent facing/four-up pages; measure them rather than assume quadrant boundaries. Preserve duplicate logical numbers and fragment captures.

All boxes are `[x0,y0,x1,y1]`, top-left of the **displayed, rotation-applied physical page**, in PDF points. Boxes must be positive and fit within their page and surface. Surface transforms may be documented under optional `notes`; crop output records deskew/trim. A printed number is also a `page_number` element at its own measured box with exact text. Running headers/footers are elements even when repeated.

## Page elements

```json
{
  "id":"e-p0007-001","type":"heading","surface_id":"s-p0007-01",
  "order":0,"bbox_pt":[60,40,520,100],"group_refs":["g-ch01"],
  "payload":{"text":"Current electricity","level":1,"role":"chapter","label_printed":"Chapter One"},
  "legibility":"clear","notes":[]
}
```

Every element has these envelope fields; `notes` is optional. `payload` obeys its registry definition. IDs are stable creation-time identifiers, not indices to renumber after insertions. Array order/`order` must agree. `legibility`: clear, partial, illegible. Every printed subpart is separate, either as an element or a nested labelled item with a box where applicable. Preserve column reading order and position; optional layout observations are descriptive, not CSS.

All textual payloads use ACSEE-style `text` and deterministic `runs`: text `{t:"text",v:...,b:true?,i:true?}`, math `{t:"math",v:...}`, blank `{t:"blank"}`, uncertain `{t:"uncertain",v:...}`, illegible `{t:"illegible"}`. Build regenerates runs in paragraph/heading/caption/item/cell/line/turn text dictionaries. Uncertainty stays in text as `[[?word]]`/`[[illegible]]`; do not remove it. Plain labels do not need runs. Inline math uses `\( ... \)`; `math.payload.latex` and Chemfig `source` have no delimiters.

Registry types have semantic definitions plus required/optional payload fields. Undeclared payload keys are errors. Allowed optional fields across types: `text`, `runs`, `label_printed`, `title`, `source_printed`, `continuation_of`, `continued_by`. The last two identify element IDs, not prose. Arbitrary printable labels/titles don't constitute new types.

## Content vocabulary

Read the registry for exact field names. Core types:

- `paragraph`; `heading` with `level` and role (title, part, chapter, section, subsection, subsubsection, other); `running_header`; `running_footer`; `page_number`.
- `exercise`, `question`, `example`, `solution`, `activity`, `task`, `project`, `note`, `summary`, `objectives`, `instruction`, `answer`, `proof`. Each holds its own printed introductory text and exact label; separate following elements are linked to the same group. Do not copy an entire exercise into both its container introduction and its question elements.
- `list`: style numbered/lettered/roman/bullet/plain; items hold exact labels, text/runs, optional box and nested items. `mcq_options` holds printed option keys and text/figure refs; `matching` holds exact list titles and entries. No inferred marks or generated answers.
- `table`: label/caption, `columns`, `header_rows`, `rows`; cells have text/runs/header/rowspan/colspan/blank/figure_ref. Optional cell `blocks` supports a display formula/chemical structure/figure inside a cell. Covered merged positions are omitted. Each page stores its own table segment, including any actually reprinted headers; one table group links segments without erasing repetition.
- `figure`, `map`, `image`: `ref` into root `figures`; `caption`: text and `target_refs` to objects. Maps preserve full legend/grid/scale and printed map metadata. Panels may be separate figure records linked by a group.
- `math`: latex plus optional printed equation label; `chemical_structure`: format chemfig, editable source, optional rendered_asset; chemistry formulas/reaction equations with linear layout use math/mhchem, spatial schemes use chemical_structure.
- `verse`: ordered `stanzas`, each with ordered text/runs lines and optional indentation; `dialogue`: ordered turns with exact speaker label and text/runs, optional stage direction. No loss of stanza breaks/turn order.
- `definition_list`, `reference_list`, `index`, `toc`: ordered entries preserving exact terms/definitions/bibliographic strings/printed page references. Resolved links are separate from printed strings. Bibliography is not rewritten into normalized citations.
- `footnote`: exact label/text plus optional marker refs; `code`: literal language/text; `publisher_notice`; `cover_detail` (printed content or image ref); `unresolved_region` (reason, preserved evidence, proposed_type if novel).

Footnotes/code are included for broader book coverage even where not established by the samples. Unknown content must follow the explicit permission workflow, not silently enlarge the vocabulary.

## Groups and relations

Groups are non-owning semantic memberships: `{id, kind, label_printed, title, parent_ref, element_refs}`. Optional `notes`. They link chapter/section hierarchy and cross-page lists, exercises, examples, activities, figures, tables, verse, dialogue and answers. An element is stored once on its original page; groups reference it, never duplicate it. Keep parent chains acyclic. Group `kind` is closed by the registry and extends only with permission. `group_refs` and group's `element_refs` must agree.

Relations: `{id,kind,from_ref,to_ref,printed_text,resolution}`. Allowed kinds: refers_to, caption_of, continues, answers_for, footnote_of, panel_of. `resolution`: resolved/unresolved/external. Resolved target must exist; unresolved target is null and printed text is retained. External targets follow the page-session contract above. Scope repeated labels within chapter/groups before book-wide resolution.

## Figures/assets, exclusions and review

`figures` records keep the ACSEE asset fields: `{id,kind,page,surface_id,bbox,bbox_norm,file,format,pixel_size,dpi,deskew_deg,used_by,printed_label,description,crop_check,crop_issue,sha256}` plus optional `map` and `transform`. `file` is relative to `<root>/assets`. `description` is descriptive metadata, never a substitute for printed captions. `used_by` uses element IDs. `crop_check`: pending, ok, flagged. Maps/photos use JPG; diagrams/graphs use PNG unless a lossless map is needed to retain fine text. Chemfig SVG paths are separate `rendered_asset` fields relative to assets.

`exclusions`: `{pdf_page,surface_id,bbox_pt,reason,text?}` for verified added noise/decorations excluded from semantic content. Actual book headers/footers/page numbers are not exclusions. `review`: `{id,issue,element_ref?,pdf_page?,detail,resolved}`; unknown types use `unknown_content_type`. Annotate uncertainty, source gaps, table/figure issues, notation errors, typography and ambiguous relations. Unresolved regions require open review entries and prevent complete status.

Statistics are derived, not manually supplied. Preserve exact pages/elements in checkpoints and fragment ownership. Visual QA and rendering checks cannot be inferred from stats or structural validation.

Current output policy: finished individual page JSONs go in the matching form folder; unfinished pages/session records/backups/scratch work go in the subject temp folder. Compilation is exclusively manual by the user.
