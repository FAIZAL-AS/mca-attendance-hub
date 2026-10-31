import os
import io
import csv
import re
import datetime
import pandas as pd
import streamlit as st

# ==================== CONFIG & PATHS ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDENTS_FILE = os.path.join(BASE_DIR, "students.csv")
ATTENDANCE_FILE = os.path.join(BASE_DIR, "attendance_records.csv")

st.set_page_config(
    page_title="MCA Attendance & Absentees Hub",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom minimal styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 12px 16px;
        border-left: 4px solid #1E88E5;
        margin-bottom: 8px;
    }
    .low-att {
        color: #d32f2f;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


# ==================== DATA ACCESS LAYER ====================
def parse_flexible_csv(file_content: str) -> pd.DataFrame:
    """Robust parser that handles irregular commas and header noise."""
    rows = []
    lines = file_content.strip().splitlines()
    for line in lines:
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if len(parts) >= 5 and parts[1].upper().startswith("RTC2026"):
            sno = parts[0]
            reg = parts[1]
            name = parts[2]
            course = parts[3]
            sec = parts[4].upper()
            if sec not in ["A", "B"]:
                sec = "A" if "A" in parts[4:] else "B"
            rows.append({
                "sno": sno,
                "reg_no": reg,
                "name": name,
                "course": course,
                "section": sec
            })
    return pd.DataFrame(rows)


def load_students() -> pd.DataFrame:
    if os.path.exists(STUDENTS_FILE):
        try:
            return pd.read_csv(STUDENTS_FILE)
        except Exception:
            with open(STUDENTS_FILE, "r", encoding="utf-8", errors="ignore") as f:
                return parse_flexible_csv(f.read())
    return pd.DataFrame(columns=["sno", "reg_no", "name", "course", "section"])


def load_attendance() -> pd.DataFrame:
    if not os.path.exists(ATTENDANCE_FILE):
        df = pd.DataFrame(columns=[
            "date", "month", "reg_no", "name", "section", "status", "marked_by", "timestamp"
        ])
        df.to_csv(ATTENDANCE_FILE, index=False)
        return df
    try:
        df = pd.read_csv(ATTENDANCE_FILE)
        if "month" not in df.columns and not df.empty and "date" in df.columns:
            df["month"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m")
        return df
    except Exception:
        return pd.DataFrame(columns=[
            "date", "month", "reg_no", "name", "section", "status", "marked_by", "timestamp"
        ])


def save_attendance(new_records_df: pd.DataFrame, date_str: str, section: str):
    current = load_attendance()
    # Remove existing entries for this specific date and section to allow clean overwrites/edits
    if not current.empty:
        mask = (current["date"] == date_str) & (current["section"] == section)
        current = current[~mask]
    
    updated = pd.concat([current, new_records_df], ignore_index=True)
    updated.to_csv(ATTENDANCE_FILE, index=False)


# ==================== LIGHTWEIGHT CHATBOT ENGINE ====================
def query_assistant(user_prompt: str, att_df: pd.DataFrame, students_df: pd.DataFrame, api_key: str = None) -> str:
    """Lightweight rule-based NLP matcher first; Gemini Flash fallback if API key given."""
    q = user_prompt.strip().lower()

    if att_df.empty:
        return "No attendance has been recorded yet. Please mark attendance first."

    # Pattern 1: Today's absentees
    if any(k in q for k in ["today", "current day"]):
        today_s = datetime.date.today().strftime("%Y-%m-%d")
        sub = att_df[(att_df["date"] == today_s) & (att_df["status"] == "Absent")]
        if sub.empty:
            return f"No absentees recorded for today ({today_s}). Everyone present or attendance not yet marked."
        return f"**Absentees Today ({today_s}):**\n" + "\n".join([f"- {r['reg_no']} : {r['name']} (Sec {r['section']})" for _, r in sub.iterrows()])

    # Pattern 2: Specific date absentees (YYYY-MM-DD or DD-MM-YYYY)
    date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", q)
    if not date_match:
        date_match = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b", q)
    if date_match:
        target_date = date_match.group(1).replace("/", "-")
        # Normalize date
        try:
            target_date = pd.to_datetime(target_date).strftime("%Y-%m-%d")
        except Exception:
            pass
        sub = att_df[(att_df["date"] == target_date) & (att_df["status"] == "Absent")]
        if sub.empty:
            return f"No absentees found for date `{target_date}`."
        return f"**Absentees on {target_date} ({len(sub)} students):**\n" + "\n".join([f"- {r['reg_no']} : {r['name']} (Sec {r['section']})" for _, r in sub.iterrows()])

    # Pattern 3: Specific student inquiry by Reg No or Name
    found_student = None
    for _, s in students_df.iterrows():
        if str(s["reg_no"]).lower() in q or (len(str(s["name"])) > 3 and str(s["name"]).lower() in q):
            found_student = s
            break

    if found_student is not None:
        reg = found_student["reg_no"]
        name = found_student["name"]
        st_records = att_df[att_df["reg_no"] == reg]
        if st_records.empty:
            return f"Student **{name}** ({reg}) exists in roster, but no attendance recorded yet."
        total_days = st_records["date"].nunique()
        absent_days = len(st_records[st_records["status"] == "Absent"])
        present_days = total_days - absent_days
        pct = (present_days / total_days * 100) if total_days > 0 else 0
        
        absent_dates = st_records[st_records["status"] == "Absent"]["date"].tolist()
        dates_msg = f"\n*Dates absent:* {', '.join(absent_dates)}" if absent_dates else "\n*Perfect attendance so far!*"
        return f"**Attendance Report for {name} ({reg}) - Sec {found_student['section']}:**\n- Total Classes: {total_days}\n- Present: {present_days}\n- Absent: {absent_days}\n- Attendance Percentage: **{pct:.1f}%**{dates_msg}"

    # Pattern 4: Low attendance / Below 75%
    if any(k in q for k in ["shortage", "below 75", "low attendance", "defaulters"]):
        student_counts = att_df.groupby(["reg_no", "name", "section", "status"]).size().unstack(fill_value=0)
        if "Absent" not in student_counts.columns:
            return "No absentees on record yet."
        student_counts["Total"] = student_counts.sum(axis=1)
        student_counts["Percentage"] = (student_counts.get("Present", 0) / student_counts["Total"]) * 100
        low = student_counts[student_counts["Percentage"] < 75].reset_index()
        if low.empty:
            return "Great news: No students are currently below 75% attendance threshold!"
        lines = [f"- {r['name']} ({r['reg_no']}) - Sec {r['section']} : **{r['Percentage']:.1f}%** ({r['Absent']} days absent)" for _, r in low.iterrows()]
        return f"**Students with Attendance Shortage (<75%):**\n" + "\n".join(lines)

    # Pattern 5: Most absent / top absentees
    if any(k in q for k in ["most absent", "top absent", "highest absent", "frequent"]):
        abs_grp = att_df[att_df["status"] == "Absent"].groupby(["reg_no", "name", "section"]).size().reset_index(name="Days")
        abs_grp = abs_grp.sort_values(by="Days", ascending=False).head(10)
        if abs_grp.empty:
            return "No absences recorded yet."
        lines = [f"- {r['name']} ({r['reg_no']}, Sec {r['section']}): **{r['Days']} days**" for _, r in abs_grp.iterrows()]
        return "**Top Frequent Absentees:**\n" + "\n".join(lines)

    # Fallback to Gemini Flash if API Key provided
    if api_key:
        try:
            import urllib.request
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            summary_csv = att_df[["date", "reg_no", "name", "section", "status"]].tail(100).to_csv(index=False)
            payload = {
                "contents": [{
                    "parts": [{
                        "text": f"You are a helpful college attendance assistant. Answer using this CSV data:\n\n{summary_csv}\n\nQuestion: {user_prompt}\nKeep answers clear, polite and concise."
                    }]
                }]
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                res_data = json.loads(resp.read().decode())
                return res_data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            return f"Lightweight NLP could not match question. (Gemini API error: {e})"

    return "I can answer questions like:\n- *'Who is absent today?'*\n- *'Who was absent on 2026-10-31?'*\n- *'Show attendance of Adheeswaran'* or *'RTC2026MCA024'*\n- *'Who has low attendance / below 75%'*\n- *'Who are the most absent students?'*"


# ==================== MAIN APPLICATION UI ====================
def main():
    students_df = load_students()
    att_df = load_attendance()

    # Sidebar: Staff profile & Quick stats
    st.sidebar.title("📌 Staff Portal")
    staff_id = st.sidebar.text_input("Staff Name / ID", value="Faculty-1")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("Live Roster Status")
    st.sidebar.write(f"Total Enrolled: **{len(students_df)}**")
    sec_a_count = len(students_df[students_df["section"] == "A"])
    sec_b_count = len(students_df[students_df["section"] == "B"])
    st.sidebar.write(f"- Section A: **{sec_a_count}** students")
    st.sidebar.write(f"- Section B: **{sec_b_count}** students")
    st.sidebar.write(f"Attendance Records: **{len(att_df)}** entries")

    if st.sidebar.button("🔄 Sync / Refresh"):
        st.cache_data.clear()
        st.rerun()

    # Tabs
    tab_mark, tab_analytics, tab_chat, tab_manage = st.tabs([
        "✏️ Mark / Edit Attendance",
        "📊 Monthly Absentees & Reports",
        "💬 Attendance Chatbot",
        "⚙️ Manage Roster"
    ])

    # ---------------- TAB 1: MARK ATTENDANCE ----------------
    with tab_mark:
        st.subheader("Mark or Update Daily Attendance")
        c1, c2, c3 = st.columns([2, 2, 2])
        with c1:
            chosen_date = st.date_input("Select Date", datetime.date.today())
            date_str = chosen_date.strftime("%Y-%m-%d")
            month_str = chosen_date.strftime("%Y-%m")
        with c2:
            chosen_sec = st.selectbox("Select Section", ["A", "B"])
        with c3:
            st.write("")
            st.write(f"**Date:** `{date_str}` | **Section:** `{chosen_sec}`")

        sec_students = students_df[students_df["section"] == chosen_sec].copy()
        if sec_students.empty:
            st.warning(f"No students found in Section {chosen_sec}. Check 'Manage Roster' tab.")
        else:
            # Check existing marks for this date & section
            existing_records = att_df[(att_df["date"] == date_str) & (att_df["section"] == chosen_sec)]
            is_already_marked = not existing_records.empty

            if is_already_marked:
                marked_by_info = existing_records["marked_by"].iloc[0] if "marked_by" in existing_records.columns else "Unknown"
                last_time = existing_records["timestamp"].iloc[0] if "timestamp" in existing_records.columns else ""
                st.info(f"ℹ️ Attendance for **Section {chosen_sec}** on **{date_str}** was already marked by **{marked_by_info}** at {last_time}. You can edit and save changes below.")
                status_dict = dict(zip(existing_records["reg_no"], existing_records["status"]))
                sec_students["is_absent"] = sec_students["reg_no"].map(lambda r: status_dict.get(r, "Present") == "Absent")
            else:
                st.success(f"New attendance sheet for **Section {chosen_sec}** on **{date_str}**.")
                sec_students["is_absent"] = False

            # Display interactive table with checkboxes
            sec_students = sec_students.sort_values(by="reg_no").reset_index(drop=True)
            
            st.caption("Check the box to mark a student **ABSENT** (Unchecked = Present). Changes sync instantly across all staff.")
            
            # Data editor
            display_df = pd.DataFrame({
                "S.No": range(1, len(sec_students) + 1),
                "Reg No": sec_students["reg_no"],
                "Name": sec_students["name"],
                "Absent?": sec_students["is_absent"]
            })

            edited_data = st.data_editor(
                display_df,
                column_config={
                    "Absent?": st.column_config.CheckboxColumn("Mark Absent", default=False),
                    "S.No": st.column_config.NumberColumn(width="small"),
                    "Reg No": st.column_config.TextColumn(disabled=True),
                    "Name": st.column_config.TextColumn(disabled=True)
                },
                disabled=["S.No", "Reg No", "Name"],
                hide_index=True,
                use_container_width=True,
                key=f"editor_{date_str}_{chosen_sec}"
            )

            col_btn1, col_btn2 = st.columns([2, 4])
            with col_btn1:
                if st.button("💾 Submit & Sync Attendance", type="primary", use_container_width=True):
                    now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    new_rows = []
                    for _, r in edited_data.iterrows():
                        status = "Absent" if r["Absent?"] else "Present"
                        new_rows.append({
                            "date": date_str,
                            "month": month_str,
                            "reg_no": r["Reg No"],
                            "name": r["Name"],
                            "section": chosen_sec,
                            "status": status,
                            "marked_by": staff_id,
                            "timestamp": now_ts
                        })
                    save_attendance(pd.DataFrame(new_rows), date_str, chosen_sec)
                    abs_count = sum(edited_data["Absent?"])
                    st.success(f"✅ Successfully saved {chosen_sec} for {date_str}! Total Absentees: {abs_count}")
                    st.rerun()

    # ---------------- TAB 2: MONTHLY ABSENTEES & REPORTS ----------------
    with tab_analytics:
        st.subheader("Monthly Absentees & Attendance Analysis")
        if att_df.empty:
            st.info("No attendance records to analyze yet.")
        else:
            # Month Filter
            available_months = sorted(att_df["date"].apply(lambda d: str(d)[:7]).unique().tolist(), reverse=True)
            chosen_month = st.selectbox("Select Month", available_months)
            
            month_df = att_df[att_df["date"].str.startswith(chosen_month)]
            abs_month = month_df[month_df["status"] == "Absent"]

            # Key KPI Cards
            working_days = month_df["date"].nunique()
            total_absences = len(abs_month)
            unique_absentees = abs_month["reg_no"].nunique()
            
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Working Days Recorded", working_days)
            kpi2.metric("Total Absences", total_absences)
            kpi3.metric("Distinct Students Absent", unique_absentees)

            st.markdown("---")

            # Chart: Daily absentee trend
            st.write(f"### Absentees Count per Day ({chosen_month})")
            daily_abs = abs_month.groupby("date").size().reset_index(name="Absentees")
            if not daily_abs.empty:
                st.bar_chart(daily_abs.set_index("date"))
            else:
                st.write("No absentees in this month!")

            # Detailed table by student
            st.write("### Student-Wise Attendance Percentage")
            # Aggregated metrics per student in this month
            summary = []
            for _, s in students_df.iterrows():
                st_data = month_df[month_df["reg_no"] == s["reg_no"]]
                if not st_data.empty:
                    presents = len(st_data[st_data["status"] == "Present"])
                    absents = len(st_data[st_data["status"] == "Absent"])
                    total = presents + absents
                    pct = (presents / total * 100) if total > 0 else 100
                    summary.append({
                        "Reg No": s["reg_no"],
                        "Name": s["name"],
                        "Section": s["section"],
                        "Present Days": presents,
                        "Absent Days": absents,
                        "Total Days": total,
                        "Attendance %": round(pct, 1)
                    })
            if summary:
                sum_df = pd.DataFrame(summary).sort_values(by="Absent Days", ascending=False)
                st.dataframe(
                    sum_df,
                    column_config={
                        "Attendance %": st.column_config.ProgressColumn(
                            "Attendance %",
                            format="%.1f%%",
                            min_value=0,
                            max_value=100
                        )
                    },
                    hide_index=True,
                    use_container_width=True
                )

                # CSV Download Button
                csv_buffer = io.StringIO()
                sum_df.to_csv(csv_buffer, index=False)
                st.download_button(
                    label="📥 Download Monthly Report CSV",
                    data=csv_buffer.getvalue(),
                    file_name=f"mca_attendance_report_{chosen_month}.csv",
                    mime="text/csv"
                )

    # ---------------- TAB 3: CHATBOT ----------------
    with tab_chat:
        st.subheader("💬 Lightweight Attendance Assistant")
        st.caption("Ask queries in natural language about student attendance, absentees, or shortage.")

        with st.expander("🔑 Optional: Add Gemini API Key for Advanced Semantic Reasoning"):
            api_key = st.text_input("Gemini API Key", type="password", help="Leave blank to use fast built-in rule matching engine.")

        # Chat history
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        # Display history
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        user_input = st.chat_input("Ask a question (e.g. 'Who is absent today?', 'Attendance of Adheeswaran', 'Students below 75%')...")
        if user_input:
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

            # Generate reply
            answer = query_assistant(user_input, att_df, students_df, api_key=api_key if api_key else None)
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
            with st.chat_message("assistant"):
                st.markdown(answer)

    # ---------------- TAB 4: MANAGE ROSTER ----------------
    with tab_manage:
        st.subheader("Student Roster Management")
        st.write(f"Currently managing **{len(students_df)}** students across sections A and B.")
        st.dataframe(students_df, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.write("### Upload Updated Roster CSV")
        st.caption("Upload raw or updated CSV sheet with student details. Empty rows and trailing commas will be auto-cleaned.")
        uploaded = st.file_uploader("Upload CSV", type=["csv"])
        if uploaded is not None:
            content = uploaded.getvalue().decode("utf-8", errors="ignore")
            parsed_df = parse_flexible_csv(content)
            if not parsed_df.empty:
                parsed_df.to_csv(STUDENTS_FILE, index=False)
                st.success(f"Successfully loaded and saved {len(parsed_df)} students!")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("Could not parse student entries. Ensure Registration Numbers start with RTC2026.")


if __name__ == "__main__":
    main()
