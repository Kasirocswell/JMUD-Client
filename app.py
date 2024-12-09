import queue
import streamlit as st
import time
from auth_handler import AuthHandler
from character_service import CharacterService
from mud_client import MUDClient, GameConfig, GameState
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components

def switch_to_signup():
    st.session_state.auth_mode = "signup"

def switch_to_signin():
    st.session_state.auth_mode = "signin"

def format_equipment_display(message: str) -> str:
    """Format equipment display with detailed item information"""
    lines = message.split('\n')

    formatted = f"""
Equipment:
{'-' * 50}
"""

    # Process each line after the header
    for line in lines[1:]:
        if ':' in line:
            slot, item = line.split(':', 1)
            item = item.strip()
            if item == "Empty":
                formatted += f"{slot:<10} | {item}\n"
            else:
                formatted += f"{slot:<10} | {item:<25} | Lvl 1 | 2.5 kg\n"

    return formatted

def format_inventory_display(message: str) -> str:
    """Format inventory display with detailed item information"""
    lines = message.split('\n')
    header = lines[0].strip()

    formatted = f"""
{header}

"""

    current_type = None
    for line in lines[1:]:
        if not line.strip():
            continue

        if line.endswith(':'):  # Type header
            if current_type:  # Add space between sections
                formatted += "\n"
            current_type = line
            formatted += f"{current_type}\n"
        elif line.startswith('  '):  # Item line
            item = line.strip()
            if '(x' in item:
                name, count = item.rsplit(' ', 1)
                formatted += f"  {name:<25} {count:>5} | Lvl 1 | 150 cr | 2.5 kg\n"
            else:
                formatted += f"  {item:<30} | Lvl 1 | 100 cr | 3.0 kg\n"

    return formatted

def handle_command():
    """Handle command input and processing"""
    if st.session_state.command_input and st.session_state.client:
        command = st.session_state.command_input
        command_parts = command.lower().split()

        success, result = st.session_state.client.send_command(command)
        if success:
            if result.get('privateMessage'):
                message = result["privateMessage"]

                # Format special command outputs
                if command == "inventory":
                    message = format_inventory_display(message)
                elif command == "equipment":
                    message = format_equipment_display(message)

                st.session_state.game_state.add_message(message, "private")

                # Handle equipment updates
                if command_parts[0] == "equip" and len(command_parts) > 1:
                    item_name = " ".join(command_parts[1:])
                    success, msg = st.session_state.character_service.update_equipment_state(
                        st.session_state.active_character['id'],
                        item_name,
                        True
                    )
                    if not success:
                        print(f"Warning: Failed to update equipment state: {msg}")
                elif command_parts[0] == "unequip" and len(command_parts) > 1:
                    slot = command_parts[1]
                    success, msg = st.session_state.character_service.update_equipment_state(
                        st.session_state.active_character['id'],
                        slot,
                        False
                    )
                    if not success:
                        print(f"Warning: Failed to update equipment state: {msg}")

            if result.get('roomMessage'):
                st.session_state.game_state.add_message(result["roomMessage"], "room")
            if result.get('message'):
                st.session_state.game_state.add_message(result["message"], "system")
        else:
            st.session_state.game_state.add_message(result.get("message", "Unknown error occurred"), "error")

        st.session_state.command_input = ""


def render_game_interface(auth_handler: AuthHandler):
    st.markdown("""
            <style>
            .block-container {
                padding-top: 1rem !important;
                padding-bottom: 0 !important;
            }

            .element-container {
                margin-top: -25px;
            }

            /* Adjusts padding of main content area */
            .main .block-container {
                max-width: unset;
            }

            /* Hide default streamlit padding */
            .stApp > header {
                display: none;
            }
            </style>
        """, unsafe_allow_html=True)

    user = auth_handler.get_current_user()

    if "game_state" not in st.session_state:
        st.session_state.game_state = GameState()

    with st.sidebar:
        st.header("User Info")
        st.write(f"Email: {user.email}")
        if 'active_character' in st.session_state:
            st.write(f"Character: {st.session_state.active_character.get('first_name', '')}")
        if st.button("Sign Out"):
            success, message = auth_handler.sign_out()
            if success:
                for key in ['client', 'game_state', 'active_character']:
                    st.session_state.pop(key, None)
                st.rerun()
            else:
                st.error(message)

    if 'character_service' not in st.session_state:
        config = GameConfig.from_ini()
        st.session_state.character_service = CharacterService(config.base_url)

    if 'active_character' not in st.session_state:
        character = render_character_selection(auth_handler, st.session_state.character_service)
        if character:
            character['id'] = str(character['id'])
            st.session_state.active_character = character
            config = GameConfig.from_ini()
            st.session_state.client = MUDClient(config)
            st.session_state.user = auth_handler.get_current_user()
            success, message = st.session_state.client.join_game(
                player_id=str(character['id']),
                user_id=auth_handler.get_current_user().id
            )
            if success:
                st.session_state.game_state.add_message(message, "system")
                st.rerun()
            else:
                st.error(message)
                st.session_state.pop('active_character', None)
                st.session_state.pop('client', None)
                return
        return

    if 'client' not in st.session_state and 'active_character' in st.session_state:
        config = GameConfig.from_ini()
        st.session_state.client = MUDClient(config)
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
    else:
        if hasattr(st.session_state.client, 'start_listener_thread'):
            st.session_state.client.start_listener_thread()

    st_autorefresh(interval=1000, key="autorefresh")

    st.title("MUD Game Terminal")

    # Add title styling
    st.markdown("""
            <style>
                /* Title styling for MUD Terminal */
                h1 {
                    color: #00ff00 !important;
                    font-family: 'Courier New', Courier, monospace !important;
                    margin-bottom: 25px;
                    text-align: center;
                }
            </style>
        """, unsafe_allow_html=True)

    if hasattr(st.session_state, 'client'):
        try:
            msg = st.session_state.client._redis_queue.get_nowait()
            if msg:
                st.session_state.game_state.add_message(msg, "system")
        except queue.Empty:
            pass

    terminal_messages_html = ''.join([
        f"<pre class='terminal-message {message['type']}-message'>[{message['timestamp']}] {message['message']}</pre>"
        for message in st.session_state.game_state.get_messages()
    ])

    html_code = f"""
    <html>
    <head>
    <style>
    .terminal-container {{
        background-color: black;
        color: #00ff00;
        font-family: 'Courier New', Courier, monospace;
        padding: 10px;
        height: 90vh;
        overflow-y: scroll; 
        margin: 0 auto;
        margin-bottom: 25px;
        border-radius: 5px;
        display: flex;
        flex-direction: column;
        width: 100%;
        margin-left: auto;
        margin-right: auto;
    }}
    .terminal-container::-webkit-scrollbar {{
        width: 0; 
        background: transparent;
    }}
    .terminal-container {{
        scrollbar-width: none; 
        -ms-overflow-style: none;
    }}
    .terminal-message {{
        margin: 0;
        padding: 2px 0;
        white-space: pre-wrap;
        word-wrap: break-word;
    }}
    .system-message {{ color: #00ff00; }}
    .private-message {{ color: #00ffff; }}
    .room-message {{ color: #ffff00; }}
    .error-message {{ color: #ff0000; }}
    </style>
    </head>
    <body>
    <div class='terminal-container' id='game-terminal'>
        {terminal_messages_html}
        <div id='scroll-anchor'></div>
    </div>
    <script>
    const anchor = document.getElementById('scroll-anchor');
    if (anchor) {{
        anchor.scrollIntoView({{ block: 'end' }});
    }}
    </script>
    </body>
    </html>
    """

    components.html(html_code, height=700, scrolling=True)

    if 'client' in st.session_state:
        st.markdown("""
            <style>
            .stTextInput {
                width: 100%;
                margin-left: auto;
                margin-right: auto;
                margin-top: 0px;
            }

            .stTextInput input {
                background-color: black;
                color: #00ff00;
                font-family: 'Courier New', Courier, monospace;
                border: 1px solid #00ff00;
            }
            </style>
        """, unsafe_allow_html=True)

        # Add sidebar styling
        st.markdown("""
                <style>
                    /* Sidebar styling */
                    .css-1d391kg {  /* Sidebar container */
                        background-color: black;
                    }

                    .css-1d391kg .block-container {
                        padding-top: 1rem;
                    }

                    /* Sidebar text */
                    .css-1d391kg h2 {
                        color: #00ff00;
                        font-family: 'Courier New', Courier, monospace;
                        padding-bottom: 100px;
                    }

                    .css-1d391kg p {
                        color: #00ff00;
                        font-family: 'Courier New', Courier, monospace;
                    }

                    /* Sidebar button */
                    .css-1d391kg .stButton button {
                        background-color: black;
                        color: #00ff00;
                        border: 1px solid #00ff00;
                        font-family: 'Courier New', Courier, monospace;
                        width: 100%;
                        margin-top: 25px;
                    }

                    .css-1d391kg .stButton button:hover {
                        background-color: #003300;
                        border: 1px solid #00ff00;
                    }
                </style>
            """, unsafe_allow_html=True)


        st.text_input(
            "Command Input",
            key="command_input",
            placeholder="Enter command...",
            on_change=handle_command,
            label_visibility="collapsed"
        )

def render_character_selection(auth_handler: AuthHandler, character_service: CharacterService):
    st.header("Character Selection")

    success, result = character_service.get_characters(auth_handler.get_current_user().id)
    if not success:
        if "Character not found" in result:
            if st.button("Create Your First Character"):
                st.session_state.show_character_creation = True
            if st.session_state.get('show_character_creation', False):
                render_character_creation(auth_handler, character_service)
            return None
        else:
            st.error(result)
            return None

    characters = result
    if characters:
        st.write("Select a character:")
        for char in characters:
            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
            with col1:
                st.write(f"{char['first_name']}")
            with col2:
                st.write(f"Level {char['level']} {char['race']} {char['class']}")
            with col3:
                if st.button("Select", key=f"select_{char['id']}"):
                    return char
            with col4:
                if st.button("Delete", key=f"delete_{char['id']}", type="secondary"):
                    if st.session_state.get(f"confirm_delete_{char['id']}", False):
                        success, message = character_service.delete_character(char['id'])
                        if success:
                            st.success("Character deleted successfully!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Failed to delete character: {message}")
                    else:
                        st.session_state[f"confirm_delete_{char['id']}"] = True
                        st.warning(f"Are you sure you want to delete {char['first_name']}? This cannot be undone.")
                        col5, col6 = st.columns(2)
                        with col5:
                            if st.button("Yes, delete", key=f"confirm_yes_{char['id']}", type="primary"):
                                success, message = character_service.delete_character(char['id'])
                                if success:
                                    st.success("Character deleted successfully!")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"Failed to delete character: {message}")
                        with col6:
                            if st.button("No, cancel", key=f"confirm_no_{char['id']}"):
                                st.session_state[f"confirm_delete_{char['id']}"] = False
                                st.rerun()

    if st.button("Create New Character"):
        st.session_state.show_character_creation = True

    if st.session_state.get('show_character_creation', False):
        render_character_creation(auth_handler, character_service)

    return None

def render_character_creation(auth_handler: AuthHandler, character_service: CharacterService):
    st.header("Create New Character")
    with st.form("character_creation"):
        col1, col2 = st.columns(2)

        with col1:
            first_name = st.text_input("First Name")
            race = st.selectbox("Race", ['HUMAN', 'DRACONIAN', 'SYNTH', 'CONSTRUCT', 'ANDROID'])

        with col2:
            character_class = st.selectbox("Class", ['SOLDIER', 'PILOT', 'HACKER', 'ENGINEER', 'MEDIC'])

            if 'attribute_rolls' not in st.session_state:
                st.session_state.attribute_rolls = []
                st.session_state.roll_count = 0

            if st.form_submit_button("Roll Attributes"):
                if st.session_state.roll_count < 3:
                    success, result = character_service.roll_attributes(auth_handler.get_current_user().id)
                    if success:
                        st.session_state.attribute_rolls.append(result)
                        st.session_state.roll_count += 1

            if st.session_state.attribute_rolls:
                st.write("Your rolls:")
                for i, roll in enumerate(st.session_state.attribute_rolls):
                    st.write(f"Roll {i + 1}:", roll)
                selected_roll = st.selectbox("Select roll to use", range(1, len(st.session_state.attribute_rolls) + 1))

        create_button = st.form_submit_button("Create Character")

        if create_button:
            if not first_name:
                st.error("Please enter a character name")
                return
            if not st.session_state.attribute_rolls:
                st.error("Please roll for attributes first")
                return

            success, result = character_service.create_character(
                owner_id=auth_handler.get_current_user().id,
                first_name=first_name,
                race=race,
                character_class=character_class,
                attributes=st.session_state.attribute_rolls[selected_roll - 1]
            )

            if success:
                spawn_success, spawn_message = character_service.give_starter_items(result['id'])
                if not spawn_success:
                    st.error(f"Warning: Failed to give starter items: {spawn_message}")

                st.success("Character created successfully!")
                st.session_state.pop('attribute_rolls', None)
                st.session_state.pop('roll_count', None)
                st.session_state.show_character_creation = False
                st.rerun()
            else:
                st.error(result)

def render_auth_page(auth_handler: AuthHandler):
    st.title("MUD Game")

    if st.session_state.auth_mode == "signup":
        render_signup_form(auth_handler)
    else:
        render_signin_form(auth_handler)

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

def main():
    st.set_page_config(
        page_title="MUD Game Client",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    auth_handler = AuthHandler()
    auth_handler.initialize_session_state()
    auth_handler.check_session()

    if not auth_handler.is_authenticated():
        render_auth_page(auth_handler)
    else:
        render_game_interface(auth_handler)

if __name__ == "__main__":
    main()