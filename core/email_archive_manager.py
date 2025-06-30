# core/email_archive_manager.py
"""
Chronological email archive management that works with Gmail's reality.
Downloads all emails before progressively later dates, however many exist.
One job: get all emails in chronological chunks that Gmail actually gives us.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from core.email_syncer import EmailSyncer
from core.database import MarinDatabase

class EmailArchiveManager:
    """Downloads entire email archive by progressively moving forward through time"""
    
    def __init__(self, syncer: Optional[EmailSyncer] = None, 
                 database: Optional[MarinDatabase] = None):
        """Initialize archive manager"""
        self.syncer = syncer or EmailSyncer()
        self.db = database or MarinDatabase()
    
    def sync_complete_archive(self, max_emails_per_session: int = 50000) -> Dict[str, Any]:
        """
        Download entire email archive by moving forward through time
        
        Args:
            max_emails_per_session: Stop after this many emails (safety limit)
            
        Returns:
            Sync results summary
        """
        print(f"🏛️ Complete Archive Download (Gmail's Way)")
        print(f"🛡️ Session limit: {max_emails_per_session:,} emails")
        print("=" * 60)
        
        total_downloaded = 0
        year_number = 1
        
        # Check if database is empty (first run)
        is_first_run = self._is_database_empty()
        
        if is_first_run:
            print(f"📭 Database is empty - finding first emails")
            # Find the first year that has emails
            first_boundary_year = self._find_first_year_with_emails()
            if first_boundary_year is None:
                print("❌ No emails found in Gmail!")
                return {'success': False, 'error': 'No emails found'}
            
            print(f"✅ Found first emails before {first_boundary_year}")
            print()
            
            # Download all emails before this boundary year
            print(f"📦 INITIAL DOWNLOAD")
            print("-" * 40)
            initial_result = self._download_all_emails_before_year(first_boundary_year)
            
            emails_downloaded = initial_result['emails_downloaded']
            if emails_downloaded > 0:
                date_range = self._get_latest_chunk_date_range()
                if date_range and date_range.get('oldest') and date_range.get('newest'):
                    print(f"   📅 Date range: {date_range['oldest']} to {date_range['newest']}")
                print(f"   📧 Downloaded: {emails_downloaded:,} emails")
                total_downloaded += emails_downloaded
            else:
                print(f"   📭 No emails found in initial download")
            
            print(f"   ✅ Initial download complete")
            print(f"   📊 Total: {total_downloaded:,} emails")
            print()
            
            # Now continue from the boundary year (which should have emails)
            start_year = first_boundary_year
        else:
            # Find where to continue
            start_year = self._find_next_year_to_process()
            print(f"📅 Continuing from year {start_year}")
            print()
        
        current_year = datetime.now().year
        
        # Process subsequent years with date ranges
        for year in range(start_year, current_year + 2):
            if total_downloaded >= max_emails_per_session:
                print(f"🛑 Reached session limit of {max_emails_per_session:,} emails")
                break
            
            print(f"📦 YEAR {year} (batch {year_number})")
            print("-" * 40)
            
            # Download emails from this specific year only
            try:
                year_result = self._download_emails_from_year(year)
            except Exception as e:
                print(f"   ❌ Error downloading from {year}: {e}")
                year_number += 1
                continue
            
            if not year_result or not isinstance(year_result, dict):
                print(f"   ❌ Invalid result from {year}")
                year_number += 1
                continue
            
            emails_in_year = year_result.get('emails_downloaded', 0)
            
            if emails_in_year == 0:
                print(f"   📭 No emails found in {year}")
                year_number += 1
                continue
            
            # Show what we actually got
            print(f"   📧 Downloaded: {emails_in_year:,} emails")
            
            # Try to show date range, but don't crash if it fails
            try:
                date_range = self._get_latest_chunk_date_range()
                if date_range and date_range.get('oldest') and date_range.get('newest'):
                    print(f"   📅 Date range: {date_range['oldest']} to {date_range['newest']}")
            except Exception as e:
                print(f"   ⚠️ Could not determine date range: {e}")
            
            total_downloaded += emails_in_year
            year_number += 1
            
            print(f"   ✅ Year {year} complete")
            print(f"   📊 Session total: {total_downloaded:,} emails")
            print()
        
        return {
            'success': True,
            'total_downloaded': total_downloaded,
            'years_processed': year_number - 1,
            'final_year': year - 1 if year > start_year else start_year
        }
    
    def _find_next_year_to_process(self) -> int:
        """Find the next year we need to process"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Count total emails and emails with dates
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_emails,
                        COUNT(date_sent) as emails_with_dates
                    FROM emails
                """)
                result = cursor.fetchone()
                total_emails = result[0] if result else 0
                emails_with_dates = result[1] if result else 0
                
                if total_emails == 0:
                    print("📭 Database is empty - starting from Gmail's beginning")
                    return 2004
                
                if emails_with_dates == 0:
                    print(f"⚠️ Found {total_emails} emails but none have valid dates - starting from 2004")
                    return 2004
                
                # Find the latest year we have emails for
                cursor.execute("""
                    SELECT EXTRACT(YEAR FROM MAX(date_sent))::integer
                    FROM emails 
                    WHERE date_sent IS NOT NULL
                """)
                
                result = cursor.fetchone()
                if result and result[0]:
                    latest_year = result[0]
                    next_year = latest_year + 1
                    print(f"📊 Latest emails in database: {latest_year} ({emails_with_dates} emails with dates)")
                    print(f"📅 Will continue from: {next_year}")
                    return next_year
                else:
                    print("⚠️ No dated emails found - starting from 2004")
                    return 2004
                    
        except Exception as e:
            print(f"⚠️ Error finding next year: {e}")
            return 2004
    
    def _is_database_empty(self) -> bool:
        """Check if we have any emails in the database"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM emails")
                count = cursor.fetchone()[0]
                return count == 0
        except Exception:
            return True
    
    def _find_first_year_with_emails(self) -> Optional[int]:
        """Find the first year that has emails by trying progressively later years"""
        print("   🔍 Searching for first emails...")
        
        for year in range(2004, datetime.now().year + 2):
            print(f"   📅 Checking for emails before {year}...")
            
            # Test query - just check if any emails exist
            query = f"before:{year}/01/01"
            try:
                result = self.syncer.gmail.list_messages(query=query, max_results=1)
                if result['success'] and result['messages']:
                    print(f"   ✅ Found emails before {year}")
                    # The emails are from BEFORE this year, so return the previous year
                    # But we need to download them with the "before" query we just used
                    return year
                else:
                    print(f"   📭 No emails before {year}")
            except Exception as e:
                print(f"   ❌ Error checking {year}: {e}")
                continue
        
        return None
    
    def _download_emails_from_year(self, year: int) -> Dict[str, Any]:
        """
        Download emails from a specific year only (not before)
        
        Args:
            year: The specific year to download
            
        Returns:
            Download results
        """
        # Create date range for just this year
        start_date = f"{year}/01/01"
        end_date = f"{year + 1}/01/01"
        query = f"after:{year - 1}/12/31 before:{end_date}"
        
        print(f"   🔍 Gmail query: '{query}' (year {year} only)")
        print(f"   📥 Downloading ALL emails from {year}, however many exist...")
        
        result = self.syncer._sync_emails_with_query(
            query=query,
            count=None,  # No limit - get them all
            batch_size=500,
            strategy=f"year_{year}_only"
        )
        
    def _download_all_emails_before_year(self, year: int) -> Dict[str, Any]:
        """
        Download ALL emails before the given year (used only for initial download)
        
        Args:
            year: Year boundary (get emails before this year)
            
        Returns:
            Download results
        """
        query = f"before:{year}/01/01"
        
        print(f"   🔍 Gmail query: '{query}' (initial download)")
        print(f"   📥 Downloading ALL emails before {year}, however many exist...")
        
        result = self.syncer._sync_emails_with_query(
            query=query,
            count=None,  # No limit - get them all
            batch_size=500,
            strategy=f"initial_before_{year}"
        )
        
        return result
    
    def _get_latest_chunk_date_range(self) -> Dict[str, Optional[str]]:
        """Get the date range of the most recently downloaded emails"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get date range from recent downloads
                cursor.execute("""
                    SELECT 
                        MIN(date_sent) as oldest,
                        MAX(date_sent) as newest
                    FROM (
                        SELECT date_sent 
                        FROM emails 
                        WHERE date_sent IS NOT NULL 
                        ORDER BY downloaded_at DESC 
                        LIMIT 5000
                    ) recent_emails
                """)
                
                result = cursor.fetchone()
                if result and result[0]:
                    oldest = result[0].strftime("%Y-%m-%d") if result[0] else None
                    newest = result[1].strftime("%Y-%m-%d") if result[1] else oldest
                    return {'oldest': oldest, 'newest': newest}
                else:
                    return {'oldest': None, 'newest': None}
                    
        except Exception as e:
            print(f"   ⚠️ Could not get date range: {e}")
            return {'oldest': None, 'newest': None}
    
    def get_sync_progress(self) -> Dict[str, Any]:
        """Get overview of archive download progress"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get total emails and date range
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_emails,
                        MIN(date_sent) as earliest,
                        MAX(date_sent) as latest
                    FROM emails 
                    WHERE date_sent IS NOT NULL
                """)
                
                result = cursor.fetchone()
                total_emails = result[0] if result else 0
                earliest = result[1] if result and result[1] else None
                latest = result[2] if result and result[2] else None
                
                # Get year-by-year breakdown
                cursor.execute("""
                    SELECT 
                        EXTRACT(YEAR FROM date_sent)::integer as year,
                        COUNT(*) as email_count
                    FROM emails 
                    WHERE date_sent IS NOT NULL
                    GROUP BY year
                    ORDER BY year ASC
                """)
                
                year_breakdown = []
                for row in cursor.fetchall():
                    year_breakdown.append({
                        'year': row[0],
                        'count': row[1]
                    })
                
                # Calculate next year to process
                next_year = self._find_next_year_to_process()
                
                return {
                    'total_emails_downloaded': total_emails,
                    'years_with_data': len(year_breakdown),
                    'year_breakdown': year_breakdown,
                    'date_range': {
                        'earliest': earliest.isoformat() if earliest else None,
                        'latest': latest.isoformat() if latest else None
                    },
                    'next_year_to_process': next_year
                }
                
        except Exception as e:
            return {'error': str(e)}
    
    def estimate_remaining_time(self, target_total: int, 
                               rate_per_minute: float = 300) -> Dict[str, Any]:
        """Estimate time to complete archive download"""
        progress = self.get_sync_progress()
        downloaded = progress.get('total_emails_downloaded', 0)
        remaining = max(0, target_total - downloaded)
        
        if remaining == 0:
            return {'completed': True, 'remaining_emails': 0}
        
        minutes = remaining / rate_per_minute
        hours = minutes / 60
        
        return {
            'completed': False,
            'remaining_emails': remaining,
            'downloaded_emails': downloaded,
            'completion_percentage': (downloaded / target_total) * 100,
            'estimated_minutes': round(minutes, 1),
            'estimated_hours': round(hours, 1),
            'rate_per_minute': rate_per_minute
        }

# Convenience functions
def create_archive_manager() -> EmailArchiveManager:
    """Create and return archive manager instance"""
    return EmailArchiveManager()
