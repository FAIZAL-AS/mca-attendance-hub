# MCA Attendance Hub

Streamlit app for daily attendance, monthly summaries, roster maintenance, and faculty activity history.

## Faculty login

The app supports `Faculty-1` through `Faculty-10`. All IDs use one shared password. Configure it in Streamlit Community Cloud under **App settings → Secrets**:

```toml
FACULTY_SHARED_PASSWORD = "set-a-private-password-here"
```

For local use, set the `FACULTY_SHARED_PASSWORD` environment variable before running `streamlit run app.py`. Do not commit the real password or `.streamlit/secrets.toml`.

## Local run

```powershell
python -m pip install -r requirements.txt
$env:FACULTY_SHARED_PASSWORD = "your-private-password"
python -m streamlit run app.py
```

## Attendance and history

- Daily attendance rows can be edited, added, and removed. New students added from a daily sheet are added to the roster.
- The roster editor supports changing existing records and adding or removing students.
- Attendance and roster changes include the signed-in faculty ID and are shown in the Faculty Activity tab.
- `faculty_activity.csv` and `.streamlit/secrets.toml` are ignored by Git to keep the audit log and password out of commits.

The app currently stores its records in CSV files alongside the app. On hosted Streamlit deployments, local file changes may not survive a restart or redeployment. Use a persistent database or storage service before relying on the hosted app as the only copy of attendance or audit data.
