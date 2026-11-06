import streamlit as st

from labelgen import MAX_STATION, ShelfType, bundle_zip, label_xml, plan_tapes, station_layout
from labelgen.preview import tape_svg

st.set_page_config(page_title="Shelf label maker", page_icon=":material/label:", layout="wide")

# --- Options ----------------------------------------------------------------------
with st.sidebar:
    st.header("Label options")

    shelf_type: ShelfType = st.segmented_control(
        "Shelf type",
        list(ShelfType),
        format_func=lambda t: t.value,
        default=ShelfType.EMPTY_RETURN,
        required=True,
        key="shelf_type",
        width="stretch",
    )

    # Separate keys per shelf type so bounds can differ (CN00 is Empty Return only).
    lo = shelf_type.min_station
    with st.container(horizontal=True):
        station_from = int(
            st.number_input("From station", min_value=lo, max_value=MAX_STATION, value=1, key=f"from_{shelf_type.name}")
        )
        station_to = int(
            st.number_input("To station", min_value=lo, max_value=MAX_STATION, value=1, key=f"to_{shelf_type.name}")
        )
    if station_from > station_to:
        station_from, station_to = station_to, station_from
    stations = range(station_from, station_to + 1)
    st.caption(
        f"CN{station_from:02d}" if station_from == station_to else f"CN{station_from:02d} – CN{station_to:02d}"
    )

    limits = {s: station_layout(shelf_type, s).max_rows for s in stations}
    max_rows = max(limits.values())
    rows = int(
        st.number_input(
            "Rows per station",
            min_value=1,
            max_value=max_rows,
            value=1,
            key=f"rows_{shelf_type.name}_{max_rows}",
            help="Shelves are generated from row 1 up to this number.",
        )
    )
    capped = sorted(s for s, limit in limits.items() if limit < rows)
    if capped:
        st.caption(
            f"{', '.join(f'CN{s:02d}' for s in capped)} only have {min(limits[s] for s in capped)} "
            f"{shelf_type.value.lower()} rows, so they're capped there."
        )

    qr = st.toggle("QR codes", value=True, key="qr", help="Off produces the retrieve-side labels without QR codes.")
    rtl = st.toggle(
        "Right-to-left numbering",
        value=False,
        key="rtl",
        help="Positions count down across the tape (10 → 01). Use for the mirrored side of the shelf.",
    )

    params = (shelf_type, station_from, station_to, rows, qr, rtl)
    generate = st.button("Generate labels", type="primary", icon=":material/label:", width="stretch", key="generate")

if generate:
    tapes = plan_tapes(*params)
    zip_name = (
        f"{shelf_type.header.title()} CN{station_from:02d}-CN{station_to:02d} "
        f"{rows} row{'s' if rows > 1 else ''} {'QR' if qr else 'no QR'} {'RTL' if rtl else 'LTR'}.zip"
    )
    # "run" changes on every generation so the preview picker starts fresh.
    run = st.session_state.get("result", {}).get("run", 0) + 1
    st.session_state.result = {"params": params, "tapes": tapes, "zip": bundle_zip(tapes), "zip_name": zip_name, "run": run}

# --- Results ----------------------------------------------------------------------
st.title("Shelf label maker")
st.caption("Brother PT-D610BT canister shelf labels (.lbx) for P-touch Editor")

result = st.session_state.get("result")
if result is None:
    st.info("Pick the stations and label style in the sidebar, then select **Generate labels**.", icon=":material/arrow_back:")
    st.stop()

if result["params"] != params:
    st.warning(
        "The options have changed since these labels were generated. Select **Generate labels** to update them.",
        icon=":material/sync_problem:",
    )

tapes = result["tapes"]
with st.container(horizontal=True, vertical_alignment="center"):
    st.subheader(f"{len(tapes)} label file{'s' if len(tapes) != 1 else ''}", width="content")
    st.download_button(
        "Download .zip",
        data=result["zip"],
        file_name=result["zip_name"],
        mime="application/zip",
        type="primary",
        icon=":material/download:",
        on_click="ignore",
    )

st.dataframe(
    [
        {
            "File": f"CN{t.station:02d}/{t.filename}",
            "Positions": f"{t.slots[0].name} → {t.slots[-1].name}",
            "QR codes": f"{t.slots[0].key} → {t.slots[-1].key}" if t.qr else "—",
        }
        for t in tapes
    ],
    hide_index=True,
    height=min(36 * (len(tapes) + 1) + 2, 300),
    alt="Generated label files with their position and QR code ranges",
)

st.subheader("Preview")
by_path = {f"CN{t.station:02d}/{t.filename}": t for t in tapes}
choice = st.selectbox("Label file", list(by_path), key=f"preview_{result['run']}")
tape = by_path.get(choice or "", tapes[0])
with st.container(border=True):
    st.image(
        tape_svg(label_xml(tape)),
        width="stretch",
        alt=f"Preview of {tape.filename}: positions {tape.slots[0].name} to {tape.slots[-1].name}",
    )
