# core/database.py
"""
Database layer for Marin email management system.
Handles PostgreSQL operations for emails, analysis, and metadata.
"""

import psycopg2
import psycopg2.extras
import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass

from utils.config import get_config

@dataclass
class EmailRecord:
    """Data class for email records"""
    id: Optional[int] = None
    message_id: str = ''
    thread_id: Optional[str] = None
    subject: str = ''
    sender: str = ''
    sender_email: str = ''
    sender_name: str = ''
    recipient: str = ''
    date_sent: Optional[datetime] = None
    date_received: Optional[datetime] = None
    body_text: str = ''
    body_html: str = ''
    snippet: str = ''
    headers: str = ''  # JSON string
    labels: List[str] = None
    has_attachments: bool = False
    attachment_count: int = 0
    size_estimate_bytes: Optional[int] = None
    gmail_labels: str = ''  # JSON string
    is_unread: bool = False
    is_important: bool = False
    raw_gmail_data: str = ''  # JSON string
    downloaded_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass 
class AnalysisRecord:
    """Data class for email analysis records"""
    id: Optional[int] = None
    email_id: int = 0
    analysis_version: str = 'v1.0'
    ai_model: str = ''
    category: str = ''
    summary: str = ''
    fraud_score: Optional[int] = None
    fraud_flags: str = ''  # JSON string
    deletion_candidate: bool = False
    deletion_reason: str = ''
    importance_score: Optional[int] = None
    confidence_score: Optional[int] = None
    processing_time_ms: Optional[int] = None
    processing_tier: Optional[int] = None
    analyzed_at: Optional[datetime] = None

class MarinDatabase:
    """PostgreSQL database operations for Marin email system"""
    
    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize database connection
        
        Args:
            connection_string: PostgreSQL connection string
        """
        self.config = get_config()
        self.connection_string = connection_string or self.config.database_url
        self._test_connection()
    
    def _test_connection(self) -> None:
        """Test database connection"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT version();")
                version = cursor.fetchone()[0]
                print(f"✅ Connected to PostgreSQL: {version}")
        except Exception as e:
            raise Exception(f"❌ Database connection failed: {e}")
    
    @contextmanager
    def get_connection(self):
        """Get database connection with automatic cleanup"""
        conn = None
        try:
            conn = psycopg2.connect(self.connection_string)
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()
    
    def create_tables(self) -> None:
        """Create all necessary database tables"""
        
        create_emails_table = """
        CREATE TABLE IF NOT EXISTS emails (
            id SERIAL PRIMARY KEY,
            message_id VARCHAR(50) UNIQUE NOT NULL,
            thread_id VARCHAR(50),
            subject TEXT,
            sender TEXT,
            sender_email VARCHAR(255),
            sender_name VARCHAR(255),
            recipient TEXT,
            date_sent TIMESTAMP WITH TIME ZONE,
            date_received TIMESTAMP WITH TIME ZONE,
            body_text TEXT,
            body_html TEXT,
            snippet TEXT,
            headers JSONB,
            labels TEXT[],
            has_attachments BOOLEAN DEFAULT FALSE,
            attachment_count INTEGER DEFAULT 0,
            size_estimate_bytes INTEGER,
            gmail_labels JSONB,
            is_unread BOOLEAN DEFAULT FALSE,
            is_important BOOLEAN DEFAULT FALSE,
            raw_gmail_data JSONB,
            downloaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """
        
        create_analysis_table = """
        CREATE TABLE IF NOT EXISTS email_analysis (
            id SERIAL PRIMARY KEY,
            email_id INTEGER REFERENCES emails(id) ON DELETE CASCADE,
            analysis_version VARCHAR(50) NOT NULL,
            ai_model VARCHAR(50) NOT NULL,
            category VARCHAR(50),
            summary TEXT,
            fraud_score INTEGER CHECK (fraud_score >= 0 AND fraud_score <= 100),
            fraud_flags JSONB,
            deletion_candidate BOOLEAN DEFAULT FALSE,
            deletion_reason TEXT,
            importance_score INTEGER CHECK (importance_score >= 0 AND importance_score <= 100),
            confidence_score INTEGER CHECK (confidence_score >= 0 AND confidence_score <= 100),
            processing_time_ms INTEGER,
            processing_tier INTEGER,
            analyzed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            
            UNIQUE(email_id, analysis_version, ai_model)
        );
        """
        
        create_attachments_table = """
        CREATE TABLE IF NOT EXISTS attachments (
            id SERIAL PRIMARY KEY,
            email_id INTEGER REFERENCES emails(id) ON DELETE CASCADE,
            gmail_attachment_id VARCHAR(100),
            filename TEXT,
            content_type TEXT,
            size_bytes INTEGER,
            is_downloadable BOOLEAN DEFAULT TRUE,
            downloaded BOOLEAN DEFAULT FALSE,
            local_path TEXT,
            download_attempted_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """
        
        create_sync_sessions_table = """
        CREATE TABLE IF NOT EXISTS sync_sessions (
            id SERIAL PRIMARY KEY,
            session_id UUID DEFAULT gen_random_uuid(),
            sync_type VARCHAR(50) NOT NULL,
            sync_strategy VARCHAR(50),
            start_date DATE,
            end_date DATE,
            total_emails_estimated INTEGER,
            emails_downloaded INTEGER DEFAULT 0,
            emails_failed INTEGER DEFAULT 0,
            last_processed_message_id VARCHAR(50),
            next_page_token TEXT,
            status VARCHAR(20) DEFAULT 'running',
            error_message TEXT,
            started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            completed_at TIMESTAMP WITH TIME ZONE,
            api_calls_made INTEGER DEFAULT 0,
            quota_units_used INTEGER DEFAULT 0,
            avg_emails_per_minute DECIMAL(8,2)
        );
        """
        
        create_learned_patterns_table = """
        CREATE TABLE IF NOT EXISTS learned_patterns (
            id SERIAL PRIMARY KEY,
            pattern_type VARCHAR(50),
            pattern_value TEXT,
            confidence DECIMAL(3,2),
            learned_from_emails INTEGER,
            first_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            last_confirmed TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            times_matched INTEGER DEFAULT 0
        );
        """
        
        create_indexes = """
        CREATE INDEX IF NOT EXISTS idx_emails_date_sent ON emails(date_sent);
        CREATE INDEX IF NOT EXISTS idx_emails_sender_email ON emails(sender_email);
        CREATE INDEX IF NOT EXISTS idx_emails_message_id ON emails(message_id);
        CREATE INDEX IF NOT EXISTS idx_emails_labels_gin ON emails USING GIN(labels);
        
        CREATE INDEX IF NOT EXISTS idx_analysis_category ON email_analysis(category);
        CREATE INDEX IF NOT EXISTS idx_analysis_deletion_candidate ON email_analysis(deletion_candidate);
        CREATE INDEX IF NOT EXISTS idx_analysis_model_version ON email_analysis(ai_model, analysis_version);
        
        CREATE INDEX IF NOT EXISTS idx_sync_sessions_status ON sync_sessions(status);
        """
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create tables
            cursor.execute(create_emails_table)
            cursor.execute(create_analysis_table)  
            cursor.execute(create_attachments_table)
            cursor.execute(create_sync_sessions_table)
            cursor.execute(create_learned_patterns_table)
            
            # Create indexes
            cursor.execute(create_indexes)
            
            conn.commit()
            print("✅ Database tables and indexes created successfully")
    
    def insert_email(self, email_data: Dict[str, Any]) -> int:
        """
        Insert email into database, return email ID
        
        Args:
            email_data: Email data dictionary
            
        Returns:
            Email ID
        """
        query = """
            INSERT INTO emails (
                message_id, thread_id, subject, sender, sender_email, sender_name,
                recipient, date_sent, date_received, body_text, body_html, snippet,
                headers, labels, has_attachments, attachment_count, size_estimate_bytes,
                gmail_labels, is_unread, is_important, raw_gmail_data
            ) VALUES (
                %(message_id)s, %(thread_id)s, %(subject)s, %(sender)s, %(sender_email)s, %(sender_name)s,
                %(recipient)s, %(date_sent)s, %(date_received)s, %(body_text)s, %(body_html)s, %(snippet)s,
                %(headers)s, %(labels)s, %(has_attachments)s, %(attachment_count)s, %(size_estimate_bytes)s,
                %(gmail_labels)s, %(is_unread)s, %(is_important)s, %(raw_gmail_data)s
            ) ON CONFLICT (message_id) DO UPDATE SET
                updated_at = NOW(),
                subject = EXCLUDED.subject,
                sender = EXCLUDED.sender,
                body_text = EXCLUDED.body_text,
                snippet = EXCLUDED.snippet
            RETURNING id;
        """
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, email_data)
            email_id = cursor.fetchone()[0]
            conn.commit()
            return email_id
    
    def insert_analysis(self, analysis_data: Dict[str, Any]) -> int:
        """
        Insert AI analysis results
        
        Args:
            analysis_data: Analysis data dictionary
            
        Returns:
            Analysis ID
        """
        query = """
            INSERT INTO email_analysis (
                email_id, analysis_version, ai_model, category, summary,
                fraud_score, fraud_flags, deletion_candidate, deletion_reason,
                importance_score, confidence_score, processing_time_ms, processing_tier
            ) VALUES (
                %(email_id)s, %(analysis_version)s, %(ai_model)s, %(category)s, %(summary)s,
                %(fraud_score)s, %(fraud_flags)s, %(deletion_candidate)s, %(deletion_reason)s,
                %(importance_score)s, %(confidence_score)s, %(processing_time_ms)s, %(processing_tier)s
            ) ON CONFLICT (email_id, analysis_version, ai_model) DO UPDATE SET
                category = EXCLUDED.category,
                summary = EXCLUDED.summary,
                fraud_score = EXCLUDED.fraud_score,
                fraud_flags = EXCLUDED.fraud_flags,
                deletion_candidate = EXCLUDED.deletion_candidate,
                deletion_reason = EXCLUDED.deletion_reason,
                importance_score = EXCLUDED.importance_score,
                confidence_score = EXCLUDED.confidence_score,
                processing_time_ms = EXCLUDED.processing_time_ms,
                processing_tier = EXCLUDED.processing_tier,
                analyzed_at = NOW()
            RETURNING id;
        """
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, analysis_data)
            analysis_id = cursor.fetchone()[0]
            conn.commit()
            return analysis_id
    
    def get_unanalyzed_emails(self, analysis_version: str, ai_model: str, 
                             limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get emails that haven't been analyzed with specific model/version
        
        Args:
            analysis_version: Analysis version to check
            ai_model: AI model to check
            limit: Maximum number of emails to return
            
        Returns:
            List of email dictionaries
        """
        query = """
            SELECT e.id, e.message_id, e.subject, e.sender, e.sender_email, e.date_sent, 
                   e.body_text, e.snippet, e.labels, e.has_attachments
            FROM emails e
            LEFT JOIN email_analysis a ON e.id = a.email_id 
                AND a.analysis_version = %(analysis_version)s 
                AND a.ai_model = %(ai_model)s
            WHERE a.id IS NULL
            ORDER BY e.date_sent ASC
            LIMIT %(limit)s;
        """
        
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute(query, {
                'analysis_version': analysis_version,
                'ai_model': ai_model,
                'limit': limit
            })
            return [dict(row) for row in cursor.fetchall()]
    
    def get_deletion_candidates(self, analysis_version: str = 'v1.0', 
                               categories: Optional[List[str]] = None,
                               max_fraud_score: Optional[int] = 30,
                               older_than_days: Optional[int] = 365,
                               min_confidence: int = 70) -> List[Dict[str, Any]]:
        """
        Get emails that are candidates for deletion
        
        Args:
            analysis_version: Analysis version to use
            categories: Categories to include
            max_fraud_score: Maximum fraud score to include
            older_than_days: Only emails older than this many days
            min_confidence: Minimum confidence score
            
        Returns:
            List of deletion candidate dictionaries
        """
        conditions = ["a.deletion_candidate = true"]
        params = {'analysis_version': analysis_version}
        
        if categories:
            conditions.append("a.category = ANY(%(categories)s)")
            params['categories'] = categories
        
        if max_fraud_score is not None:
            conditions.append("(a.fraud_score IS NULL OR a.fraud_score <= %(max_fraud_score)s)")
            params['max_fraud_score'] = max_fraud_score
        
        if older_than_days:
            conditions.append("e.date_sent < NOW() - INTERVAL '%(older_than_days)s days'")
            params['older_than_days'] = older_than_days
        
        if min_confidence:
            conditions.append("(a.confidence_score IS NULL OR a.confidence_score >= %(min_confidence)s)")
            params['min_confidence'] = min_confidence
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
            SELECT e.id, e.message_id, e.subject, e.sender, e.sender_email, e.date_sent,
                   a.category, a.summary, a.fraud_score, a.deletion_reason, a.confidence_score
            FROM emails e
            JOIN email_analysis a ON e.id = a.email_id
            WHERE a.analysis_version = %(analysis_version)s AND {where_clause}
            ORDER BY e.date_sent ASC;
        """
        
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_daily_digest_emails(self, days_back: int = 2) -> List[Dict[str, Any]]:
        """
        Get recent emails for daily digest
        
        Args:
            days_back: Number of days back to include
            
        Returns:
            List of email dictionaries
        """
        query = """
            SELECT e.id, e.message_id, e.subject, e.sender, e.sender_email, e.date_sent,
                   a.category, a.summary, a.importance_score, a.fraud_flags, a.fraud_score
            FROM emails e
            LEFT JOIN email_analysis a ON e.id = a.email_id
            WHERE e.date_sent >= NOW() - INTERVAL '%(days_back)s days'
            ORDER BY e.date_sent DESC;
        """
        
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute(query, {'days_back': days_back})
            return [dict(row) for row in cursor.fetchall()]
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get database statistics
        
        Returns:
            Dictionary with various statistics
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Email counts
            cursor.execute("SELECT COUNT(*) FROM emails;")
            total_emails = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM email_analysis;")
            analyzed_emails = cursor.fetchone()[0]
            
            # Date range
            cursor.execute("""
                SELECT MIN(date_sent), MAX(date_sent) 
                FROM emails 
                WHERE date_sent IS NOT NULL;
            """)
            date_range = cursor.fetchone()
            
            # Category breakdown
            cursor.execute("""
                SELECT category, COUNT(*) as count
                FROM email_analysis 
                GROUP BY category 
                ORDER BY count DESC;
            """)
            categories = dict(cursor.fetchall())
            
            # Deletion candidates
            cursor.execute("""
                SELECT COUNT(*) 
                FROM email_analysis 
                WHERE deletion_candidate = true;
            """)
            deletion_candidates = cursor.fetchone()[0]
            
            return {
                'total_emails': total_emails,
                'analyzed_emails': analyzed_emails,
                'date_range': {
                    'oldest': date_range[0].isoformat() if date_range[0] else None,
                    'newest': date_range[1].isoformat() if date_range[1] else None
                },
                'categories': categories,
                'deletion_candidates': deletion_candidates,
                'analysis_coverage': round(analyzed_emails / total_emails * 100, 1) if total_emails > 0 else 0
            }
    
    def cleanup_old_analysis(self, retention_days: int = 90) -> int:
        """
        Clean up old analysis data
        
        Args:
            retention_days: Keep analysis newer than this many days
            
        Returns:
            Number of records deleted
        """
        query = """
            DELETE FROM email_analysis 
            WHERE analyzed_at < NOW() - INTERVAL '%(retention_days)s days'
            RETURNING id;
        """
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, {'retention_days': retention_days})
            deleted_count = len(cursor.fetchall())
            conn.commit()
            return deleted_count

# Convenience functions
def create_database() -> MarinDatabase:
    """Create and return database instance"""
    return MarinDatabase()

def initialize_database() -> bool:
    """Initialize database with tables"""
    try:
        db = MarinDatabase()
        db.create_tables()
        return True
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

# Example usage and testing
if __name__ == "__main__":
    """Test the database system"""
    
    print("🗄️ Testing Database System")
    print("=" * 50)
    
    try:
        # Initialize database
        if not initialize_database():
            exit(1)
        
        # Create database instance
        db = create_database()
        
        # Test basic operations
        print("\n📊 Database Statistics:")
        stats = db.get_database_stats()
        
        print(f"   Total emails: {stats['total_emails']:,}")
        print(f"   Analyzed emails: {stats['analyzed_emails']:,}")
        print(f"   Analysis coverage: {stats['analysis_coverage']}%")
        print(f"   Deletion candidates: {stats['deletion_candidates']:,}")
        
        if stats['date_range']['oldest']:
            print(f"   Date range: {stats['date_range']['oldest']} to {stats['date_range']['newest']}")
        
        if stats['categories']:
            print(f"   Top categories:")
            for category, count in list(stats['categories'].items())[:5]:
                print(f"     {category}: {count:,} emails")
        
        print("\n🎉 Database test completed successfully!")
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        exit(1)
