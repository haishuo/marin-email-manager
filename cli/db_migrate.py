#!/usr/bin/env python3
"""
Marin Database Migration CLI
One job: handle all database schema migrations and upgrades.
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database_migration import DatabaseMigration, apply_learning_migration, check_learning_system_status
from core.database import initialize_database

def cmd_apply_learning_migration(args):
    """Apply learning system database schema updates"""
    print("🗄️ Applying Learning System Migration")
    print("=" * 40)
    
    try:
        success = apply_learning_migration()
        return 0 if success else 1
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return 1

def cmd_check_migration_status(args):
    """Check current migration and learning system status"""
    print("📊 Database Migration Status")
    print("=" * 40)
    
    try:
        check_learning_system_status()
        return 0
    except Exception as e:
        print(f"❌ Status check failed: {e}")
        return 1

def cmd_initialize_base_tables(args):
    """Initialize base Marin database tables"""
    print("🏗️ Initializing Base Database Tables")
    print("=" * 40)
    
    try:
        success = initialize_database()
        if success:
            print("✅ Base tables initialized successfully")
            return 0
        else:
            print("❌ Base table initialization failed")
            return 1
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return 1

def cmd_full_migration(args):
    """Run complete database setup (base + learning)"""
    print("🚀 Full Database Migration")
    print("=" * 40)
    
    try:
        # Step 1: Initialize base tables
        print("Step 1: Initializing base tables...")
        base_success = initialize_database()
        if not base_success:
            print("❌ Base table initialization failed")
            return 1
        
        print("✅ Base tables ready")
        
        # Step 2: Apply learning system migration
        print("\nStep 2: Applying learning system updates...")
        learning_success = apply_learning_migration()
        if not learning_success:
            print("❌ Learning system migration failed")
            return 1
        
        print("✅ Learning system ready")
        
        # Step 3: Verify everything
        print("\nStep 3: Verifying migration...")
        check_learning_system_status()
        
        print("\n🎉 Full database migration completed successfully!")
        return 0
        
    except Exception as e:
        print(f"❌ Full migration failed: {e}")
        return 1

def cmd_verify_migration(args):
    """Verify that all database tables and schema are correct"""
    print("🔍 Verifying Database Schema")
    print("=" * 40)
    
    try:
        migration = DatabaseMigration()
        
        # Get learning system status
        status = migration.get_learning_system_status()
        
        if 'error' in status:
            print(f"❌ Learning system verification failed: {status['error']}")
            return 1
        
        # Check base tables exist
        from core.database import MarinDatabase
        db = MarinDatabase()
        base_stats = db.get_database_stats()
        
        print("✅ Database Schema Verification")
        print(f"   Base tables: OK")
        print(f"   Learning tables: OK")
        print(f"   Total emails: {base_stats['total_emails']:,}")
        print(f"   Learning progress: {status['learning_progress']['total_classifications']:,} classifications")
        print(f"   Active rules: {status['active_rules']:,}")
        print(f"   Training batches: {status['training_batches']:,}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return 1

def create_parser():
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description='Marin Database Migration Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m cli.db_migrate full-migration     # Complete database setup
  python -m cli.db_migrate apply-learning     # Apply learning system updates
  python -m cli.db_migrate status             # Check migration status
  python -m cli.db_migrate verify             # Verify schema integrity
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Full migration
    subparsers.add_parser('full-migration', help='Run complete database setup (base + learning)')
    
    # Individual migrations
    subparsers.add_parser('init-base', help='Initialize base Marin database tables')
    subparsers.add_parser('apply-learning', help='Apply learning system schema updates')
    
    # Status and verification
    subparsers.add_parser('status', help='Check current migration and learning system status')
    subparsers.add_parser('verify', help='Verify database schema integrity')
    
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
        'full-migration': cmd_full_migration,
        'init-base': cmd_initialize_base_tables,
        'apply-learning': cmd_apply_learning_migration,
        'status': cmd_check_migration_status,
        'verify': cmd_verify_migration
    }
    
    if args.command in commands:
        try:
            return commands[args.command](args)
        except KeyboardInterrupt:
            print("\n⏹️ Migration cancelled by user")
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
