
import json
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_FILE = Path("clinic_queue.json")

DEFAULT_ROOMS = [
    "Room 1",
    "Room 2",
    "Room 3",
    "Room 4",
    "Room 5",
    "Room 6",
]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def parse_dt(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def load_data() -> list[dict]:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except json.JSONDecodeError:
            pass

    data = [
        {
            "room": room,
            "patient": "",
            "status": "Available",
            "check_in_time": None,
            "notes": "",
        }
        for room in DEFAULT_ROOMS
    ]
    save_data(data)
    return data


def save_data(data: list[dict]) -> None:
    DATA_FILE.write_text(json.dumps(data, indent=2))


def elapsed_text(check_in_time: str | None) -> str:
    check_in = parse_dt(check_in_time)
    if not check_in:
        return ""
    seconds = int((datetime.now() - check_in).total_seconds())
    if seconds < 0:
        seconds = 0
    minutes = seconds // 60
    hours = minutes // 60
    mins = minutes % 60

    if hours:
        return f"{hours}h {mins}m"
    return f"{mins}m"


def elapsed_minutes(check_in_time: str | None) -> int:
    check_in = parse_dt(check_in_time)
    if not check_in:
        return 0
    return max(0, int((datetime.now() - check_in).total_seconds() // 60))


def status_badge(status: str, minutes: int) -> str:
    if status == "Available":
        return "🟢 Available"
    if status == "Checked Out":
        return "⚪ Checked Out"
    if minutes >= 30:
        return "🔴 Checked In"
    if minutes >= 15:
        return "🟠 Checked In"
    return "🟡 Checked In"


def check_in(data: list[dict], index: int, patient: str, notes: str) -> None:
    data[index]["patient"] = patient.strip()
    data[index]["status"] = "Checked In"
    data[index]["check_in_time"] = now_iso()
    data[index]["notes"] = notes.strip()
    save_data(data)


def check_out(data: list[dict], index: int) -> None:
    data[index]["status"] = "Checked Out"
    data[index]["patient"] = ""
    data[index]["check_in_time"] = None
    data[index]["notes"] = ""
    save_data(data)


def clear_room(data: list[dict], index: int) -> None:
    data[index]["status"] = "Available"
    data[index]["patient"] = ""
    data[index]["check_in_time"] = None
    data[index]["notes"] = ""
    save_data(data)


st.set_page_config(
    page_title="Clinic Check-In Monitor",
    page_icon="🏥",
    layout="wide",
)

st.title("Clinic Check-In Monitor")

# Auto-refresh every 10 seconds.
refresh_seconds = st.sidebar.slider("Refresh monitor every seconds", 5, 60, 10)
time.sleep(0.1)
st.sidebar.caption(f"Screen refreshes every {refresh_seconds} seconds.")

data = load_data()

with st.sidebar:
    st.header("Check In Patient")

    rooms = [item["room"] for item in data]
    selected_room = st.selectbox("Room", rooms)
    selected_index = rooms.index(selected_room)

    patient = st.text_input("Patient name or initials")
    notes = st.text_area("Notes", height=80)

    if st.button("Check In", type="primary", use_container_width=True):
        if not patient.strip():
            st.warning("Enter a patient name or initials first.")
        else:
            check_in(data, selected_index, patient, notes)
            st.rerun()

    st.divider()

    st.header("Room Actions")
    action_room = st.selectbox("Select room", rooms, key="action_room")
    action_index = rooms.index(action_room)

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Check Out", use_container_width=True):
            check_out(data, action_index)
            st.rerun()
    with col_b:
        if st.button("Clear", use_container_width=True):
            clear_room(data, action_index)
            st.rerun()

    st.divider()

    st.header("Room Setup")
    new_room = st.text_input("Add room")
    if st.button("Add Room", use_container_width=True):
        if new_room.strip():
            data.append(
                {
                    "room": new_room.strip(),
                    "patient": "",
                    "status": "Available",
                    "check_in_time": None,
                    "notes": "",
                }
            )
            save_data(data)
            st.rerun()

    remove_room = st.selectbox("Remove room", [""] + rooms)
    if st.button("Remove Selected Room", use_container_width=True):
        if remove_room:
            data = [item for item in data if item["room"] != remove_room]
            save_data(data)
            st.rerun()

monitor_rows = []
for item in data:
    minutes = elapsed_minutes(item["check_in_time"])
    monitor_rows.append(
        {
            "Room": item["room"],
            "Patient": item["patient"],
            "Status": status_badge(item["status"], minutes),
            "Wait Time": elapsed_text(item["check_in_time"]),
            "Checked In At": parse_dt(item["check_in_time"]).strftime("%I:%M %p") if parse_dt(item["check_in_time"]) else "",
            "Notes": item["notes"],
            "_minutes": minutes,
        }
    )

checked_in = [row for row in monitor_rows if "Checked In" in row["Status"]]
avg_wait = round(sum(row["_minutes"] for row in checked_in) / len(checked_in), 1) if checked_in else 0
longest_wait = max((row["_minutes"] for row in checked_in), default=0)

m1, m2, m3 = st.columns(3)
m1.metric("Checked In", len(checked_in))
m2.metric("Average Wait", f"{avg_wait} min")
m3.metric("Longest Wait", f"{longest_wait} min")

st.divider()

st.subheader("Live Room Monitor")

display_df = pd.DataFrame(monitor_rows).drop(columns=["_minutes"])

def highlight_wait(row):
    raw = next((r for r in monitor_rows if r["Room"] == row["Room"]), None)
    minutes = raw["_minutes"] if raw else 0

    # Leave non-checked-in rows alone so they follow the app/browser theme.
    if "Checked In" not in row["Status"]:
        return [""] * len(row)

    # Force dark text only on colored checked-in rows.
    base_style = "color: #111111; font-weight: bold"

    if minutes >= 30:
        return [f"background-color: #ffd6d6; {base_style}"] * len(row)
    if minutes >= 15:
        return [f"background-color: #fff0cc; {base_style}"] * len(row)
    return [f"background-color: #e8f5e9; {base_style}"] * len(row)

st.dataframe(
    display_df.style.apply(highlight_wait, axis=1),
    use_container_width=True,
    hide_index=True,
    height=500,
)

st.caption("Color rules: yellow under 15 minutes, orange after 15 minutes, red after 30 minutes.")

# This causes the monitor to refresh.
time.sleep(refresh_seconds)
st.rerun()
