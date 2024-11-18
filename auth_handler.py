from supabase import create_client, Client
from dotenv import load_dotenv
import os
import streamlit as st
from typing import Optional, Dict, Tuple
from datetime import datetime

load_dotenv()


class AuthHandler:
    def __init__(self):
        self.supabase: Client = create_client(
            os.getenv("SUPABASE_URL", ""),
            os.getenv("SUPABASE_KEY", "")
        )

    def initialize_session_state(self):
        """Initialize session state variables for authentication"""
        if "authenticated" not in st.session_state:
            st.session_state.authenticated = False
        if "user" not in st.session_state:
            st.session_state.user = None
        if "auth_mode" not in st.session_state:
            st.session_state.auth_mode = "signin"

    def check_user_exists(self, email: str) -> bool:
        """Check if a user exists in the user table"""
        try:
            response = self.supabase.table('user').select('email').eq('email', email).execute()
            return len(response.data) > 0
        except Exception as e:
            st.error(f"Error checking user: {str(e)}")
            return False

    def create_user(self, auth_user) -> bool:
        """Create a new user in the user table"""
        try:
            user_data = {
                'id': auth_user.id,
                'email': auth_user.email,
                'characters': [],
                'created_at': datetime.utcnow().isoformat()
            }

            response = self.supabase.table('user').insert(user_data).execute()
            return True
        except Exception as e:
            st.error(f"Error creating user: {str(e)}")
            return False

    def sign_up(self, email: str, password: str) -> Tuple[bool, str]:
        """Sign up a new user"""
        try:
            # Check if user already exists
            if self.check_user_exists(email):
                return False, "User already exists. Please sign in instead."

            # Create auth user
            response = self.supabase.auth.sign_up({
                "email": email,
                "password": password
            })

            if response.user:
                # Create user in user table
                if self.create_user(response.user):
                    st.session_state.authenticated = True
                    st.session_state.user = response.user
                    return True, "Successfully signed up!"
                else:
                    return False, "Failed to create user profile. Please try again."

            return False, "Failed to sign up. Please try again."
        except Exception as e:
            return False, f"Error signing up: {str(e)}"

    def sign_in(self, email: str, password: str) -> Tuple[bool, str]:
        """Sign in an existing user"""
        try:
            # Check if user exists in user table
            if not self.check_user_exists(email):
                return False, "User not found. Please sign up first."

            # Attempt to sign in
            response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            if response.user:
                st.session_state.authenticated = True
                st.session_state.user = response.user
                return True, "Successfully signed in!"

            return False, "Failed to sign in. Please check your credentials."
        except Exception as e:
            return False, f"Error signing in: {str(e)}"

    def sign_out(self):
        """Sign out the current user"""
        try:
            self.supabase.auth.sign_out()
            st.session_state.authenticated = False
            st.session_state.user = None
            return True, "Signed out successfully!"
        except Exception as e:
            return False, f"Error signing out: {str(e)}"

    def check_session(self):
        """Check if there's an active session"""
        try:
            session = self.supabase.auth.get_session()
            if session and session.user:
                st.session_state.authenticated = True
                st.session_state.user = session.user
                return True
        except Exception:
            pass
        return False

    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return st.session_state.get('authenticated', False)

    def get_current_user(self) -> Optional[Dict]:
        """Get the current authenticated user"""
        return st.session_state.get('user')

    def get_user_characters(self, user_id: str) -> list:
        """Get user's characters from user table"""
        try:
            response = self.supabase.table('user').select('characters').eq('id', user_id).execute()
            if response.data:
                return response.data[0]['characters'] or []
            return []
        except Exception as e:
            st.error(f"Error fetching user characters: {str(e)}")
            return []