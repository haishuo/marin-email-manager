# cli/archive_commands.py
"""
CLI commands for realistic email archive management.
One job: handle archive commands that work with Gmail's reality.
"""

from core.email_archive_manager import EmailArchiveManager

def cmd_sync_archive(args):
    """Download email archive by moving forward through time"""
    print("🏛️ Complete Archive Download")
    print("=" * 40)
    
    try:
        manager = EmailArchiveManager()
        
        # Show current status
        progress = manager.get_sync_progress()
        current_total = progress.get('total_emails_downloaded', 0)
        
        if current_total > 0:
            print(f"📊 Current Status:")
            print(f"   Total emails: {current_total:,}")
            if progress['date_range']['earliest']:
                earliest = progress['date_range']['earliest'][:10]
                latest = progress['date_range']['latest'][:10]
                print(f"   Date range: {earliest} to {latest}")
            print(f"   Next year to process: {progress.get('next_year_to_process', 'TBD')}")
            print()
        
        # Show session plan
        session_limit = args.session_limit
        print(f"📈 This Session:")
        print(f"   Will download whatever Gmail gives us (up to {session_limit:,} emails)")
        print(f"   Strategy: Year-by-year, all emails per year")
        print()
        
        # Start the download
        result = manager.sync_complete_archive(
            max_emails_per_session=session_limit
        )
        
        if result['success']:
            print(f"🎉 Session completed!")
            print(f"📈 Downloaded {result['total_downloaded']:,} emails from {result['years_processed']} year periods")
            
            # Show updated status
            new_progress = manager.get_sync_progress()
            new_total = new_progress.get('total_emails_downloaded', 0)
            
            print(f"📊 Updated Status:")
            print(f"   Total emails: {new_total:,}")
            if new_progress['date_range']['earliest']:
                earliest = new_progress['date_range']['earliest'][:10]
                latest = new_progress['date_range']['latest'][:10]
                print(f"   Date range: {earliest} to {latest}")
            
            next_year = new_progress.get('next_year_to_process')
            if next_year and next_year <= datetime.now().year:
                print(f"   Next: Will process {next_year} in next session")
            else:
                print(f"   🎉 Archive download appears complete!")
            
            return 0
        else:
            print(f"❌ Session failed")
            return 1
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

def cmd_sync_progress(args):
    """Show email archive download progress"""
    print("📊 Email Archive Progress")
    print("=" * 40)
    
    try:
        manager = EmailArchiveManager()
        progress = manager.get_sync_progress()
        
        if 'error' in progress:
            print(f"❌ Error: {progress['error']}")
            return 1
        
        total_downloaded = progress.get('total_emails_downloaded', 0)
        
        if total_downloaded == 0:
            print(f"📭 No emails downloaded yet")
            print(f"   Next: Will start from Gmail's beginning (2004)")
            return 0
        
        print(f"📧 Archive Status:")
        print(f"   Total emails: {total_downloaded:,}")
        
        if progress.get('date_range', {}).get('earliest'):
            earliest = progress['date_range']['earliest'][:10]
            latest = progress['date_range']['latest'][:10]
            print(f"   Date range: {earliest} to {latest}")
        
        next_year = progress.get('next_year_to_process')
        if next_year:
            current_year = datetime.now().year
            if next_year <= current_year:
                print(f"   Next: Will process year {next_year}")
            else:
                print(f"   🎉 Archive appears complete (up to {current_year})")
        
        print(f"   Years with data: {progress.get('years_with_data', 0)}")
        
        # Show year breakdown
        if progress.get('year_breakdown'):
            print(f"\n📅 Year-by-Year Breakdown:")
            for year_info in progress['year_breakdown']:
                year = year_info['year']
                count = year_info['count']
                print(f"   {year}: {count:,} emails")
        
        # Estimate remaining work
        target = 127852  # Your Gmail total
        if total_downloaded < target:
            estimate = manager.estimate_remaining_time(target)
            remaining = estimate['remaining_emails']
            print(f"\n⏱️ Estimate to Complete:")
            print(f"   Remaining: ~{remaining:,} emails")
            print(f"   Progress: {estimate['completion_percentage']:.1f}%")
            print(f"   Estimated time: ~{estimate['estimated_hours']:.1f} hours")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

def cmd_sync_year(args):
    """Download all emails from a specific year"""
    print(f"📅 Download All Emails Before {args.year}")
    print("=" * 40)
    
    try:
        manager = EmailArchiveManager()
        
        # Download everything before this year
        result = manager._download_all_emails_before_year(args.year)
        
        if result['success']:
            print(f"\n🎉 Download completed!")
            print(f"📈 Downloaded {result['emails_downloaded']:,} emails before {args.year}")
            
            # Show what we got
            date_range = manager._get_latest_chunk_date_range()
            if date_range['oldest']:
                print(f"📅 Date range: {date_range['oldest']} to {date_range['newest']}")
            
            return 0
        else:
            print(f"\n❌ Download failed")
            return 1
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

# Import needed for datetime
from datetime import datetime
