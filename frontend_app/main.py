import mimetypes
import os
import time

import pandas as pd
import requests
import streamlit as st

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "600"))
PREVIEW_TIMEOUT = int(os.environ.get("PREVIEW_TIMEOUT_SECONDS", "120"))
COURSE_COLUMNS = ["code", "title", "credits", "grade", "semester"]
FIXED_MODEL_NAME = "qwen3.6-plus"


def _normalize_text(value):
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _normalize_credits(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _infer_content_type(uploaded_file) -> str:
    guessed_type, _ = mimetypes.guess_type(uploaded_file.name)
    return uploaded_file.type or guessed_type or "application/octet-stream"


def _courses_to_dataframe(courses):
    if not courses:
        courses = [{"code": "", "title": "", "credits": None, "grade": "", "semester": ""}]
    return pd.DataFrame(courses, columns=COURSE_COLUMNS)


def _auth_headers():
    token = st.session_state.get("access_token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _clear_login_state():
    for key in [
        "access_token",
        "username",
        "role",
        "transcript_data",
        "ocr_preview",
        "user_list",
        "backend_health",
        "extract_job_id",
        "extract_job_status",
    ]:
        st.session_state.pop(key, None)


def _handle_auth_failure():
    _clear_login_state()
    st.error("Your session is no longer authorized. Please sign in again.")
    st.stop()


def _build_payload(edited_courses):
    transcript_data = st.session_state["transcript_data"]
    courses = []
    for row in edited_courses.to_dict("records"):
        course = {
            "code": _normalize_text(row.get("code")),
            "title": _normalize_text(row.get("title")),
            "credits": _normalize_credits(row.get("credits")),
            "grade": _normalize_text(row.get("grade")),
            "semester": _normalize_text(row.get("semester")),
        }
        if any(value not in (None, "") for value in course.values()):
            courses.append(course)

    return {
        "student_info": {
            "name": _normalize_text(st.session_state.get("student_name")),
            "student_id": _normalize_text(st.session_state.get("student_id")),
            "major": _normalize_text(st.session_state.get("major")),
            "institution": _normalize_text(st.session_state.get("institution")),
        },
        "courses": courses,
        "gpa_summary": transcript_data.get("gpa_summary", {}),
        "validation_summary": transcript_data.get("validation_summary", {}),
    }


def _ocr_form_data():
    return {
        "ocr_enabled": str(bool(st.session_state.get("ocr_enabled_ui", False))).lower(),
        "ocr_language": st.session_state.get("ocr_language_ui", "eng+chi_sim"),
        "ocr_dpi": int(st.session_state.get("ocr_dpi_ui", 200)),
        "ocr_max_pages": int(st.session_state.get("ocr_max_pages_ui", 8)),
        "ocr_page_timeout_seconds": float(st.session_state.get("ocr_page_timeout_ui", 8.0)),
        "ocr_total_timeout_seconds": float(st.session_state.get("ocr_total_timeout_ui", 30.0)),
    }


def _refresh_health():
    try:
        response = requests.get(f"{BACKEND_URL}/healthz", timeout=15)
        response.raise_for_status()
        st.session_state["backend_health"] = response.json()
    except requests.RequestException as exc:
        st.session_state["backend_health"] = {"status": "unreachable", "detail": str(exc)}


def _start_extract_job(uploaded_file):
    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            _infer_content_type(uploaded_file),
        )
    }
    response = requests.post(
        f"{BACKEND_URL}/extract/transcript/jobs",
        files=files,
        data=_ocr_form_data(),
        headers=_auth_headers(),
        timeout=60,
    )
    if response.status_code in (401, 403):
        _handle_auth_failure()
    response.raise_for_status()
    payload = response.json()
    st.session_state["extract_job_id"] = payload["task_id"]
    st.session_state["extract_job_status"] = payload
    return payload


def _poll_extract_job(max_wait_seconds: int = 15):
    job_id = st.session_state.get("extract_job_id")
    if not job_id:
        return None

    deadline = time.monotonic() + max_wait_seconds
    latest_payload = None
    while time.monotonic() <= deadline:
        response = requests.get(
            f"{BACKEND_URL}/extract/transcript/jobs/{job_id}",
            headers=_auth_headers(),
            timeout=30,
        )
        if response.status_code in (401, 403):
            _handle_auth_failure()
        response.raise_for_status()
        latest_payload = response.json()
        st.session_state["extract_job_status"] = latest_payload
        if latest_payload["status"] == "completed":
            st.session_state["transcript_data"] = latest_payload["result"]
            st.session_state["student_name"] = latest_payload["result"].get("student_info", {}).get("name") or ""
            st.session_state["student_id"] = latest_payload["result"].get("student_info", {}).get("student_id") or ""
            st.session_state["major"] = latest_payload["result"].get("student_info", {}).get("major") or ""
            st.session_state["institution"] = latest_payload["result"].get("student_info", {}).get("institution") or ""
            return latest_payload
        if latest_payload["status"] == "failed":
            return latest_payload
        time.sleep(2)
    return latest_payload


def _fetch_users():
    response = requests.get(f"{BACKEND_URL}/auth/users", headers=_auth_headers(), timeout=30)
    if response.status_code in (401, 403):
        _handle_auth_failure()
    response.raise_for_status()
    st.session_state["user_list"] = response.json()


def run():
    st.set_page_config(page_title="Transcript App", layout="wide")
    st.title("AI-Powered Academic Transcript Generator")
    st.caption("Secure review workflow with login, validation, OCR preview/tuning, and polished PDF export.")

    for key, default in {
        "ocr_enabled_ui": False,
        "ocr_language_ui": "eng+chi_sim",
        "ocr_dpi_ui": 200,
        "ocr_max_pages_ui": 8,
        "ocr_page_timeout_ui": 8.0,
        "ocr_total_timeout_ui": 30.0,
        "preview_chars_ui": 4000,
        "request_timeout_ui": REQUEST_TIMEOUT,
    }.items():
        st.session_state.setdefault(key, default)

    st.sidebar.header("Access Control")

    if st.session_state.get("access_token"):
        st.sidebar.success(f"Signed in as `{st.session_state.get('username')}` ({st.session_state.get('role')})")
        if st.sidebar.button("Log Out"):
            _clear_login_state()
            st.rerun()
    else:
        with st.sidebar.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            login_clicked = st.form_submit_button("Sign In")

        if login_clicked:
            try:
                response = requests.post(
                    f"{BACKEND_URL}/auth/login",
                    json={"username": username, "password": password},
                    timeout=30,
                )
                response.raise_for_status()
                auth_payload = response.json()
                st.session_state["access_token"] = auth_payload["access_token"]
                st.session_state["username"] = auth_payload["username"]
                st.session_state["role"] = auth_payload["role"]
                _refresh_health()
                st.sidebar.success("Login successful.")
                st.rerun()
            except requests.RequestException as exc:
                st.sidebar.error(f"Login failed: {exc}")

    st.sidebar.header("OCR Settings")
    st.sidebar.caption(f"Extraction Model: `{FIXED_MODEL_NAME}`")
    st.sidebar.checkbox("Enable OCR fallback", key="ocr_enabled_ui")
    st.sidebar.text_input("OCR Language", key="ocr_language_ui", help="Example: eng+chi_sim")
    st.sidebar.number_input("OCR DPI", min_value=72, max_value=400, step=10, key="ocr_dpi_ui")
    st.sidebar.number_input("OCR Max Pages", min_value=1, max_value=50, step=1, key="ocr_max_pages_ui")
    st.sidebar.number_input("Per-page OCR Timeout (s)", min_value=1.0, max_value=60.0, step=1.0, key="ocr_page_timeout_ui")
    st.sidebar.number_input("Total OCR Timeout (s)", min_value=5.0, max_value=300.0, step=5.0, key="ocr_total_timeout_ui")
    st.sidebar.number_input("Preview Characters", min_value=500, max_value=10000, step=500, key="preview_chars_ui")
    st.sidebar.number_input("Extract Request Timeout (s)", min_value=60, max_value=1200, step=30, key="request_timeout_ui")

    if st.sidebar.button("Refresh Backend Status"):
        _refresh_health()

    if "backend_health" in st.session_state:
        health = st.session_state["backend_health"]
        if health.get("status") == "ok":
            st.sidebar.info(
                f"Backend OK\nModel: {health.get('model')}\nLLM configured: {health.get('llm_configured')}\nOCR default: {health.get('ocr_enabled')}\nLang: {health.get('ocr_language')}"
            )
        else:
            st.sidebar.error(f"Backend status: {health.get('status', 'unknown')}\n{health.get('detail', '')}")

    st.sidebar.header("Workflow")
    st.sidebar.markdown(
        """
1. Sign in with a reviewer or admin account.
2. Tune OCR settings if the file is scanned or bilingual.
3. Preview the extracted text before sending it to the model.
4. Extract, review, validate, and generate the final PDF.
"""
    )

    if not st.session_state.get("access_token"):
        st.info("Please sign in from the sidebar before extracting or generating transcripts.")
        st.stop()

    uploaded_file = st.file_uploader("Upload Transcript Source (.txt or .pdf)", type=["txt", "pdf"])
    if uploaded_file is not None:
        st.caption(
            "If extraction still feels slow, keep the fixed model `qwen3.6-plus`, preview the text first, and raise `Extract Request Timeout (s)`."
        )

    tab_titles = ["Extract & Review", "OCR Preview", "Reset Password"]
    if st.session_state.get("role") == "admin":
        tab_titles.insert(1, "User Management")
    tabs = st.tabs(tab_titles)
    tab_lookup = {title: tab for title, tab in zip(tab_titles, tabs)}

    with tab_lookup["Extract & Review"]:
        if uploaded_file is not None and st.button("Extract Structured Data", type="primary"):
            with st.spinner("Starting background extraction task..."):
                try:
                    job_payload = _start_extract_job(uploaded_file)
                    st.info(f"Extraction task `{job_payload['task_id']}` created. Polling for early result...")
                    final_payload = _poll_extract_job(
                        max_wait_seconds=min(int(st.session_state.get("request_timeout_ui", REQUEST_TIMEOUT)), 30)
                    )
                    if final_payload and final_payload["status"] == "completed":
                        st.success("Extraction successful. Please review the results before generating the PDF.")
                    elif final_payload and final_payload["status"] == "failed":
                        st.error(final_payload.get("error") or "Background extraction failed.")
                    else:
                        st.warning("The extraction is still running in the backend. Use the refresh button below to keep checking.")
                except requests.Timeout:
                    st.warning("The background task was created, but frontend polling timed out. Use the refresh button below to continue checking.")
                except requests.RequestException as exc:
                    st.error(f"Failed to extract data: {exc}")

        active_job = st.session_state.get("extract_job_status")
        if active_job and active_job.get("status") in {"queued", "running", "failed"}:
            status_col1, status_col2 = st.columns([3, 1])
            with status_col1:
                st.info(
                    f"Task `{active_job.get('task_id')}` status: `{active_job.get('status')}`. "
                    f"{active_job.get('message') or ''}"
                )
                if active_job.get("error"):
                    st.error(active_job["error"])
            with status_col2:
                if st.button("Refresh Extraction Status"):
                    try:
                        latest_payload = _poll_extract_job(max_wait_seconds=5)
                        if latest_payload and latest_payload["status"] == "completed":
                            st.success("Background extraction completed.")
                            st.rerun()
                        if latest_payload and latest_payload["status"] == "failed":
                            st.error(latest_payload.get("error") or "Background extraction failed.")
                    except requests.RequestException as exc:
                        st.error(f"Failed to refresh extraction status: {exc}")

        if "transcript_data" in st.session_state:
            transcript_data = st.session_state["transcript_data"]
            validation = transcript_data.get("validation_summary", {})
            gpa_summary = transcript_data.get("gpa_summary", {})
            st.subheader("Review and Edit")
            st.caption(
                f"Source: `{validation.get('source_file_name') or 'Current transcript'}` | Type: `{validation.get('source_file_type') or 'manual'}` | "
                f"Extraction: `{validation.get('extraction_method') or 'unknown'}` | OCR used: `{validation.get('ocr_used', False)}`"
            )
            for warning in validation.get("warnings", []):
                st.warning(warning)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Extracted Courses", len(transcript_data.get("courses", [])))
            col2.metric("Counted Credits", gpa_summary.get("total_credits", 0.0))
            calculated_gpa = gpa_summary.get("calculated_gpa")
            col3.metric("Calculated GPA", calculated_gpa if calculated_gpa is not None else "N/A")
            col4.metric("Skipped Courses", gpa_summary.get("skipped_courses", 0))

            info_col1, info_col2 = st.columns(2)
            with info_col1:
                st.text_input("Student Name", key="student_name")
                st.text_input("Major", key="major")
            with info_col2:
                st.text_input("Student ID", key="student_id")
                st.text_input("Institution", key="institution")

            edited_courses = st.data_editor(
                _courses_to_dataframe(transcript_data.get("courses", [])),
                hide_index=True,
                num_rows="dynamic",
                use_container_width=True,
                key="course_editor",
            )

            action_col1, action_col2 = st.columns(2)
            if action_col1.button("Refresh GPA and Validation"):
                try:
                    response = requests.post(
                        f"{BACKEND_URL}/validate/transcript",
                        json=_build_payload(edited_courses),
                        headers=_auth_headers(),
                        timeout=90,
                    )
                    if response.status_code in (401, 403):
                        _handle_auth_failure()
                    response.raise_for_status()
                    st.session_state["transcript_data"] = response.json()
                    st.success("Validation refreshed.")
                    st.rerun()
                except requests.RequestException as exc:
                    st.error(f"Validation failed: {exc}")

            if action_col2.button("Generate PDF", type="primary"):
                try:
                    response = requests.post(
                        f"{BACKEND_URL}/generate-pdf",
                        json=_build_payload(edited_courses),
                        headers=_auth_headers(),
                        timeout=120,
                    )
                    if response.status_code in (401, 403):
                        _handle_auth_failure()
                    response.raise_for_status()
                    st.download_button(
                        label="Download PDF Transcript",
                        data=response.content,
                        file_name="official_transcript.pdf",
                        mime="application/pdf",
                    )
                except requests.RequestException as exc:
                    st.error(f"Failed to generate PDF: {exc}")

            with st.expander("Structured JSON Preview"):
                st.json(_build_payload(edited_courses))

    with tab_lookup["OCR Preview"]:
        st.subheader("OCR Preview and Tuning")
        if uploaded_file is None:
            st.info("Upload a transcript file first to use OCR Preview.")
        elif st.button("Run OCR/Text Preview"):
            try:
                files = {
                    "file": (
                        uploaded_file.name,
                        uploaded_file.getvalue(),
                        _infer_content_type(uploaded_file),
                    )
                }
                form_data = _ocr_form_data()
                form_data["preview_chars"] = int(st.session_state.get("preview_chars_ui", 4000))
                response = requests.post(
                    f"{BACKEND_URL}/preview/ocr",
                    files=files,
                    data=form_data,
                    headers=_auth_headers(),
                    timeout=PREVIEW_TIMEOUT,
                )
                if response.status_code in (401, 403):
                    _handle_auth_failure()
                response.raise_for_status()
                st.session_state["ocr_preview"] = response.json()
                st.success("OCR preview completed.")
            except requests.RequestException as exc:
                st.error(f"OCR preview failed: {exc}")

        if "ocr_preview" in st.session_state:
            preview = st.session_state["ocr_preview"]
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Pages", preview.get("page_count") or 0)
            col2.metric("Extraction", preview.get("extraction_method") or "unknown")
            col3.metric("OCR Used", preview.get("ocr_used"))
            col4.metric("Characters", preview.get("extracted_characters") or 0)
            st.caption(
                f"Language: `{preview.get('effective_ocr_language')}` | DPI: `{preview.get('effective_ocr_dpi')}` | OCR Max Pages: `{preview.get('effective_ocr_max_pages')}`"
            )
            for warning in preview.get("warnings", []):
                st.warning(warning)
            st.text_area("Preview Text", value=preview.get("preview_text", ""), height=320)

    if "User Management" in tab_lookup:
        with tab_lookup["User Management"]:
            st.subheader("Administrator User Management")
            if st.button("Refresh User List"):
                try:
                    _fetch_users()
                    st.success("User list refreshed.")
                except requests.RequestException as exc:
                    st.error(f"Failed to load users: {exc}")

            if "user_list" in st.session_state:
                st.dataframe(pd.DataFrame(st.session_state["user_list"]), use_container_width=True, hide_index=True)

            with st.form("create_user_form"):
                new_username = st.text_input("New Username")
                new_password = st.text_input("Initial Password", type="password")
                new_role = st.selectbox("Role", options=["reviewer", "admin"])
                new_is_active = st.checkbox("Active", value=True)
                create_clicked = st.form_submit_button("Create User")

            if create_clicked:
                try:
                    response = requests.post(
                        f"{BACKEND_URL}/auth/users",
                        json={
                            "username": new_username,
                            "password": new_password,
                            "role": new_role,
                            "is_active": new_is_active,
                        },
                        headers=_auth_headers(),
                        timeout=30,
                    )
                    if response.status_code in (401, 403):
                        _handle_auth_failure()
                    response.raise_for_status()
                    st.success(f"User `{new_username}` created.")
                    _fetch_users()
                except requests.RequestException as exc:
                    st.error(f"Failed to create user: {exc}")

    with tab_lookup["Reset Password"]:
        st.subheader("Reset Password")
        is_admin = st.session_state.get("role") == "admin"
        with st.form("reset_password_form"):
            target_username = st.text_input("Username", value=st.session_state.get("username", ""))
            current_password = None
            if not is_admin:
                current_password = st.text_input("Current Password", type="password")
            new_password = st.text_input("New Password", type="password")
            reset_clicked = st.form_submit_button("Update Password")

        if reset_clicked:
            try:
                response = requests.post(
                    f"{BACKEND_URL}/auth/reset-password",
                    json={
                        "username": target_username,
                        "new_password": new_password,
                        "current_password": current_password or None,
                    },
                    headers=_auth_headers(),
                    timeout=30,
                )
                if response.status_code in (401, 403):
                    _handle_auth_failure()
                response.raise_for_status()
                st.success(response.json().get("message", "Password updated."))
            except requests.RequestException as exc:
                st.error(f"Failed to reset password: {exc}")


if __name__ == "__main__":
    run()
