import streamlit as st


def render_quit_dialog():
    """
    Renders Quit button + grouped confirmation block.
    Returns:
        True  -> If user confirmed quit
        False -> Otherwise
    """

    if "confirm_quit" not in st.session_state:
        st.session_state.confirm_quit = False

    # ================= NORMAL STATE =================
    if not st.session_state.confirm_quit:
        if st.button("🛑 Quit Exam"):
            st.session_state.confirm_quit = True
            st.rerun()
        return False

    # ================= CONFIRMATION BLOCK =================
    # Everything grouped inside ONE container
    confirmation_box = st.container()

    with confirmation_box:
        st.warning("⚠️ Are you sure you want to quit the exam?")

        col_yes, col_no = st.columns(2)

        if col_yes.button("✅ Yes, Quit"):
            st.session_state.confirm_quit = False
            return True

        if col_no.button("❌ No, Continue"):
            st.session_state.confirm_quit = False
            st.rerun()

    return False