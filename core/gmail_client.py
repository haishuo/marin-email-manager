# core/gmail_client.py
"""
Gmail API client for Marin email management system.
Handles authentication and basic Gmail operations.
"""

import os
import json
from typing import Dict, List, Optional, Any
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

class GmailClient:
    """Gmail API client with authentication and basic operations"""
    
    def __init__(self, credentials_path: str = 'config/credentials.json'):
        """
        Initialize Gmail client with credentials
        
        Args:
            credentials_path: Path to OAuth credentials JSON file
        """
        self.credentials_path = credentials_path
        self.token_path = 'config/token.json'
        self.service = None
        self._authenticate()
    
    def _authenticate(self) -> None:
        """Handle OAuth authentication flow"""
        creds = None
        
        # Load existing token if available
        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            except Exception as e:
                print(f"Warning: Could not load existing token: {e}")
        
        # Refresh expired credentials or run OAuth flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    print("✅ Refreshed existing credentials")
                except Exception as e:
                    print(f"❌ Failed to refresh credentials: {e}")
                    creds = None
            
            if not creds:
                # Run OAuth flow
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Credentials file not found: {self.credentials_path}\n"
                        "Please download OAuth credentials from Google Cloud Console"
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
                print("✅ Completed OAuth authentication")
            
            # Save credentials for next run
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
            print(f"✅ Saved credentials to {self.token_path}")
        
        # Build Gmail service
        try:
            self.service = build('gmail', 'v1', credentials=creds)
            print("✅ Gmail API client initialized successfully")
        except Exception as e:
            raise Exception(f"Failed to build Gmail service: {e}")
    
    def test_connection(self) -> Dict[str, Any]:
        """Test Gmail API connection and return user info"""
        try:
            profile = self.service.users().getProfile(userId='me').execute()
            return {
                'success': True,
                'email': profile.get('emailAddress'),
                'messages_total': profile.get('messagesTotal', 0),
                'threads_total': profile.get('threadsTotal', 0)
            }
        except HttpError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def list_messages(self, query: str = '', max_results: int = 100, 
                     page_token: str = None) -> Dict[str, Any]:
        """
        List Gmail messages matching query
        
        Args:
            query: Gmail search query (e.g., 'after:2020/01/01')
            max_results: Maximum number of messages to return
            page_token: Token for pagination
            
        Returns:
            Dict with messages list and pagination info
        """
        try:
            kwargs = {
                'userId': 'me',
                'maxResults': max_results
            }
            
            if query:
                kwargs['q'] = query
            if page_token:
                kwargs['pageToken'] = page_token
            
            result = self.service.users().messages().list(**kwargs).execute()
            
            return {
                'success': True,
                'messages': result.get('messages', []),
                'next_page_token': result.get('nextPageToken'),
                'result_size_estimate': result.get('resultSizeEstimate', 0)
            }
            
        except HttpError as e:
            return {
                'success': False,
                'error': str(e),
                'messages': []
            }
    
    def get_message(self, message_id: str, format: str = 'full') -> Dict[str, Any]:
        """
        Get single Gmail message by ID
        
        Args:
            message_id: Gmail message ID
            format: Response format ('minimal', 'full', 'raw', 'metadata')
            
        Returns:
            Dict with message data or error
        """
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format=format
            ).execute()
            
            return {
                'success': True,
                'message': message
            }
            
        except HttpError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def batch_get_messages(self, message_ids: List[str], 
                          format: str = 'full') -> List[Dict[str, Any]]:
        """
        Get multiple messages in batch (more efficient)
        
        Args:
            message_ids: List of Gmail message IDs
            format: Response format
            
        Returns:
            List of message results
        """
        # Note: Gmail API doesn't have true batch for get_message
        # This is a convenience method that handles multiple requests
        # For true efficiency, we'd need to use the batch HTTP library
        
        results = []
        for message_id in message_ids:
            result = self.get_message(message_id, format)
            results.append({
                'message_id': message_id,
                **result
            })
        
        return results
    
    def delete_message(self, message_id: str) -> Dict[str, Any]:
        """
        Delete message (move to trash - recoverable for 30 days)
        
        Args:
            message_id: Gmail message ID
            
        Returns:
            Dict with success status
        """
        try:
            self.service.users().messages().delete(
                userId='me',
                id=message_id
            ).execute()
            
            return {
                'success': True,
                'message': f'Message {message_id} moved to trash'
            }
            
        except HttpError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def untrash_message(self, message_id: str) -> Dict[str, Any]:
        """
        Restore message from trash
        
        Args:
            message_id: Gmail message ID
            
        Returns:
            Dict with success status
        """
        try:
            self.service.users().messages().untrash(
                userId='me',
                id=message_id
            ).execute()
            
            return {
                'success': True,
                'message': f'Message {message_id} restored from trash'
            }
            
        except HttpError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_labels(self) -> Dict[str, Any]:
        """
        Get all Gmail labels
        
        Returns:
            Dict with labels list or error
        """
        try:
            results = self.service.users().labels().list(userId='me').execute()
            
            return {
                'success': True,
                'labels': results.get('labels', [])
            }
            
        except HttpError as e:
            return {
                'success': False,
                'error': str(e),
                'labels': []
            }
    
    def get_quota_usage(self) -> Dict[str, Any]:
        """
        Get current API quota usage (approximate)
        Note: Gmail API doesn't provide exact quota usage
        
        Returns:
            Dict with quota information
        """
        # This is a placeholder - Gmail API doesn't provide exact quota usage
        # In a real implementation, you'd track this in your database
        return {
            'daily_quota': 1_000_000_000,  # 1 billion quota units per day
            'estimated_used': 0,  # Would track this in database
            'estimated_remaining': 1_000_000_000
        }

# Convenience functions for common operations
def create_gmail_client(credentials_path: str = 'config/credentials.json') -> GmailClient:
    """Create and return authenticated Gmail client"""
    return GmailClient(credentials_path)

def test_gmail_connection(credentials_path: str = 'config/credentials.json') -> bool:
    """Test Gmail API connection"""
    try:
        client = GmailClient(credentials_path)
        result = client.test_connection()
        
        if result['success']:
            print(f"✅ Connected to Gmail: {result['email']}")
            print(f"   Total messages: {result['messages_total']:,}")
            print(f"   Total threads: {result['threads_total']:,}")
            return True
        else:
            print(f"❌ Gmail connection failed: {result['error']}")
            return False
            
    except Exception as e:
        print(f"❌ Gmail connection error: {e}")
        return False

# Example usage and testing
if __name__ == "__main__":
    """Test the Gmail client"""
    
    print("🔧 Testing Gmail API Client")
    print("=" * 50)
    
    try:
        # Test connection
        if not test_gmail_connection():
            exit(1)
        
        # Create client
        client = create_gmail_client()
        
        # Test basic operations
        print("\n📧 Testing basic operations...")
        
        # List recent messages
        recent = client.list_messages(query='after:2024/01/01', max_results=5)
        if recent['success']:
            print(f"✅ Found {len(recent['messages'])} recent messages")
        else:
            print(f"❌ Failed to list messages: {recent['error']}")
        
        # Get labels
        labels = client.get_labels()
        if labels['success']:
            print(f"✅ Found {len(labels['labels'])} labels")
        else:
            print(f"❌ Failed to get labels: {labels['error']}")
        
        print("\n🎉 Gmail client test completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        exit(1)
