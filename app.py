import streamlit as st
from auth_handler import AuthHandler
from mud_client import MUDClient, GameConfig, GameState


def create_terminal_style():
    """Add custom CSS for terminal-like appearance"""
    st.markdown("""
        <style>
            /* Page layout fixes */
            .block-container {
                padding-top: 1rem !important;
                padding-bottom: 0rem !important;
                margin-bottom: 0rem !important;
            }

            /* Hide unnecessary padding */
            .appview-container .main .block-container {
                padding: 1rem 1rem 0rem 1rem;
                max-width: unset;
            }

            .stApp > header {
                display: none;
            }

            /* Terminal container */
            .terminal-container {
                background-color: black;
                color: #00ff00;
                font-family: 'Courier New', Courier, monospace;
                padding: 10px;
                height: 70vh;
                overflow-y: auto;
                margin-bottom: 0.5rem;
                border-radius: 5px;
            }

            /* Message styles */
            .terminal-message {
                margin: 0;
                padding: 2px 0;
                white-space: pre-wrap;
                word-wrap: break-word;
            }

            .system-message { color: #00ff00; }
            .private-message { color: #00ffff; }
            .room-message { color: #ffff00; }
            .error-message { color: #ff0000; }

            /* Command input styling */
            .stTextInput > div > div {
                padding: 0;
            }

            .stTextInput input {
                font-family: 'Courier New', Courier, monospace;
                background-color: black;
                color: #00ff00;
                border: 1px solid #00ff00;
                padding: 0.5rem;
                border-radius: 5px;
            }

            /* Hide Streamlit elements we don't want */
            #MainMenu, footer {display: none;}
            .stDeployButton {display: none;}

            /* Container layout */
            .main-container {
                display: flex;
                flex-direction: column;
                height: calc(100vh - 2rem);
                padding: 0;
                margin: 0;
            }

            /* Compact title */
            h1 {
                margin: 0 !important;
                padding: 0 !important;
                font-size: 1.5rem !important;
            }

            /* Style sidebar */
            .css-1d391kg {
                padding-top: 1rem;
            }
        </style>
    """, unsafe_allow_html=True)


def switch_to_signup():
    st.session_state.auth_mode = "signup"


def switch_to_signin():
    st.session_state.auth_mode = "signin"


def handle_command():
    """Handle command input and processing"""
    if st.session_state.command_input and st.session_state.client:
        command = st.session_state.command_input
        success, result = st.session_state.client.send_command(command)
        if success:
            if result.get("privateMessage"):
                st.session_state.game_state.add_message(result["privateMessage"], "private")
            if result.get("roomMessage"):
                st.session_state.game_state.add_message(result["roomMessage"], "room")
            if result.get("message"):
                st.session_state.game_state.add_message(result["message"], "system")
        else:
            st.session_state.game_state.add_message(result.get("message", "Unknown error occurred"), "error")

        st.session_state.command_input = ""


def render_signup_form(auth_handler: AuthHandler):
    st.header("Sign Up")
    with st.form("signup_form"):
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
        submit = st.form_submit_button("Sign Up")

        if submit:
            if password != confirm_password:
                st.error("Passwords do not match!")
            elif len(password) < 6:
                st.error("Password must be at least 6 characters long!")
            else:
                success, message = auth_handler.sign_up(email, password)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

    st.button("Already have an account? Sign In", on_click=switch_to_signin)


def render_signin_form(auth_handler: AuthHandler):
    st.header("Sign In")
    with st.form("signin_form"):
        email = st.text_input("Email", key="signin_email")
        password = st.text_input("Password", type="password", key="signin_password")
        submit = st.form_submit_button("Sign In")

        if submit:
            success, message = auth_handler.sign_in(email, password)
            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    st.button("Don't have an account? Sign Up", on_click=switch_to_signup)


def render_auth_page(auth_handler: AuthHandler):
    st.title("MUD Game")

    if st.session_state.auth_mode == "signup":
        render_signup_form(auth_handler)
    else:
        render_signin_form(auth_handler)


def render_game_interface(auth_handler: AuthHandler):
    user = auth_handler.get_current_user()

    # Initialize game state if not already done
    if "game_state" not in st.session_state:
        st.session_state.game_state = GameState()

    # Create the layout
    create_terminal_style()

    # Sidebar with user info and logout
    with st.sidebar:
        st.header("User Info")
        st.write(f"Email: {user.email}")
        if st.button("Sign Out"):
            success, message = auth_handler.sign_out()
            if success:
                st.rerun()
            else:
                st.error(message)

    # Main game area with compact title
    st.title("MUD Game Terminal")

    # Initialize game connection if needed
    if "client" not in st.session_state:
        config = GameConfig.from_ini()
        client = MUDClient(config)
        username = user.email.split('@')[0]
        success, message = client.join_game(username)
        if success:
            st.session_state.client = client
            st.session_state.game_state.add_message(message)
        else:
            st.error(message)
            return

    # Terminal display area
    terminal_html = "<div class='terminal-container'>"
    for message in st.session_state.game_state.get_messages():
        css_class = f"{message['type']}-message"
        terminal_html += f"<pre class='terminal-message {css_class}'>[{message['timestamp']}] {message['message']}</pre>"
    terminal_html += "</div>"
    st.markdown(terminal_html, unsafe_allow_html=True)

    # Command input
    st.text_input(
        "",
        key="command_input",
        placeholder="Enter command...",
        on_change=handle_command,
        label_visibility="collapsed"
    )


def main():
    st.set_page_config(
        page_title="MUD Game Client",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Initialize authentication
    auth_handler = AuthHandler()
    auth_handler.initialize_session_state()

    # Check for active session
    auth_handler.check_session()

    # Show either auth forms or game interface
    if not auth_handler.is_authenticated():
        render_auth_page(auth_handler)
    else:
        render_game_interface(auth_handler)


if __name__ == "__main__":
    main()