# ACSEE methods adapted to book pages

These conventions reuse the user's ACSEE extraction approach without importing its exam tree or subject/year limits. The local helpers reflect the inspected `qplib_acsee.crop_fig` and `render_chemfig.py` methods; book cropping keeps live labels by default.

## Text, mathematics and physics

Inline math in `text`: `\( ... \)`; display element: `type:math`, `payload:{latex:"...",printed_label:"(1.7)"}`. Serialize backslashes normally in JSON. No dollar delimiters. Keep ordinary prose numbers, labels and dates plain. Preserve bold/italic using `**...**`/`*...*`; escape literal stars as `\*`. Additional printed underline/sub/sup text styling can be documented in `payload.typography` on text-bearing types: `{start,end,style}` spans index the canonical text, with style underline/superscript/subscript; retain them through build. Do not represent math superscripts as Unicode. IPA and language characters remain Unicode.

Inline fractions `\tfrac`; display fractions `\frac`; powers `x^{2}`; roots `\sqrt`; multiplication/division `\times`/`\div`; matrices `pmatrix`/`bmatrix`/`vmatrix` with row separators `\\`; cases/alignments `cases`/`aligned`/`array`. Preserve bracket styles and equation labels; no unit conversions or mathematical corrections. Don't use `\dfrac`, `\displaystyle`, `\over`, `\degree`, custom macros, `align`/`eqnarray` environments or Unicode mathematical symbols inside LaTeX; flag genuinely unsupported notation.

Physics variables italic, units upright: `\(9.8\,\mathrm{N/kg}\)`, `\(1000\,\mathrm{kg\,m^{-3}}\)`, `\(25\,\mathrm{cm}\)`, `\(100\,^\circ\mathrm{C}\)`, `\vec{F}`, `P=\frac{mgh}{t}`. Keep printed unit styles, exponents and significant figures. Nuclides: `\ce{^{235}_{92}U}`. Quantity plus unit in science/maths text is inline maths; ordinary geography/history language measurements can remain plain. Derivations are ordered math/prose elements within a proof/example group; don't combine away intermediate lines.

## Chemistry

Use mhchem for molecular/condensed formulas, ions, nuclides and linear equations:

```json
{"type":"paragraph","payload":{"text":"Add \\(\\ce{HCl}\\)."}}
{"type":"math","payload":{"latex":"\\ce{CO(g) + 2H2(g) <=> CH3OH(g)}"}}
```

Keep printed states, arrows, coefficients/conditions and unknowns. Use `\ce{SO4^2-}`, `\ce{CH3CH2OH}`; preserve printed formula arrangement. Use Chemfig when the page draws branched/ring/skeletal/displayed structures, stereochemistry or spatial reaction schemes. Applies to CSEE and ACSEE **books**. Store:

```json
{"type":"chemical_structure","payload":{"format":"chemfig","source":"\\chemfig{CH_3-C(=[2]O)-OH}","rendered_asset":"books/<book-id>/chemistry/chemfig_<hash>.svg"}}
```

`source` is an editable LaTeX fragment without delimiters/full document. Connected schemes use `\schemestart ... \schemestop` and remain together. Preserve printed atom labels, bond direction/order, charges, wedges/dashes, arrows and conditions. Do not label skeletal carbons/hydrogens that were not printed, identify unnamed molecules or repair source chemistry. Never send Chemfig through KaTeX or embed SVG markup in JSON.

Reuse the actual existing renderer without importing qplib:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(book_root) / 'tools'))
from render_chemfig import render
asset = render(source, asset_dir='books/' + book_id + '/chemistry')
```

Tectonic: before the first Chemfig render in a session, run `tectonic --version`. If it is missing, install it with `mkdir -p ~/.local/bin && cd ~/.local/bin && curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh && export PATH="$HOME/.local/bin:$PATH"` (or run the repo's `setup.sh`), then verify again. If the install fails, keep the chemistry as `unresolved_region` and report the error. The renderer returns an assets-relative SVG path. If checking the SVG, glance once for obvious missing labels/bonds or a failed render; do not require a repeated atom-by-atom audit. If compiler/tooling/source is unresolved, save editable work and source evidence in `unresolved_region` plus review; do not silently fall back to chemical screenshots as completed structures. Source crops for QA are allowed. A successful compile alone is not QA.

## Tables

Use ACSEE table cells: `text`, generated `runs`, `header`, `rowspan`, `colspan`, `blank`, optional `figure_ref`. Table payload includes columns/rows/header_rows and optional exact printed_label/caption. Omit covered positions; place a merged cell once at its top left. Span grid must cover every position exactly, with no overlap/out-of-bounds spans. Empty printed data cell is `text:""`; fill-in cell has `blank:true`. Preserve all row values, units and totals. Use `blocks` only for actual cell-contained formulas/figures/chemical structures; this is nested existing block content, not a new type.

Don't use the exam DSL's limited TABLE/ROW grammar for book merged cells. Write the JSON grid directly. Matching/MCQ column layouts are their own supported types. An unrepresentable diagram across a grid may be a figure with kind table_image and an open table_irregular review entry, not a falsely validated semantic table. Keep printed repeated table headers on their original pages; link table segments through groups.

## Automatic crops

The agent visually determines the bbox, then executes the crop helper, which saves the crop without user intervention. Coordinates are displayed-page PDF points, or pixels of a render with known DPI. **Caption text is separate from a figure; all in-image labels remain.** Exclude acquisition watermarks only if that does not remove source content; record unavoidable interference.

```powershell
python "$bookTool" crop --pdf "$TETEA_ROOT/tie/books/csee/biology/Book.pdf" --root "$TETEA_ROOT" --book-id 'actual-id' --figure-id 'f-p0007-01' --page 7 --surface-id 's-p0007-01' --bbox 60 120 350 400 --kind diagram --dpi 300
python "$bookTool" crop --pdf "$TETEA_ROOT/tie/books/csee/biology/Book.pdf" --root "$TETEA_ROOT" --book-id 'actual-id' --figure-id 'f-p0007-02' --page 7 --surface-id 's-p0007-01' --bbox 125 250 730 1000 --coords pixels --render-dpi 150 --kind map --dpi 300
```

Helpers return a JSON figure record plus preview path. Record actual resolution; scans can't gain detail by upscaling. Set crop DPI to source scan resolution when it is lower. Deskew: `--deskew` clockwise degrees, with a padded crop and optional `--trim left top right bottom` pixels. Never overwrite a source PDF. Default keeps live text/labels. Prefer a tight box; do not blanket redact the text layer. Save maps with title/grid/legend/scale; photographs as JPG, line drawings/graphs as PNG. Four-up pages use physical coordinates matching the specific surface.

Glance at each saved crop; correct obvious clipping once when practical, then flag remaining problems. Set `crop_check:ok` only after viewing it. If still defective use flagged, crop_issue and review. Root figures `used_by` and element refs must agree. Contact sheets:

```powershell
python "$bookTool" contact --book "$TETEA_ROOT/tie/output/csee/biology/temp/book.json" --root "$TETEA_ROOT" --output "$TETEA_ROOT/tie/output/csee/biology/temp/qa/contact.jpg"
```

They are bounded-width grids, not a single infinitely wide strip. Contact sheets are optional when they help investigate a specific crop problem. Inspect doubtful images at full size.
