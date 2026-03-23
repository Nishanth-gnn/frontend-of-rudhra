import streamlit as st
import os
import io
from rag_manager import (
    get_file_hash, 
    check_material_exists, 
    list_all_materials, 
    DATA_DIR
)
from ingest_service import process_and_ingest

def render_material_library():
    """
    Dedicated Page for managing RAG materials.
    """
    st.title("📚 Material Library")
    st.subheader("Manage your knowledge base for RAG Mode")

    # Sidebar Status Indicator
    with st.sidebar:
        st.markdown("### 🔌 Connection Status")
        if "active_rag_name" in st.session_state:
            st.success(f"**Connected to:**\n{st.session_state.active_rag_name}")
        else:
            st.warning("No material connected.")

    # FIXED: This button now clears the redirection flag
    if st.button("⬅ Back to Chat"):
        st.session_state.show_library = False 
        st.rerun()

    st.markdown("---")

    # 1. AVAILABLE MATERIALS SECTION
    st.write("### 📂 Available Materials")
    materials = list_all_materials()

    if not materials:
        st.info("No materials ingested yet. Upload your first PDF below!")
    else:
        # Table-like display for existing materials
        for m in materials:
            col1, col2, col3 = st.columns([3, 2, 1])
            col1.write(f"📄 **{m['source_filename']}**")
            col2.write(f"⏰ {m['upload_date']}")
            
            # Highlight the button if it's already connected
            is_active = st.session_state.get("active_rag_hash") == m['content_hash']
            btn_label = "Connected" if is_active else "Connect"
            
            if col3.button(btn_label, key=f"conn_{m['content_hash']}", disabled=is_active):
                st.session_state.active_rag_hash = m['content_hash']
                st.session_state.active_rag_name = m['source_filename']
                # Ensure Chat with PDF is ON when we connect a file
                st.session_state.rag_mode = True 
                st.success(f"Connected to {m['source_filename']} ✅")
                st.rerun()

    st.markdown("---")

    # 2. CONNECT NEW MATERIAL SECTION
    st.write("### ➕ Connect to Other Material")
    
    uploaded_file = st.file_uploader(
        "Select a PDF to add to your library", 
        type=["pdf"], 
        key="new_rag_upload"
    )

    if uploaded_file:
        # Initialize ingesting state if not present
        if "is_ingesting" not in st.session_state:
            st.session_state.is_ingesting = False

        file_bytes = uploaded_file.read()
        file_hash = get_file_hash(file_bytes)
        
        # CRITICAL CASE CHECK: Duplication
        existing = check_material_exists(file_hash)
        
        if existing:
            st.warning(f"⚠️ This content already exists as '{existing['source_filename']}'.")
            if st.button("Use Existing Instance"):
                st.session_state.active_rag_hash = existing['content_hash']
                st.session_state.active_rag_name = existing['source_filename']
                st.session_state.rag_mode = True
                st.rerun()
        else:
            # DOUBLE-CLICK PREVENTION: Disable button while ingesting
            if st.button("🚀 Start Ingestion", disabled=st.session_state.is_ingesting):
                st.session_state.is_ingesting = True
                
                with st.spinner("Processing PDF and generating embeddings... Please wait."):
                    try:
                        # Save raw file to data folder
                        save_path = os.path.join(DATA_DIR, f"{file_hash}.pdf")
                        with open(save_path, "wb") as f:
                            f.write(file_bytes)
                        
                        # Run the ingestion service
                        success = process_and_ingest(save_path, uploaded_file.name, file_hash)
                        
                        if success:
                            st.session_state.active_rag_hash = file_hash
                            st.session_state.active_rag_name = uploaded_file.name
                            st.session_state.rag_mode = True
                            st.session_state.is_ingesting = False
                            st.rerun()
                    except Exception as e:
                        st.error(f"Ingestion failed: {str(e)}")
                        st.session_state.is_ingesting = False