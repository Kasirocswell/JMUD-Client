import requests
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict
import time
import streamlit as st
from configparser import ConfigParser
from character_service import CharacterService
import json
import redis
import threading
import queue


@dataclass
class GameConfig:
    """Game configuration settings"""
    base_url: str
    refresh_rate: float
    max_messages: int
    redis_host: str = "localhost"
    redis_port: int = 6379

    @classmethod
    def from_ini(cls, environment: str = "development") -> "GameConfig":
        config = ConfigParser()
        config.read("config.ini")
        env_config = config[environment]

        return cls(
            base_url=env_config.get("base_url"),
            refresh_rate=env_config.getfloat("refresh_rate"),
            max_messages=env_config.getint("max_messages"),
            redis_host=env_config.get("redis_host", "localhost"),
            redis_port=env_config.getint("redis_port", 6379)
        )


class MUDClient:
    def __init__(self, config: GameConfig):
        self.config = config
        self.player_id = None
        self._redis_queue = queue.Queue()  # Create instance-level queue

        # Initialize Redis
        try:
            self.redis_client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                decode_responses=True
            )
            self.pubsub = self.redis_client.pubsub(ignore_subscribe_messages=True)
            self._stop_listening = threading.Event()
            self.listener_thread = None  # Add this attribute
            print("Redis connection initialized successfully")
        except Exception as e:
            print(f"Failed to initialize Redis connection: {e}")
            self.redis_client = None
            self.pubsub = None

    def join_game(self, player_id: str, user_id: str) -> tuple[bool, str]:
        """Join game with a character"""
        try:
            print(f"Joining game with player_id: {player_id}, user_id: {user_id}")

            # First, try to get the character from game state
            get_response = requests.get(f"{self.config.base_url}/game/characters/get/{player_id}")

            # If character doesn't exist in game state, we need to create it
            if get_response.status_code == 404:
                print("Character not found in game state, retrieving from Supabase...")
                # Get character data from Supabase
                char_service = CharacterService(self.config.base_url)
                success, char_data = char_service.get_character(player_id)

                print(f"Supabase character data: {char_data}")

                if success:
                    # Convert attributes from string to dict if needed
                    attributes = char_data.get('attributes')
                    if isinstance(attributes, str):
                        attributes = json.loads(attributes)

                    # Create request payload
                    create_payload = {
                        "id": player_id,
                        "ownerId": user_id,
                        "firstName": char_data['first_name'],
                        "lastName": char_data.get('last_name', ''),
                        "race": str(char_data['race']).upper(),
                        "characterClass": str(char_data['class']).upper(),
                        "attributes": attributes,
                        "currentRoomName": char_data.get('room_name')
                    }
                    print(f"Creating character with payload: {create_payload}")

                    # Create character in game state
                    create_response = requests.post(
                        f"{self.config.base_url}/game/characters",
                        json=create_payload
                    )
                    print(f"Create character response: {create_response.status_code}, {create_response.text}")

                    if create_response.status_code != 200:
                        error_message = create_response.text
                        try:
                            error_data = create_response.json()
                            if 'error' in error_data:
                                error_message = error_data['error']
                        except Exception:
                            pass
                        return False, f"Failed to create character in game state: {error_message}"

                    # Get the game server's character ID from response
                    game_character = create_response.json()
                    game_character_id = game_character['id']

                    # Store both IDs in session state for reference
                    if not hasattr(self, 'id_mapping'):
                        self.id_mapping = {}
                    self.id_mapping[player_id] = game_character_id

                    # Use the game server's ID for joining
                    player_id = game_character_id

                else:
                    return False, f"Failed to get character data from Supabase: {char_data}"

            # Now try to join with the game server's ID
            join_payload = {
                "playerId": player_id,
                "userId": user_id
            }
            print(f"Sending join payload: {join_payload}")

            response = requests.post(
                f"{self.config.base_url}/game/join",
                json=join_payload
            )
            print(f"Join game response: {response.text}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    self.player_id = player_id
                    # Start Redis subscription if available
                    if self.redis_client:
                        self.subscribe_to_redis(player_id)
                    return True, data["message"]
                except Exception as e:
                    print(f"Error parsing join response: {e}")
                    return False, f"Error parsing join response: {str(e)}"

            # Try to get detailed error message from response
            error_message = response.text
            try:
                error_data = response.json()
                if 'error' in error_data:
                    error_message = error_data['error']
            except Exception:
                pass
            return False, f"Failed to join game: {error_message}"

        except Exception as e:
            print(f"Exception in join_game: {str(e)}")
            return False, f"Error joining game: {str(e)}"

    def send_command(self, command: str) -> tuple[bool, dict]:
        """Send a command to the game server"""
        try:
            if not self.player_id:
                return False, {"message": "Not connected to game"}

            # Parse command into command name and args
            parts = command.strip().split(maxsplit=1)
            command_name = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""

            print(f"Sending command: {command_name}, args: {args}")  # Debug print

            response = requests.post(
                f"{self.config.base_url}/game/command",
                json={
                    "playerId": str(self.player_id),
                    "command": command
                }
            )
            print(f"Command response: {response.text}")  # Debug print

            if response.status_code == 200:
                result = response.json()
                # Extract the result message from the CommandResult
                if 'result' in result:
                    message = result['result'].get('message', '')
                    success = result['result'].get('success', False)
                    private_message = result['result'].get('privateMessage', '')
                    room_message = result['result'].get('roomMessage', '')

                    return True, {
                        "success": success,
                        "message": message,
                        "privateMessage": private_message,
                        "roomMessage": room_message
                    }
                return True, result

            # Handle error responses
            try:
                error_data = response.json()
                error_msg = error_data.get('error', f"Command failed: {response.text}")
            except:
                error_msg = f"Command failed: {response.text}"

            return False, {"message": error_msg}

        except Exception as e:
            print(f"Exception in send_command: {str(e)}")  # Debug print
            return False, {"message": f"Error sending command: {str(e)}"}

    def start_listener_thread(self):
        """Ensure the Redis listener thread is running."""
        if self.listener_thread is None or not self.listener_thread.is_alive():
            self._stop_listening.clear()
            self.listener_thread = threading.Thread(target=self.listen_to_redis, daemon=True)
            self.listener_thread.start()

    def listen_to_redis(self):
        """Background thread to listen to Redis messages."""
        try:
            while not self._stop_listening.is_set():
                message = self.pubsub.get_message()
                if message and message['type'] == 'message':
                    data = message['data']
                    # Use instance queue instead of session state
                    self._redis_queue.put(data)
                    print(f"Added message to queue: {data}")
                time.sleep(0.1)
        except Exception as e:
            print(f"Redis listener error: {e}")

    def subscribe_to_redis(self, player_id: str):
        """Subscribe to Redis channels for system messages"""
        if not self.redis_client:
            return

        # Subscribe to channels
        print(f"Subscribing to Redis channels for player {player_id}")
        self.pubsub.subscribe(f"player:{player_id}", "system")
        self.start_listener_thread()

    # Removed the __del__ method to prevent listener thread from stopping
    # def __del__(self):
    #     """Cleanup Redis connections"""
    #     if hasattr(self, '_stop_listening'):
    #         self._stop_listening.set()
    #     if hasattr(self, 'pubsub'):
    #         try:
    #             self.pubsub.unsubscribe()
    #             self.pubsub.close()
    #         except:
    #             pass
    #     if hasattr(self, 'redis_client'):
    #         try:
    #             self.redis_client.close()
    #         except:
    #             pass


class GameState:
    """Manages the game state in the Streamlit session"""

    def __init__(self):
        if "messages" not in st.session_state:
            st.session_state.messages = []

    def add_message(self, message: str, message_type: str = "system"):
        """Add a message to the game history"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        st.session_state.messages.append({
            "timestamp": timestamp,
            "message": message,
            "type": message_type
        })

        # Keep only the last 100 messages
        while len(st.session_state.messages) > 100:
            st.session_state.messages.pop(0)

    def get_messages(self):
        """Get all messages in chronological order"""
        return st.session_state.messages

    def clear_messages(self):
        """Clear all messages"""
        st.session_state.messages = []
