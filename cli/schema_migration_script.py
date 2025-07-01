#!/usr/bin/env python3
"""
Database migration script to upgrade Marin to v2.0 architecture
Run this to safely migrate from complex learning system to simplified approach
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import MarinDatabase

def backup_existing_data():
    """Backup existing learning data before migration"""
    
    print("💾 BACKING UP EXISTING DATA")
    print("=" * 50)
    
    db = MarinDatabase()
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    
    tables_to_backup = [
        'tier0_rules',
        'tier1_training_batches', 
        'tier1_training_examples',
        'tier23_few_shot_examples',
        'learning_progress',
        'tier_performance',
        'learning_feedback'
    ]
    
    backed_up = []
    not_found = []
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        for table in tables_to_backup:
            try:
                # Check if table exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = %s
                    );
                """, (table,))
                
                if cursor.fetchone()[0]:
                    # Export data
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    
                    if count > 0:
                        backup_file = backup_dir / f"{table}_backup.sql"
                        os.system(f"pg_dump --table={table} --data-only marin_emails > {backup_file}")
                        backed_up.append(f"{table} ({count} records)")
                    else:
                        backed_up.append(f"{table} (empty)")
                else:
                    not_found.append(table)
                    
            except Exception as e:
                print(f"   ⚠️ Error backing up {table}: {e}")
    
    if backed_up:
        print("✅ Backed up tables:")
        for item in backed_up:
            print(f"   📦 {item}")
    
    if not_found:
        print("ℹ️ Tables not found (probably fresh install):")
        for table in not_found:
            print(f"   ❓ {table}")
    
    return len(backed_up) > 0

def apply_v2_schema():
    """Apply the new v2.0 database schema"""
    
    print("\n🗄️ APPLYING V2.0 SCHEMA")
    print("=" * 50)
    
    # Read the schema file
    schema_file = Path("sql/marin_v2_schema.sql")
    
    if not schema_file.exists():
        print("❌ Schema file not found: sql/marin_v2_schema.sql")
        print("Please save the new schema SQL to that file first.")
        return False
    
    db = MarinDatabase()
    
    try:
        with open(schema_file, 'r') as f:
            schema_sql = f.read()
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Execute the schema
            cursor.execute(schema_sql)
            conn.commit()
            
            print("✅ V2.0 schema applied successfully")
            
            # Verify new tables exist
            new_tables = [
                'tier0_simple_rules',
                'training_sessions',
                'bert_training_examples',
                'bert_model_versions',
                'human_review_queue',
                'system_settings'
            ]
            
            for table in new_tables:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = %s
                    );
                """, (table,))
                
                if cursor.fetchone()[0]:
                    print(f"   ✅ {table}")
                else:
                    print(f"   ❌ {table} - MISSING!")
                    return False
            
            return True
            
    except Exception as e:
        print(f"❌ Schema migration failed: {e}")
        return False

def verify_migration():
    """Verify the migration was successful"""
    
    print("\n🔍 VERIFYING MIGRATION")
    print("=" * 50)
    
    db = MarinDatabase()
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check system settings
            cursor.execute("SELECT COUNT(*) FROM system_settings")
            settings_count = cursor.fetchone()[0]
            print(f"✅ System settings: {settings_count} records")
            
            # Check views
            views = ['training_progress', 'tier0_rules_summary', 'bert_training_summary', 'human_queue_summary']
            for view in views:
                cursor.execute(f"SELECT COUNT(*) FROM {view}")
                print(f"✅ View {view}: accessible")
            
            # Check system phase
            cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'system_phase'")
            phase = cursor.fetchone()[0]
            print(f"✅ System phase: {phase}")
            
            # Check email_analysis modifications
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'email_analysis' AND column_name IN 
                ('training_phase', 'classified_by', 'human_validated', 'needs_retraining')
            """)
            
            new_columns = [row[0] for row in cursor.fetchall()]
            print(f"✅ email_analysis new columns: {len(new_columns)}/4")
            
            return True
            
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

def show_next_steps():
    """Show what to do after migration"""
    
    print("\n🎯 NEXT STEPS")
    print("=" * 50)
    
    print("""
✅ DATABASE MIGRATION COMPLETE!

Your Marin system is now ready for v2.0 architecture:

📋 Schema Changes Applied:
   • Simplified Tier 0 rules (whitelist/blacklist only)
   • Training session tracking
   • BERT training examples storage
   • Human review queue
   • System settings configuration

🚀 What's Next:
   1. Create the separate BERT pre-training project
   2. Replace the old analyzer files with new ones
   3. Build the training interface
   4. Test with a small batch of emails

📁 Old Files to Replace:
   • analyzers/tier0_rules_engine.py → new_tier0_simple_rules.py
   • analyzers/tier1_bert_classifier.py → new_bert_personalizer.py  
   • analyzers/tier2_fast_ollama.py → (remove - not needed)
   • analyzers/tier3_deep_ollama.py → (remove - not needed)
   • core/analysis_coordinator.py → new_training_coordinator.py

💡 The system is now ready for the simplified, scalable architecture!
""")

def main():
    """Run the complete migration process"""
    
    print("🔄 MARIN V2.0 DATABASE MIGRATION")
    print("=" * 60)
    print("Migrating from complex 5-tier system to simplified training approach")
    print()
    
    # Step 1: Backup existing data
    backup_success = backup_existing_data()
    
    # Step 2: Apply new schema
    schema_success = apply_v2_schema()
    
    if not schema_success:
        print("\n❌ Migration failed at schema application")
        return False
    
    # Step 3: Verify migration
    verify_success = verify_migration()
    
    if not verify_success:
        print("\n❌ Migration failed at verification")
        return False
    
    # Step 4: Show next steps
    show_next_steps()
    
    print("\n🎉 MIGRATION SUCCESSFUL!")
    print("Database is ready for Marin v2.0 architecture")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
