import os
from supabase import create_client, Client
from typing import Dict, List, Tuple
import requests
import uuid


class CharacterService:
    def __init__(self, game_base_url: str):
        self.game_base_url = game_base_url
        self.supabase: Client = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )

    def update_location(self, character_id: str, room_name: str) -> Tuple[bool, str]:
        """Update character's location in Supabase"""
        try:
            response = self.supabase.table('character').update({
                'room_name': room_name
            }).eq('id', character_id).execute()

            if not response.data:
                return False, "Failed to update location"
            return True, "Location updated successfully"
        except Exception as e:
            print(f"Error updating location: {e}")
            return False, str(e)

    def get_characters(self, owner_id: str) -> Tuple[bool, List[Dict] | str]:
        try:
            response = self.supabase.from_('character').select(
                'id, first_name, race, class, level'
            ).eq('owner_id', owner_id).execute()

            return True, response.data
        except Exception as e:
            print(f"Error getting characters: {e}")
            return False, str(e)

    def create_character(self, owner_id: str, first_name: str,
                         race: str, character_class: str,
                         attributes: Dict) -> Tuple[bool, Dict | str]:
        try:
            # Name check first
            name_check = self.supabase.from_('character').select(
                'first_name'
            ).ilike('first_name', first_name).execute()

            if name_check.data:
                print(f"Name check failed: {first_name} already exists")
                return False, "Character name already exists"

            # Generate UUID for new character
            character_id = str(uuid.uuid4())

            # Create character in database first
            character_data = {
                'id': character_id,
                'owner_id': owner_id,
                'first_name': first_name,
                'last_name': None,
                'race': race,
                'class': character_class,
                'attributes': attributes,
                'level': 1,
                'credits': 100,
                'health': 100,
                'energy': 100
            }

            # Insert into Supabase
            db_response = self.supabase.from_('character').insert(
                character_data
            ).execute()
            print(f"Create character response from Supabase: {db_response.data}")

            if not db_response.data:
                return False, "Failed to create character in database"

            # Create in game server - single create call
            game_request = {
                "id": character_id,
                "ownerId": owner_id,
                "firstName": first_name,
                "lastName": "",
                "race": race,
                "characterClass": character_class,
                "attributes": attributes
            }

            game_response = requests.post(
                f"{self.game_base_url}/game/characters",
                json=game_request
            )

            print(f"Game server response: {game_response.text}")

            if game_response.status_code != 200:
                # Clean up database if game server fails
                self.supabase.from_('character').delete().eq('id', character_id).execute()
                return False, f"Failed to create character in game server: {game_response.text}"

            return True, db_response.data[0]

        except Exception as e:
            print(f"Error in create_character: {e}")
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