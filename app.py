import streamlit as st
from auth_handler import AuthHandler
from character_service import CharacterService
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


def render_character_creation(auth_handler: AuthHandler, character_service: CharacterService):
    """Render character creation form"""
    st.header("Create New Character")
    with st.form("character_creation"):
        col1, col2 = st.columns(2)

        with col1:
            first_name = st.text_input("First Name")
            race = st.selectbox("Race", ['HUMAN', 'DRACONIAN', 'SYNTH', 'CONSTRUCT', 'ANDROID'])

        with col2:
            character_class = st.selectbox("Class", ['SOLDIER', 'PILOT', 'HACKER', 'ENGINEER', 'MEDIC'])

            # Show roll results section
            if 'attribute_rolls' not in st.session_state:
                st.session_state.attribute_rolls = []
                st.session_state.roll_count = 0

            if st.form_submit_button("Roll Attributes"):
                if st.session_state.roll_count < 3:
                    # Call backend to get roll results
                    success, result = character_service.roll_attributes(auth_handler.get_current_user().id)
                    if success:
                        st.session_state.attribute_rolls.append(result)
                        st.session_state.roll_count += 1

            # Display rolls if any exist
            if st.session_state.attribute_rolls:
                st.write("Your rolls:")
                for i, roll in enumerate(st.session_state.attribute_rolls):
                    st.write(f"Roll {i + 1}:", roll)

                # Let user select which roll to use
                selected_roll = st.selectbox("Select roll to use", range(1, len(st.session_state.attribute_rolls) + 1))

        create_button = st.form_submit_button("Create Character")

        if create_button:
            if not first_name:
                st.error("Please enter a character name")
                return

            if not hasattr(st.session_state, 'attribute_rolls') or not st.session_state.attribute_rolls:
                st.error("Please roll for attributes first")
                return

            # Send character creation request to backend
            success, result = character_service.create_character(
                owner_id=auth_handler.get_current_user().id,
                first_name=first_name,
                race=race,
                character_class=character_class,
                attributes=st.session_state.attribute_rolls[selected_roll - 1]
            )

            if success:
                st.success("Character created successfully!")
                # Clear the creation state
                st.session_state.pop('attribute_rolls', None)
                st.session_state.pop('roll_count', None)
                st.session_state.show_character_creation = False
                st.rerun()
            else:
                st.error(result)


def render_character_selection(auth_handler: AuthHandler, character_service: CharacterService):
    st.header("Character Selection")

    # Get user's characters from backend
    success, result = character_service.get_characters(auth_handler.get_current_user().id)

    if not success:
        if "Character not found" in result:  # Or whatever error indicates no characters
            if st.button("Create Your First Character"):
                st.session_state.show_character_creation = True

            if st.session_state.get('show_character_creation', False):
                render_character_creation(auth_handler, character_service)
            return None
        else:
            st.error(result)
            return None

    # Display existing characters
    characters = result
    if characters:
        st.write("Select a character:")
        print("Debug - Available characters:", characters)  # Debug print
        for char in characters:
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.write(f"{char['first_name']}")
            with col2:
                st.write(f"Level {char['level']} {char['race']} {char['class']}")
            with col3:
                if st.button("Select", key=f"select_{char['id']}"):
                    print(f"Debug - Selected character: {char}")  # Debug print
                    return char  # Just return the character, game interface handles joining

    if st.button("Create New Character"):
        st.session_state.show_character_creation = True

    if st.session_state.get('show_character_creation', False):
        render_character_creation(auth_handler, character_service)

    return None


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
        if 'active_character' in st.session_state:
            st.write(f"Character: {st.session_state.active_character.get('first_name', '')}")
        if st.button("Sign Out"):
            success, message = auth_handler.sign_out()
            if success:
                # Clear session state on logout
                for key in ['client', 'game_state', 'active_character']:
                    st.session_state.pop(key, None)
                st.rerun()
            else:
                st.error(message)

    # Initialize services if needed
    if 'character_service' not in st.session_state:
        config = GameConfig.from_ini()
        st.session_state.character_service = CharacterService(config.base_url)

    # Character selection if no character is active
    if 'active_character' not in st.session_state:
        character = render_character_selection(auth_handler, st.session_state.character_service)
        if character:
            print(f"Selected character data: {character}")  # Debug print
            # Ensure character ID is string
            character['id'] = str(character['id'])
            st.session_state.active_character = character
            # Initialize the game client when character is selected
            config = GameConfig.from_ini()
            st.session_state.client = MUDClient(config)
            # Store user info from auth handler
            st.session_state.user = auth_handler.get_current_user()
            success, message = st.session_state.client.join_game(
                player_id=str(character['id']),  # Explicitly convert to string
                user_id=auth_handler.get_current_user().id
            )
            if success:
                st.session_state.game_state.add_message(message, "system")
                st.rerun()
            else:
                st.error(message)
                # Clean up on failure
                st.session_state.pop('active_character', None)
                st.session_state.pop('client', None)
                return
        return

    # Initialize client if missing (e.g., after page refresh)
    if 'client' not in st.session_state and 'active_character' in st.session_state:
        config = GameConfig.from_ini()
        st.session_state.client = MUDClient(config)
        # Ensure we're using string ID
        player_id = str(st.session_state.active_character['id'])
        success, message = st.session_state.client.join_game(
            player_id=player_id,
            user_id=auth_handler.get_current_user().id
        )
        if not success:
            st.error(message)
            st.session_state.pop('active_character', None)
            st.rerun()
            return

    # Main game area - only show if character is selected and client is initialized
    st.title("MUD Game Terminal")

    # Terminal display area
    terminal_html = "<div class='terminal-container'>"
    for message in st.session_state.game_state.get_messages():
        css_class = f"{message['type']}-message"
        terminal_html += f"<pre class='terminal-message {css_class}'>[{message['timestamp']}] {message['message']}</pre>"
    terminal_html += "</div>"
    st.markdown(terminal_html, unsafe_allow_html=True)

    # Command input
    if 'client' in st.session_state:  # Only show input if client is initialized
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