#!/usr/bin/env python3
"""
Marin Email Manager - CLI Interface
Clean, modular command dispatcher following Unix philosophy.
One job: route commands to appropriate handlers.
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.gmail_client import GmailClient, test_gmail_connection
from core.database import MarinDatabase, initialize_database
from core.email_syncer import EmailSyncer, quick_sync_test
from utils.config import MarinConfig, validate_setup

# Import command modules
from cli.archive_commands import cmd_sync_archive, cmd_sync_progress, cmd_sync_year

def cmd_test_gmail(args):
    """Test Gmail API connection"""
    print("📧 Testing Gmail API Connection")
    print("=" * 40)
    
    try:
        success = test_gmail_connection()
        return 0 if success else 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

def cmd_test_database(args):
    """Test database connection and setup"""
    print("🗄️ Testing Database Connection")
    print("=" * 40)
    
    try:
        db = MarinDatabase()
        print("✅ Database connection successful")
        
        if args.init:
            print("\n📋 Initializing database tables...")
            db.create_tables()
        
        stats = db.get_database_stats()
        print(f"\n📊 Database Statistics:")
        print(f"   Total emails: {stats['total_emails']:,}")
        print(f"   Analyzed emails: {stats['analyzed_emails']:,}")
        
        if stats['total_emails'] == 0:
            print("\nℹ️  Database is empty. Use 'marin sync-oldest' to download emails.")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Database error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure PostgreSQL is running")
        print("2. Create database: createdb marin_emails")
        print("3. Check DATABASE_URL in config/.env")
        return 1

def cmd_setup(args):
    """Setup and validate Marin configuration"""
    print("🔧 Marin Setup and Validation")
    print("=" * 40)
    
    config = MarinConfig()
    
    # Create .env template if it doesn't exist
    env_example = config.config_dir / '.env.example'
    if not env_example.exists():
        config.create_env_template()
    
    is_valid = validate_setup()
    
    print(f"\n📁 Configuration:")
    print(f"   Config directory: {config.config_dir}")
    print(f"   Data directory: {config.data_dir}")
    print(f"   Database URL: {config.database_url}")
    print(f"   Default AI model: {config.default_ai_model}")
    
    print(f"\n📂 Required files:")
    print(f"   Credentials: {'✅' if Path(config.credentials_path).exists() else '❌'} {config.credentials_path}")
    print(f"   Token: {'✅' if Path(config.token_path).exists() else '➖'} {config.token_path} (auto-generated)")
    
    if not is_valid:
        print(f"\n❌ Setup incomplete!")
        print(f"\nNext steps:")
        print(f"1. Download Gmail OAuth credentials from Google Cloud Console")
        print(f"2. Save as: {config.credentials_path}")
        print(f"3. Run: marin test-gmail")
        return 1
    else:
        print(f"\n✅ Setup is complete!")
        return 0

def cmd_config(args):
    """Show current configuration"""
    print("⚙️ Marin Configuration")
    print("=" * 40)
    
    config = MarinConfig()
    
    print(f"🗄️ Database:")
    print(f"   URL: {config.database_url}")
    
    print(f"\n🤖 AI Models:")
    print(f"   Default: {config.default_ai_model}")
    print(f"   Fast: {config.fast_ai_model}")
    print(f"   Comprehensive: {config.comprehensive_ai_model}")
    print(f"   Ollama URL: {config.ollama_url}")
    
    print(f"\n⚙️ Processing:")
    print(f"   Batch size: {config.default_batch_size}")
    print(f"   Safety mode: {config.safety_mode}")
    print(f"   Adaptive learning: {config.adaptive_learning_enabled}")
    
    deletion_criteria = config.get_deletion_criteria()
    print(f"\n🗑️ Deletion Criteria:")
    print(f"   Safe categories: {', '.join(deletion_criteria['safe_categories'])}")
    print(f"   Preserve categories: {', '.join(deletion_criteria['preserve_categories'])}")
    print(f"   Min age (days): {deletion_criteria['min_age_days']}")
    print(f"   Preview mode: {deletion_criteria['preview_mode']}")
    
    return 0

def cmd_stats(args):
    """Show database statistics"""
    print("📊 Database Statistics")
    print("=" * 40)
    
    try:
        db = MarinDatabase()
        stats = db.get_database_stats()
        
        print(f"📧 Emails:")
        print(f"   Total: {stats['total_emails']:,}")
        print(f"   Analyzed: {stats['analyzed_emails']:,}")
        print(f"   Analysis coverage: {stats['analysis_coverage']}%")
        
        if stats['date_range']['oldest']:
            print(f"   Date range: {stats['date_range']['oldest'][:10]} to {stats['date_range']['newest'][:10]}")
        
        print(f"\n🗑️ Cleanup:")
        print(f"   Deletion candidates: {stats['deletion_candidates']:,}")
        
        if stats['categories']:
            print(f"\n📂 Categories:")
            for category, count in stats['categories'].items():
                print(f"   {category}: {count:,} emails")
        
        if stats['total_emails'] == 0:
            print(f"\nℹ️  Database is empty. Use 'marin sync-oldest' to download emails.")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error getting stats: {e}")
        return 1

def cmd_test_all(args):
    """Run all tests"""
    print("🧪 Running All Tests")
    print("=" * 40)
    
    tests = [
        ("Configuration", lambda: validate_setup()),
        ("Database", lambda: cmd_test_database(args) == 0),
        ("Gmail API", lambda: test_gmail_connection())
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🔍 Testing {test_name}...")
        try:
            success = test_func()
            results.append((test_name, success))
            print(f"   {'✅' if success else '❌'} {test_name}")
        except Exception as e:
            results.append((test_name, False))
            print(f"   ❌ {test_name}: {e}")
    
    print(f"\n📋 Test Summary:")
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        print(f"   {'✅' if success else '❌'} {test_name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Marin is ready to use.")
        return 0
    else:
        print("❌ Some tests failed. Check configuration and setup.")
        return 1

def cmd_sync_oldest(args):
    """Sync oldest emails (best deletion candidates)"""
    print("📧 Syncing Oldest Emails")
    print("=" * 40)
    
    try:
        syncer = EmailSyncer()
        result = syncer.sync_oldest_emails(
            count=args.count,
            batch_size=args.batch_size
        )
        
        if result['success']:
            print(f"\n🎉 Sync completed successfully!")
            print(f"📈 Downloaded {result['emails_downloaded']:,} emails in {result['duration_minutes']:.1f} minutes")
            return 0
        else:
            return 1
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

def cmd_sync_recent(args):
    """Sync recent emails"""
    print("📧 Syncing Recent Emails")
    print("=" * 40)
    
    try:
        syncer = EmailSyncer()
        result = syncer.sync_recent_emails(
            days_back=args.days,
            batch_size=args.batch_size
        )
        
        if result['success']:
            print(f"\n🎉 Sync completed successfully!")
            print(f"📈 Downloaded {result['emails_downloaded']:,} emails in {result['duration_minutes']:.1f} minutes")
            return 0
        else:
            return 1
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

def cmd_sync_by_year(args):
    """Sync emails from a specific year"""
    print(f"📧 Syncing Emails from {args.year}")
    print("=" * 40)
    
    try:
        syncer = EmailSyncer()
        
        # Build query for specific year
        query = f"after:{args.year}/01/01 before:{args.year + 1}/01/01"
        
        result = syncer._sync_emails_with_query(
            query=query,
            count=args.count,
            batch_size=args.batch_size,
            strategy=f"year_{args.year}"
        )
        
        if result['success']:
            print(f"\n🎉 Sync completed successfully!")
            print(f"📈 Downloaded {result['emails_downloaded']:,} emails from {args.year}")
            return 0
        else:
            return 1
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

def cmd_quick_test(args):
    """Quick test with a few emails"""
    print("🧪 Quick Email Sync Test")
    print("=" * 40)
    
    try:
        success = quick_sync_test(count=args.count)
        return 0 if success else 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

def create_parser():
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description='Marin Email Manager - AI-powered email liberation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  marin setup                          # Setup and validate configuration
  marin test-all                       # Run all connection tests
  marin quick-test --count=10          # Test with 10 emails
  marin sync-oldest --count=1000       # Download 1000 oldest emails
  marin sync-archive --max-per-session=5000  # Systematic archive download
  marin sync-progress                  # Show download progress
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Setup and config commands
    subparsers.add_parser('setup', help='Setup and validate configuration')
    subparsers.add_parser('config', help='Show current configuration')
    
    # Test commands
    subparsers.add_parser('test-gmail', help='Test Gmail API connection')
    test_db_parser = subparsers.add_parser('test-database', help='Test database connection')
    test_db_parser.add_argument('--init', action='store_true', help='Initialize database tables')
    subparsers.add_parser('test-all', help='Run all tests')
    
    # Stats
    subparsers.add_parser('stats', help='Show database statistics')
    
    # Basic sync commands
    sync_oldest_parser = subparsers.add_parser('sync-oldest', help='Download oldest emails (best deletion candidates)')
    sync_oldest_parser.add_argument('--count', type=int, default=1000, help='Number of emails to download (default: 1000)')
    sync_oldest_parser.add_argument('--batch-size', type=int, default=100, help='Batch size for processing (default: 100)')
    
    sync_recent_parser = subparsers.add_parser('sync-recent', help='Download recent emails')
    sync_recent_parser.add_argument('--days', type=int, default=7, help='Number of days back to sync (default: 7)')
    sync_recent_parser.add_argument('--batch-size', type=int, default=100, help='Batch size for processing (default: 100)')
    
    sync_year_parser = subparsers.add_parser('sync-by-year', help='Download emails from specific year')
    sync_year_parser.add_argument('year', type=int, help='Year to download (e.g., 2020)')
    sync_year_parser.add_argument('--count', type=int, default=None, help='Max emails to download (default: all)')
    sync_year_parser.add_argument('--batch-size', type=int, default=100, help='Batch size for processing (default: 100)')
    
    # Archive management commands
    sync_archive_parser = subparsers.add_parser('sync-archive', help='Download email archive year by year')
    sync_archive_parser.add_argument('--session-limit', type=int, default=50000, help='Max emails per session (default: 50000)')
    
    subparsers.add_parser('sync-progress', help='Show archive download progress')
    
    sync_year_parser = subparsers.add_parser('sync-year', help='Download all emails before specific year')
    sync_year_parser.add_argument('year', type=int, help='Year boundary (download emails before this year)')
    
    sync_date_range_parser = subparsers.add_parser('sync-date-range', help='Download emails from specific date range')
    sync_date_range_parser.add_argument('start_date', help='Start date (YYYY/MM/DD format)')
    sync_date_range_parser.add_argument('end_date', help='End date (YYYY/MM/DD format)')
    sync_date_range_parser.add_argument('--chunk-size', type=int, default=5000, help='Emails per chunk (default: 5000)')
    
    # Quick test
    quick_test_parser = subparsers.add_parser('quick-test', help='Quick test with a few emails')
    quick_test_parser.add_argument('--count', type=int, default=5, help='Number of emails to test with (default: 5)')
    
    return parser

def main():
    """Main CLI entry point"""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Command mapping
    commands = {
        'setup': cmd_setup,
        'config': cmd_config,
        'test-gmail': cmd_test_gmail,
        'test-database': cmd_test_database,
        'test-all': cmd_test_all,
        'stats': cmd_stats,
        'sync-oldest': cmd_sync_oldest,
        'sync-recent': cmd_sync_recent,
        'sync-by-year': cmd_sync_by_year,
        'sync-archive': cmd_sync_archive,
        'sync-progress': cmd_sync_progress,
        'sync-year': cmd_sync_year,
        'quick-test': cmd_quick_test
    }
    
    if args.command in commands:
        try:
            return commands[args.command](args)
        except KeyboardInterrupt:
            print("\n⏹️ Operation cancelled by user")
            return 130
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return 1
    else:
        print(f"❌ Unknown command: {args.command}")
        parser.print_help()
        return 1

if __name__ == "__main__":
    sys.exit(main())