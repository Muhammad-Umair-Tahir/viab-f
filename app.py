"""
VIAB BOQ Orchestrator Streamlit App

This app connects to the FastAPI backend server that should be running on localhost:8000.
To start the backend server, run: python main.py
The server will expose the following endpoints:
- POST /api/v1/boq/run - for intelligent workflow routing
- GET /api/v1/boq/state - for session state
- GET / - health check endpoint
"""

import streamlit as st
import requests
import uuid
import json
import os
from dotenv import load_dotenv
import io
from typing import List, Optional

# Load environment variables
load_dotenv()

# --------- CONFIG ---------
BASE_API_URL = os.getenv("BASE_API_URL", "http://127.0.0.1:8000")
WORKFLOW_ENDPOINT = f"{BASE_API_URL}/api/v1/boq/workflow"
STATE_ENDPOINT = f"{BASE_API_URL}/api/v1/boq/state"

st.set_page_config(page_title="VIAB BOQ Orchestrator", layout="wide")

# --------- BACKEND COMMUNICATION ---------
def send_to_workflow(msg: str, files: Optional[List] = None, user_id: str = None, session_id: str = None):
    """
    Send message and files to the workflow endpoint.
    """
    data = {
        "user_id": user_id,
        "session_id": session_id,
        "user_input": msg
    }
    files_payload = []
    if files:
        for file in files:
            files_payload.append(("files", (file.name, file.getvalue(), file.type)))
    try:
        response = requests.post(
            WORKFLOW_ENDPOINT,
            data=data,
            files=files_payload if files_payload else None,
            timeout=300
        )
        response.raise_for_status()
        result = response.json()
        return format_workflow_response(result)
    except requests.exceptions.RequestException as e:
        return f":red[Backend error: {e}]"
    except Exception as e:
        return f":red[Unexpected error: {e}]"

def format_workflow_response(result: dict) -> str:
    """Format the workflow response for display."""
    response_parts = []
    # Show main content
    if "content" in result:
        response_parts.append(result["content"])
    # Show agent metadata if available
    if "boq_data" in result:
        response_parts.append(str(result["boq_data"]))
    if "visualization_data" in result:
        response_parts.append(str(result["visualization_data"]))
    if "analysis_data" in result:
        response_parts.append(str(result["analysis_data"]))
    if "interview_data" in result:
        response_parts.append(str(result["interview_data"]))
    return "\n\n".join(response_parts)

def get_session_state():
    """Get the last session state from backend."""
    try:
        response = requests.get(STATE_ENDPOINT, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to get session state: {e}")
        return None

def check_backend_health():
    """Check if the backend API is running."""
    try:
        response = requests.get(f"{BASE_API_URL}/", timeout=5)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException:
        return False

# --------- SIDEBAR ---------
with st.sidebar:
    st.header("Project & Controls")

    # File upload
    uploaded_files = st.file_uploader(
        "Architectural files (PDF, image, etc):",
        type=["pdf", "jpg", "jpeg", "png", "bmp", "gif", "webp"],
        accept_multiple_files=True,
        key="file_upload"
    )

    st.markdown("---")

    # User and session IDs
    user_input_id = st.text_input("User ID (blank = random):", value="", key="user_id_input")
    session_input_id = st.text_input("Session ID (blank = random):", value="", key="session_id_input")

    # Always generate if blank
    if user_input_id.strip():
        user_id = user_input_id.strip()
    else:
        if "user_id" not in st.session_state or not st.session_state["user_id"]:
            st.session_state["user_id"] = str(uuid.uuid4())
        user_id = st.session_state["user_id"]

    if session_input_id.strip():
        session_id = session_input_id.strip()
    else:
        if "session_id" not in st.session_state or not st.session_state["session_id"]:
            st.session_state["session_id"] = str(uuid.uuid4())
        session_id = st.session_state["session_id"]

    st.text(f"User: {user_id[:8]}")
    st.text(f"Session: {session_id[:8]}")

    # Session controls
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 New Session"):
            st.session_state["session_id"] = str(uuid.uuid4())
            st.session_state["chat_messages"] = []
            st.rerun()

    with col2:
        if st.button("📊 Session State"):
            state = get_session_state()
            if state:
                st.json(state)
            else:
                st.error("No session state found")

    st.markdown("---")

    # Backend status indicator
    if check_backend_health():
        st.success("🟢 Backend API Connected")
    else:
        st.error("🔴 Backend API Offline")
        st.caption("Make sure the backend server is running on localhost:8000")

# Add this in your sidebar after file_uploader
if uploaded_files:
    if st.button("Upload Files Only"):
        with st.spinner("Uploading files..."):
            bot_msg = send_to_workflow(
                msg="",  # No message, just files
                files=uploaded_files,
                user_id=user_id,
                session_id=session_id
            )
            st.session_state["chat_messages"].append({"role": "assistant", "msg": bot_msg})
        st.rerun()

# --------- CHAT HISTORY ---------
if "chat_messages" not in st.session_state:
    st.session_state["chat_messages"] = []

chat_history = st.session_state["chat_messages"]

# --------- MAIN PAGE ---------
st.markdown("<h1 style='text-align: center;'>VIAB BOQ Orchestrator 🤖</h1>", unsafe_allow_html=True)
st.caption("Professional AI agent for Quantity Surveying – Interview & Plan Analysis")

st.markdown("---")

# Display chat history
for entry in chat_history:
    with st.chat_message(entry["role"]):
        st.markdown(entry["msg"])

# New user message input
user_msg = st.chat_input("Your question or request...")
if user_msg is not None:
    st.session_state["chat_messages"].append({"role": "user", "msg": user_msg})

    with st.spinner("Processing your request..."):
        bot_msg = send_to_workflow(
            user_msg,
            files=uploaded_files,
            user_id=user_id,
            session_id=session_id
        )
        st.session_state["chat_messages"].append({"role": "assistant", "msg": bot_msg})

    st.rerun()

st.markdown("---")

# Help section
with st.expander("ℹ️ Help & Usage"):
    st.markdown("""
    **Usage Tips:**
    - Upload files first, then ask questions
    - Use keywords like "BOQ", "bill of quantities" for BOQ generation
    - The interface shows only the essential results and responses
    - Check session state to see generated files in the sidebar

    **Smart Routing:**
    - Files + BOQ keywords → Analysis then BOQ generation
    - Files + no BOQ keywords → Analysis only
    - Files only → Automatic analysis
    - Text + BOQ keywords → BOQ agent response
    - Text + no BOQ keywords → Interview agent conversation
    """)

st.markdown("---")
st.markdown("© 2024 VIAB / AI-driven Quantity Surveying")
