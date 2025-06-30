#!/usr/bin/env python3
"""
Dry run test script for Marin email analysis system.
Tests the complete 5-tier analysis pipeline with real emails.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.analysis_coordinator import AnalysisCoordinator
from core.database import MarinDatabase

def run_dry_run_test(num_emails: int = 10):
    """
    Run dry run test with real emails from database
    
    Args:
        num_emails: Number of emails to test with
    """
    print("🧪 MARIN EMAIL ANALYSIS - DRY RUN TEST")
    print("=" * 60)
    
    try:
        # Initialize coordinator in dry run mode
        coordinator = AnalysisCoordinator(dry_run=True)
        db = MarinDatabase()
        
        # Get some real emails for testing
        print(f"📧 Fetching {num_emails} emails for testing...")
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get a diverse sample of emails
            cursor.execute("""
                SELECT id, message_id, subject, sender, sender_email, sender_name,
                       snippet, body_text, has_attachments, attachment_count,
                       date_sent, labels
                FROM emails 
                WHERE subject IS NOT NULL 
                    AND sender IS NOT NULL
                    AND snippet IS NOT NULL
                ORDER BY date_sent DESC  -- Start with recent emails
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
            print("❌ No emails found in database for testing")
            return False
        
        print(f"✅ Found {len(emails)} emails for testing")
        print(f"📅 Date range: {emails[-1]['date_sent']} to {emails[0]['date_sent']}")
        
        # Show sample of what we're testing
        print(f"\n📝 Sample emails to be analyzed:")
        for i, email in enumerate(emails[:3]):
            subject = email['subject'][:60] + '...' if len(email['subject']) > 60 else email['subject']
            sender = email['sender_email'] or email['sender']
            print(f"   {i+1}. [{email['date_sent'].strftime('%Y-%m-%d')}] {sender}")
            print(f"      Subject: {subject}")
        
        if len(emails) > 3:
            print(f"   ... and {len(emails) - 3} more emails")
        
        # Confirm dry run
        print(f"\n⚠️  DRY RUN MODE: No data will be written to database")
        print(f"🎯 The system will classify emails but not store results")
        
        input(f"\nPress Enter to start dry run analysis (or Ctrl+C to cancel)...")
        
        # Run the analysis
        result = coordinator.analyze_batch(emails, batch_name="dry_run_test")
        
        # Show final results
        print(f"\n📊 DRY RUN TEST RESULTS:")
        print(f"   Success: {result['successful_analyses']}/{result['total_emails']} emails classified")
        print(f"   Failed: {result['failed_analyses']} emails")
        print(f"   Human escalations: {result['human_escalations']} emails")
        print(f"   Processing rate: {result['emails_per_minute']:.1f} emails/minute")
        
        if result['successful_analyses'] > 0:
            print(f"\n🎉 DRY RUN SUCCESSFUL!")
            print(f"   The analysis pipeline is working correctly")
            print(f"   Ready for production run with --confirm flag")
            return True
        else:
            print(f"\n❌ DRY RUN FAILED!")
            print(f"   No emails were successfully classified")
            return False
            
    except KeyboardInterrupt:
        print(f"\n⏹️ Dry run cancelled by user")
        return False
    except Exception as e:
        print(f"\n❌ Dry run failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_quick_dry_run():
    """Quick dry run with just 3 emails"""
    print("⚡ QUICK DRY RUN - 3 EMAILS")
    return run_dry_run_test(num_emails=3)

if __name__ == "__main__":
    """Run dry run test"""
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Marin Email Analysis Dry Run Test')
    parser.add_argument('--emails', type=int, default=10, help='Number of emails to test (default: 10)')
    parser.add_argument('--quick', action='store_true', help='Quick test with 3 emails')
    args = parser.parse_args()
    
    if args.quick:
        success = run_quick_dry_run()
    else:
        success = run_dry_run_test(args.emails)
    
    sys.exit(0 if success else 1)
