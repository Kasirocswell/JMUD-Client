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
                'energy': 100,
                'initial_spawn': True  # Set initial_spawn to True for new characters
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

    def should_spawn_initial_items(self, character_id: str) -> bool:
        """Check if character should receive initial items"""
        try:
            response = self.supabase.from_('character').select(
                'initial_spawn'
            ).eq('id', character_id).execute()

            if response.data and response.data[0]:
                return response.data[0].get('initial_spawn', False)
            return False
        except Exception as e:
            print(f"Error checking initial_spawn: {e}")
            return False

    def mark_initial_spawn_complete(self, character_id: str) -> bool:
        """Mark that initial items have been spawned"""
        try:
            response = self.supabase.from_('character').update({
                'initial_spawn': False
            }).eq('id', character_id).execute()

            return bool(response.data)
        except Exception as e:
            print(f"Error updating initial_spawn: {e}")
            return False

    def give_starter_items(self, character_id: str) -> tuple[bool, str]:
        """Give starter items if needed"""
        try:
            # Check initial spawn status
            check_response = self.supabase.from_('character').select(
                'initial_spawn, first_name'
            ).eq('id', character_id).execute()

            print("\n=== Initial Items Distribution Check ===")
            print(f"Character ID: {character_id}")
            print(f"Initial check response: {check_response.data}")

            if not check_response.data:
                print("ERROR: Character not found in database")
                return False, "Character not found"

            character_name = check_response.data[0].get('first_name', 'Unknown')
            initial_spawn = check_response.data[0].get('initial_spawn')

            print(f"Character Name: {character_name}")
            print(f"Initial Spawn Value: {initial_spawn}")

            if not initial_spawn:
                print("Initial items already distributed, skipping")
                return True, "Starter items already given"

            # Give starter items
            print("\nAttempting to distribute starter items...")
            items_response = self.supabase.rpc('give_starter_items', {
                'player_id': character_id
            }).execute()

            print(f"Starter items distribution response: {items_response.data}")

            if items_response.data is not None:
                # Try direct SQL update via RPC
                print("\nAttempting to update initial_spawn flag via RPC...")
                update_response = self.supabase.rpc(
                    'update_initial_spawn',
                    {'p_character_id': character_id}
                ).execute()

                print(f"Update response: {update_response.data}")

                # Verify the update
                verify_response = self.supabase.from_('character').select(
                    'initial_spawn'
                ).eq('id', character_id).execute()

                print("\n=== Final Verification ===")
                print(f"Verification response: {verify_response.data}")
                print(
                    f"New initial_spawn value: {verify_response.data[0].get('initial_spawn') if verify_response.data else 'Unknown'}")

                if verify_response.data and not verify_response.data[0].get('initial_spawn'):
                    print(f"SUCCESS: Initial spawn completed for {character_name}")
                    return True, "Starter items given successfully"
                else:
                    print(f"ERROR: Failed to verify initial spawn update for {character_name}")
                    return False, "Failed to verify initial spawn update"

            print("ERROR: Failed to distribute starter items")
            return False, "Failed to give starter items"
        except Exception as e:
            print("\n=== Error in give_starter_items ===")
            print(f"Exception type: {type(e)}")
            print(f"Exception message: {str(e)}")
            print(f"Character ID: {character_id}")
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

    def delete_character(self, character_id: str) -> tuple[bool, str]:
        """Delete a character and its associated inventory items"""
        try:
            # First delete inventory items
            response = self.supabase.from_('inventory_items').delete().eq('player_id', character_id).execute()
            if not response.data:
                return False, "Failed to delete inventory items"

            # Then delete the character
            response = self.supabase.from_('character').delete().eq('id', character_id).execute()
            if not response.data:
                return False, "Failed to delete character"

            # Finally tell the game server to remove the character
            server_response = requests.delete(f"{self.game_base_url}/game/characters/{character_id}")
            if server_response.status_code != 200:
                print(f"Warning: Game server character deletion failed: {server_response.text}")
                # Don't return false here since DB deletion was successful

            return True, "Character deleted successfully"
        except Exception as e:
            print(f"Error in delete_character: {e}")
            return False, str(e)

    def update_equipment_state(self, player_id: str, item_name: str, equipping: bool) -> tuple[bool, str]:
        """Update equipment state in database"""
        try:
            if equipping:
                # First try exact match
                item_query = self.supabase.from_('items').select('id').ilike('name', item_name).execute()

                # If no exact match, try partial match
                if not item_query.data:
                    item_query = self.supabase.from_('items').select('id').ilike('name', f'%{item_name}%').execute()

                if not item_query.data:
                    return False, f"Item not found: {item_name}"

                item_id = item_query.data[0]['id']

                # Update the equipped status for this specific item
                response = self.supabase.from_('inventory_items').update({
                    'equipped': True
                }).eq('player_id', player_id).eq('item_id', item_id).execute()

                print(f"Equip response: {response.data}")  # Debug print

            else:
                # Unequipping logic remains the same
                slot = item_name.upper()
                item_query = self.supabase.from_('items').select('id').eq('slot', slot).execute()
                if not item_query.data:
                    return False, f"No items found for slot: {slot}"

                item_ids = [item['id'] for item in item_query.data]

                response = self.supabase.from_('inventory_items').update({
                    'equipped': False
                }).eq('player_id', player_id).in_('item_id', item_ids).eq('equipped', True).execute()

                print(f"Unequip response: {response.data}")  # Debug print

            if response.data is not None:
                return True, "Equipment state updated"
            return False, "Failed to update equipment state"

        except Exception as e:
            print(f"Error updating equipment state: {e}")
            return False, str(e)