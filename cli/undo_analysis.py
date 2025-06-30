#!/usr/bin/env python3
"""
Undo analysis script for Marin email classification system.
Removes analysis results and learning data to allow re-processing.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.database import MarinDatabase

def undo_recent_analysis(hours_back: int = 1):
    """
    Undo analysis results from the last N hours
    
    Args:
        hours_back: How many hours back to undo (default: 1)
    """
    print("🔄 MARIN ANALYSIS UNDO UTILITY")
    print("=" * 50)
    
    try:
        db = MarinDatabase()
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        print(f"⏰ Looking for analysis results newer than: {cutoff_time}")
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Find recent analysis results
            cursor.execute("""
                SELECT COUNT(*), MIN(analyzed_at), MAX(analyzed_at)
                FROM email_analysis 
                WHERE analyzed_at > %s
            """, (cutoff_time,))
            
            result = cursor.fetchone()
            count = result[0]
            earliest = result[1]
            latest = result[2]
            
            if count == 0:
                print(f"✅ No recent analysis results found to undo")
                return True
            
            print(f"🔍 Found {count} analysis results to undo:")
            print(f"   Time range: {earliest} to {latest}")
            
            # Show sample of what will be deleted
            cursor.execute("""
                SELECT e.id, e.subject, a.category, a.processing_tier
                FROM email_analysis a
                JOIN emails e ON a.email_id = e.id
                WHERE a.analyzed_at > %s
                ORDER BY a.analyzed_at DESC
                LIMIT 5
            """, (cutoff_time,))
            
            samples = cursor.fetchall()
            print(f"\n📝 Sample analysis results to be removed:")
            for sample in samples:
                subject = sample[1][:60] + '...' if len(sample[1]) > 60 else sample[1]
                print(f"   Email {sample[0]}: {subject}")
                print(f"     → {sample[2]} (Tier {sample[3]})")
            
            if count > 5:
                print(f"   ... and {count - 5} more results")
            
            # Confirm deletion
            print(f"\n⚠️  This will permanently delete {count} analysis results")
            print(f"🎯 Emails will become 'unanalyzed' and can be re-processed")
            
            confirm = input(f"\nType 'DELETE' to proceed with undo: ").strip()
            
            if confirm != 'DELETE':
                print(f"❌ Undo cancelled")
                return False
            
            # Delete analysis results
            cursor.execute("""
                DELETE FROM email_analysis 
                WHERE analyzed_at > %s
            """, (cutoff_time,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            print(f"\n✅ Successfully deleted {deleted_count} analysis results")
            print(f"🔄 {deleted_count} emails are now unanalyzed and ready for re-processing")
            
            return True
            
    except Exception as e:
        print(f"\n❌ Undo failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def undo_specific_batch(batch_size: int = 100):
    """
    Undo the most recent N analysis results
    
    Args:
        batch_size: Number of most recent results to undo
    """
    print(f"🔄 UNDO LAST {batch_size} ANALYSIS RESULTS")
    print("=" * 50)
    
    try:
        db = MarinDatabase()
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Find most recent analysis results
            cursor.execute("""
                SELECT a.id, e.id as email_id, e.subject, a.category, a.processing_tier, a.analyzed_at
                FROM email_analysis a
                JOIN emails e ON a.email_id = e.id
                ORDER BY a.analyzed_at DESC
                LIMIT %s
            """, (batch_size,))
            
            results = cursor.fetchall()
            
            if not results:
                print(f"✅ No analysis results found to undo")
                return True
            
            print(f"🔍 Found {len(results)} recent analysis results:")
            print(f"   Time range: {results[-1][5]} to {results[0][5]}")
            
            # Show sample
            print(f"\n📝 Most recent analysis results to be removed:")
            for i, result in enumerate(results[:5]):
                subject = result[2][:60] + '...' if len(result[2]) > 60 else result[2]
                print(f"   {i+1}. Email {result[1]}: {subject}")
                print(f"      → {result[3]} (Tier {result[4]}) at {result[5]}")
            
            if len(results) > 5:
                print(f"   ... and {len(results) - 5} more results")
            
            # Confirm deletion
            print(f"\n⚠️  This will permanently delete {len(results)} analysis results")
            print(f"🎯 These emails will become 'unanalyzed' and can be re-processed")
            
            confirm = input(f"\nType 'DELETE' to proceed with undo: ").strip()
            
            if confirm != 'DELETE':
                print(f"❌ Undo cancelled")
                return False
            
            # Delete the specific analysis results
            analysis_ids = [str(result[0]) for result in results]
            placeholders = ','.join(['%s'] * len(analysis_ids))
            
            cursor.execute(f"""
                DELETE FROM email_analysis 
                WHERE id IN ({placeholders})
            """, analysis_ids)
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            print(f"\n✅ Successfully deleted {deleted_count} analysis results")
            print(f"🔄 {deleted_count} emails are now unanalyzed and ready for re-processing")
            
            return True
            
    except Exception as e:
        print(f"\n❌ Undo failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def clear_all_learning_data():
    """Clear all learning data (rules, training examples, etc.)"""
    print(f"🗑️ CLEAR ALL LEARNING DATA")
    print("=" * 50)
    
    try:
        db = MarinDatabase()
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Count learning data
            cursor.execute("SELECT COUNT(*) FROM tier0_rules")
            rules_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM tier23_few_shot_examples")
            examples_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM tier1_training_examples")
            training_count = cursor.fetchone()[0]
            
            total_learning_data = rules_count + examples_count + training_count
            
            if total_learning_data == 0:
                print(f"✅ No learning data found to clear")
                return True
            
            print(f"🔍 Found learning data to clear:")
            print(f"   Tier 0 rules: {rules_count}")
            print(f"   Few-shot examples: {examples_count}")
            print(f"   Training examples: {training_count}")
            print(f"   Total: {total_learning_data} items")
            
            # Confirm deletion
            print(f"\n⚠️  This will permanently delete ALL learning data")
            print(f"🎯 The system will return to 'blank slate' state")
            
            confirm = input(f"\nType 'CLEAR' to proceed: ").strip()
            
            if confirm != 'CLEAR':
                print(f"❌ Clear cancelled")
                return False
            
            # Clear all learning tables
            cursor.execute("DELETE FROM tier0_rules")
            cursor.execute("DELETE FROM tier23_few_shot_examples") 
            cursor.execute("DELETE FROM tier1_training_examples")
            cursor.execute("DELETE FROM learning_feedback")
            
            # Reset learning progress
            cursor.execute("""
                UPDATE learning_progress 
                SET total_classifications = 0,
                    last_training_batch = 0,
                    tier0_rules_count = 0,
                    tier23_examples_count = 0,
                    last_updated = NOW()
            """)
            
            conn.commit()
            
            print(f"\n✅ Successfully cleared all learning data")
            print(f"🔄 System reset to blank slate - ready for fresh learning")
            
            return True
            
    except Exception as e:
        print(f"\n❌ Clear failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    """Run undo utility"""
    
    import argparse
    parser = argparse.ArgumentParser(description='Marin Analysis Undo Utility')
    parser.add_argument('--hours', type=int, default=1, help='Undo analysis from last N hours')
    parser.add_argument('--batch', type=int, help='Undo last N analysis results')
    parser.add_argument('--clear-learning', action='store_true', help='Clear all learning data')
    args = parser.parse_args()
    
    if args.clear_learning:
        success = clear_all_learning_data()
    elif args.batch:
        success = undo_specific_batch(args.batch)
    else:
        success = undo_recent_analysis(args.hours)
    
    if success:
        print(f"\n🎉 Undo completed successfully!")
    else:
        print(f"\n❌ Undo failed - check logs above")
    
    sys.exit(0 if success else 1)
