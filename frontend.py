import streamlit as st
st.set_page_config(page_title="Agent Chat", layout="wide")

import asyncio
from backend import UnifiedAgent, generate_chat_title
from rag import ask_pdf
from langchain_core.messages import HumanMessage, AIMessage
import uuid
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import tkinter as tk
from tkinter import filedialog
import time
from streamlit_mic_recorder import mic_recorder 
from streamlit_paste_button import paste_image_button
import base64
import os
import io
from PIL import Image

from rag_pages import render_material_library
from exam_mode import run_exam_mode
from personalization_ui import render_personalization_page

# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------
if "agent" not in st.session_state:
    agent = UnifiedAgent()
    asyncio.run(agent.initialize())
    st.session_state.agent = agent

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "chat_titles" not in st.session_state:
    st.session_state.chat_titles = {}

if "pdf_responses_map" not in st.session_state:
    st.session_state.pdf_responses_map = {}

if "pdf_file_map" not in st.session_state:
    st.session_state.pdf_file_map = {}

if "exam_mode" not in st.session_state:
    st.session_state.exam_mode = False

if "rag_mode" not in st.session_state:
    st.session_state.rag_mode = False

if "show_library" not in st.session_state:
    st.session_state.show_library = False

if "show_personalization" not in st.session_state:
    st.session_state.show_personalization = False

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

if "voice_key" not in st.session_state:
    st.session_state.voice_key = 1000

if "current_image_bytes" not in st.session_state:
    st.session_state.current_image_bytes = None

current_tid = st.session_state.thread_id
if current_tid not in st.session_state.pdf_responses_map:
    st.session_state.pdf_responses_map[current_tid] = []

# --------------------------------------------------
# PDF UTILS
# --------------------------------------------------
def choose_pdf_path():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.asksaveasfilename(defaultextension=".pdf")
    root.destroy()
    return path

def append_to_pdf(file_path, data):
    styles = getSampleStyleSheet()
    elements = []

    if os.path.exists(file_path):
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(file_path)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    for line in text.split("\n"):
                        elements.append(Paragraph(line.strip(), styles["Normal"]))
                        elements.append(Spacer(1, 6))
                    elements.append(Spacer(1, 12))
        except:
            pass

    for q, a in data:
        elements.append(Paragraph(f"<b>Q:</b> {q}", styles["Normal"]))
        elements.append(Spacer(1, 8))
        for line in a.split("\n"):
            line = line.strip()
            if not line:
                elements.append(Spacer(1, 6))
                continue
            if line.startswith(("-", "•", "*")):
                elements.append(Paragraph(f"• {line[1:].strip()}", styles["Normal"]))
            else:
                elements.append(Paragraph(line, styles["Normal"]))
            elements.append(Spacer(1, 6))
        elements.append(Spacer(1, 16))

    doc = SimpleDocTemplate(file_path)
    doc.build(elements)

# --------------------------------------------------
# MODES
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
    
    st.title("Conversations")

    if st.button("➕ New Chat", use_container_width=True):
        new_tid = str(uuid.uuid4())
        st.session_state.thread_id = new_tid
        st.session_state.current_image_bytes = None
        st.session_state.pdf_responses_map[new_tid] = []
        st.rerun()

    for tid_btn, title in st.session_state.chat_titles.items():
        if st.sidebar.button(f"💬 {title}", key=f"btn_{tid_btn}", use_container_width=True):
            st.session_state.thread_id = tid_btn
            st.session_state.current_image_bytes = None
            st.rerun()

    st.markdown("---")
    
    st.session_state.rag_mode = st.toggle("📄 Chat with PDF", value=st.session_state.rag_mode)
    
    if st.button("📚 Manage Material Library", use_container_width=True):
        st.session_state.show_library = True
        st.rerun()
    
    if st.session_state.rag_mode:
        if "active_rag_hash" not in st.session_state:
            st.warning("⚠️ No material connected. Click Manage Library.")
        else:
            st.info(f"Connected to: {st.session_state.active_rag_name}")

    st.write("🖼️ **Image Input**")
    uploaded_file = st.file_uploader(
        "Upload Image",
        type=["jpg", "jpeg", "png"],
        key=f"img_{st.session_state.uploader_key}"
    )
    
    pasted_img = paste_image_button(
        label="📋 Paste from Clipboard",
        key=f"paste_{st.session_state.uploader_key}"
    )

    if uploaded_file:
        st.image(uploaded_file, caption="Uploaded Image")
        st.session_state.current_image_bytes = uploaded_file.read()
    elif pasted_img and pasted_img.image_data is not None:
        st.image(pasted_img.image_data, caption="Pasted Image")
        img_rgb = pasted_img.image_data.convert("RGB")
        img_io = io.BytesIO()
        img_rgb.save(img_io, format="JPEG")
        st.session_state.current_image_bytes = img_io.getvalue()

# --------------------------------------------------
# MAIN CHAT DISPLAY
# --------------------------------------------------
st.title("💬 Agent")

active_tid = st.session_state.thread_id

state_values = st.session_state.agent.chatbot.get_state(
    config={"configurable": {"thread_id": active_tid}}
).values

messages = state_values.get("messages", [])
active_pdf_responses = st.session_state.pdf_responses_map.get(active_tid, [])

assistant_index = 0
pdf_index = 0   # ✅ NEW FIX

for msg in messages:
    if isinstance(msg, HumanMessage):
        with st.chat_message("user"):
            st.markdown(msg.content)

    elif isinstance(msg, AIMessage):
        content = str(msg.content).strip()
        if not content:
            continue

        with st.chat_message("assistant"):
            is_image = content.startswith("[IMAGE_BASE64]")

            if is_image:
                img_data = base64.b64decode(content.replace("[IMAGE_BASE64]", ""))
                st.success("🖼️ Image generated successfully.")
                st.download_button(
                    label="⬇️ Download Generated Image",
                    data=img_data,
                    file_name=f"generated_{active_tid[:8]}.png",
                    mime="image/png",
                    key=f"img_dl_{active_tid}_{assistant_index}"
                )
            else:
                st.markdown(content)

                if pdf_index < len(active_pdf_responses):
                    if st.button("📄 Download PDF", key=f"pdf_btn_{active_tid}_{pdf_index}"):
                        if active_tid not in st.session_state.pdf_file_map:
                            path = choose_pdf_path()
                            if path:
                                st.session_state.pdf_file_map[active_tid] = path
                        
                        if active_tid in st.session_state.pdf_file_map:
                            append_to_pdf(
                                st.session_state.pdf_file_map[active_tid],
                                [active_pdf_responses[pdf_index]]
                            )
                            st.success("Saved to PDF ✅")

                pdf_index += 1   # ✅ ONLY for text

            assistant_index += 1

# --------------------------------------------------
# INPUT FLOW
# --------------------------------------------------
user_input = st.chat_input("Type message...")
voice_text = None
if audio_data and "bytes" in audio_data:
    voice_text = st.session_state.agent.transcribe_audio(audio_data["bytes"])

final_input = voice_text or user_input

if final_input:
    with st.chat_message("user"):
        st.markdown(final_input)

    with st.chat_message("assistant"):
        placeholder = st.empty()

    if st.session_state.rag_mode:
        full_response = ask_pdf(final_input)
        st.session_state.agent.chatbot.update_state(
            {"configurable": {"thread_id": active_tid}},
            {"messages": [HumanMessage(content=final_input), AIMessage(content=full_response)]}
        )
    else:
        st.session_state.agent.chatbot.update_state(
            {"configurable": {"thread_id": active_tid}},
            {"messages": [HumanMessage(content=final_input)], "image_bytes": st.session_state.current_image_bytes}
        )
        asyncio.run(
            st.session_state.agent.chatbot.ainvoke(
                {"messages": [], "image_bytes": st.session_state.current_image_bytes},
                config={"configurable": {"thread_id": active_tid}}
            )
        )
        curr = st.session_state.agent.chatbot.get_state(
            config={"configurable": {"thread_id": active_tid}}
        ).values
        full_response = curr["messages"][-1].content

    if active_tid not in st.session_state.chat_titles:
        st.session_state.chat_titles[active_tid] = generate_chat_title(final_input)

    # ✅ FIX: STORE ONLY TEXT RESPONSES
    if not str(full_response).startswith("[IMAGE_BASE64]"):
        st.session_state.pdf_responses_map[active_tid].append((final_input, full_response))

    if not str(full_response).startswith("[IMAGE_BASE64]"):
        out = ""
        for ch in str(full_response):
            out += ch
            placeholder.markdown(out)
            time.sleep(0.003)
    else:
        placeholder.info("🖼️ Image generated successfully.")

    st.session_state.current_image_bytes = None
    st.session_state.uploader_key += 1
    st.session_state.voice_key += 1
    st.rerun()