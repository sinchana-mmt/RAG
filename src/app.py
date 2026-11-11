"""Floor screen: paste the sentence, get the FAQ fix."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import streamlit as st

from answer import answer_question

st.set_page_config(
    page_title="DigiTrail Known Issues Assistant",
    page_icon="▣",
    layout="centered",
)

st.markdown(
    """
    <style>
      .stApp { background: #0f1720; color: #e8edf2; }
      .block-container { padding-top: 2rem; max-width: 760px; }
      h1, h2, h3 { color: #f4f7fa !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("What is on the screen?")
st.caption("Paste the exact sentence. This shows the official DigiTrail fix, and nothing else.")

with st.form("resolve"):
    question = st.text_area(
        "Sentence on the screen",
        placeholder="sampling_qty must be greater than zero",
        height=110,
        label_visibility="collapsed",
    )
    resolve = st.form_submit_button("Resolve", type="primary", use_container_width=True)

if resolve:
    query = question.strip()
    if not query:
        st.warning("Paste the sentence that is on the screen.")
    else:
        result = answer_question(query)
        if not result["found"] or not result["cases"]:
            st.error("This sentence is not in the Known Issues FAQ. Stop and escalate.")
            st.markdown(
                "Write the screen name, the exact sentence, the PR, the item code, "
                "the Kaynes Unique ID, the username, and the time. "
                "Add one sentence about what you already tried, and send that to IT."
            )
        else:
            case = result["cases"][0]
            st.success(f"Case {case['case_id']}: {case['title']}")
            st.subheader("What it means")
            st.write(case["what_it_means"])
            st.subheader("How to resolve")
            for step in case["what_to_do"]:
                st.write(step)
            st.subheader("Done when")
            st.write(case["pass_when"])
            st.subheader("Stop and escalate when")
            st.write(case["escalate_when"])
