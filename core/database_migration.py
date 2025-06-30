# core/database_migration.py
"""
Database migration utilities for Marin learning system.
One job: safely apply schema updates for tiered learning.
"""

import os
from pathlib import Path
from typing import Dict, Any
from core.database import MarinDatabase

class DatabaseMigration:
    """Handles database schema migrations for learning system"""
    
    def __init__(self, database: MarinDatabase = None):
        self.db = database or MarinDatabase()
        self.sql_dir = Path(__file__).parent.parent / 'sql'
    
    def apply_learning_schema_updates(self) -> Dict[str, Any]:
        """
        Apply learning system schema updates
        
        Returns:
            Migration result summary
        """
        print("🗄️ Applying Learning System Database Updates")
        print("=" * 50)
        
        migration_file = self.sql_dir / 'schema_updates_learning.sql'
        
        if not migration_file.exists():
            return {
                'success': False,
                'error': f'Migration file not found: {migration_file}'
            }
        
        try:
            # Read migration SQL
            with open(migration_file, 'r') as f:
                migration_sql = f.read()
            
            # Apply migration
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Execute the migration SQL
                cursor.execute(migration_sql)
                conn.commit()
                
                print("✅ Learning system tables created/updated")
                
                # Verify new tables exist
                verification_result = self._verify_learning_tables(cursor)
                
                if verification_result['success']:
                    print("✅ All learning tables verified")
                    return {
                        'success': True,
                        'tables_created': verification_result['tables'],
                        'message': 'Learning system database migration completed successfully'
                    }
                else:
                    return {
                        'success': False,
                        'error': f"Migration applied but verification failed: {verification_result['error']}"
                    }
        
        except Exception as e:
            return {
                'success': False,
                'error': f"Migration failed: {e}"
            }
    
    def _verify_learning_tables(self, cursor) -> Dict[str, Any]:
        """Verify that learning system tables were created correctly"""
        
        expected_tables = [
            'tier0_rules',
            'tier1_training_batches', 
            'tier1_training_examples',
            'tier23_few_shot_examples',
            'learning_progress',
            'tier_performance',
            'learning_feedback'
        ]
        
        try:
            # Check each table exists
            existing_tables = []
            for table_name in expected_tables:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = %s
                    );
                """, (table_name,))
                
                exists = cursor.fetchone()[0]
                if exists:
                    existing_tables.append(table_name)
                else:
                    return {
                        'success': False,
                        'error': f'Table {table_name} was not created'
                    }
            
            # Check that learning_progress has initial data
            cursor.execute("SELECT COUNT(*) FROM learning_progress;")
            progress_count = cursor.fetchone()[0]
            
            if progress_count == 0:
                return {
                    'success': False,
                    'error': 'learning_progress table is empty - initial data not inserted'
                }
            
            return {
                'success': True,
                'tables': existing_tables
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Verification error: {e}'
            }
    
    def get_learning_system_status(self) -> Dict[str, Any]:
        """Get current status of learning system"""
        
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get learning progress
                cursor.execute("""
                    SELECT 
                        total_classifications,
                        next_training_threshold,
                        tier0_rules_count,
                        tier1_model_version,
                        tier23_examples_count,
                        last_updated
                    FROM learning_progress 
                    ORDER BY id DESC 
                    LIMIT 1
                """)
                
                progress = cursor.fetchone()
                if not progress:
                    return {'error': 'No learning progress data found'}
                
                # Get tier performance summary
                cursor.execute("""
                    SELECT 
                        tier_level,
                        SUM(emails_processed) as total_processed,
                        AVG(avg_confidence) as avg_confidence
                    FROM tier_performance 
                    GROUP BY tier_level 
                    ORDER BY tier_level
                """)
                
                tier_stats = cursor.fetchall()
                
                # Get active rules count
                cursor.execute("SELECT COUNT(*) FROM tier0_rules WHERE is_active = true")
                active_rules = cursor.fetchone()[0]
                
                # Get training batches count
                cursor.execute("SELECT COUNT(*) FROM tier1_training_batches")
                training_batches = cursor.fetchone()[0]
                
                return {
                    'learning_progress': {
                        'total_classifications': progress[0],
                        'next_training_threshold': progress[1], 
                        'progress_in_batch': progress[0] % progress[1],
                        'tier0_rules_count': progress[2],
                        'tier1_model_version': progress[3],
                        'tier23_examples_count': progress[4],
                        'last_updated': progress[5]
                    },
                    'tier_performance': [
                        {
                            'tier': stat[0],
                            'emails_processed': stat[1],
                            'avg_confidence': float(stat[2]) if stat[2] else 0
                        }
                        for stat in tier_stats
                    ],
                    'active_rules': active_rules,
                    'training_batches': training_batches
                }
                
        except Exception as e:
            return {'error': f'Status check failed: {e}'}

def apply_learning_migration() -> bool:
    """Convenience function to apply learning system migration"""
    try:
        migration = DatabaseMigration()
        result = migration.apply_learning_schema_updates()
        
        if result['success']:
            print(f"✅ {result['message']}")
            return True
        else:
            print(f"❌ Migration failed: {result['error']}")
            return False
            
    except Exception as e:
        print(f"❌ Migration error: {e}")
        return False

def check_learning_system_status() -> None:
    """Check and display learning system status"""
    try:
        migration = DatabaseMigration()
        status = migration.get_learning_system_status()
        
        if 'error' in status:
            print(f"❌ Status check failed: {status['error']}")
            return
        
        progress = status['learning_progress']
        print("📊 Learning System Status")
        print("=" * 40)
        print(f"Classifications: {progress['total_classifications']:,}")
        print(f"Next training at: {progress['next_training_threshold']:,}")
        print(f"Progress in batch: {progress['progress_in_batch']:,}")
        print(f"Active rules: {status['active_rules']:,}")
        print(f"Training batches: {status['training_batches']:,}")
        print(f"Few-shot examples: {progress['tier23_examples_count']:,}")
        
        if progress['tier1_model_version']:
            print(f"BERT model: {progress['tier1_model_version']}")
        
        print(f"\n🏆 Tier Performance:")
        for tier in status['tier_performance']:
            print(f"   Tier {tier['tier']}: {tier['emails_processed']:,} processed, {tier['avg_confidence']:.2f} avg confidence")
            
    except Exception as e:
        print(f"❌ Status check error: {e}")

# Example usage and testing
if __name__ == "__main__":
    """Test database migration"""
    
    print("🔧 Testing Learning System Migration")
    print("=" * 50)
    
    # Apply migration
    success = apply_learning_migration()
    
    if success:
        print("\n📊 Checking system status...")
        check_learning_system_status()
        print("\n🎉 Migration test completed successfully!")
    else:
        print("\n❌ Migration test failed")
