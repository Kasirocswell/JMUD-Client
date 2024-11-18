import requests
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict
import time
import streamlit as st
from configparser import ConfigParser


@dataclass
class GameConfig:
    """Game configuration settings"""
    base_url: str
    refresh_rate: float
    max_messages: int

    @classmethod
    def from_ini(cls, environment: str = "development") -> "GameConfig":
        config = ConfigParser()
        config.read("config.ini")
        env_config = config[environment]

        return cls(
            base_url=env_config.get("base_url"),
            refresh_rate=env_config.getfloat("refresh_rate"),
            max_messages=env_config.getint("max_messages")
        )


class MUDClient:
    def __init__(self, config: GameConfig):
        self.config = config
        self.player_id = None
        self.player_name = None
        self._verify_connection()

    def _verify_connection(self):
        """Verify connection to the game server"""
        try:
            requests.get(f"{self.config.base_url}/health")
            return True
        except Exception as e:
            st.error(f"Unable to connect to game server: {str(e)}")
            return False

    def join_game(self, player_name: str) -> tuple[bool, str]:
        try:
            if not self._verify_connection():
                return False, "Game server is not available"

            response = requests.post(
                f"{self.config.base_url}/game/join",
                json={"name": player_name}
            )
            if response.status_code == 200:
                data = response.json()
                self.player_id = data["playerId"]
                self.player_name = player_name
                return True, data["message"]
            return False, f"Failed to join game: {response.text}"
        except Exception as e:
            return False, f"Error joining game: {str(e)}"

    def send_command(self, command: str) -> tuple[bool, dict]:
        try:
            if not self.player_id:
                return False, {"message": "Not connected to game"}

            response = requests.post(
                f"{self.config.base_url}/game/command",
                json={"playerId": self.player_id, "command": command}
            )
            if response.status_code == 200:
                return True, response.json()["result"]
            return False, {"message": f"Command failed: {response.text}"}
        except Exception as e:
            return False, {"message": f"Error sending command: {str(e)}"}


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