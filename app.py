"""
VIAB BOQ Orchestrator Streamlit App

This app connects to the FastAPI backend server that should be running on localhost:8000.
To start the backend server, run: python agents/main.py
The server will expose the following endpoints:
- POST /api/v1/boq/workflow - for intelligent workflow routing
- POST /api/v1/boq/analyze-only - for file analysis only
- POST /api/v1/boq/generate-boq - for BOQ generation
- POST /api/v1/boq/chat - for chat-only interactions
- GET /api/v1/boq/status/{user_id}/{session_id} - for session status
- DELETE /api/v1/boq/cleanup/{user_id}/{session_id} - for cleanup
- GET / - health check endpoint
"""

import streamlit as st
import requests
import uuid
import json
import os
from dotenv import load_dotenv
from fpdf import FPDF
import io
from typing import List, Optional

# Load environment variables
load_dotenv()

# --------- CONFIG ---------
BASE_API_URL = os.getenv("BASE_API_URL", "http://localhost:8000")
WORKFLOW_ENDPOINT = f"{BASE_API_URL}/api/v1/boq/workflow"
ANALYZE_ENDPOINT = f"{BASE_API_URL}/api/v1/boq/analyze-only"
BOQ_ENDPOINT = f"{BASE_API_URL}/api/v1/boq/generate-boq"
CHAT_ENDPOINT = f"{BASE_API_URL}/api/v1/boq/chat"
STATUS_ENDPOINT = f"{BASE_API_URL}/api/v1/boq/status"
CLEANUP_ENDPOINT = f"{BASE_API_URL}/api/v1/boq/cleanup"

st.set_page_config(page_title="VIAB BOQ Orchestrator", layout="wide")

# --------- BACKEND COMMUNICATION ---------
def send_to_workflow(msg: str, files: Optional[List] = None, user_id: str = None, session_id: str = None, endpoint_type: str = "auto"):
    """
    Send message to the appropriate workflow endpoint.
    
    Args:
        msg: User message
        files: List of uploaded files
        user_id: User identifier
        session_id: Session identifier
        endpoint_type: "auto", "analyze", "boq", or "chat"
    """
    # Prepare form data
    data = {
        "user_id": user_id,
        "session_id": session_id,
    }
    
    # Choose endpoint based on type
    if endpoint_type == "analyze":
        endpoint = ANALYZE_ENDPOINT
    elif endpoint_type == "boq":
        endpoint = BOQ_ENDPOINT
        if not msg.lower().strip():
            msg = "Generate BOQ for uploaded files"
    elif endpoint_type == "chat":
        endpoint = CHAT_ENDPOINT
        data["user_input"] = msg
    else:  # auto
        endpoint = WORKFLOW_ENDPOINT
        data["user_input"] = msg
    
    # Add user_input for non-chat endpoints
    if endpoint_type != "chat" and msg:
        data["user_input"] = msg
    
    # Prepare files payload
    files_payload = []
    if files:
        for file in files:
            files_payload.append(("files", (file.name, file.getvalue(), file.type)))
    
    try:
        response = requests.post(
            endpoint,
            data=data,
            files=files_payload if files_payload else None,
            timeout=300  # long timeout for BOQ
        )
        response.raise_for_status()
        result = response.json()
        
        if result.get("success"):
            return format_workflow_response(result)
        else:
            return f":red[Error: {result.get('error', 'Unknown error')}]"
            
    except requests.exceptions.RequestException as e:
        return f":red[Backend error: {e}]"
    except Exception as e:
        return f":red[Unexpected error: {e}]"

def format_workflow_response(result: dict) -> str:
    """Format the workflow response for display - results only."""
    response_parts = []
    
    # Extract workflow responses
    if "workflow_responses" in result:
        responses = result["workflow_responses"]
    elif "analysis_results" in result:
        responses = result["analysis_results"]
    elif "boq_results" in result:
        responses = result["boq_results"]
    elif "chat_responses" in result:
        responses = result["chat_responses"]
    else:
        responses = []
    
    if responses:
        for step in responses:
            content = step.get("content", "")
            if content:
                response_parts.append(content)
            
            # Extract actual data from metadata if available
            metadata = step.get("metadata")
            if metadata and isinstance(metadata, dict):
                # Check for BOQ data
                if "boq_data" in metadata:
                    boq_data = metadata["boq_data"]
                    if isinstance(boq_data, dict):
                        # If it's a dict, format it nicely
                        if "content" in boq_data:
                            response_parts.append(boq_data["content"])
                        else:
                            # Format dict as readable text
                            formatted_boq = format_dict_data(boq_data)
                            response_parts.append(formatted_boq)
                    elif isinstance(boq_data, str):
                        response_parts.append(boq_data)
                
                # Check for analysis data
                elif "analysis_data" in metadata:
                    analysis_data = metadata["analysis_data"]
                    if isinstance(analysis_data, dict):
                        if "content" in analysis_data:
                            response_parts.append(analysis_data["content"])
                        else:
                            # Format dict as readable text
                            formatted_analysis = format_dict_data(analysis_data)
                            response_parts.append(formatted_analysis)
                    elif isinstance(analysis_data, str):
                        response_parts.append(analysis_data)
                
                # Check for interview data
                elif "interview_data" in metadata:
                    interview_data = metadata["interview_data"]
                    if isinstance(interview_data, dict):
                        if "content" in interview_data:
                            response_parts.append(interview_data["content"])
                        else:
                            # Format dict as readable text
                            formatted_interview = format_dict_data(interview_data)
                            response_parts.append(formatted_interview)
                    elif isinstance(interview_data, str):
                        response_parts.append(interview_data)
    
    # If no responses found, show a fallback message
    if not response_parts:
        response_parts.append("Processing completed successfully.")
    
    return "\n\n".join(response_parts)

def format_dict_data(data: dict) -> str:
    """Format dictionary data into readable text."""
    if not isinstance(data, dict):
        return str(data)
    
    formatted_parts = []
    
    for key, value in data.items():
        # Skip metadata fields
        if key in ["timestamp", "user_id", "session_id", "workflow_type"]:
            continue
            
        # Format key
        formatted_key = key.replace("_", " ").title()
        
        if isinstance(value, dict):
            # Nested dictionary
            formatted_parts.append(f"**{formatted_key}:**")
            for sub_key, sub_value in value.items():
                formatted_sub_key = sub_key.replace("_", " ").title()
                formatted_parts.append(f"  • {formatted_sub_key}: {sub_value}")
        elif isinstance(value, list):
            # List
            formatted_parts.append(f"**{formatted_key}:**")
            for item in value:
                formatted_parts.append(f"  • {item}")
        else:
            # Simple value
            formatted_parts.append(f"**{formatted_key}:** {value}")
    
    return "\n".join(formatted_parts)

def get_session_status(user_id: str, session_id: str):
    """Get the status of the current session."""
    try:
        response = requests.get(f"{STATUS_ENDPOINT}/{user_id}/{session_id}", timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to get session status: {e}")
        return None

def cleanup_session(user_id: str, session_id: str):
    """Clean up the current session."""
    try:
        response = requests.delete(f"{CLEANUP_ENDPOINT}/{user_id}/{session_id}", timeout=10)
        response.raise_for_status()
        result = response.json()
        if result.get("success"):
            st.success(f"Cleaned up {len(result.get('deleted_files', []))} files")
            return True
        else:
            st.error(f"Cleanup failed: {result.get('error')}")
            return False
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to cleanup session: {e}")
        return False

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
    
    # Workflow mode selection
    workflow_mode = st.selectbox(
        "Workflow Mode:",
        ["auto", "analyze", "boq", "chat"],
        format_func=lambda x: {
            "auto": "🤖 Auto (Smart Routing)",
            "analyze": "🔍 Analysis Only",
            "boq": "📊 BOQ Generation",
            "chat": "💬 Chat Only"
        }[x],
        help="Choose how to process your input"
    )
    
    st.markdown("---")
    
    # File upload (disabled for chat mode)
    if workflow_mode != "chat":
        # Use a key that can be reset to clear the file uploader
        file_uploader_key = st.session_state.get("file_uploader_key", "file_upload_1")
        
        uploaded_files = st.file_uploader(
            "Architectural files (PDF, image, etc):",
            type=["pdf", "jpg", "jpeg", "png", "bmp", "gif", "webp"],
            accept_multiple_files=True,
            key=file_uploader_key
        )
        
        # Show upload button only if files are selected
        if uploaded_files:
            upload_clicked = st.button("⬆ Upload Files", type="primary")
            st.caption(f"{len(uploaded_files)} file(s) selected")
        else:
            upload_clicked = False
            st.info("Select files to upload")
    else:
        uploaded_files = None
        upload_clicked = False
        st.info("Chat mode: File upload disabled")
    
    st.markdown("---")
    
    # User and session IDs
    user_input_id = st.text_input("User ID (blank = random):", value="", key="user_id_input")
    if user_input_id:
        user_id = user_input_id
    else:
        user_id = st.session_state.get("user_id", str(uuid.uuid4()))
        st.session_state["user_id"] = user_id
        
    session_input_id = st.text_input("Session ID (blank = random):", value="", key="session_id_input")
    if session_input_id:
        session_id = session_input_id
        st.session_state["session_id"] = session_id
    else:
        session_id = st.session_state.get("session_id", str(uuid.uuid4()))
        st.session_state["session_id"] = session_id
    
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
        if st.button("🗑️ Cleanup"):
            if cleanup_session(user_id, session_id):
                st.session_state["chat_messages"] = []
                st.rerun()
    
    # Session status
    if st.button("📊 Session Status"):
        status = get_session_status(user_id, session_id)
        if status and status.get("success"):
            st.json(status)
        elif status:
            st.error("No session data found")
    
    st.markdown("---")
    
    # Backend status indicator
    if check_backend_health():
        st.success("🟢 Backend API Connected")
    else:
        st.error("🔴 Backend API Offline")
        st.caption("Make sure the backend server is running on localhost:8000")

# --------- CHAT HISTORY ---------
if "chat_messages" not in st.session_state:
    st.session_state["chat_messages"] = []

chat_history = st.session_state["chat_messages"]

# --------- CUSTOM RENDERING FUNCTIONS (keep existing) ---------
def render_plan_json(data):
    st.markdown("## 📑 Table of Contents")
    toc = []
    if "plan_summary" in data:
        toc.append("[Plan Summary](#plan-summary)")
    if "room_details" in data:
        toc.append("[Room Details](#room-details)")
    if "elevation_details" in data:
        toc.append("[Elevation Details](#elevation-details)")
    st.markdown(" - " + "\n - ".join(toc), unsafe_allow_html=True)

    # ---- PLAN SUMMARY ----
    if "plan_summary" in data:
        st.markdown("<h3 id='plan-summary'>🏠 Plan Summary</h3>", unsafe_allow_html=True)
        summary = data["plan_summary"]
        rows = []
        for k, v in summary.items():
            if isinstance(v, dict):
                for subk, subv in v.items():
                    rows.append((f"{k.replace('_',' ').title()} - {subk.title()}", subv))
            else:
                rows.append((k.replace("_", " ").title(), v))
        st.table(rows)

    # ---- ROOM DETAILS ----
    if "room_details" in data:
        st.markdown("<h3 id='room-details'>🛏 Room Details</h3>", unsafe_allow_html=True)
        room_details = data["room_details"]
        for room, details in room_details.items():
            with st.expander(room.replace("_", " ").title()):
                for k, v in details.items():
                    if k == "features" and isinstance(v, list):
                        st.markdown("*Features:*")
                        for feat in v:
                            st.markdown(f"- {feat}")
                    else:
                        st.markdown(f"**{k.replace('_', ' ').title()}:** {v}")

    # ---- ELEVATION DETAILS ----
    if "elevation_details" in data:
        st.markdown("<h3 id='elevation-details'>🏗 Elevation Details</h3>", unsafe_allow_html=True)
        elevations = data["elevation_details"]
        for side, side_details in elevations.items():
            with st.expander(side.replace("_", " ").title()):
                if side_details:
                    for k, v in side_details.items():
                        st.markdown(f"**{k.replace('_', ' ').title()}:** {v}")
                else:
                    st.info("No details provided.")

def try_render_plan_json(bot_msg):
    """Try rendering the assistant message as plan table if JSON, else False."""
    try:
        data = json.loads(bot_msg)
        if any(key in data for key in ("plan_summary", "room_details", "elevation_details")):
            render_plan_json(data)
            return True
        return False
    except Exception:
        return False

def plan_json_to_pdf(data):
    """Convert plan JSON to PDF (keep existing implementation)."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, "Plan Analysis Report", ln=True, align="C")
    pdf.ln(10)

    # Plan Summary
    if "plan_summary" in data:
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "🏠 Plan Summary", ln=True)
        pdf.set_font("Arial", size=11)
        summary = data["plan_summary"]
        for k, v in summary.items():
            if isinstance(v, dict):
                for subk, subv in v.items():
                    pdf.cell(0, 8, f"{k.replace('_',' ').title()} - {subk.title()}: {subv}", ln=True)
            else:
                pdf.cell(0, 8, f"{k.replace('_',' ').title()}: {v}", ln=True)
        pdf.ln(5)

    pdf_buffer = io.BytesIO()
    pdf.output(pdf_buffer)
    pdf_buffer.seek(0)
    return pdf_buffer

# --------- MAIN PAGE ---------
st.markdown("<h1 style='text-align: center;'>VIAB BOQ Orchestrator 🤖</h1>", unsafe_allow_html=True)
st.caption("Professional AI agent for Quantity Surveying – Interview & Plan Analysis")

# Show current mode
mode_emoji = {
    "auto": "🤖",
    "analyze": "🔍", 
    "boq": "📊",
    "chat": "💬"
}

mode_descriptions = {
    "auto": "Smart routing based on your input",
    "analyze": "File analysis only", 
    "boq": "BOQ generation workflow",
    "chat": "Text-only conversation"
}

st.info(f"{mode_emoji[workflow_mode]} Current Mode: **{workflow_mode.upper()}** - {mode_descriptions[workflow_mode]}")

st.markdown("---")

# Handle explicit file upload
if upload_clicked and uploaded_files:
    with st.spinner("Uploading files and processing..."):
        bot_msg = send_to_workflow(
            "Please analyze these uploaded files", 
            files=uploaded_files, 
            user_id=user_id, 
            session_id=session_id,
            endpoint_type=workflow_mode
        )
        st.session_state["chat_messages"].append(
            {"role": "assistant", "msg": bot_msg}
        )
        
        # Clear the file uploader by changing its key
        current_key = st.session_state.get("file_uploader_key", "file_upload_1")
        if current_key == "file_upload_1":
            st.session_state["file_uploader_key"] = "file_upload_2"
        else:
            st.session_state["file_uploader_key"] = "file_upload_1"
        
        # Show success message
        st.success(f"✅ {len(uploaded_files)} file(s) processed successfully!")
        
    st.rerun()

# Display chat history
for entry in chat_history:
    with st.chat_message(entry["role"]):
        if entry["role"] == "assistant" and try_render_plan_json(entry["msg"]):
            pass  # Already rendered by try_render_plan_json
        else:
            st.markdown(entry["msg"])

# New user message input
user_msg = st.chat_input("Your question or request...")
if user_msg is not None:
    st.session_state["chat_messages"].append({"role": "user", "msg": user_msg})
    
    with st.spinner("Processing your request..."):
        # For text input, also consider any currently selected files
        files_to_send = uploaded_files if workflow_mode != "chat" else None
        
        bot_msg = send_to_workflow(
            user_msg, 
            files=files_to_send,
            user_id=user_id, 
            session_id=session_id,
            endpoint_type=workflow_mode
        )
        st.session_state["chat_messages"].append({"role": "assistant", "msg": bot_msg})
        
        # If files were sent with the message, clear them
        if files_to_send:
            current_key = st.session_state.get("file_uploader_key", "file_upload_1")
            if current_key == "file_upload_1":
                st.session_state["file_uploader_key"] = "file_upload_2"
            else:
                st.session_state["file_uploader_key"] = "file_upload_1"
            
            st.success(f"✅ Message sent with {len(files_to_send)} file(s)!")
    
    st.rerun()

st.markdown("---")

# Download functionality for plan JSON
plan_json_msg = None
for entry in reversed(chat_history):
    if entry["role"] == "assistant":
        try:
            data = json.loads(entry["msg"])
            if any(key in data for key in ("plan_summary", "room_details", "elevation_details")):
                plan_json_msg = data
                break
        except Exception:
            continue

if plan_json_msg:
    pdf_buffer = plan_json_to_pdf(plan_json_msg)
    st.download_button(
        label="⬇ Download Plan as PDF",
        data=pdf_buffer,
        file_name="plan_analysis.pdf",
        mime="application/pdf"
    )

# Help section
with st.expander("ℹ️ Help & Usage"):
    st.markdown("""
    **Workflow Modes:**
    - **🤖 Auto**: Intelligently routes your request based on keywords (BOQ, bill of quantities, etc.)
    - **🔍 Analysis Only**: Forces file analysis without BOQ generation
    - **📊 BOQ Generation**: Forces BOQ generation workflow
    - **💬 Chat Only**: Text-only conversation mode (no file processing)
    
    **Usage Tips:**
    - Upload files first, then ask questions
    - Use keywords like "BOQ", "bill of quantities" for BOQ generation
    - The interface shows only the essential results and responses
    - Check session status to see generated files in the sidebar
    - Use cleanup to remove session files when done
    
    **Smart Routing (Auto Mode):**
    - Files + BOQ keywords → Analysis then BOQ generation
    - Files + no BOQ keywords → Analysis only
    - Files only → Automatic analysis
    - Text + BOQ keywords → BOQ agent response
    - Text + no BOQ keywords → Interview agent conversation
    """)

st.markdown("---")
st.markdown("© 2024 VIAB / AI-driven Quantity Surveying")

