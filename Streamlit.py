import anthropic
import os
from pathlib import Path
import streamlit as st
import base64

# Page configuration
st.set_page_config(
    page_title="Dr. Carofino's Post-Op Assistant",
    page_icon="🏥",
    layout="wide"
)

# Title and description
st.title("🏥 Dr. Carofino's Post-Op Assistant")
st.markdown("Ask questions about your post-operative care and recovery.")

# Initialize the Anthropic client
@st.cache_resource
def get_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        st.error("ANTHROPIC_API_KEY environment variable not set!")
        st.stop()
    return anthropic.Anthropic(api_key=api_key)

client = get_client()

# Load PDFs
@st.cache_data
def load_pdfs():
    pdf_dir = Path("postop_handouts")
    if not pdf_dir.exists():
        st.error(f"Directory '{pdf_dir}' not found!")
        return []
    
    pdf_files = list(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        st.warning(f"No PDF files found in '{pdf_dir}'")
        return []
    
    pdf_contents = []
    for pdf_file in pdf_files:
        with open(pdf_file, "rb") as f:
            pdf_data = f.read()
            pdf_contents.append({
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": base64.b64encode(pdf_data).decode()
                },
                "cache_control": {"type": "ephemeral"}
            })
    
    return pdf_contents

# Load protocol files with caching
@st.cache_data
def load_protocols():
    protocol_dir = Path("protocols")
    if not protocol_dir.exists():
        return ""
    
    protocol_files = list(protocol_dir.glob("*.txt"))
    if not protocol_files:
        return ""
    
    protocols_text = ""
    for protocol_file in protocol_files:
        with open(protocol_file, 'r', encoding='utf-8') as f:
            protocols_text += f"\n\n=== {protocol_file.name} ===\n\n"
            protocols_text += f.read()
    
    return protocols_text

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

if "pdf_contents" not in st.session_state:
    with st.spinner("Loading post-operative handouts..."):
        st.session_state.pdf_contents = load_pdfs()
        st.session_state.protocols_text = load_protocols()

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask about your recovery (e.g., 'When can I shower after rotator cuff surgery?')"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Generate assistant response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        # Build the system message (text only)
        system_message = """You are a helpful post-operative care assistant for Dr. Carofino's surgical practice. Your role is to help patients understand their post-operative instructions and answer questions about their recovery.

Guidelines:
- Answer questions based on the post-operative instruction handouts and protocols provided
- Be clear, compassionate, and encouraging
- If information isn't in the handouts, say so and recommend contacting the office
- Always prioritize patient safety - if something sounds urgent, recommend immediate contact with the office or emergency services
- Use simple, patient-friendly language
- When relevant, cite which specific handout or protocol you're referencing"""

        # Add protocols to system message if available
        if st.session_state.protocols_text:
            system_message += f"\n\nAdditional Protocols:\n{st.session_state.protocols_text}"
        
        # Build conversation history for API
        api_messages = []
        
        if len(st.session_state.messages) == 1:  # First user message
            # Include PDFs with first message
            first_message_content = st.session_state.pdf_contents.copy()
            first_message_content.append({
                "type": "text",
                "text": st.session_state.messages[0]["content"]
            })
            api_messages.append({
                "role": "user",
                "content": first_message_content
            })
        else:
            # For subsequent messages, use regular format
            for msg in st.session_state.messages:
                api_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        # Call Claude API with streaming
        try:
            full_response = ""
            with client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                system=system_message,
                messages=api_messages
            ) as stream:
                for text in stream.text_stream:
                    full_response += text
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            st.error(f"Error: {str(e)}")

# Sidebar with information
with st.sidebar:
    st.header("About")
    st.markdown("""
    This chatbot helps you understand your post-operative care instructions.
    
    **Important Notes:**
    - This is for informational purposes only
    - Always follow your doctor's specific instructions
    - For urgent concerns, contact the office or seek emergency care
    """)
    
    st.divider()
    
    # Show loaded resources
    st.header("Loaded Resources")
    st.write(f"📄 PDF Handouts: {len(st.session_state.pdf_contents)}")
    if st.session_state.protocols_text:
        protocol_count = st.session_state.protocols_text.count("===")
        st.write(f"📋 Protocol Files: {protocol_count}")
    
    st.divider()
    
    # Clear chat button
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()
