#!/usr/bin/env python3
"""
Marin Email Manager - CLI Interface
Basic commands for testing and initial setup
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.gmail_client import GmailClient, test_gmail_connection
from core.database import MarinDatabase, initialize_database
from utils.config import MarinConfig, validate_setup

def cmd_test_gmail(args):
    """Test Gmail API connection"""
    print("📧 Testing Gmail API Connection")
    print("=" * 40)
    
    try:
        success = test_gmail_connection()
        if success:
            print("\n✅ Gmail connection test passed!")
            return 0
        else:
            print("\n❌ Gmail connection test failed!")
            return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

def cmd_test_database(args):
    """Test database connection and setup"""
    print("🗄️ Testing Database Connection")
    print("=" * 40)
    
    try:
        # Test basic connection
        db = MarinDatabase()
        print("✅ Database connection successful")
        
        # Initialize tables if needed
        if args.init:
            print("\n📋 Initializing database tables...")
            db.create_tables()
            print("✅ Database tables created")
        
        # Show stats
        print("\n📊 Database Statistics:")
        stats = db.get_database_stats()
        print(f"   Total emails: {stats['total_emails']:,}")
        print(f"   Analyzed emails: {stats['analyzed_emails']:,}")
        
        if stats['total_emails'] == 0:
            print("\nℹ️  Database is empty. Use 'marin sync' to download emails.")
        
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
    
    # Initialize configuration
    config = MarinConfig()
    
    # Create .env template if it doesn't exist
    env_example = config.config_dir / '.env.example'
    if not env_example.exists():
        config.create_env_template()
    
    # Validate configuration
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
    
    print(f"\n📂 Directories:")
    print(f"   Config: {config.config_dir}")
    print(f"   Data: {config.data_dir}")
    print(f"   Attachments: {config.attachments_dir}")
    print(f"   Exports: {config.exports_dir}")
    print(f"   Logs: {config.logs_dir}")
    
    # Show deletion criteria
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

def create_parser():
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description='Marin Email Manager - AI-powered email liberation',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Setup command
    setup_parser = subparsers.add_parser('setup', help='Setup and validate configuration')
    
    # Config command  
    config_parser = subparsers.add_parser('config', help='Show current configuration')
    
    # Test commands
    test_gmail_parser = subparsers.add_parser('test-gmail', help='Test Gmail API connection')
    
    test_db_parser = subparsers.add_parser('test-database', help='Test database connection')
    test_db_parser.add_argument('--init', action='store_true', help='Initialize database tables')
    
    test_all_parser = subparsers.add_parser('test-all', help='Run all tests')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show database statistics')
    
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
        'stats': cmd_stats
    }
    
    if args.command in commands:
        try:
            return commands[args.command](args)
        except KeyboardInterrupt:
            print("\n⏹️ Operation cancelled by user")
            return 130
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return 1
    else:
        print(f"❌ Unknown command: {args.command}")
        parser.print_help()
        return 1

if __name__ == "__main__":
    sys.exit(main())
