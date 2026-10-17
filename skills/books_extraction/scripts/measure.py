#!/usr/bin/env python3
"""Compact numeric page measurement for books_extraction.

Renders one physical page and prints a compact table of the geometry an
extractor needs to place elements: text-line bands, long horizontal/vertical
rules (figure boxes) and coloured banner bands. All coordinates are reported
in render_size_px (150 dpi prep) space so they paste straight into the
book_batch input snippet. Nothing here OCRs or reads PDF text: image geometry
only, matching the skill's visual-only contract.

Usage:
    python measure.py --page-json <temp/page-XXXX.json> [--root <TETEA_ROOT>]
                      [--dpi 300] [--ink 120] [--xpad 40] [--json]
                      [--x0 90 --x1 335]           # restrict to one column
    python measure.py --shrink <image> --out <small.png> [--max-width 760]

Read one page image for layout/semantics, then use this tool for the numbers
instead of reading further images. `--shrink` writes a downscaled preview so a
large figure asset can be checked cheaply.
"""
import argparse
import json
import os
import sys
from pathlib import Path


def _rowscan(rgb, W, H, xL, xR, ink):
    """Single pass: ink min/max x per row, gray-rule and colour counts."""
    rowmin = [None] * H
    rowmax = [None] * H
    grayrow = [0] * H
    colorow = [0] * H
    for y in range(H):
        imn = None
        imx = None
        gc = 0
        cc = 0
        for x in range(xL, xR):
            r, g, b = rgb[x, y]
            if r < ink and g < ink and b < ink:
                if imn is None:
                    imn = x
                imx = x
            elif abs(r - g) < 25 and abs(g - b) < 25 and 120 < r < 215:
                gc += 1
            hi = max(r, g, b)
            lo = min(r, g, b)
            if hi - lo > 60 and hi > 150:
                cc += 1
        rowmin[y] = imn
        rowmax[y] = imx
        grayrow[y] = gc
        colorow[y] = cc
    return rowmin, rowmax, grayrow, colorow


def _group(flags):
    """Group consecutive True rows into [start,end] index pairs."""
    out = []
    cur = None
    for i, v in enumerate(flags):
        if v:
            cur = [i, i] if cur is None else [cur[0], i]
        else:
            if cur:
                out.append(cur)
                cur = None
    if cur:
        out.append(cur)
    return out


def measure_page(pdf_path, page_no, dpi=300, ink=120, xpad=40.0, x0=None, x1=None):
    """Return the geometry table for one 1-based physical page as a dict."""
    import pymupdf
    from PIL import Image

    doc = pymupdf.open(pdf_path)
    page = doc[page_no - 1]
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    rgb = img.load()
    W, H = img.size
    sc = dpi / 150.0                      # render px -> 150dpi prep px
    xL = int((x0 if x0 is not None else xpad) * sc)
    xR = int((x1 if x1 is not None else (W / sc - xpad)) * sc)
    span = xR - xL

    rowmin, rowmax, grayrow, colorow = _rowscan(rgb, W, H, xL, xR, ink)

    def rp(v):
        return round(v / sc, 1)

    # text-line bands (contiguous rows containing ink), with x-extent
    ink_rows = [rowmin[y] is not None for y in range(H)]
    text_lines = []
    for y0, y1 in _group(ink_rows):
        xs = [x for x in range(xL, xR)
              if any(rowmin[y] is not None and rowmin[y] <= x <= rowmax[y]
                     for y in range(y0, y1 + 1))]
        if xs:
            text_lines.append([rp(xs[0]), rp(y0), rp(xs[-1]), rp(y1)])
    # drop speckle (registration ticks, anti-alias fragments) too small to place
    text_lines = [t for t in text_lines if (t[2] - t[0]) >= 3 and (t[3] - t[1]) >= 1]

    # horizontal rules (figure box top/bottom, table lines)
    h_flags = [grayrow[y] > 0.55 * span for y in range(H)]
    h_lines = []
    for y0, y1 in _group(h_flags):
        y = (y0 + y1) // 2
        xs = [x for x in range(xL, xR)
              if abs(rgb[x, y][0] - rgb[x, y][1]) < 25
              and abs(rgb[x, y][1] - rgb[x, y][2]) < 25
              and 120 < rgb[x, y][0] < 215]
        if xs:
            h_lines.append({'y': rp(y), 'x0': rp(xs[0]), 'x1': rp(xs[-1])})

    # vertical rules between consecutive horizontal rules (figure box sides)
    v_lines = []
    for i in range(len(h_lines) - 1):
        ytop = int(h_lines[i]['y'] * sc)
        ybot = int(h_lines[i + 1]['y'] * sc)
        if ybot - ytop < 60:
            continue
        need = 0.7 * (ybot - ytop)
        for x in range(xL, xR):
            gc = 0
            for y in range(ytop, ybot):
                r, g, b = rgb[x, y]
                if abs(r - g) < 25 and abs(g - b) < 25 and 120 < r < 215:
                    gc += 1
            if gc > need:
                v_lines.append({'x': rp(x), 'y0': rp(ytop), 'y1': rp(ybot)})

    # coloured banner bands
    c_flags = [colorow[y] > 0.45 * span for y in range(H)]
    banners = []
    for y0, y1 in _group(c_flags):
        y = (y0 + y1) // 2
        xs = [x for x in range(xL, xR)
              if (lambda p: max(p) - min(p) > 60 and max(p) > 150)(rgb[x, y])]
        if xs:
            p = rgb[(xs[0] + xs[-1]) // 2, y]
            banners.append([rp(xs[0]), rp(y0), rp(xs[-1]), rp(y1),
                            f'#{p[0]:02x}{p[1]:02x}{p[2]:02x}'])

    # watermark (light gray text on cream) sits in a fixed top band; report it
    # for the exclusions block. Search only prep y 55..120 to avoid body text.
    wy0, wy1 = int(55 * sc), int(120 * sc)
    wm_rows = []
    for y in range(wy0, min(wy1, H)):
        c = 0
        for x in range(xL, xR):
            r, g, b = rgb[x, y]
            if abs(r - g) < 15 and abs(g - b) < 15 and 195 < r < 245:
                c += 1
        wm_rows.append(c)
    wm = None
    groups = _group([c > 8 for c in wm_rows])
    if groups:
        g0, g1 = max(groups, key=lambda g: sum(wm_rows[g[0]:g[1] + 1]))
        y0, y1 = g0 + wy0, g1 + wy0
        xs = [x for x in range(xL, xR)
              if any(abs(rgb[x, y][0] - rgb[x, y][1]) < 15
                     and abs(rgb[x, y][1] - rgb[x, y][2]) < 15
                     and 195 < rgb[x, y][0] < 245 for y in range(y0, y1 + 1))]
        if xs:
            wm = [rp(xs[0]), rp(y0), rp(xs[-1]), rp(y1)]

    return {
        'pdf_page': page_no,
        'prep_size': [round(W / sc), round(H / sc)],
        'text_lines': text_lines,
        'h_lines': h_lines,
        'v_lines': v_lines,
        'banners': banners,
        'watermark': wm,
    }


def format_measure(result):
    out = [f"page {result['pdf_page']}  prep {result['prep_size']}",
           "text_lines [x0,y0,x1,y1]:"]
    out += ['   ' + json.dumps(t) for t in result['text_lines']]
    out.append("h_lines: " + json.dumps(result['h_lines']))
    out.append("v_lines: " + json.dumps(result['v_lines']))
    out.append("banners [x0,y0,x1,y1,color]: " + json.dumps(result['banners']))
    out.append("watermark: " + json.dumps(result['watermark']))
    return '\n'.join(out)


def shrink(src, out, max_width):
    from PIL import Image
    with Image.open(src) as im:
        im = im.convert('RGB')
        if max_width and im.width > max_width:
            h = max(1, round(im.height * max_width / im.width))
            im = im.resize((max_width, h), Image.LANCZOS)
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        im.save(out)
        return [im.width, im.height]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--page-json', help='working page JSON in temp/')
    ap.add_argument('--root', default=__import__('book_tools').default_root())
    ap.add_argument('--dpi', type=int, default=300, help='render dpi for measurement')
    ap.add_argument('--ink', type=int, default=120, help='dark-pixel threshold (0-255)')
    ap.add_argument('--xpad', type=float, default=40.0, help='content margin in prep px')
    ap.add_argument('--x0', type=float, default=None, help='left content edge in prep px')
    ap.add_argument('--x1', type=float, default=None, help='right content edge in prep px')
    ap.add_argument('--json', action='store_true', help='emit JSON instead of text')
    ap.add_argument('--shrink', help='image to downscale for cheap viewing')
    ap.add_argument('--out', help='output path for --shrink')
    ap.add_argument('--max-width', type=int, default=760, help='preview max width for --shrink')
    args = ap.parse_args()

    if args.shrink:
        if not args.out:
            ap.error('--shrink requires --out')
        size = shrink(args.shrink, args.out, args.max_width)
        print(json.dumps({'preview': args.out, 'size': size}))
        return

    if not args.page_json:
        ap.error('--page-json is required (or use --shrink)')
    meta = json.loads(Path(args.page_json).read_text(encoding='utf-8'))
    pdf_path = os.path.join(args.root, meta['source']['pdf'])
    page_no = meta['extraction']['requested_pdf_pages'][0]  # 1-based physical page
    result = measure_page(pdf_path, page_no, dpi=args.dpi, ink=args.ink,
                          xpad=args.xpad, x0=args.x0, x1=args.x1)
    print(json.dumps(result, ensure_ascii=False) if args.json else format_measure(result))


if __name__ == '__main__':
    main()
