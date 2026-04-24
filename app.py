
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import pandas as pd
import streamlit as st
import pymssql

def get_sql_connection():
    cfg = st.secrets["azure_sql"]

    return pymssql.connect(
        server=cfg["server"],
        user=cfg["username"],
        password=cfg["password"],
        database=cfg["database"],
    )

CLINIC_DEFAULT_ROOMS = {
    "DMC": [
        "DMC Room 1",
        "DMC Room 2",
        "DMC Room 3",
        "DMC Room 4",
    ],
    "EMC": [
        "EMC Room 1",
        "EMC Room 2",
        "EMC Room 3",
        "EMC Room 4",
    ],
    "DDNC": [
        "DDNC Room 1",
        "DDNC Room 2",
        "DDNC Room 3",
        "DDNC Room 4",
    ],
    "PIHC": [
        "PIHC Room 1",
        "PIHC Room 2",
        "PIHC Room 3",
        "PIHC Room 4",
    ],
    "WFCC": [
        "WFCC Room 1",
        "WFCC Room 2",
        "WFCC Room 3",
        "WFCC Room 4",
    ],
    "VFC": [
        "VFC Room 1",
        "VFC Room 2",
        "VFC Room 3",
        "VFC Room 4",
    ],
    "MIM": [
        "MIM Room 1",
        "MIM Room 2",
        "MIM Room 3",
        "MIM Room 4",
    ],
}

DATA_DIR = Path("clinic_data")
DATA_DIR.mkdir(exist_ok=True)
CENTRAL = ZoneInfo("America/Chicago")

def log_history(clinic: str, room_data: dict) -> None:
    check_in = parse_dt(room_data.get("check_in_time"))
    if not check_in:
        return

    check_out = datetime.now(CENTRAL)
    wait_minutes = int((check_out - check_in).total_seconds() // 60)

    conn = get_sql_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO dbo.WaitTimeHistory
            (clinic, room, patient, check_in_time, check_out_time, wait_minutes, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        clinic,
        room_data.get("room", ""),
        room_data.get("patient", ""),
        check_in,
        check_out,
        wait_minutes,
        room_data.get("notes", ""),
    )

    conn.commit()
    cursor.close()
    conn.close()

def clinic_file(clinic: str) -> Path:
    safe_name = clinic.lower().replace(" ", "_")
    return DATA_DIR / f"{safe_name}_queue.json"


def now_iso() -> str:
    return datetime.now(ZoneInfo("America/Chicago")).isoformat(timespec="seconds")


def parse_dt(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def default_data_for_clinic(clinic: str) -> list[dict]:
    return [
        {
            "room": room,
            "patient": "",
            "status": "Available",
            "check_in_time": None,
            "notes": "",
        }
        for room in CLINIC_DEFAULT_ROOMS[clinic]
    ]


def load_data(clinic: str) -> list[dict]:
    data_file = clinic_file(clinic)

    if data_file.exists():
        try:
            return json.loads(data_file.read_text())
        except json.JSONDecodeError:
            pass

    data = default_data_for_clinic(clinic)
    save_data(clinic, data)
    return data


def save_data(clinic: str, data: list[dict]) -> None:
    clinic_file(clinic).write_text(json.dumps(data, indent=2))


def reset_clinic_rooms(clinic: str) -> None:
    save_data(clinic, default_data_for_clinic(clinic))


def elapsed_text(check_in_time: str | None) -> str:
    check_in = parse_dt(check_in_time)
    if not check_in:
        return ""
    seconds = int((datetime.now(ZoneInfo("America/Chicago")) - check_in).total_seconds())
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
    return max(0, int((datetime.now(ZoneInfo("America/Chicago")) - check_in).total_seconds() // 60))


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


def check_out(clinic: str, data: list[dict], index: int) -> None:
    log_history(clinic, data[index])

    data[index]["status"] = "Checked Out"
    data[index]["patient"] = ""
    data[index]["check_in_time"] = None
    data[index]["notes"] = ""


def clear_room(data: list[dict], index: int) -> None:
    data[index]["status"] = "Available"
    data[index]["patient"] = ""
    data[index]["check_in_time"] = None
    data[index]["notes"] = ""


st.set_page_config(
    page_title="Clinic Check-In Monitor",
    page_icon="🏥",
    layout="wide",
)

st.title("Clinic Check-In Monitor")

with st.sidebar:
    st.header("Clinic")
    clinic = st.selectbox("Select clinic", list(CLINIC_DEFAULT_ROOMS.keys()))

    st.divider()
    refresh_seconds = st.slider("Refresh monitor every seconds", 5, 60, 10)
    st.caption(f"Screen refreshes every {refresh_seconds} seconds.")

data = load_data(clinic)

st.subheader(f"{clinic} Live Monitor")

with st.sidebar:
    st.divider()
    st.header("Check In Patient")

    rooms = [item["room"] for item in data]

    if not rooms:
        st.warning("No rooms exist for this clinic. Add a room below or reset defaults.")
    else:
        selected_room = st.selectbox("Room", rooms)
        selected_index = rooms.index(selected_room)

        patient = st.text_input("Patient name or initials")
        notes = st.text_area("Notes", height=80)

        if st.button("Check In", type="primary", use_container_width=True):
            if not patient.strip():
                st.warning("Enter a patient name or initials first.")
            else:
                check_in(data, selected_index, patient, notes)
                save_data(clinic, data)
                st.rerun()

    st.divider()

    st.header("Room Actions")
    rooms = [item["room"] for item in data]

    if rooms:
        action_room = st.selectbox("Select room", rooms, key="action_room")
        action_index = rooms.index(action_room)

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Check Out", use_container_width=True):
                check_out(clinic, data, action_index)
                save_data(clinic, data)
                st.rerun()
        with col_b:
            if st.button("Clear", use_container_width=True):
                clear_room(data, action_index)
                save_data(clinic, data)
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
            save_data(clinic, data)
            st.rerun()

    rooms = [item["room"] for item in data]
    remove_room = st.selectbox("Remove room", [""] + rooms)
    if st.button("Remove Selected Room", use_container_width=True):
        if remove_room:
            data = [item for item in data if item["room"] != remove_room]
            save_data(clinic, data)
            st.rerun()

    if st.button("Reset This Clinic to Default Rooms", use_container_width=True):
        reset_clinic_rooms(clinic)
        st.rerun()

monitor_rows = []
for item in data:
    minutes = elapsed_minutes(item["check_in_time"])
    checked_in_at = parse_dt(item["check_in_time"])
    monitor_rows.append(
        {
            "Clinic": clinic,
            "Room": item["room"],
            "Patient": item["patient"],
            "Status": status_badge(item["status"], minutes),
            "Wait Time": elapsed_text(item["check_in_time"]),
            "Checked In At": checked_in_at.strftime("%I:%M %p") if checked_in_at else "",
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

display_df = pd.DataFrame(monitor_rows).drop(columns=["_minutes"])

def highlight_wait(row):
    raw = next((r for r in monitor_rows if r["Room"] == row["Room"]), None)
    minutes = raw["_minutes"] if raw else 0

    if "Checked In" not in row["Status"]:
        return [""] * len(row)

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

st.caption("Color rules: green under 15 minutes, orange after 15 minutes, red after 30 minutes.")

time.sleep(refresh_seconds)
st.rerun()
