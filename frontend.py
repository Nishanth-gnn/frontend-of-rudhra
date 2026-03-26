import streamlit as st
st.set_page_config(page_title="Agent Chat", layout="wide")

import asyncio
import uuid
import time
import base64
import os
import io
from PIL import Image
from datetime import datetime

# PDF Handling
from PyPDF2 import PdfReader, PdfWriter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# Internal modules
from backend import UnifiedAgent, generate_chat_title
from rag import ask_pdf
from db_bck import DatabaseManager  # ✅ Integrated Database
from langchain_core.messages import HumanMessage, AIMessage

# UI Components
from streamlit_mic_recorder import mic_recorder 
from streamlit_paste_button import paste_image_button
import tkinter as tk
from tkinter import filedialog

from rag_pages import render_material_library
from exam_mode import run_exam_mode
from personalization_ui import render_personalization_page

# --------------------------------------------------
# INITIALIZATION
# --------------------------------------------------
db = DatabaseManager()

if "agent" not in st.session_state:
    agent = UnifiedAgent()
    asyncio.run(agent.initialize())
    st.session_state.agent = agent

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "pdf_responses_map" not in st.session_state:
    st.session_state.pdf_responses_map = {}

# Simple UI toggles
for key in ["exam_mode", "rag_mode", "show_library", "show_personalization"]:
    if key not in st.session_state:
        st.session_state[key] = False

# Keys for refreshing widgets
if "uploader_key" not in st.session_state: st.session_state.uploader_key = 0
if "voice_key" not in st.session_state: st.session_state.voice_key = 1000
if "current_image_bytes" not in st.session_state: st.session_state.current_image_bytes = None

active_tid = st.session_state.thread_id

# --------------------------------------------------
# PDF UTILS
# --------------------------------------------------
def choose_pdf_path():
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.asksaveasfilename(
            title="Select PDF for this Conversation",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")]
        )
        root.destroy()
        return path if path else None
    except:
        return None

def append_to_pdf(file_path, query, response):
    try:
        styles = getSampleStyleSheet()
        packet = io.BytesIO()
        q_style = styles["Heading4"]
        q_style.textColor = colors.HexColor("#1F618D") 
        r_style = styles["Normal"]
        
        doc = SimpleDocTemplate(packet)
        elements = []
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f"<b>Time:</b> {timestamp}", styles["Italic"]))
        elements.append(Spacer(1, 8))
        elements.append(Paragraph(f"<b>Query:</b> {query}", q_style))
        elements.append(Spacer(1, 6))
        
        clean_res = response.replace('\n', '<br/>')
        elements.append(Paragraph(f"<b>Agent:</b> {clean_res}", r_style))
        elements.append(Spacer(1, 20))
        
        doc.build(elements)
        packet.seek(0)
        
        new_pdf = PdfReader(packet)
        writer = PdfWriter()

        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            existing_pdf = PdfReader(file_path)
            for page in existing_pdf.pages:
                writer.add_page(page)
        
        for page in new_pdf.pages:
            writer.add_page(page)

        with open(file_path, "wb") as f:
            writer.write(f)
        return True
    except Exception as e:
        st.error(f"Append Error: {e}")
        return False

# --------------------------------------------------
# PAGE ROUTING
# --------------------------------------------------
if st.session_state.exam_mode:
    if st.button("⬅ Back to Chat"):
        st.session_state.exam_mode = False
        st.rerun()
    run_exam_mode()
    st.stop()

if st.session_state.show_personalization:
    render_personalization_page(user_id="default_user")
    st.stop()

if st.session_state.show_library:
    render_material_library()
    st.stop()

# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------
with st.sidebar:
    st.title("🛠️ Tools")
    
    if st.button("🎯 Personalization", use_container_width=True):
        st.session_state.show_personalization = True
        st.rerun()
    
    if st.button("📝 Exam Mode", use_container_width=True):
        st.session_state.exam_mode = True
        st.rerun()

    st.markdown("---")
    
    audio_data = mic_recorder(
        start_prompt="🎤 Record Voice",
        stop_prompt="🛑 Stop & Send",
        just_once=True,
        key=f"voice_{st.session_state.voice_key}"
    )
    
    st.markdown("---")
    
    # ✅ BUG FIX: Check connection status during toggle without disappearing UI
    rag_toggle = st.toggle("📄 Chat with PDF", value=st.session_state.rag_mode)
    
    if rag_toggle and "active_rag_hash" not in st.session_state:
        st.error("⚠️ No material connected!")
        st.info("Please connect a PDF in the 'Manage Material Library' below.")
        st.session_state.rag_mode = False
    else:
        st.session_state.rag_mode = rag_toggle
    
    if st.button("📚 Manage Material Library", use_container_width=True):
        st.session_state.show_library = True
        st.rerun()

    st.write("🖼️ **Image Input**")
    uploaded_file = st.file_uploader("Upload", type=["jpg", "png", "jpeg"], key=f"img_{st.session_state.uploader_key}")
    pasted_img = paste_image_button(label="📋 Paste", key=f"paste_{st.session_state.uploader_key}")

    if uploaded_file is not None:
        st.session_state.current_image_bytes = uploaded_file.getvalue()
        st.image(st.session_state.current_image_bytes, caption="Image Ready", width=250)
    elif pasted_img.image_data is not None:
        img_io = io.BytesIO()
        pasted_img.image_data.convert("RGB").save(img_io, format="JPEG")
        st.session_state.current_image_bytes = img_io.getvalue()
        st.image(st.session_state.current_image_bytes, caption="Image Pasted", width=250)
    
    if st.session_state.current_image_bytes and st.button("🗑️ Clear Image"):
        st.session_state.current_image_bytes = None
        st.rerun()

    st.markdown("<div style='height: 10vh;'></div>", unsafe_allow_html=True)
    st.markdown("---")
    st.title("Conversations")

    if st.button("➕ New Chat", use_container_width=True):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.current_image_bytes = None
        st.rerun()

    existing_threads = db.get_all_threads(user_id="default_user")
    for row in existing_threads:
        t_id = str(row['thread_id'])
        t_title = row['title']
        col_btn, col_opt = st.columns([0.8, 0.2])
        with col_btn:
            if st.button(f"💬 {t_title}", key=f"btn_{t_id}", use_container_width=True):
                st.session_state.thread_id = t_id
                st.session_state.current_image_bytes = None
                st.rerun()
        with col_opt:
            with st.popover("⚙️"):
                new_name = st.text_input("Rename Chat", value=t_title, key=f"rename_input_{t_id}")
                if st.button("Save Name", key=f"save_{t_id}"):
                    if new_name.strip(): 
                        db.update_chat_title(t_id, new_name.strip())
                        st.rerun()
                if st.button("🗑️ Delete Chat", key=f"del_{t_id}", type="primary"):
                    db.delete_chat_thread(t_id)
                    if st.session_state.thread_id == t_id:
                        st.session_state.thread_id = str(uuid.uuid4())
                    st.rerun()

# --------------------------------------------------
# MAIN CHAT DISPLAY
# --------------------------------------------------
st.title("💬 Agent")

state = st.session_state.agent.chatbot.get_state(config={"configurable": {"thread_id": active_tid}})
messages = state.values.get("messages", [])

for idx, msg in enumerate(messages):
    if isinstance(msg, HumanMessage):
        with st.chat_message("user"):
            st.markdown(msg.content)
    elif isinstance(msg, AIMessage):
        content = str(msg.content).strip()
        if not content: continue
        with st.chat_message("assistant"):
            if content.startswith("[IMAGE_STORED_ID:"):
                att_id = content.replace("[IMAGE_STORED_ID:", "").replace("]", "")
                img_record = db.get_image_by_id(att_id)
                if img_record:
                    img_bytes = bytes(img_record['file_data'])
                    st.image(img_bytes, caption="Generated Image", width=450)
                    st.download_button(label="⬇️ Download Image", data=img_bytes, file_name=f"gen_{att_id}.png")
            else:
                st.markdown(content)
                if st.button("📄 Save to PDF", key=f"dl_text_{idx}"):
                    user_query = messages[idx-1].content if idx > 0 and isinstance(messages[idx-1], HumanMessage) else "Unknown Query"
                    saved_path = db.get_chat_download_path(active_tid) or choose_pdf_path()
                    if saved_path:
                        db.save_chat_download_path(active_tid, saved_path)
                        if append_to_pdf(saved_path, user_query, content):
                            st.toast(f"✅ Appended!", icon="📄")

# --------------------------------------------------
# INPUT FLOW
# --------------------------------------------------
user_input = st.chat_input("Type message...")
final_input = (st.session_state.agent.transcribe_audio(audio_data["bytes"]) if audio_data else None) or user_input

if final_input:
    # Final safety check before processing
    if st.session_state.rag_mode and "active_rag_hash" not in st.session_state:
        st.error("⚠️ Connection lost. Please manage library.")
        st.session_state.rag_mode = False
        st.rerun()
    else:
        with st.chat_message("user"):
            st.markdown(final_input)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            if len(messages) == 0:
                db.save_chat_thread(active_tid, generate_chat_title(final_input))

            with st.status("Thinking...", expanded=False) as status:
                if st.session_state.rag_mode:
                    status.update(label="Searching PDF...", state="running")
                    full_response = ask_pdf(final_input)
                    st.session_state.agent.chatbot.update_state(
                        {"configurable": {"thread_id": active_tid}}, 
                        {"messages": [HumanMessage(content=final_input), AIMessage(content=full_response)]}
                    )
                else:
                    status.update(label="Thinking ...", state="running")
                    st.session_state.agent.chatbot.update_state(
                        {"configurable": {"thread_id": active_tid}}, 
                        {"messages": [HumanMessage(content=final_input)], "image_bytes": st.session_state.current_image_bytes}
                    )
                    new_state = st.session_state.agent.chatbot.invoke(
                        {"messages": [], "image_bytes": st.session_state.current_image_bytes}, 
                        config={"configurable": {"thread_id": active_tid}}
                    )
                    full_response = new_state["messages"][-1].content
                status.update(label="Complete!", state="complete", expanded=False)

            if "[IMAGE_STORED_ID:" not in str(full_response):
                out = ""
                for ch in str(full_response):
                    out += ch
                    placeholder.markdown(out)
                    time.sleep(0.002)
            else:
                placeholder.info("🖼️ Image generated.")

        st.session_state.current_image_bytes = None
        st.session_state.uploader_key += 1
        st.session_state.voice_key += 1
        st.rerun()