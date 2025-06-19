# app.py
import streamlit as st
import requests

API_URL = "https://no-code-ai-agent-builder.onrender.com"

st.set_page_config(page_title="🤖 AI Agent Builder", page_icon="🤖", layout="wide")

# --- Session State ---
if "page" not in st.session_state:
    st.session_state.page = "login"
if "user" not in st.session_state:
    st.session_state.user = None
if "agents" not in st.session_state:
    st.session_state.agents = []
if "current_agent" not in st.session_state:
    st.session_state.current_agent = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- Sidebar Navigation ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/robot-2.png", width=80)
    st.title("AI Agent Builder")
    if st.session_state.user:
        st.markdown(f"👤 **{st.session_state.user['email']}**")
        if st.button("🏠 Dashboard"):
            st.session_state.page = "dashboard"
        if st.button("➕ New Agent"):
            st.session_state.page = "create_agent"
        if st.button("🚪 Logout"):
            st.session_state.user = None
            st.session_state.page = "login"
            st.session_state.chat_history = []
    else:
        st.markdown("Welcome! Please log in or register.")

# --- Pages ---
def register_page():
    st.title("📝 Register")
    with st.form("register_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Register")
        if submitted:
            if password != confirm_password:
                st.error("❌ Passwords do not match.")
            elif not email or not password:
                st.error("❌ Please fill in all fields.")
            else:
                resp = requests.post(f"{API_URL}/register", json={"email": email, "password": password})
                if resp.status_code == 200:
                    st.success("✅ Registration successful! Please log in.")
                    st.session_state.page = "login"
                else:
                    st.error("❌ " + resp.json().get("detail", "Registration failed."))
    if st.button("Back to Login"):
        st.session_state.page = "login"

def login_page():
    st.title("🔐 Login")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            resp = requests.post(f"{API_URL}/login", json={"email": email, "password": password})
            if resp.status_code == 200:
                st.session_state.user = resp.json()
                st.session_state.page = "dashboard"
            else:
                st.error("❌ Invalid credentials.")
    if st.button("Register"):
        st.session_state.page = "register"

def dashboard_page():
    st.title("🤖 Your AI Agents")
    user_id = st.session_state.user["id"]
    resp = requests.get(f"{API_URL}/agents/{user_id}")
    st.session_state.agents = resp.json()
    st.markdown("### 👇 Select an agent to test or upload knowledge base:")
    for agent in st.session_state.agents:
        with st.container():
            cols = st.columns([4, 1, 1])
            with cols[0]:
                st.markdown(f"**{agent['name']}**<br><span style='font-size:0.9em'>📝 {agent['purpose']}<br>🎨 {agent['tone']}</span>", unsafe_allow_html=True)
            with cols[1]:
                if st.button("💬 Test", key=f"test_{agent['id']}"):
                    st.session_state.current_agent = agent
                    st.session_state.page = "chat"
                    st.session_state.chat_history = []
            with cols[2]:
                if st.button("📄 Upload KB", key=f"upload_{agent['id']}"):
                    st.session_state.current_agent = agent
                    st.session_state.page = "upload_kb"
    st.markdown("---")
    if st.button("➕ Create New Agent"):
        st.session_state.page = "create_agent"

def create_agent_page():
    st.title("✨ Create New Agent")
    with st.form("create_agent_form"):
        name = st.text_input("Agent Name")
        purpose = st.text_area("Purpose")
        tone = st.selectbox("Tone", ["Professional", "Friendly", "Humorous", "Direct", "Empathetic"])
        fallback_message = st.text_input("Fallback Message", value="I'm sorry, I cannot answer that based on my current knowledge.")
        submitted = st.form_submit_button("Save Agent")
        if submitted:
            user_id = st.session_state.user["id"]
            payload = {
                "name": name,
                "purpose": purpose,
                "tone": tone,
                "fallback_message": fallback_message
            }
            resp = requests.post(f"{API_URL}/agent", params={"user_id": user_id}, json=payload)
            if resp.status_code == 200:
                st.success("✅ Agent created!")
                st.session_state.page = "dashboard"
            else:
                st.error("❌ " + resp.json().get("detail", "Failed to create agent."))
    if st.button("Back to Dashboard"):
        st.session_state.page = "dashboard"

def upload_kb_page():
    agent = st.session_state.current_agent
    st.title(f"📄 Upload Knowledge Base for {agent['name']}")
    uploaded_file = st.file_uploader("Upload a TXT or PDF file", type=["txt", "pdf"])
    if uploaded_file is not None:
        files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
        with st.spinner("Processing knowledge base..."):
            resp = requests.post(
                f"{API_URL}/upload_kb/",
                params={"agent_id": agent["id"]},
                files=files
            )
        if resp.status_code == 200 and resp.json().get("status") == "success":
            st.success("✅ Knowledge base uploaded and processed!")
        else:
            st.error("❌ " + resp.json().get("detail", "Upload failed."))
    if st.button("Back to Dashboard"):
        st.session_state.page = "dashboard"

def chat_page():
    agent = st.session_state.current_agent
    st.title(f"💬 Chat with {agent['name']}")
    st.caption(f"📝 {agent['purpose']} | 🎨 {agent['tone']}")
    for msg in st.session_state.chat_history:
        with st.chat_message(msg['role']):
            st.markdown(msg['content'])
    user_query = st.chat_input("Type your message...")
    if user_query:
        st.session_state.chat_history.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)
        with st.chat_message("assistant"):
            with st.spinner("Agent is thinking..."):
                payload = {
                    "agent_id": agent["id"],
                    "agent_config": agent,
                    "user_query": user_query
                }
                resp = requests.post(f"{API_URL}/chat", json=payload)
                if resp.status_code == 200:
                    answer = resp.json()["response"]
                else:
                    answer = "❌ " + resp.json().get("detail", "Error from agent.")
                st.markdown(answer)
                st.session_state.chat_history.append({"role": "assistant", "content": answer})
    if st.button("Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.session_state.chat_history = []

def hosted_chat_page():
    # Get agent_id from URL query params
    query_params = st.experimental_get_query_params()
    agent_id = query_params.get("agent_id", [None])[0]
    if not agent_id:
        st.error("No agent specified.")
        return

    # Fetch agent config from backend
    resp = requests.get(f"{API_URL}/agents/{st.session_state.user['id']}" if st.session_state.user else f"{API_URL}/agents/0")
    agents = resp.json() if resp.status_code == 200 else []
    agent = next((a for a in agents if str(a["id"]) == str(agent_id)), None)
    if not agent:
        st.error("Agent not found.")
        return

    st.title(f"💬 Chat with {agent['name']}")
    st.caption(f"📝 {agent['purpose']} | 🎨 {agent['tone']}")
    if f"hosted_chat_history_{agent_id}" not in st.session_state:
        st.session_state[f"hosted_chat_history_{agent_id}"] = []
    for msg in st.session_state[f"hosted_chat_history_{agent_id}"]:
        with st.chat_message(msg['role']):
            st.markdown(msg['content'])
    user_query = st.chat_input("Type your message...")
    if user_query:
        st.session_state[f"hosted_chat_history_{agent_id}"].append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)
        with st.chat_message("assistant"):
            with st.spinner("Agent is thinking..."):
                payload = {
                    "agent_id": agent["id"],
                    "agent_config": agent,
                    "user_query": user_query
                }
                resp = requests.post(f"{API_URL}/chat", json=payload)
                if resp.status_code == 200:
                    answer = resp.json()["response"]
                else:
                    answer = "❌ " + resp.json().get("detail", "Error from agent.")
                st.markdown(answer)
                st.session_state[f"hosted_chat_history_{agent_id}"].append({"role": "assistant", "content": answer})

# --- Page Routing ---
query_params = st.query_params
if query_params.get("page", [None])[0] == "hosted_chat":
    hosted_chat_page()
else:
    if st.session_state.page == "login":
        login_page()
    elif st.session_state.page == "register":
        register_page()
    elif st.session_state.page == "dashboard":
        dashboard_page()
    elif st.session_state.page == "create_agent":
        create_agent_page()
    elif st.session_state.page == "upload_kb":
        upload_kb_page()
    elif st.session_state.page == "chat":
        chat_page()
