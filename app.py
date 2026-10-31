import datetime
import hmac
import io
import json
import os
import re

import pandas as pd
import streamlit as st


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDENTS_FILE = os.path.join(BASE_DIR, "students.csv")
ATTENDANCE_FILE = os.path.join(BASE_DIR, "attendance_records.csv")
AUDIT_FILE = os.path.join(BASE_DIR, "faculty_activity.csv")
AUDIT_COLUMNS = [
    "timestamp", "faculty_id", "action", "date", "section",
    "reg_no", "student_name", "old_value", "new_value",
]
ATTENDANCE_COLUMNS = [
    "date", "month", "reg_no", "name", "section", "status", "marked_by", "timestamp"
]
ROSTER_COLUMNS = ["sno", "reg_no", "name", "course", "section"]
FACULTY_IDS = [f"faculty_{i}" for i in range(1, 11)]
APP_TIMEZONE = datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IST")

st.set_page_config(
    page_title="MCA Attendance Hub",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.8rem; }
    [data-testid="stMetric"] { background: #f5f7fb; padding: 0.8rem; border-radius: 0.7rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def shared_password():
    """Read the shared password from Streamlit Secrets (or an environment variable locally)."""
    try:
        configured = st.secrets.get("FACULTY_SHARED_PASSWORD", "")
    except Exception:
        configured = ""
    return str(configured or os.environ.get("FACULTY_SHARED_PASSWORD", ""))


def login_gate() -> bool:
    password = shared_password()
    if not password:
        st.title("MCA Attendance Hub")
        st.error("Faculty login is not configured yet.")
        st.markdown(
            "In Streamlit hosting, add `FACULTY_SHARED_PASSWORD` under **App settings → Secrets**. "
            "For local use, set the same environment variable before starting the app."
        )
        st.code('FACULTY_SHARED_PASSWORD = "choose-a-shared-password"', language="toml")
        return False

    if st.session_state.get("faculty_id") not in FACULTY_IDS:
        st.title("MCA Attendance Hub")
        st.caption("Sign in with your faculty username. All ten faculty usernames use the same shared password.")
        with st.form("faculty_login"):
            faculty_id = st.text_input("Username", placeholder="faculty_1")
            entered_password = st.text_input("Shared password", type="password")
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if submitted:
            normalized_id = faculty_id.strip().lower()
            if normalized_id in FACULTY_IDS and hmac.compare_digest(entered_password, password):
                st.session_state["faculty_id"] = normalized_id
                st.rerun()
            st.error("Enter a valid username (faculty_1 through faculty_10) and the shared password.")
        return False
    return True


def parse_flexible_csv(file_content: str) -> pd.DataFrame:
    """Read the roster's older comma-separated format, including trailing fields."""
    rows = []
    for line in file_content.strip().splitlines():
        parts = [part.strip() for part in line.split(",") if part.strip()]
        if len(parts) >= 5 and parts[1].upper().startswith("RTC2026"):
            section = parts[4].upper()
            if section not in {"A", "B"}:
                section = "A" if "A" in parts[4:] else "B"
            rows.append({
                "sno": parts[0], "reg_no": parts[1], "name": parts[2],
                "course": parts[3], "section": section,
            })
    return pd.DataFrame(rows, columns=ROSTER_COLUMNS)


def load_students() -> pd.DataFrame:
    if not os.path.exists(STUDENTS_FILE):
        return pd.DataFrame(columns=ROSTER_COLUMNS)
    try:
        df = pd.read_csv(STUDENTS_FILE, dtype={"reg_no": str})
        for col in ROSTER_COLUMNS:
            if col not in df.columns:
                df[col] = "" if col != "sno" else range(1, len(df) + 1)
        df = df[ROSTER_COLUMNS].fillna("")
        df["reg_no"] = df["reg_no"].astype(str).str.strip()
        df["section"] = df["section"].astype(str).str.upper().str.strip()
        return df
    except Exception:
        with open(STUDENTS_FILE, "r", encoding="utf-8-sig", errors="ignore") as roster_file:
            return parse_flexible_csv(roster_file.read())


def load_attendance() -> pd.DataFrame:
    if not os.path.exists(ATTENDANCE_FILE):
        return pd.DataFrame(columns=ATTENDANCE_COLUMNS)
    try:
        df = pd.read_csv(ATTENDANCE_FILE, dtype={"reg_no": str})
        for col in ATTENDANCE_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        df["date"] = df["date"].astype(str)
        if "month" in df.columns:
            missing_month = df["month"].astype(str).isin(["", "nan"])
            df.loc[missing_month, "month"] = df.loc[missing_month, "date"].str[:7]
        return df[ATTENDANCE_COLUMNS].fillna("")
    except Exception:
        return pd.DataFrame(columns=ATTENDANCE_COLUMNS)


def load_audit() -> pd.DataFrame:
    if not os.path.exists(AUDIT_FILE):
        return pd.DataFrame(columns=AUDIT_COLUMNS)
    try:
        df = pd.read_csv(AUDIT_FILE, keep_default_na=False)
        for col in AUDIT_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        return df[AUDIT_COLUMNS]
    except Exception:
        return pd.DataFrame(columns=AUDIT_COLUMNS)


def append_audit(entries):
    if not entries:
        return
    audit_df = pd.DataFrame(entries, columns=AUDIT_COLUMNS)
    write_header = not os.path.exists(AUDIT_FILE) or os.path.getsize(AUDIT_FILE) == 0
    audit_df.to_csv(AUDIT_FILE, mode="a", index=False, header=write_header)


def save_attendance(records: pd.DataFrame, date_str: str, section: str, faculty_id: str):
    current = load_attendance()
    if current.empty:
        old_rows = pd.DataFrame(columns=ATTENDANCE_COLUMNS)
    else:
        old_rows = current[(current["date"] == date_str) & (current["section"] == section)]
    old_by_reg = {str(row["reg_no"]): row for _, row in old_rows.iterrows()}

    now = datetime.datetime.now(APP_TIMEZONE).isoformat(timespec="seconds")
    records = records.copy()
    records["date"] = date_str
    records["month"] = date_str[:7]
    records["section"] = section
    records["marked_by"] = faculty_id
    records["timestamp"] = now
    records = records[ATTENDANCE_COLUMNS]

    audit_entries = []
    new_regs = set(records["reg_no"].astype(str))
    for _, row in records.iterrows():
        reg_no = str(row["reg_no"])
        old = old_by_reg.get(reg_no)
        old_status = str(old["status"]) if old is not None else "Not recorded"
        new_status = str(row["status"])
        old_name = str(old["name"]) if old is not None else ""
        if old_status != new_status or old_name != str(row["name"]):
            audit_entries.append({
                "timestamp": now, "faculty_id": faculty_id,
                "action": "Attendance added" if old is None else "Attendance updated",
                "date": date_str, "section": section, "reg_no": reg_no,
                "student_name": row["name"],
                "old_value": old_status if old_name == str(row["name"]) else f"{old_name} / {old_status}",
                "new_value": new_status if old_name == str(row["name"]) else f"{row['name']} / {new_status}",
            })
    for reg_no, old in old_by_reg.items():
        if reg_no not in new_regs:
            audit_entries.append({
                "timestamp": now, "faculty_id": faculty_id, "action": "Attendance row removed",
                "date": date_str, "section": section, "reg_no": reg_no,
                "student_name": old["name"], "old_value": old["status"], "new_value": "Removed",
            })

    if not current.empty:
        current = current[~((current["date"] == date_str) & (current["section"] == section))]
    pd.concat([current, records], ignore_index=True).to_csv(ATTENDANCE_FILE, index=False)
    append_audit(audit_entries)


def validate_roster(roster: pd.DataFrame):
    roster = roster[ROSTER_COLUMNS].copy().fillna("")
    for col in ROSTER_COLUMNS:
        roster[col] = roster[col].astype(str).str.strip()
    roster["section"] = roster["section"].str.upper()
    if (roster["reg_no"] == "").any() or (roster["name"] == "").any():
        return None, "Every student needs a registration number and name."
    if roster["reg_no"].duplicated().any():
        return None, "Registration numbers must be unique."
    if not roster["section"].isin(["A", "B"]).all():
        return None, "Section must be A or B for every student."
    roster["sno"] = range(1, len(roster) + 1)
    return roster, ""


def save_roster(roster: pd.DataFrame, faculty_id: str):
    updated, error = validate_roster(roster)
    if error:
        return error
    previous = load_students()
    old = {str(r["reg_no"]): r for _, r in previous.iterrows()}
    new = {str(r["reg_no"]): r for _, r in updated.iterrows()}
    now = datetime.datetime.now(APP_TIMEZONE).isoformat(timespec="seconds")
    changes = []
    for reg_no, row in new.items():
        before = old.get(reg_no)
        old_value = "Not on roster" if before is None else json.dumps(before.to_dict(), ensure_ascii=False)
        new_value = json.dumps(row.to_dict(), ensure_ascii=False)
        if before is None or any(str(before[c]) != str(row[c]) for c in ROSTER_COLUMNS if c != "sno"):
            changes.append({
                "timestamp": now, "faculty_id": faculty_id,
                "action": "Student added" if before is None else "Roster details updated",
                "date": "", "section": row["section"], "reg_no": reg_no,
                "student_name": row["name"], "old_value": old_value, "new_value": new_value,
            })
    for reg_no, row in old.items():
        if reg_no not in new:
            changes.append({
                "timestamp": now, "faculty_id": faculty_id, "action": "Student removed",
                "date": "", "section": row["section"], "reg_no": reg_no,
                "student_name": row["name"], "old_value": json.dumps(row.to_dict(), ensure_ascii=False),
                "new_value": "Removed from roster",
            })
    updated.to_csv(STUDENTS_FILE, index=False)
    append_audit(changes)
    return ""


def parse_target_date(question: str):
    q = question.lower()
    today = datetime.datetime.now(APP_TIMEZONE).date()
    if "yesterday" in q:
        return (today - datetime.timedelta(days=1)).isoformat()
    if "today" in q or "current day" in q:
        return today.isoformat()
    match = re.search(r"\b(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{4})\b", q)
    if not match:
        return None
    try:
        return pd.to_datetime(match.group(1), dayfirst="-" not in match.group(1)).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def query_assistant(user_prompt: str, attendance: pd.DataFrame, students: pd.DataFrame) -> str:
    """Answer common attendance questions from saved records without sending data outside the app."""
    q = user_prompt.strip().lower()
    if not q:
        return "Ask about absentees, attendance percentages, a student, a section, or a date."
    if attendance.empty:
        return "No attendance has been recorded yet. Mark attendance first, then ask again."

    date_filter = parse_target_date(q)
    data = attendance.copy()
    if date_filter:
        data = data[data["date"] == date_filter]
    else:
        month_match = re.search(r"\b(20\d{2})[-/](0?[1-9]|1[0-2])\b", q)
        if month_match:
            month = f"{month_match.group(1)}-{int(month_match.group(2)):02d}"
            data = data[data["date"].str.startswith(month)]

    section_match = re.search(r"\bsection\s*([ab])\b|\bsec\s*([ab])\b", q)
    requested_section = next((part.upper() for part in section_match.groups() if part), None) if section_match else None
    if requested_section:
        data = data[data["section"].astype(str).str.upper() == requested_section]

    # Student-specific questions take precedence over general status queries.
    student_matches = []
    for _, student in students.iterrows():
        reg_no = str(student.get("reg_no", "")).strip()
        name = str(student.get("name", "")).strip()
        if (reg_no and reg_no.lower() in q) or (len(name) > 2 and name.lower() in q):
            student_matches.append(student)
    if student_matches:
        student = student_matches[0]
        reg_no = str(student["reg_no"])
        rows = attendance[attendance["reg_no"].astype(str) == reg_no]
        if date_filter:
            rows = rows[rows["date"] == date_filter]
        if requested_section:
            rows = rows[rows["section"].astype(str).str.upper() == requested_section]
        if rows.empty:
            return f"No attendance records found for {student['name']} ({reg_no}) in that period."
        total = rows["date"].nunique()
        present = int((rows["status"] == "Present").sum())
        absent_rows = rows[rows["status"] == "Absent"]
        pct = present / max(len(rows), 1) * 100
        dates = ", ".join(absent_rows["date"].astype(str).tolist()) or "none"
        period = date_filter or "the selected period"
        if date_filter:
            status = str(rows.iloc[-1]["status"])
            return f"**{student['name']} ({reg_no})** — {status} on {date_filter}."
        return (
            f"**{student['name']} ({reg_no}) — Section {student['section']}**\n\n"
            f"- Recorded class days: {total}\n- Present: {present}\n"
            f"- Absent: {len(absent_rows)}\n- Attendance: **{pct:.1f}%**\n- Absent dates: {dates}"
        )

    if data.empty:
        return f"No attendance entries found for {date_filter or 'that period'}" + (f" in Section {requested_section}." if requested_section else ".")

    absent_terms = ("absent", "absence", "missed", "not present")
    present_terms = ("present", "attended", "in class")
    if any(term in q for term in absent_terms):
        result = data[data["status"] == "Absent"]
        label = "absent"
    elif any(term in q for term in present_terms):
        result = data[data["status"] == "Present"]
        label = "present"
    else:
        result = pd.DataFrame()
        label = ""

    if label:
        if any(term in q for term in ("how many", "count", "number of", "total")):
            return f"There were **{len(result)} {label}** in {len(data['date'].unique())} recorded class day(s)."
        if result.empty:
            return f"No students were recorded as {label} for that period."
        heading = f"{label.title()} students"
        if date_filter:
            heading += f" on {date_filter}"
        if requested_section:
            heading += f" in Section {requested_section}"
        lines = [f"- {r['name']} ({r['reg_no']}) — Section {r['section']}" for _, r in result.iterrows()]
        return f"**{heading} ({len(result)}):**\n" + "\n".join(lines)

    if any(term in q for term in ("below", "shortage", "low attendance", "defaulter")):
        threshold_match = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", q)
        threshold = float(threshold_match.group(1)) if threshold_match else 75.0
        grouped = data.groupby(["reg_no", "name", "section"])["status"].value_counts().unstack(fill_value=0)
        present_counts = grouped.get("Present", pd.Series(0, index=grouped.index))
        totals = grouped.sum(axis=1)
        percentages = present_counts / totals.clip(lower=1) * 100
        low = percentages[percentages < threshold].sort_values()
        if low.empty:
            return f"No students are below {threshold:g}% attendance in the selected period."
        lines = [
            f"- {idx[1]} ({idx[0]}, Section {idx[2]}): **{percentages.loc[idx]:.1f}%**"
            for idx in low.index
        ]
        return f"**Below {threshold:g}% attendance ({len(lines)}):**\n" + "\n".join(lines)

    if any(term in q for term in ("most absent", "top absentee", "frequent absence", "most absences")):
        totals = data[data["status"] == "Absent"].groupby(["reg_no", "name", "section"]).size().sort_values(ascending=False).head(10)
        if totals.empty:
            return "No absences were recorded for that period."
        return "**Most recorded absences:**\n" + "\n".join(
            f"- {idx[1]} ({idx[0]}, Section {idx[2]}): {count} day(s)" for idx, count in totals.items()
        )

    days = ", ".join(sorted(data["date"].astype(str).unique()))
    return (
        f"I found {len(data)} attendance entries across {data['reg_no'].nunique()} students "
        f"for {days}. Try asking who was absent, who was present, a student's attendance, "
        "or who is below 75%."
    )


def render_attendance_editor(students: pd.DataFrame, attendance: pd.DataFrame, faculty_id: str):
    st.subheader("Mark or edit daily attendance")
    date_col, section_col = st.columns(2)
    with date_col:
        selected_date = st.date_input("Attendance date", datetime.date.today())
    with section_col:
        section = st.selectbox("Section", ["A", "B"])
    date_str = selected_date.isoformat()
    month_str = selected_date.strftime("%Y-%m")

    section_students = students[students["section"] == section].copy()
    existing = attendance[(attendance["date"] == date_str) & (attendance["section"] == section)]
    if not existing.empty:
        st.info(f"This sheet has {len(existing)} saved row(s). Use the editor to make changes; each save is recorded in Faculty Activity.")

    if not section_students.empty:
        status_by_reg = dict(zip(existing["reg_no"].astype(str), existing["status"]))
        student_rows = [
            {"Reg No": str(row["reg_no"]), "Name": row["name"], "Status": status_by_reg.get(str(row["reg_no"]), "Present")}
            for _, row in section_students.sort_values("reg_no").iterrows()
        ]
        known_regs = set(section_students["reg_no"].astype(str))
        for _, row in existing.iterrows():
            if str(row["reg_no"]) not in known_regs:
                student_rows.append({"Reg No": str(row["reg_no"]), "Name": row["name"], "Status": row["status"]})
    else:
        student_rows = [
            {"Reg No": str(row["reg_no"]), "Name": row["name"], "Status": row["status"]}
            for _, row in existing.iterrows()
        ]

    st.caption("Edit registration number, name, or status. Add rows for students not yet on the roster; remove a row to omit it from this date's sheet.")
    edited = st.data_editor(
        pd.DataFrame(student_rows, columns=["Reg No", "Name", "Status"]),
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        key=f"attendance_{date_str}_{section}",
        column_config={
            "Reg No": st.column_config.TextColumn("Registration number", required=True),
            "Name": st.column_config.TextColumn("Student name", required=True),
            "Status": st.column_config.SelectboxColumn("Status", options=["Present", "Absent"], required=True),
        },
    )
    if st.button("Save attendance", type="primary", use_container_width=True):
        clean = edited.copy().fillna("")
        clean["Reg No"] = clean["Reg No"].astype(str).str.strip()
        clean["Name"] = clean["Name"].astype(str).str.strip()
        clean["Status"] = clean["Status"].astype(str).str.strip().str.title()
        clean = clean[(clean["Reg No"] != "") | (clean["Name"] != "")]
        if (clean["Reg No"] == "").any() or (clean["Name"] == "").any():
            st.error("Each row needs both a registration number and student name.")
        elif clean["Reg No"].duplicated().any():
            st.error("Registration numbers must be unique on this attendance sheet.")
        elif not clean["Status"].isin(["Present", "Absent"]).all():
            st.error("Status must be Present or Absent.")
        else:
            records = pd.DataFrame({
                "date": date_str, "month": month_str,
                "reg_no": clean["Reg No"], "name": clean["Name"],
                "section": section, "status": clean["Status"],
                "marked_by": faculty_id, "timestamp": "",
            })
            save_attendance(records, date_str, section, faculty_id)

            # Keep newly entered students available for reports and later attendance sheets.
            roster = load_students()
            known = set(roster["reg_no"].astype(str))
            additions = clean[~clean["Reg No"].isin(known)]
            if not additions.empty:
                append_rows = pd.DataFrame({
                    "sno": range(len(roster) + 1, len(roster) + len(additions) + 1),
                    "reg_no": additions["Reg No"].tolist(), "name": additions["Name"].tolist(),
                    "course": "MCA", "section": section,
                })
                combined = pd.concat([roster, append_rows], ignore_index=True)[ROSTER_COLUMNS]
                combined.to_csv(STUDENTS_FILE, index=False)
                now = datetime.datetime.now(APP_TIMEZONE).isoformat(timespec="seconds")
                append_audit([{
                    "timestamp": now, "faculty_id": faculty_id, "action": "Student added from attendance",
                    "date": date_str, "section": section, "reg_no": row["Reg No"],
                    "student_name": row["Name"], "old_value": "Not on roster",
                    "new_value": "Added to roster from attendance sheet",
                } for _, row in additions.iterrows()])
            st.success("Attendance saved. Faculty edits are visible in the Faculty Activity tab.")
            st.rerun()


def main():
    if not login_gate():
        return

    faculty_id = st.session_state["faculty_id"]
    students = load_students()
    attendance = load_attendance()
    audit = load_audit()

    with st.sidebar:
        st.title("Faculty Portal")
        st.write(f"Signed in as **{faculty_id}**")
        if st.button("Sign out", use_container_width=True):
            del st.session_state["faculty_id"]
            st.rerun()
        st.divider()
        st.metric("Students on roster", len(students))
        st.metric("Attendance entries", len(attendance))
        st.metric("Faculty activity entries", len(audit))
        if not audit.empty:
            st.caption(f"Latest activity: {audit.iloc[-1]['faculty_id']} · {audit.iloc[-1]['action']}")
        if st.button("Refresh data", use_container_width=True):
            st.rerun()

    st.title("MCA Attendance Hub")
    attendance_tab, reports_tab, chatbot_tab, roster_tab, activity_tab = st.tabs([
        "Daily Attendance", "Monthly Reports", "Attendance Chatbot", "Manage Roster", "Faculty Activity",
    ])

    with attendance_tab:
        render_attendance_editor(students, attendance, faculty_id)

    with reports_tab:
        st.subheader("Monthly absentees and attendance analysis")
        if attendance.empty:
            st.info("No attendance records to analyze yet.")
        else:
            months = sorted(attendance["date"].astype(str).str[:7].unique(), reverse=True)
            month = st.selectbox("Select month", months)
            month_data = attendance[attendance["date"].astype(str).str.startswith(month)]
            absences = month_data[month_data["status"] == "Absent"]
            k1, k2, k3 = st.columns(3)
            k1.metric("Recorded class days", month_data["date"].nunique())
            k2.metric("Absence entries", len(absences))
            k3.metric("Students absent", absences["reg_no"].nunique())
            daily = absences.groupby("date").size().rename("Absentees")
            st.subheader("Absentees by day")
            if daily.empty:
                st.info("No absences were recorded this month.")
            else:
                st.bar_chart(daily)

            summary = []
            for _, student in students.iterrows():
                records = month_data[month_data["reg_no"].astype(str) == str(student["reg_no"])]
                if not records.empty:
                    present = int((records["status"] == "Present").sum())
                    absent = int((records["status"] == "Absent").sum())
                    total = present + absent
                    summary.append({
                        "Reg No": student["reg_no"], "Name": student["name"], "Section": student["section"],
                        "Present Days": present, "Absent Days": absent, "Total Days": total,
                        "Attendance %": round(present / total * 100, 1) if total else 0,
                    })
            if summary:
                summary_df = pd.DataFrame(summary).sort_values("Absent Days", ascending=False)
                st.subheader("Student-wise attendance")
                st.dataframe(summary_df, hide_index=True, use_container_width=True)
                csv_buffer = io.StringIO()
                summary_df.to_csv(csv_buffer, index=False)
                st.download_button(
                    "Download monthly report CSV", csv_buffer.getvalue(),
                    file_name=f"mca_attendance_report_{month}.csv", mime="text/csv",
                )

    with chatbot_tab:
        st.subheader("Attendance Chatbot")
        st.caption("Ask about a student's record, absentees, attendance percentages, or a date. Answers use saved app data only.")
        prompts = ["Who was absent yesterday?", "Show Section A absentees for 2026-10-31", "Who is below 75% attendance?", "Attendance of RTC2026MCA024"]
        st.caption("Examples: " + " · ".join(prompts))
        if "chat_history" not in st.session_state:
            st.session_state["chat_history"] = []
        if st.button("Clear chat"):
            st.session_state["chat_history"] = []
            st.rerun()
        for message in st.session_state["chat_history"]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        user_input = st.chat_input("Ask an attendance question…")
        if user_input:
            answer = query_assistant(user_input, attendance, students)
            st.session_state["chat_history"].extend([
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": answer},
            ])
            st.rerun()

    with roster_tab:
        st.subheader("Student roster")
        st.caption("Edit existing details or add rows. Save records the faculty ID and before/after values in Faculty Activity.")
        roster_view = students.copy()
        roster_view.columns = ["S.No", "Reg No", "Name", "Course", "Section"]
        edited_roster = st.data_editor(
            roster_view,
            num_rows="dynamic",
            hide_index=True,
            use_container_width=True,
            key="roster_editor",
            column_config={
                "S.No": st.column_config.TextColumn("S.No", disabled=True),
                "Reg No": st.column_config.TextColumn("Reg No", required=True),
                "Name": st.column_config.TextColumn("Name", required=True),
                "Course": st.column_config.TextColumn("Course"),
                "Section": st.column_config.SelectboxColumn("Section", options=["A", "B"], required=True),
            },
        )
        if st.button("Save roster changes", type="primary"):
            candidate = edited_roster.copy()
            candidate.columns = ROSTER_COLUMNS
            error = save_roster(candidate, faculty_id)
            if error:
                st.error(error)
            else:
                st.success("Roster saved. Changes are listed in Faculty Activity.")
                st.rerun()

        st.markdown("#### Import roster CSV")
        uploaded = st.file_uploader("Choose a CSV roster", type=["csv"], key="roster_upload")
        if uploaded is not None:
            parsed = parse_flexible_csv(uploaded.getvalue().decode("utf-8-sig", errors="ignore"))
            if parsed.empty:
                try:
                    parsed = pd.read_csv(io.BytesIO(uploaded.getvalue()), dtype={"reg_no": str})
                    parsed.columns = [str(column).strip().lower() for column in parsed.columns]
                    parsed = parsed.rename(columns={"registration number": "reg_no", "student name": "name"})
                    for col in ROSTER_COLUMNS:
                        if col not in parsed.columns:
                            parsed[col] = "" if col != "sno" else range(1, len(parsed) + 1)
                    parsed = parsed[ROSTER_COLUMNS]
                except Exception:
                    parsed = pd.DataFrame(columns=ROSTER_COLUMNS)
            st.dataframe(parsed, hide_index=True, use_container_width=True)
            if st.button("Save uploaded roster", key="save_upload"):
                error = save_roster(parsed, faculty_id)
                if error:
                    st.error(error)
                else:
                    st.success("Uploaded roster saved and logged.")
                    st.rerun()

    with activity_tab:
        st.subheader("Faculty activity history")
        st.caption("Attendance status changes, roster additions, edits, and removals are recorded with faculty ID and timestamp.")
        if audit.empty:
            st.info("No faculty changes have been recorded yet.")
        else:
            filters = st.columns(3)
            faculty_filter = filters[0].selectbox("Faculty", ["All"] + sorted(audit["faculty_id"].astype(str).unique().tolist()))
            action_filter = filters[1].selectbox("Action", ["All"] + sorted(audit["action"].astype(str).unique().tolist()))
            section_filter = filters[2].selectbox("Section", ["All", "A", "B"])
            visible = audit.copy()
            if faculty_filter != "All":
                visible = visible[visible["faculty_id"] == faculty_filter]
            if action_filter != "All":
                visible = visible[visible["action"] == action_filter]
            if section_filter != "All":
                visible = visible[visible["section"] == section_filter]
            st.dataframe(visible.iloc[::-1], hide_index=True, use_container_width=True)
            st.download_button(
                "Download activity CSV", visible.to_csv(index=False),
                file_name="faculty_activity.csv", mime="text/csv",
            )


if __name__ == "__main__":
    main()
