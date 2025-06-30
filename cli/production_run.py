#!/usr/bin/env python3
"""
Production analysis script for Marin email classification system.
Processes real emails and stores results in database.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.analysis_coordinator import AnalysisCoordinator
from core.database import MarinDatabase

def run_production_analysis(num_emails: int = 100, strategy: str = "oldest"):
    """
    Run production analysis with real database writes
    
    Args:
        num_emails: Number of emails to process
        strategy: Email selection strategy ("oldest", "newest", "random")
    """
    print("🚀 MARIN EMAIL ANALYSIS - PRODUCTION RUN")
    print("=" * 60)
    
    try:
        # Initialize coordinator in production mode
        coordinator = AnalysisCoordinator(dry_run=False)
        db = MarinDatabase()
        
        # Get emails based on strategy
        print(f"📧 Fetching {num_emails} {strategy} emails for analysis...")
        
        # Build query based on strategy
        if strategy == "oldest":
            order_clause = "ORDER BY date_sent ASC"
            description = "oldest emails (best deletion candidates)"
        elif strategy == "newest":
            order_clause = "ORDER BY date_sent DESC"  
            description = "newest emails"
        else:  # random
            order_clause = "ORDER BY RANDOM()"
            description = "random emails"
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get emails that haven't been analyzed yet
            cursor.execute(f"""
                SELECT e.id, e.message_id, e.subject, e.sender, e.sender_email, e.sender_name,
                       e.snippet, e.body_text, e.has_attachments, e.attachment_count,
                       e.date_sent, e.labels
                FROM emails e
                LEFT JOIN email_analysis a ON e.id = a.email_id
                WHERE e.subject IS NOT NULL 
                    AND e.sender IS NOT NULL
                    AND e.snippet IS NOT NULL
                    AND a.id IS NULL  -- Not yet analyzed
                {order_clause}
                LIMIT %s
            """, (num_emails,))
            
            emails = []
            for row in cursor.fetchall():
                emails.append({
                    'id': row[0],
                    'message_id': row[1],
                    'subject': row[2],
                    'sender': row[3],
                    'sender_email': row[4],
                    'sender_name': row[5],
                    'snippet': row[6],
                    'body_text': row[7],
                    'has_attachments': row[8],
                    'attachment_count': row[9],
                    'date_sent': row[10],
                    'labels': row[11] if row[11] else []
                })
        
        if not emails:
            print("❌ No unanalyzed emails found in database")
            print("💡 All emails may have already been processed")
            return False
        
        print(f"✅ Found {len(emails)} unanalyzed emails")
        print(f"📅 Date range: {emails[0]['date_sent']} to {emails[-1]['date_sent']}")
        print(f"🎯 Strategy: {description}")
        
        # Show sample of what we're analyzing
        print(f"\n📝 Sample emails to be analyzed:")
        for i, email in enumerate(emails[:5]):
            subject = email['subject'][:50] + '...' if len(email['subject']) > 50 else email['subject']
            sender = email['sender_email'] or email['sender']
            date_str = email['date_sent'].strftime('%Y-%m-%d')
            print(f"   {i+1}. [{date_str}] {sender}")
            print(f"      {subject}")
        
        if len(emails) > 5:
            print(f"   ... and {len(emails) - 5} more emails")
        
        # Show current database state
        stats = db.get_database_stats()
        print(f"\n📊 Current Database Status:")
        print(f"   Total emails: {stats['total_emails']:,}")
        print(f"   Already analyzed: {stats['analyzed_emails']:,}")
        print(f"   Will analyze: {len(emails):,} emails")
        print(f"   After completion: {stats['analyzed_emails'] + len(emails):,} analyzed ({((stats['analyzed_emails'] + len(emails))/stats['total_emails']*100):.1f}%)")
        
        # Final confirmation
        print(f"\n⚠️  PRODUCTION MODE: Results will be written to database")
        print(f"🎯 This will permanently classify and store analysis results")
        
        print(f"\nReady to start production analysis?")
        print(f"This will process {len(emails)} emails and may take 10-30 minutes...")
        
        confirm = input(f"Type 'YES' to proceed with production run: ").strip()
        
        if confirm != 'YES':
            print(f"❌ Production run cancelled")
            return False
        
        print(f"\n🚀 Starting production analysis...")
        start_time = datetime.now()
        
        # Run the analysis
        result = coordinator.analyze_batch(emails, batch_name=f"production_{strategy}_{num_emails}")
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        # Show final results
        print(f"\n🎉 PRODUCTION RUN COMPLETED!")
        print(f"⏱️ Total time: {duration}")
        print(f"📊 Final Results:")
        print(f"   Success: {result['successful_analyses']}/{result['total_emails']} emails classified")
        print(f"   Failed: {result['failed_analyses']} emails")
        print(f"   Human escalations: {result['human_escalations']} emails")
        print(f"   Processing rate: {result['emails_per_minute']:.1f} emails/minute")
        print(f"   Learning events: {result['learning_events']} training triggers")
        
        # Update database stats
        new_stats = db.get_database_stats()
        print(f"\n📈 Database Progress:")
        print(f"   Before: {stats['analyzed_emails']:,} analyzed")
        print(f"   After: {new_stats['analyzed_emails']:,} analyzed")
        print(f"   Progress: {new_stats['analysis_coverage']:.1f}% of total emails")
        
        if result['successful_analyses'] > result['total_emails'] * 0.8:
            print(f"\n🌟 EXCELLENT RESULTS!")
            print(f"   High success rate indicates the system is working well")
            if result['human_escalations'] < result['total_emails'] * 0.1:
                print(f"   Low human escalation rate shows good AI automation")
            print(f"   Ready for larger batches or full dataset processing")
            return True
        else:
            print(f"\n⚠️ MIXED RESULTS")
            print(f"   Success rate lower than expected - may need tuning")
            return False
            
    except KeyboardInterrupt:
        print(f"\n⏹️ Production run cancelled by user")
        return False
    except Exception as e:
        print(f"\n❌ Production run failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_oldest_100():
    """Run production analysis on 100 oldest emails"""
    return run_production_analysis(num_emails=100, strategy="oldest")

def run_newest_50():
    """Run production analysis on 50 newest emails"""
    return run_production_analysis(num_emails=50, strategy="newest")

if __name__ == "__main__":
    """Run production analysis"""
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Marin Email Analysis Production Run')
    parser.add_argument('--emails', type=int, default=100, help='Number of emails to process (default: 100)')
    parser.add_argument('--strategy', choices=['oldest', 'newest', 'random'], default='oldest', 
                       help='Email selection strategy (default: oldest)')
    parser.add_argument('--oldest-100', action='store_true', help='Quick run: 100 oldest emails')
    parser.add_argument('--newest-50', action='store_true', help='Quick run: 50 newest emails')
    args = parser.parse_args()
    
    if args.oldest_100:
        success = run_oldest_100()
    elif args.newest_50:
        success = run_newest_50()
    else:
        success = run_production_analysis(args.emails, args.strategy)
    
    if success:
        print(f"\n🎉 Production run completed successfully!")
        print(f"💡 Next steps:")
        print(f"   - Review results in database")
        print(f"   - Run larger batches if performance is good")
        print(f"   - Implement actual email deletion when confident")
    else:
        print(f"\n❌ Production run had issues - review logs above")
    
    sys.exit(0 if success else 1)
