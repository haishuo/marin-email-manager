-- Marin Email Database Schema
-- PostgreSQL database schema for the Marin email management system
-- Run this with: psql marin_emails < sql/schema.sql

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Core email storage table
CREATE TABLE IF NOT EXISTS emails (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR(50) UNIQUE NOT NULL,    -- Gmail message ID
    thread_id VARCHAR(50),                     -- Gmail thread ID
    subject TEXT,
    sender TEXT,                               -- Full "Name <email@domain>" format
    sender_email VARCHAR(255),                 -- Just email part
    sender_name VARCHAR(255),                  -- Just name part
    recipient TEXT,
    date_sent TIMESTAMP WITH TIME ZONE,
    date_received TIMESTAMP WITH TIME ZONE,
    body_text TEXT,                            -- Plain text version
    body_html TEXT,                            -- HTML version (if available)
    snippet TEXT,                              -- Gmail's snippet preview
    headers JSONB,                             -- All email headers as JSON
    labels TEXT[],                             -- Gmail labels array
    has_attachments BOOLEAN DEFAULT FALSE,
    attachment_count INTEGER DEFAULT 0,
    size_estimate_bytes INTEGER,               -- Rough size estimate
    gmail_labels JSONB,                        -- Detailed Gmail label info
    is_unread BOOLEAN DEFAULT FALSE,
    is_important BOOLEAN DEFAULT FALSE,
    raw_gmail_data JSONB,                      -- Store full Gmail API response for debugging
    downloaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- AI Analysis results (separate table for experimentation)
CREATE TABLE IF NOT EXISTS email_analysis (
    id SERIAL PRIMARY KEY,
    email_id INTEGER REFERENCES emails(id) ON DELETE CASCADE,
    analysis_version VARCHAR(50) NOT NULL,    -- Track different analysis runs
    ai_model VARCHAR(50) NOT NULL,            -- e.g., 'llama3.2:3b'
    category VARCHAR(50),                     -- SHOPPING, WORK, FINANCIAL, etc.
    summary TEXT,                             -- AI-generated one-line summary
    fraud_score INTEGER CHECK (fraud_score >= 0 AND fraud_score <= 100),
    fraud_flags JSONB,                        -- Array of fraud indicators
    deletion_candidate BOOLEAN DEFAULT FALSE, -- Safe to delete?
    deletion_reason TEXT,                     -- Why it's safe to delete
    importance_score INTEGER CHECK (importance_score >= 0 AND importance_score <= 100),
    confidence_score INTEGER CHECK (confidence_score >= 0 AND confidence_score <= 100),
    processing_time_ms INTEGER,               -- AI processing time
    processing_tier INTEGER,                  -- Which tier processed this (1=rules, 2=fast AI, 3=deep AI)
    analyzed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Allow multiple analyses of same email with different models/versions
    UNIQUE(email_id, analysis_version, ai_model)
);

-- Attachment metadata (track but don't download content by default)
CREATE TABLE IF NOT EXISTS attachments (
    id SERIAL PRIMARY KEY,
    email_id INTEGER REFERENCES emails(id) ON DELETE CASCADE,
    gmail_attachment_id VARCHAR(100),         -- Gmail's attachment ID
    filename TEXT,
    content_type TEXT,
    size_bytes INTEGER,
    is_downloadable BOOLEAN DEFAULT TRUE,     -- Some attachments can't be downloaded
    downloaded BOOLEAN DEFAULT FALSE,         -- Have we downloaded it locally?
    local_path TEXT,                          -- Where we saved it (if downloaded)
    download_attempted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Sync progress tracking (crucial for resumable downloads)
CREATE TABLE IF NOT EXISTS sync_sessions (
    id SERIAL PRIMARY KEY,
    session_id UUID DEFAULT uuid_generate_v4(),
    sync_type VARCHAR(50) NOT NULL,           -- 'full_sync', 'incremental', 'oldest_first'
    sync_strategy VARCHAR(50),                -- 'oldest_first', 'newest_first', 'by_year'
    start_date DATE,                          -- Date range being synced (if applicable)
    end_date DATE,
    total_emails_estimated INTEGER,
    emails_downloaded INTEGER DEFAULT 0,
    emails_failed INTEGER DEFAULT 0,
    last_processed_message_id VARCHAR(50),    -- For resuming interrupted syncs
    next_page_token TEXT,                     -- Gmail API pagination token
    status VARCHAR(20) DEFAULT 'running',     -- 'running', 'completed', 'failed', 'paused'
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Performance metrics
    api_calls_made INTEGER DEFAULT 0,
    quota_units_used INTEGER DEFAULT 0,
    avg_emails_per_minute DECIMAL(8,2)
);

-- API usage tracking (respect Gmail rate limits)
CREATE TABLE IF NOT EXISTS api_usage_log (
    id SERIAL PRIMARY KEY,
    date DATE DEFAULT CURRENT_DATE,
    hour INTEGER DEFAULT EXTRACT(HOUR FROM NOW()),
    endpoint VARCHAR(100),                    -- 'messages.list', 'messages.get', etc.
    requests_made INTEGER DEFAULT 0,
    quota_units_used INTEGER DEFAULT 0,
    errors_encountered INTEGER DEFAULT 0,
    
    UNIQUE(date, hour, endpoint)
);

-- Learned patterns for adaptive processing
CREATE TABLE IF NOT EXISTS learned_patterns (
    id SERIAL PRIMARY KEY,
    pattern_type VARCHAR(50),                 -- 'newsletter_domain', 'promo_subject', etc.
    pattern_value TEXT,                       -- 'shop.williams-sonoma.com', '% off everything'
    confidence DECIMAL(3,2),                  -- How confident we are in this pattern
    learned_from_emails INTEGER,              -- How many emails contributed to learning this
    first_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_confirmed TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    times_matched INTEGER DEFAULT 0
);

-- Cleanup operations log (track what we've deleted)
CREATE TABLE IF NOT EXISTS cleanup_operations (
    id SERIAL PRIMARY KEY,
    operation_id UUID DEFAULT uuid_generate_v4(),
    operation_type VARCHAR(50),               -- 'preview', 'delete', 'undelete'
    analysis_version VARCHAR(50),             -- Which analysis results were used
    filter_criteria JSONB,                   -- What filters were applied
    emails_affected INTEGER,
    emails_deleted INTEGER,
    emails_failed INTEGER,
    dry_run BOOLEAN DEFAULT TRUE,            -- Was this just a preview?
    executed_by VARCHAR(100),                -- User/system that ran it
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Safety: can we undo this operation?
    is_reversible BOOLEAN DEFAULT TRUE,
    reversal_deadline TIMESTAMP WITH TIME ZONE  -- When emails are permanently deleted
);

-- Track individual email deletions (for undo capability)
CREATE TABLE IF NOT EXISTS deleted_emails (
    id SERIAL PRIMARY KEY,
    cleanup_operation_id INTEGER REFERENCES cleanup_operations(id),
    email_id INTEGER REFERENCES emails(id),
    message_id VARCHAR(50),                   -- Gmail message ID for restoration
    deleted_from_gmail_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    restoration_deadline TIMESTAMP WITH TIME ZONE,  -- 30 days from deletion
    restored_at TIMESTAMP WITH TIME ZONE
);

-- Batch performance tracking for adaptive learning
CREATE TABLE IF NOT EXISTS batch_performance (
    id SERIAL PRIMARY KEY,
    batch_number INTEGER,
    emails_processed INTEGER,
    tier0_percentage DECIMAL(5,2),            -- Adaptive learned rules
    tier1_percentage DECIMAL(5,2),            -- Static rules  
    tier2_percentage DECIMAL(5,2),            -- Fast AI
    tier3_percentage DECIMAL(5,2),            -- Deep AI
    patterns_learned INTEGER,
    processing_time_minutes DECIMAL(8,2),
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_emails_date_sent ON emails(date_sent);
CREATE INDEX IF NOT EXISTS idx_emails_sender_email ON emails(sender_email);
CREATE INDEX IF NOT EXISTS idx_emails_has_attachments ON emails(has_attachments);
CREATE INDEX IF NOT EXISTS idx_emails_message_id ON emails(message_id);
CREATE INDEX IF NOT EXISTS idx_emails_labels_gin ON emails USING GIN(labels);

CREATE INDEX IF NOT EXISTS idx_analysis_category ON email_analysis(category);
CREATE INDEX IF NOT EXISTS idx_analysis_deletion_candidate ON email_analysis(deletion_candidate);
CREATE INDEX IF NOT EXISTS idx_analysis_model_version ON email_analysis(ai_model, analysis_version);
CREATE INDEX IF NOT EXISTS idx_analysis_processing_tier ON email_analysis(processing_tier);

CREATE INDEX IF NOT EXISTS idx_sync_sessions_status ON sync_sessions(status);
CREATE INDEX IF NOT EXISTS idx_api_usage_date_hour ON api_usage_log(date, hour);
CREATE INDEX IF NOT EXISTS idx_learned_patterns_type ON learned_patterns(pattern_type);

-- Useful views for common queries
CREATE OR REPLACE VIEW deletion_candidates AS
SELECT 
    e.id,
    e.message_id,
    e.subject,
    e.sender,
    e.sender_email,
    e.date_sent,
    a.category,
    a.summary,
    a.fraud_score,
    a.deletion_reason,
    a.confidence_score,
    a.processing_tier,
    a.analyzed_at
FROM emails e
JOIN email_analysis a ON e.id = a.email_id
WHERE a.deletion_candidate = true
ORDER BY e.date_sent ASC;

CREATE OR REPLACE VIEW daily_digest_emails AS  
SELECT 
    e.id,
    e.message_id,
    e.subject,
    e.sender,
    e.sender_email,
    e.date_sent,
    a.category,
    a.summary,
    a.importance_score,
    a.fraud_flags,
    a.fraud_score
FROM emails e
LEFT JOIN email_analysis a ON e.id = a.email_id
WHERE e.date_sent >= CURRENT_DATE - INTERVAL '2 days'
ORDER BY e.date_sent DESC;

CREATE OR REPLACE VIEW processing_performance AS
SELECT 
    a.processing_tier,
    a.ai_model,
    COUNT(*) as emails_processed,
    AVG(a.processing_time_ms) as avg_processing_time_ms,
    AVG(a.confidence_score) as avg_confidence,
    COUNT(*) FILTER (WHERE a.deletion_candidate = true) as deletion_candidates
FROM email_analysis a
GROUP BY a.processing_tier, a.ai_model
ORDER BY a.processing_tier, a.ai_model;

-- Sample queries for testing and analytics

-- Count emails by year
/*
SELECT 
    EXTRACT(YEAR FROM date_sent) as year,
    COUNT(*) as email_count
FROM emails 
WHERE date_sent IS NOT NULL
GROUP BY year 
ORDER BY year DESC;
*/

-- Deletion candidates by category
/*
SELECT 
    category,
    COUNT(*) as deletable_count,
    AVG(fraud_score) as avg_fraud_score,
    AVG(confidence_score) as avg_confidence
FROM deletion_candidates
GROUP BY category
ORDER BY deletable_count DESC;
*/

-- Top senders by email volume
/*
SELECT 
    sender_email,
    COUNT(*) as email_count,
    MIN(date_sent) as first_email,
    MAX(date_sent) as last_email,
    COUNT(*) FILTER (WHERE has_attachments = true) as emails_with_attachments
FROM emails 
WHERE sender_email IS NOT NULL
GROUP BY sender_email
HAVING COUNT(*) > 10
ORDER BY email_count DESC
LIMIT 20;
*/

-- Processing tier efficiency
/*
SELECT 
    processing_tier,
    COUNT(*) as emails_processed,
    AVG(processing_time_ms) as avg_time_ms,
    AVG(confidence_score) as avg_confidence,
    ROUND(COUNT(*) FILTER (WHERE deletion_candidate = true) * 100.0 / COUNT(*), 1) as deletion_rate_pct
FROM email_analysis 
GROUP BY processing_tier
ORDER BY processing_tier;
*/

-- Adaptive learning progress over time
/*
SELECT 
    batch_number,
    tier0_percentage,
    tier1_percentage,
    tier2_percentage,
    tier3_percentage,
    patterns_learned,
    processing_time_minutes
FROM batch_performance 
ORDER BY batch_number;
*/

-- Storage analysis
/*
SELECT 
    EXTRACT(YEAR FROM date_sent) as year,
    COUNT(*) as email_count,
    SUM(size_estimate_bytes) / 1024 / 1024 as total_mb,
    AVG(size_estimate_bytes) as avg_bytes_per_email,
    COUNT(*) FILTER (WHERE has_attachments = true) as emails_with_attachments
FROM emails 
WHERE date_sent IS NOT NULL AND size_estimate_bytes IS NOT NULL
GROUP BY year
ORDER BY year DESC;
*/

-- Success message
SELECT 'Marin email database schema created successfully!' as status;
