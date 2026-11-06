"""Location naming and storage-key numbering for canister shelf labels.

See SCHEMA.md for how these rules were derived. Summary:

* Location name: ``CNss-Krr-pp``. ``ss`` is the station, ``K`` is ``R`` (Empty Return)
  or ``P`` (Full Pickup), ``rr`` is the shelf row and ``pp`` is the canister position.
* Storage key (the QR value): ``CNSTR`` / ``CNSTG`` followed by a running number,
  zero-padded to at least 3 digits.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

MAX_STATION = 8  # The numbering workbooks define stations CN01-CN08.


class ShelfType(Enum):
    EMPTY_RETURN = "Empty return"
    FULL_PICKUP = "Full pickup"

    @property
    def header(self) -> str:
        """Header text printed above every position."""
        return "EMPTY RETURN" if self is ShelfType.EMPTY_RETURN else "FULL PICKUP"

    @property
    def row_letter(self) -> str:
        return "R" if self is ShelfType.EMPTY_RETURN else "P"

    @property
    def key_prefix(self) -> str:
        return "CNSTR" if self is ShelfType.EMPTY_RETURN else "CNSTG"

    @property
    def min_station(self) -> int:
        # CN00 (Cart Load/Unload) only has Empty Return shelves.
        return 0 if self is ShelfType.EMPTY_RETURN else 1


@dataclass(frozen=True)
class StationLayout:
    max_rows: int  # Shelves reserved in the numbering scheme.
    positions: int  # Canister positions per shelf.
    per_tape: int  # Positions printed on one tape (one .lbx file).


def station_layout(shelf_type: ShelfType, station: int) -> StationLayout:
    if shelf_type is ShelfType.EMPTY_RETURN:
        if station == 0:
            return StationLayout(max_rows=8, positions=30, per_tape=15)
        return StationLayout(max_rows=4, positions=20, per_tape=10)
    return StationLayout(max_rows=5, positions=30, per_tape=10)


def validate(shelf_type: ShelfType, station: int, row: int, pos: int) -> None:
    if not shelf_type.min_station <= station <= MAX_STATION:
        raise ValueError(f"{shelf_type.value}: station must be {shelf_type.min_station}-{MAX_STATION}, got {station}")
    layout = station_layout(shelf_type, station)
    if not 1 <= row <= layout.max_rows:
        raise ValueError(f"CN{station:02d} {shelf_type.value}: row must be 1-{layout.max_rows}, got {row}")
    if not 1 <= pos <= layout.positions:
        raise ValueError(f"CN{station:02d} {shelf_type.value}: position must be 1-{layout.positions}, got {pos}")


def location_name(shelf_type: ShelfType, station: int, row: int, pos: int) -> str:
    validate(shelf_type, station, row, pos)
    return f"CN{station:02d}-{shelf_type.row_letter}{row:02d}-{pos:02d}"


def storage_key(shelf_type: ShelfType, station: int, row: int, pos: int) -> str:
    validate(shelf_type, station, row, pos)
    if shelf_type is ShelfType.EMPTY_RETURN:
        if station == 0:
            n = (row - 1) * 30 + pos
        else:
            n = 240 + (station - 1) * 80 + (row - 1) * 20 + pos
    else:
        n = (station - 1) * 150 + (row - 1) * 30 + pos
    return f"{shelf_type.key_prefix}{n:03d}"


@dataclass(frozen=True)
class Slot:
    """One canister position on a tape."""

    header: str
    name: str  # Printed location name, e.g. CN01-R01-05.
    key: str  # Storage key encoded in the QR code, e.g. CNSTR245.


@dataclass(frozen=True)
class Tape:
    """One printed strip (= one .lbx file)."""

    shelf_type: ShelfType
    station: int
    row: int
    qr: bool
    rtl: bool
    slots: tuple[Slot, ...]  # In print order, left to right on the tape.

    @property
    def first_pos(self) -> str:
        return self.slots[0].name[-2:]

    @property
    def last_pos(self) -> str:
        return self.slots[-1].name[-2:]

    @property
    def filename(self) -> str:
        qr = " QR" if self.qr else ""
        return (
            f"CN{self.station:02d} {self.shelf_type.row_letter}{self.row:02d} "
            f"{self.shelf_type.header}{qr} {self.first_pos}-{self.last_pos}.lbx"
        )


def plan_tapes(
    shelf_type: ShelfType,
    station_from: int,
    station_to: int,
    rows: int,
    qr: bool,
    rtl: bool,
) -> list[Tape]:
    """List every tape for the selected stations.

    ``rows`` is capped at each station's maximum. For example, asking for 5 Empty
    Return rows gives CN00 5 rows but CN01+ only their 4.
    """
    if station_from > station_to:
        station_from, station_to = station_to, station_from
    if rows < 1:
        raise ValueError("rows must be at least 1")

    tapes: list[Tape] = []
    for station in range(station_from, station_to + 1):
        layout = station_layout(shelf_type, station)
        for row in range(1, min(rows, layout.max_rows) + 1):
            for start in range(1, layout.positions + 1, layout.per_tape):
                positions = list(range(start, start + layout.per_tape))
                if rtl:
                    positions.reverse()
                slots = tuple(
                    Slot(
                        header=shelf_type.header,
                        name=location_name(shelf_type, station, row, p),
                        key=storage_key(shelf_type, station, row, p),
                    )
                    for p in positions
                )
                tapes.append(Tape(shelf_type, station, row, qr, rtl, slots))
    return tapes
