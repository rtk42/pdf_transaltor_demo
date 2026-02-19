"""Streamlit frontend for the PDF Translator."""

from __future__ import annotations

import os
import time

import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="PDF Translator (DE/EN)", layout="centered")
st.title("PDF Translator")
st.markdown("Translate PDF documents between **German** and **English**.")

# ── Sidebar / config ─────────────────────────────────────────────────────
direction = st.selectbox(
    "Translation direction",
    options=["de-en", "en-de"],
    format_func=lambda d: "German → English" if d == "de-en" else "English → German",
)

uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

translate_btn = st.button("Translate", disabled=uploaded_file is None)

# ── State ─────────────────────────────────────────────────────────────────
if "job_id" not in st.session_state:
    st.session_state.job_id = None
if "done" not in st.session_state:
    st.session_state.done = False
if "error" not in st.session_state:
    st.session_state.error = None

# ── Upload & translate ────────────────────────────────────────────────────
if translate_btn and uploaded_file is not None:
    st.session_state.done = False
    st.session_state.error = None
    st.session_state.job_id = None

    # 1. Upload
    with st.spinner("Uploading PDF..."):
        try:
            resp = requests.post(
                f"{BACKEND_URL}/api/upload",
                files={"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")},
                data={"direction": direction},
            )
            resp.raise_for_status()
            job_id = resp.json()["job_id"]
            st.session_state.job_id = job_id
        except requests.RequestException as exc:
            detail = ""
            if hasattr(exc, "response") and exc.response is not None:
                try:
                    detail = exc.response.json().get("detail", "")
                except Exception:
                    detail = exc.response.text
            st.session_state.error = f"Upload failed: {detail or exc}"

    # 2. Trigger translation
    if st.session_state.job_id and not st.session_state.error:
        try:
            resp = requests.post(f"{BACKEND_URL}/api/translate/{st.session_state.job_id}")
            resp.raise_for_status()
        except requests.RequestException as exc:
            st.session_state.error = f"Could not start translation: {exc}"

    # 3. Poll for progress
    if st.session_state.job_id and not st.session_state.error:
        progress_bar = st.progress(0, text="Starting...")
        status_text = st.empty()

        while True:
            try:
                resp = requests.get(f"{BACKEND_URL}/api/status/{st.session_state.job_id}")
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException:
                time.sleep(1)
                continue

            status = data["status"]
            progress = data["progress"]
            message = data.get("message", "")

            progress_bar.progress(min(progress, 100), text=message)
            status_text.text(f"Status: {status}")

            if status == "DONE":
                st.session_state.done = True
                break
            elif status == "FAILED":
                st.session_state.error = data.get("error", "Translation failed.")
                break

            time.sleep(1)

        progress_bar.empty()
        status_text.empty()

# ── Show results ──────────────────────────────────────────────────────────
if st.session_state.error:
    st.error(st.session_state.error)

if st.session_state.done and st.session_state.job_id:
    st.success("Translation complete!")
    try:
        resp = requests.get(f"{BACKEND_URL}/api/result/{st.session_state.job_id}")
        resp.raise_for_status()
        st.download_button(
            label="Download Translated PDF",
            data=resp.content,
            file_name=f"translated_{st.session_state.job_id}.pdf",
            mime="application/pdf",
        )
    except requests.RequestException as exc:
        st.error(f"Could not fetch result: {exc}")
