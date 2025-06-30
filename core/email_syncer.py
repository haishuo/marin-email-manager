# core/email_syncer.py
"""
Email syncing engine for Marin email management system.
Downloads emails from Gmail API and stores them in PostgreSQL database.
"""

import time
import json
import base64
import email
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime
import re

from core.gmail_client import GmailClient
from core.database import MarinDatabase
from utils.config import get_config

class EmailSyncer:
    """Downloads emails from Gmail to PostgreSQL in batches"""
    
    def __init__(self, gmail_client: Optional[GmailClient] = None, 
                 database: Optional[MarinDatabase] = None):
        """
        Initialize email syncer
        
        Args:
            gmail_client: Gmail API client (creates new if None)
            database: Database connection (creates new if None)
        """
        self.config = get_config()
        self.gmail = gmail_client or GmailClient()
        self.db = database or MarinDatabase()
        
        # Rate limiting
        self.api_calls_made = 0
        self.batch_start_time = time.time()
        
    def sync_oldest_emails(self, count: int = 1000, batch_size: int = 100) -> Dict[str, Any]:
        """
        Download oldest emails first (best candidates for deletion)
        
        Args:
            count: Total number of emails to download
            batch_size: Number of emails to process per batch
            
        Returns:
            Sync results summary
        """
        print(f"🚀 Starting sync of {count:,} oldest emails")
        print(f"📦 Batch size: {batch_size}")
        print("=" * 60)
        
        # Build query for oldest emails - start with emails older than 2020
        query = "before:2020/01/01"
        
        return self._sync_emails_with_query(
            query=query,
            count=count,
            batch_size=batch_size,
            strategy="oldest_first"
        )
    
    def sync_recent_emails(self, days_back: int = 7, batch_size: int = 100) -> Dict[str, Any]:
        """
        Download recent emails
        
        Args:
            days_back: Number of days back to sync
            batch_size: Number of emails to process per batch
            
        Returns:
            Sync results summary
        """
        print(f"🚀 Starting sync of emails from last {days_back} days")
        print(f"📦 Batch size: {batch_size}")
        print("=" * 60)
        
        # Build query for recent emails
        query = f"newer_than:{days_back}d"
        
        return self._sync_emails_with_query(
            query=query,
            count=None,  # Download all recent emails
            batch_size=batch_size,
            strategy="recent"
        )
    
    def _sync_emails_with_query(self, query: str, count: Optional[int], 
                               batch_size: int, strategy: str) -> Dict[str, Any]:
        """
        Core email syncing logic with Gmail query
        
        Args:
            query: Gmail search query
            count: Maximum emails to download (None for all)
            batch_size: Batch size for processing
            strategy: Sync strategy name
            
        Returns:
            Sync results summary
        """
        start_time = time.time()
        emails_downloaded = 0
        emails_failed = 0
        emails_skipped = 0  # Already exist in database
        page_token = None
        
        print(f"🔍 Gmail query: '{query}'")
        
        while True:
            # Get batch of message IDs
            print(f"\n📋 Fetching message list (batch {emails_downloaded//batch_size + 1})...")
            
            message_list = self.gmail.list_messages(
                query=query,
                max_results=batch_size,
                page_token=page_token
            )
            
            if not message_list['success']:
                print(f"❌ Failed to list messages: {message_list['error']}")
                break
            
            messages = message_list['messages']
            if not messages:
                print("✅ No more messages to process")
                break
            
            print(f"📧 Processing {len(messages)} emails...")
            
            # Download and process each email in this batch
            batch_success = 0
            batch_failed = 0
            batch_skipped = 0
            
            for i, message_info in enumerate(messages):
                try:
                    # Show progress every 10 emails
                    if (i + 1) % 10 == 0:
                        print(f"   📥 Processing email {i + 1}/{len(messages)}...")
                    
                    # Check if we already have this email
                    message_id = message_info['id']
                    if self._email_exists(message_id):
                        batch_skipped += 1
                        continue
                    
                    # Download full message
                    message_result = self.gmail.get_message(message_id)
                    
                    if not message_result['success']:
                        print(f"   ❌ Failed to get message {message_id}: {message_result['error']}")
                        batch_failed += 1
                        continue
                    
                    # Parse and store email
                    email_data = self._parse_gmail_message(message_result['message'])
                    
                    if email_data:
                        self.db.insert_email(email_data)
                        batch_success += 1
                    else:
                        batch_failed += 1
                    
                    # Rate limiting - pause between requests
                    time.sleep(0.1)  # 100ms between API calls
                    
                except Exception as e:
                    print(f"   ❌ Error processing message {message_info['id']}: {e}")
                    batch_failed += 1
                    continue
            
            emails_downloaded += batch_success
            emails_failed += batch_failed
            emails_skipped += batch_skipped
            
            print(f"✅ Batch complete: {batch_success} downloaded, {batch_failed} failed, {batch_skipped} skipped")
            print(f"📊 Total progress: {emails_downloaded:,} downloaded, {emails_failed} failed, {emails_skipped} skipped")
            
            # Check if we've reached our target count
            if count and emails_downloaded >= count:
                print(f"🎯 Reached target count of {count:,} emails")
                break
            
            # Check if there are more pages
            page_token = message_list.get('next_page_token')
            if not page_token:
                print("✅ Reached end of email list")
                break
            
            # Brief pause between batches
            time.sleep(1)
        
        end_time = time.time()
        duration_minutes = (end_time - start_time) / 60
        
        print(f"\n🎉 Sync completed!")
        print(f"📈 Results:")
        print(f"   Emails downloaded: {emails_downloaded:,}")
        print(f"   Emails failed: {emails_failed}")
        print(f"   Emails skipped (existing): {emails_skipped}")
        print(f"   Duration: {duration_minutes:.1f} minutes")
        if duration_minutes > 0:
            print(f"   Rate: {emails_downloaded/duration_minutes:.1f} emails/minute")
        
        return {
            'success': True,
            'strategy': strategy,
            'emails_downloaded': emails_downloaded,
            'emails_failed': emails_failed,
            'emails_skipped': emails_skipped,
            'duration_minutes': duration_minutes,
            'rate_per_minute': emails_downloaded/duration_minutes if duration_minutes > 0 else 0
        }
    
    def _email_exists(self, message_id: str) -> bool:
        """Check if email already exists in database"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM emails WHERE message_id = %s", (message_id,))
                return cursor.fetchone() is not None
        except Exception:
            return False
    
    def _parse_gmail_message(self, gmail_message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse Gmail API message into database format
        
        Args:
            gmail_message: Raw Gmail API message
            
        Returns:
            Parsed email data for database insertion
        """
        try:
            message_id = gmail_message['id']
            thread_id = gmail_message.get('threadId')
            
            # Extract headers
            headers = {}
            payload = gmail_message.get('payload', {})
            
            for header in payload.get('headers', []):
                headers[header['name']] = header['value']
            
            # Extract basic info from headers
            subject = headers.get('Subject', '')
            sender = headers.get('From', '')
            recipient = headers.get('To', '')
            date_header = headers.get('Date', '')
            
            # Parse sender email and name
            sender_email, sender_name = self._parse_sender(sender)
            
            # Parse date with fallbacks
            date_sent = self._parse_date_with_fallbacks(date_header, headers, gmail_message)
            
            # Extract body content
            body_text, body_html = self._extract_body(payload)
            
            # Extract snippet
            snippet = gmail_message.get('snippet', '')
            
            # Extract labels
            labels = gmail_message.get('labelIds', [])
            
            # Check for attachments
            has_attachments = self._has_attachments(payload)
            attachment_count = self._count_attachments(payload)
            
            # Size estimate
            size_estimate = gmail_message.get('sizeEstimate', 0)
            
            # Determine read status and importance
            is_unread = 'UNREAD' in labels
            is_important = 'IMPORTANT' in labels
            
            return {
                'message_id': message_id,
                'thread_id': thread_id,
                'subject': subject,
                'sender': sender,
                'sender_email': sender_email,
                'sender_name': sender_name,
                'recipient': recipient,
                'date_sent': date_sent,
                'date_received': datetime.now(timezone.utc),
                'body_text': body_text,
                'body_html': body_html,
                'snippet': snippet,
                'headers': json.dumps(headers),
                'labels': labels,
                'has_attachments': has_attachments,
                'attachment_count': attachment_count,
                'size_estimate_bytes': size_estimate,
                'gmail_labels': json.dumps(labels),
                'is_unread': is_unread,
                'is_important': is_important,
                'raw_gmail_data': json.dumps(gmail_message)
            }
            
        except Exception as e:
            print(f"   ⚠️ Error parsing message: {e}")
            return None
    
    def _parse_sender(self, sender: str) -> Tuple[str, str]:
        """
        Parse sender string into email and name components
        
        Args:
            sender: Raw sender string (e.g., "John Doe <john@example.com>")
            
        Returns:
            Tuple of (email, name)
        """
        if not sender:
            return '', ''
        
        # Try to extract email from angle brackets
        email_match = re.search(r'<([^>]+)>', sender)
        if email_match:
            email_addr = email_match.group(1)
            name = sender.replace(f'<{email_addr}>', '').strip().strip('"\'')
            return email_addr, name
        
        # If no angle brackets, assume the whole thing is an email
        if '@' in sender:
            return sender.strip(), ''
        
        return '', sender.strip()
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse email date string to datetime
        
        Args:
            date_str: Date string from email header
            
        Returns:
            Parsed datetime or None
        """
        try:
            if date_str:
                return parsedate_to_datetime(date_str)
        except Exception:
            pass
        return None
    
    def _parse_date_with_fallbacks(self, date_header: str, headers: Dict[str, str], 
                                  gmail_message: Dict[str, Any]) -> Optional[datetime]:
        """
        Parse email date with multiple fallback options
        
        Args:
            date_header: Primary Date header
            headers: All email headers
            gmail_message: Full Gmail message data
            
        Returns:
            Parsed datetime or None
        """
        # Try 1: Standard Date header
        if date_header:
            parsed = self._parse_date(date_header)
            if parsed:
                return parsed
        
        # Try 2: Received header (often more reliable)
        received_header = headers.get('Received', '')
        if received_header:
            # Received headers often have format: "...date_info"
            # Extract the last part which usually has the date
            try:
                # Look for date pattern in Received header
                import re
                date_match = re.search(r'([A-Za-z]{3},\s+\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\s+\d{2}:\d{2}:\d{2}\s+[+-]\d{4})', received_header)
                if date_match:
                    parsed = self._parse_date(date_match.group(1))
                    if parsed:
                        return parsed
            except Exception:
                pass
        
        # Try 3: Gmail's internalDate (Unix timestamp in milliseconds)
        internal_date = gmail_message.get('internalDate')
        if internal_date:
            try:
                # Convert milliseconds to seconds
                timestamp = int(internal_date) / 1000
                return datetime.fromtimestamp(timestamp, tz=timezone.utc)
            except Exception:
                pass
        
        # Try 4: Any other date-like headers
        for header_name, header_value in headers.items():
            if 'date' in header_name.lower() and header_value:
                parsed = self._parse_date(header_value)
                if parsed:
                    return parsed
        
        print(f"   ⚠️ Could not parse any date for email")
        return None
        """
        Parse email date string to datetime
        
        Args:
            date_str: Date string from email header
            
        Returns:
            Parsed datetime or None
        """
        try:
            if date_str:
                return parsedate_to_datetime(date_str)
        except Exception:
            pass
        return None
    
    def _extract_body(self, payload: Dict[str, Any]) -> Tuple[str, str]:
        """
        Extract text and HTML body from Gmail payload
        
        Args:
            payload: Gmail message payload
            
        Returns:
            Tuple of (text_body, html_body)
        """
        text_body = ''
        html_body = ''
        
        def extract_from_part(part):
            nonlocal text_body, html_body
            
            mime_type = part.get('mimeType', '')
            
            if mime_type == 'text/plain':
                data = part.get('body', {}).get('data')
                if data:
                    try:
                        text_body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    except Exception:
                        pass
            
            elif mime_type == 'text/html':
                data = part.get('body', {}).get('data')
                if data:
                    try:
                        html_body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    except Exception:
                        pass
            
            # Recursively process parts
            for subpart in part.get('parts', []):
                extract_from_part(subpart)
        
        extract_from_part(payload)
        
        return text_body, html_body
    
    def _has_attachments(self, payload: Dict[str, Any]) -> bool:
        """Check if message has attachments"""
        def check_part(part):
            if part.get('filename'):
                return True
            for subpart in part.get('parts', []):
                if check_part(subpart):
                    return True
            return False
        
        return check_part(payload)
    
    def _count_attachments(self, payload: Dict[str, Any]) -> int:
        """Count number of attachments"""
        count = 0
        
        def count_part(part):
            nonlocal count
            if part.get('filename'):
                count += 1
            for subpart in part.get('parts', []):
                count_part(subpart)
        
        count_part(payload)
        return count

# Convenience functions
def create_email_syncer() -> EmailSyncer:
    """Create and return email syncer instance"""
    return EmailSyncer()

def quick_sync_test(count: int = 10) -> bool:
    """Quick test sync of a few emails"""
    try:
        syncer = EmailSyncer()
        result = syncer.sync_oldest_emails(count=count, batch_size=min(count, 10))
        return result['success']
    except Exception as e:
        print(f"❌ Quick sync test failed: {e}")
        return False

# Example usage and testing
if __name__ == "__main__":
    """Test the email syncer"""
    
    print("📧 Testing Email Syncer")
    print("=" * 50)
    
    try:
        # Quick test with 5 emails
        print("🧪 Running quick sync test...")
        success = quick_sync_test(count=5)
        
        if success:
            print("🎉 Email syncer test completed successfully!")
        else:
            print("❌ Email syncer test failed")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
