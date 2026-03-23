import streamlit as st
from database import save_user_context, get_user_context

def render_personalization_page(user_id: str):
    """Renders the personalization settings interface."""
    st.title("🎯 Personalization Settings")
    st.markdown("---")
    
    # 1. Fetch existing context from DB to show 'Live' data
    existing_data = get_user_context(user_id)
    saved_prefs = existing_data.get("raw_text", "")

    st.subheader("How should the agent personalize its responses?")
    
    # 2. Text input area pre-filled with existing data
    user_input = st.text_area(
        "Enter your background, interests, and interaction preferences:",
        value=saved_prefs,
        height=300,
        placeholder="Example: My name is Nitish. I teach AI on YouTube. I prefer concise answers and Python examples."
    )

    # UI Buttons for saving and returning
    col1, col2 = st.columns([1, 4])
    
    with col1:
        if st.button("💾 Save", use_container_width=True):
            save_user_context(user_id, {"raw_text": user_input})
            st.success("Preferences saved!")
            # We don't rerun here so the user sees the success message
            
    with col2:
        if st.button("⬅ Back to Chat", use_container_width=True):
            # We will use this session state key in frontend.py later
            st.session_state.show_personalization = False
            st.rerun()