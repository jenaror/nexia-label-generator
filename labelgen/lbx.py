"""Write Brother P-touch Editor (.lbx) shelf labels from a template.

An .lbx file is a ZIP holding ``label.xml`` (layout) and ``prop.xml`` (metadata).
The templates are real labels taken from the existing set, one 10-position and one
15-position tape, both with QR codes. Generating a tape works like this:

* Divider lines are kept exactly where the template has them.
* Each position's header, location name and QR value are replaced.
* For no-QR labels, the QR codes are removed and the text widens to fill the
  position. This is how the existing no-QR files are laid out.
* The templates also contain a small clipart object (PTC Dingbats3 glyph) at the
  top of each position. It isn't meant to be on the labels, so it is left out.

The XML is edited as text rather than re-serialised, so everything we don't touch
stays byte-for-byte as P-touch Editor wrote it.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

from .schema import Tape

TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATES = {10: "slots10_qr.lbx", 15: "slots15_qr.lbx"}

_OBJECT_RE = re.compile(r"<(text:text|image:clipart|barcode:barcode|draw:poly)>.*?</\1>", re.S)
_STYLE_RE = re.compile(r"<pt:objectStyle\s[^>]*>")
_DATA_RE = re.compile(r"(<pt:data>)(.*?)(</pt:data>)", re.S)
_STRING_ITEM_RE = re.compile(r'<text:stringItem charLen="\d+">(.*?)</text:stringItem>', re.S)


def _attr(tag: str, name: str) -> str:
    m = re.search(rf'(?<=\s){name}="([^"]*)"', tag)
    if not m:
        raise ValueError(f"attribute {name!r} missing in {tag[:80]}")
    return m.group(1)


def _pt(value: str) -> float:
    return float(value.removesuffix("pt"))


def _fmt_pt(value: float) -> str:
    return f"{round(value, 1):g}pt"


def _set_style_attr(obj_xml: str, name: str, value: float) -> str:
    """Set an attribute on the object's own (first) <pt:objectStyle> tag."""
    m = _STYLE_RE.search(obj_xml)
    assert m is not None
    tag = re.sub(rf'(?<=\s){name}="[^"]*"', f'{name}="{_fmt_pt(value)}"', m.group(0), count=1)
    return obj_xml[: m.start()] + tag + obj_xml[m.end() :]


def _set_data(obj_xml: str, value: str) -> str:
    return _DATA_RE.sub(lambda m: m.group(1) + escape(value) + m.group(3), obj_xml, count=1)


def _set_text(obj_xml: str, value: str) -> str:
    """Replace a text object's string and rebuild its formatting runs.

    P-touch stores per-run formatting as ``<text:stringItem charLen=N>`` entries, and
    their lengths must add up to the string length. The template text is uniformly
    formatted, so a single run covering the whole new string is enough.
    """
    obj_xml = _set_data(obj_xml, value)
    items = list(_STRING_ITEM_RE.finditer(obj_xml))
    if not items:
        return obj_xml
    single = f'<text:stringItem charLen="{len(value)}">{items[0].group(1)}</text:stringItem>'
    return obj_xml[: items[0].start()] + single + obj_xml[items[-1].end() :]


@dataclass
class _Obj:
    kind: str  # text:text | image:clipart | barcode:barcode | draw:poly
    xml: str
    x: float
    width: float
    role: str = ""  # header | name | symbol | qr | divider
    slot: int = -1


@dataclass
class _Template:
    head: str  # label.xml up to and including <pt:objects>
    tail: str  # </pt:objects> to the end
    objects: list[_Obj]
    slot_right_edges: list[float]  # Right boundary of each position (divider or printable end).
    prop_xml: str
    slots: int


@lru_cache(maxsize=None)
def _load_template(slots: int) -> _Template:
    if slots not in TEMPLATES:
        raise ValueError(f"no template for {slots}-position tapes")
    with zipfile.ZipFile(TEMPLATE_DIR / TEMPLATES[slots]) as z:
        label = z.read("label.xml").decode("utf-8")
        prop = z.read("prop.xml").decode("utf-8")

    start = label.index("<pt:objects>") + len("<pt:objects>")
    end = label.index("</pt:objects>")
    body = label[start:end]

    objects: list[_Obj] = []
    pos = 0
    for m in _OBJECT_RE.finditer(body):
        if body[pos : m.start()].strip():
            raise ValueError("template contains unsupported objects (groups, tables…)")
        pos = m.end()
        style = _STYLE_RE.search(m.group(0))
        assert style is not None
        objects.append(_Obj(m.group(1), m.group(0), _pt(_attr(style.group(0), "x")), _pt(_attr(style.group(0), "width"))))
    if body[pos:].strip():
        raise ValueError("template contains unsupported objects (groups, tables…)")

    # Divider x positions; some templates draw a line twice in the same place.
    dividers: list[float] = []
    for o in sorted((o for o in objects if o.kind == "draw:poly"), key=lambda o: o.x):
        o.role = "divider"
        if not dividers or o.x - dividers[-1] > 1.0:
            dividers.append(o.x)
    if len(dividers) != slots - 1:
        raise ValueError(f"template has {len(dividers)} dividers, expected {slots - 1}")

    background = re.search(r"<style:backGround\s[^>]*>", label)
    assert background is not None
    printable_end = _pt(_attr(background.group(0), "x")) + _pt(_attr(background.group(0), "width"))

    for o in objects:
        if o.kind == "draw:poly":
            continue
        center = o.x + o.width / 2
        o.slot = sum(1 for d in dividers if d < center)
        if o.kind == "barcode:barcode":
            o.role = "qr"
        elif o.kind == "image:clipart":
            o.role = "symbol"
        else:
            data = _DATA_RE.search(o.xml)
            o.role = "name" if data and re.match(r"CN\d", data.group(2)) else "header"

    for i in range(slots):
        roles = sorted(o.role for o in objects if o.slot == i)
        if roles != ["header", "name", "qr", "symbol"]:
            raise ValueError(f"template position {i + 1} has unexpected objects: {roles}")

    return _Template(
        head=label[:start],
        tail=label[end:],
        objects=objects,
        slot_right_edges=dividers + [printable_end],
        prop_xml=prop,
        slots=slots,
    )


def label_xml(tape: Tape) -> str:
    tpl = _load_template(len(tape.slots))

    out: list[str] = []
    for o in tpl.objects:
        if o.role == "divider":
            out.append(o.xml)
            continue
        if o.role == "symbol":
            continue  # Template artifact, not part of the label.
        slot = tape.slots[o.slot]
        xml = o.xml
        if o.role == "qr":
            if not tape.qr:
                continue
            xml = _set_data(xml, slot.key)
        elif o.role in ("header", "name"):
            xml = _set_text(xml, slot.header if o.role == "header" else slot.name)
            if not tape.qr:
                # Widen the text to run up to the position's right-hand divider.
                xml = _set_style_attr(xml, "width", tpl.slot_right_edges[o.slot] - o.x)
        out.append(xml)
    return tpl.head + "".join(out) + tpl.tail


def prop_xml(tape: Tape) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prop = _load_template(len(tape.slots)).prop_xml
    prop = re.sub(r"(<dcterms:created>)[^<]*(</dcterms:created>)", rf"\g<1>{now}\g<2>", prop)
    prop = re.sub(r"(<dcterms:modified>)[^<]*(</dcterms:modified>)", rf"\g<1>{now}\g<2>", prop)
    return prop


def _write_entry(z: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    z.writestr(info, data)


def lbx_bytes(tape: Tape) -> bytes:
    """Build a complete .lbx file for one tape."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        _write_entry(z, "label.xml", label_xml(tape).encode("utf-8"))
        _write_entry(z, "prop.xml", prop_xml(tape).encode("utf-8"))
    return buf.getvalue()


def bundle_zip(tapes: list[Tape]) -> bytes:
    """Zip all tapes together, with one folder per station."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for tape in tapes:
            z.writestr(f"CN{tape.station:02d}/{tape.filename}", lbx_bytes(tape))
    return buf.getvalue()
