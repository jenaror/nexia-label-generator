"""Render a generated label.xml as an SVG preview.

The preview is drawn from the generated XML itself, so it shows what is in the
file, as one strip with every position in a row. QR codes are drawn with
``segno`` from the same value. They
encode the same data, though P-touch may pick a different QR version or mask
when printing.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from xml.sax.saxutils import escape

import segno

NS = {
    "pt": "http://schemas.brother.info/ptouch/2007/lbx/main",
    "style": "http://schemas.brother.info/ptouch/2007/lbx/style",
    "text": "http://schemas.brother.info/ptouch/2007/lbx/text",
    "barcode": "http://schemas.brother.info/ptouch/2007/lbx/barcode",
}
FONT = "Helvetica, Arial, sans-serif"


@dataclass
class _Box:
    kind: str
    x: float
    y: float
    w: float
    h: float
    data: str = ""
    size: float = 0.0
    weight: int = 400


def _pt(v: str) -> float:
    return float(v.removesuffix("pt"))


def _read(label_xml: str) -> tuple[float, float, list[_Box]]:
    root = ET.fromstring(label_xml)
    paper = root.find(".//style:paper", NS)
    assert paper is not None
    tape_w, length = _pt(paper.get("width", "0")), _pt(paper.get("height", "0"))
    boxes: list[_Box] = []
    objects = root.find(".//pt:objects", NS)
    assert objects is not None
    for obj in objects:
        st = obj.find("pt:objectStyle", NS)
        assert st is not None
        kind = obj.tag.split("}")[1]
        box = _Box(kind, _pt(st.get("x", "0")), _pt(st.get("y", "0")), _pt(st.get("width", "0")), _pt(st.get("height", "0")))
        data = obj.find("pt:data", NS)
        if data is not None and data.text:
            box.data = data.text
        ext = obj.find("text:ptFontInfo/text:fontExt", NS)
        if ext is not None:
            box.size = _pt(ext.get("size", "10pt"))
        font = obj.find("text:ptFontInfo/text:logFont", NS)
        if font is not None:
            box.weight = int(font.get("weight", "400"))
        boxes.append(box)
    return tape_w, length, boxes


def _qr_path(data: str, x: float, y: float, size: float) -> str:
    qr = segno.make_qr(data, error="m")
    matrix = [list(row) for row in qr.matrix]
    n = len(matrix)
    border = 2
    cell = size / (n + 2 * border)
    parts = []
    for r, row in enumerate(matrix):
        for c, dark in enumerate(row):
            if dark:
                px, py = x + (c + border) * cell, y + (r + border) * cell
                parts.append(f"M{px:.2f} {py:.2f}h{cell:.2f}v{cell:.2f}h{-cell:.2f}z")
    return f'<path d="{"".join(parts)}" fill="#000"/>'


def _render_box(b: _Box) -> str:
    if b.kind == "poly":
        cx = b.x + b.w / 2
        return f'<line x1="{cx:.1f}" y1="{b.y:.1f}" x2="{cx:.1f}" y2="{b.y + b.h:.1f}" stroke="#000" stroke-width="0.6"/>'
    if b.kind == "barcode":
        return _qr_path(b.data, b.x, b.y, min(b.w, b.h))
    if b.kind == "text":
        size = b.size * 0.92
        # Shrink-to-fit, like P-touch's "shrink" text option.
        est = 0.58 * size * len(b.data)
        fit = f' textLength="{b.w - 2:.1f}" lengthAdjust="spacingAndGlyphs"' if est > b.w - 2 else ""
        return (
            f'<text x="{b.x + b.w / 2:.1f}" y="{b.y + b.h / 2:.1f}" font-family="{FONT}" '
            f'font-size="{size:.1f}" font-weight="{b.weight}" text-anchor="middle" '
            f'dominant-baseline="central"{fit}>{escape(b.data)}</text>'
        )
    return ""


def tape_svg(label_xml: str) -> str:
    """SVG of the whole tape as a single strip, in tape coordinates (points)."""
    tape_w, length, boxes = _read(label_xml)
    pad = 2.0
    width, height = length + 2 * pad, tape_w + 2 * pad
    body = "".join(_render_box(b) for b in boxes)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-pad} {-pad} {width:.1f} {height:.1f}" '
        f'width="{width:.0f}" height="{height:.0f}">'
        f'<clipPath id="tape"><rect x="0" y="0" width="{length:.1f}" height="{tape_w:.1f}"/></clipPath>'
        f'<rect x="0" y="0" width="{length:.1f}" height="{tape_w:.1f}" rx="2" fill="#fff" stroke="#9aa0a6" stroke-width="0.8"/>'
        f'<g clip-path="url(#tape)">{body}</g>'
        "</svg>"
    )
