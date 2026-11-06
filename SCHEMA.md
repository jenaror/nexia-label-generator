# Shelf label schema (reverse-engineered)

Source: the 222 shelf `.lbx` files under `Shelf Labels/` and `Smart Shelf Lightway/`, plus the four `.xlsx` workbooks.
`Brother D610BT Templates/` is a near-identical copy of those two folders (205 files byte-identical).

## 1. Location IDs

### Printed name: `CNss-Krr-pp`

| Part | Meaning |
|------|---------|
| `CNss` | Station. `CN00` = Cart Load/Unload station; `CN01`–`CN08` = Canister Replenishment Station 1–8 |
| `K` | Shelf type: `R` = Empty Return shelf, `P` = Full Pickup shelf |
| `rr` | Shelf (row) number on that station |
| `pp` | Canister position along the shelf, counted from 01 |

### Database key (the value in the QR code): `<area><n>`

`n` is zero-padded to **at least** 3 digits. It reaches 4 digits from `CNSTG1000` on, so it isn't a fixed "last 3 characters".

| Area | Used for | Station | Shelves × positions | Formula for `n` |
|------|----------|---------|---------------------|-----------------|
| `CNSTR` | Empty Return | CN00 | 8 × 30 | `(rr-1)*30 + pp` → 001–240 |
| `CNSTR` | Empty Return | CN01–CN08 | 4 × 20 | `240 + (ss-1)*80 + (rr-1)*20 + pp` → 241–880 |
| `CNSTG` | Full Pickup | CN01–CN08 | 5 × 30 | `(ss-1)*150 + (rr-1)*30 + pp` → 001–1200 |

These formulas match the Excel numbering sheets exactly. They also match 970 of the 1020 QR/ID pairs found in the label files; the other 50 are the errors in section 5.

In practice, only some of the reserved shelves have labels:
- CN00: R01–R06 (R07–R08 are reserved)
- CN01–CN05: R01–R03 and P01–P03 (R04, P04 and P05 are reserved)
- CN06–CN08: in Excel only, with no label files yet

## 2. Physical layout (from `Replenishment and Cart Load shelf Label layout.xlsx`)

Each replenishment station has 6 shelf rows, and each row has a label on the desk side and the pod side:

| Row | Content | Desk side | Pod side |
|-----|---------|-----------|----------|
| 1–3 | Full Pickup P01–P03, 30 positions = 3 tapes of 10 | **QR** | no QR |
| 4–6 | Empty Return R01–R03, 20 positions = 2 tapes of 10 | no QR | **QR** |

The Cart Load/Unload station (CN00) has 6 rows of Empty Return, R01–R06. Each row has 30 positions on 2 tapes of 15. Both sides have QR codes.

Direction: the desk side reads left to right (01 → 10, then 11 → 20, …). The pod side is mirrored: it reads right to left, so positions descend across the tape and the tapes run in reverse order.

## 3. Label file anatomy

- An `.lbx` file is a ZIP containing `label.xml` (layout and content) and `prop.xml` (metadata).
- Printer: Brother PT-D610BT. Orientation is landscape and `autoLength` is false.
- Tape width: `51.2pt` (18 mm) for shelf labels and `33.6pt` (12 mm) for Smart Shelf.
- One tape covers 10 positions (about 1595–1617pt long, about 160pt per slot) or 15 positions (2448pt long, about 163pt per slot).
- Each **slot** contains these objects, all positioned absolutely and none rotated or flipped:

| Object | QR variant | No-QR variant |
|--------|-----------|---------------|
| Header text, 9pt, centered: `EMPTY RETURN` / `FULL PICKUP` / `FILLED PICKUP` | width about 119pt | width about 155pt (spans the whole slot) |
| ID text, 15.8pt, centered: `CN01-R01-01` | width about 119pt | width about 155pt |
| Small clipart object (PTC Dingbats3 glyph 57442), top of slot. Not meant to be on the labels; the generator leaves it out. | yes | yes |
| QR code, 40×40pt, model 2, ECC 15%, cell 1.6pt, on the **right** of the slot | yes | — |
| Vertical divider line between slots | yes | yes |

- **Right-to-left is not a geometric mirror.** The slots are in the same places; only the order of the data is reversed. The QR stays on the right side of each slot in both directions.
- Each text object lists `<text:stringItem charLen=…>` runs whose lengths add up to the text length. When a generated text has a different length, these runs must be rewritten.

## 4. Smart Shelf Lightway (a separate family)

- ID `cc-ss-pp` (cabinet-shelf-position), for example `01-01-01`. The QR value is the same string as the text.
- 8 positions per shelf, 9 shelves, cabinet 1 only. 12 mm tape, about 288pt (4") per slot.
- The text and QR of each slot form a group. The text is right-aligned at 21.8pt.
- The front side reads left to right (01 → 08) and the back side reads right to left (08 → 01).

## 5. Data problems found in the existing files

Wrong QR values:
- `Shelf Labels/Empty Return QR/Shelf 10x Wide/CN01 R0{1,2} EMPTY RETURN QR {1-10,11-20} .lbx` (4 loose files): every QR is 30 too high (CN01-R01-01 → CNSTR271; the correct value is 241). These look like an old draft. The correct versions are in the `Replenishment 1 …` folder.
- `15x Wide/Left to Right/Emty Return  P02 1-15 QR`: CN00-R02-14 → CNSTR014 (correct: 044)
- `15x Wide/Left to Right/Emty Return  P04 16-30 QR`: CN00-R04-22 → CNSTR122 (correct: 112)
- `Full Pickup QR/Canister Replenishment 1/CN01 R02 … 11-20`: CN01-P02-18 → CNSTG038 (correct: 048)
- `Full Pickup QR/Canister Replenishment 3/CN03 R02 … 11-20`: CN03-P02-18 → CNSTG338 (correct: 348)
- `Full Pickup QR/Canister Replenishment 4/CN04 R02 … 1-10`: CN04-P02-04 → CNSTG384 (correct: 484)
- `Full Pickup QR/Canister Replenishment 5/CN05 R02 … 11-20`: CN05-P02-18 → CNSTG638 (correct: 648)

Wrong printed text:
- `Full Pickup QR/Canister Replenishment 5/CN05 R03 … 1-10`: the last slot is printed `CN01-P03-01` (correct: `CN05-P03-01`)
- `Full Pickup QR/Canister Replenishment 5/CN05 R03 … 11-20`: one slot is printed `CN051-P03-12`

Other inconsistencies:
- `Smart Shelf Lightway/CAB 1 Back Side/Cab1 Shelf 9.lbx` reads left to right, unlike the rest of the back side. `Layout.lbx` in the same folder is the right-to-left version.
- `Replenishment 2 Empty Return/Right to Left/CN01 R02 20-11 QR.lbx` actually contains CN02-R02.
- The Empty Return numbering workbook labels CN01 as "Replen Station 2" (an off-by-one). The other two workbooks call it Station 1.
- In the Brother copy, the folder `…/Replenishment 2 Empty Return/Replen 1 Empty Return Label QR/` contains CN01 labels **without** QR codes.
- Full Pickup QR files are named `1-10` but contain the positions in right-to-left order (10 → 01).

## 6. Decisions (answered 2026-11-06)

1. **Direction and QR**: the user picks both in the generator. It doesn't produce counterpart labels automatically.
2. **Header wording**: `FULL PICKUP` for both the QR and no-QR versions. `FILLED PICKUP` is retired.
3. **Out of scope**: Smart Shelf Lightway and PC Workstation labels.
