import os
from supabase import create_client, Client
from typing import Dict, List, Tuple
import requests


class CharacterService:
    def __init__(self, game_base_url: str):
        self.game_base_url = game_base_url
        self.supabase: Client = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )

    def get_characters(self, owner_id: str) -> Tuple[bool, List[Dict] | str]:
        try:
            response = self.supabase.from_('character').select(
                'id, first_name, race, class, level'
            ).eq('owner_id', owner_id).execute()
            # Convert id to string before returning
            for char in response.data:
                char['id'] = str(char['id'])
            return True, response.data
        except Exception as e:
            print(f"Error getting characters: {e}")
            return False, str(e)

    def create_character(self, owner_id: str, first_name: str,
                         race: str, character_class: str,
                         attributes: Dict) -> Tuple[bool, Dict | str]:
        try:
            # Check if name exists
            name_check = self.supabase.from_('character').select(
                'first_name'
            ).eq('first_name', first_name).execute()

            if name_check.data:
                return False, "Character name already exists"

            # First create character in game server (Dropwizard)
            game_request = {
                "ownerId": owner_id,
                "firstName": first_name,
                "lastName": "",  # Default empty last name
                "race": race,
                "characterClass": character_class,
                "attributes": attributes
            }

            try:
                game_response = requests.post(
                    f"{self.game_base_url}/game/characters",
                    json=game_request
                )
                if game_response.status_code != 200:
                    return False, f"Failed to create character in game server: {game_response.text}"

                game_character = game_response.json()
            except Exception as e:
                return False, f"Error creating character in game server: {str(e)}"

            # Then store in Supabase
            character_data = {
                'owner_id': owner_id,
                'first_name': first_name,
                'race': race,
                'class': character_class,
                'attributes': attributes,
                'level': 1,
                'game_id': str(game_character.get('id'))  # Store the game server's ID
            }

            response = self.supabase.from_('character').insert(
                character_data
            ).execute()
            print(f"Create character response: {response.data}")  # Debug print

            if not response.data:
                return False, "Failed to create character in database"

            # Ensure ID is returned as string
            character = response.data[0]
            character['id'] = str(character['id'])

            return True, character
        except Exception as e:
            print(f"Error in create_character: {e}")  # Debug print
            return False, str(e)

    def roll_attributes(self, user_id: str) -> Tuple[bool, Dict | str]:
        """Get attribute rolls from Java backend"""
        try:
            response = requests.post(
                f"{self.game_base_url}/game/attributes/roll"
            )
            if response.status_code == 200:
                return True, response.json()["rolls"]
            return False, response.text
        except Exception as e:
            return False, str(e)

    def get_character(self, character_id: str) -> Tuple[bool, Dict | str]:
        """Get a specific character from Supabase"""
        try:
            response = self.supabase.from_('character').select(
                '*'
            ).eq('id', character_id).single().execute()

            if not response.data:
                return False, "Character not found"
            return True, response.data
        except Exception as e:
            return False, str(e)

    def update_character(self, character_id: str, updates: Dict) -> Tuple[bool, str]:
        """Update character data in Supabase"""
        try:
            response = self.supabase.from_('character').update(
                updates
            ).eq('id', character_id).execute()

            if not response.data:
                return False, "Failed to update character"
            return True, "Character updated successfully"
        except Exception as e:
            return False, str(e)