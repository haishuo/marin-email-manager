-- Marin v2.0 - Simplified Database Schema
-- New architecture: Tier 0 simple rules + BERT personalization + optional human review

-- Clean slate: Drop all old learning tables
DROP TABLE IF EXISTS tier0_rules CASCADE;
DROP TABLE IF EXISTS tier1_training_batches CASCADE;
DROP TABLE IF EXISTS tier1_training_examples CASCADE;
DROP TABLE IF EXISTS tier23_few_shot_examples CASCADE;
DROP TABLE IF EXISTS learning_progress CASCADE;
DROP TABLE IF EXISTS tier_performance CASCADE;
DROP TABLE IF EXISTS learning_feedback CASCADE;

-- Keep core emails table (no changes needed)
-- Keep email_analysis table but modify it

-- Add new columns to email_analysis for v2.0
ALTER TABLE email_analysis ADD COLUMN IF NOT EXISTS training_phase VARCHAR(20) DEFAULT 'production';
ALTER TABLE email_analysis ADD COLUMN IF NOT EXISTS classified_by VARCHAR(20) DEFAULT 'unknown';
ALTER TABLE email_analysis ADD COLUMN IF NOT EXISTS human_validated BOOLEAN DEFAULT FALSE;
ALTER TABLE email_analysis ADD COLUMN IF NOT EXISTS needs_retraining BOOLEAN DEFAULT FALSE;

-- 1. TIER 0: Simple Rules (Whitelist/Blacklist only)
CREATE TABLE tier0_simple_rules (
    id SERIAL PRIMARY KEY,
    rule_type VARCHAR(20) NOT NULL,        -- 'domain', 'email', 'exact_subject'
    pattern VARCHAR(255) NOT NULL,         -- 'bankofamerica.com', 'alerts@bank.com'
    action VARCHAR(10) NOT NULL,           -- 'KEEP' or 'DELETE'
    category VARCHAR(50),                  -- 'FINANCIAL', 'WORK', etc. (optional)
    created_during_training BOOLEAN DEFAULT TRUE,
    created_by_human BOOLEAN DEFAULT TRUE,
    times_matched INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used TIMESTAMP WITH TIME ZONE,
    
    UNIQUE(rule_type, pattern),
    CHECK (action IN ('KEEP', 'DELETE')),
    CHECK (rule_type IN ('domain', 'email', 'exact_subject'))
);

-- 2. TRAINING SESSION: Track training progress
CREATE TABLE training_sessions (
    id SERIAL PRIMARY KEY,
    session_type VARCHAR(20) NOT NULL,     -- 'initial', 'retraining', 'personalization'
    target_emails INTEGER NOT NULL,        -- How many emails to process
    emails_processed INTEGER DEFAULT 0,
    emails_human_validated INTEGER DEFAULT 0,
    rules_created INTEGER DEFAULT 0,
    bert_examples_created INTEGER DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'in_progress', -- 'in_progress', 'completed', 'paused'
    
    CHECK (session_type IN ('initial', 'retraining', 'personalization')),
    CHECK (status IN ('in_progress', 'completed', 'paused', 'failed'))
);

-- 3. BERT TRAINING EXAMPLES: Human-validated examples for BERT personalization
CREATE TABLE bert_training_examples (
    id SERIAL PRIMARY KEY,
    training_session_id INTEGER REFERENCES training_sessions(id),
    email_id INTEGER REFERENCES emails(id),
    email_text TEXT NOT NULL,              -- Subject + sender + snippet for BERT
    true_category VARCHAR(50) NOT NULL,
    true_action VARCHAR(10) NOT NULL,
    human_reasoning TEXT,
    confidence DECIMAL(3,2) DEFAULT 1.0,   -- Human decisions are confident
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    used_for_training BOOLEAN DEFAULT FALSE,
    
    CHECK (true_action IN ('KEEP', 'DELETE', 'ARCHIVE'))
);

-- 4. BERT MODEL VERSIONS: Track BERT model deployments
CREATE TABLE bert_model_versions (
    id SERIAL PRIMARY KEY,
    version_name VARCHAR(50) NOT NULL,     -- 'base_v1.0', 'personalized_v1.1'
    model_type VARCHAR(20) NOT NULL,       -- 'base', 'personalized'
    training_examples_count INTEGER,
    validation_accuracy DECIMAL(4,2),
    model_file_path TEXT,
    is_active BOOLEAN DEFAULT FALSE,
    base_model_id INTEGER REFERENCES bert_model_versions(id), -- For personalized models
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deployed_at TIMESTAMP WITH TIME ZONE,
    
    CHECK (model_type IN ('base', 'personalized'))
);

-- 5. HUMAN REVIEW QUEUE: Emails waiting for human classification
CREATE TABLE human_review_queue (
    id SERIAL PRIMARY KEY,
    email_id INTEGER REFERENCES emails(id),
    added_by VARCHAR(20) NOT NULL,         -- 'bert_uncertain', 'llm_suggestion', 'manual'
    bert_suggestion JSONB,                 -- BERT's uncertain suggestion
    llm_suggestion JSONB,                  -- LLM suggestion (training phase only)
    priority INTEGER DEFAULT 5,            -- 1=high, 5=normal, 10=low
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reviewed_by VARCHAR(50),               -- 'human', 'system'
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'reviewed', 'skipped'
    
    CHECK (priority BETWEEN 1 AND 10),
    CHECK (status IN ('pending', 'reviewed', 'skipped'))
);

-- 6. SYSTEM SETTINGS: Configuration and state
CREATE TABLE system_settings (
    id SERIAL PRIMARY KEY,
    setting_key VARCHAR(50) UNIQUE NOT NULL,
    setting_value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert initial system settings
INSERT INTO system_settings (setting_key, setting_value, description) VALUES
('system_phase', 'setup', 'Current system phase: setup, training, production'),
('bert_base_model_path', '', 'Path to the base BERT model'),
('current_bert_version', '', 'Currently active BERT model version'),
('training_target_emails', '1000', 'Target emails for initial training'),
('retraining_threshold', '300', 'Human classifications needed to trigger retraining'),
('bert_confidence_threshold', '0.85', 'BERT confidence threshold for auto-classification');

-- Indexes for performance
CREATE INDEX idx_simple_rules_pattern ON tier0_simple_rules(rule_type, pattern);
CREATE INDEX idx_simple_rules_active ON tier0_simple_rules(created_at) WHERE times_matched > 0;

CREATE INDEX idx_training_examples_session ON bert_training_examples(training_session_id);
CREATE INDEX idx_training_examples_category ON bert_training_examples(true_category);
CREATE INDEX idx_training_examples_unused ON bert_training_examples(used_for_training) WHERE used_for_training = FALSE;

CREATE INDEX idx_human_queue_status ON human_review_queue(status, priority);
CREATE INDEX idx_human_queue_pending ON human_review_queue(added_at) WHERE status = 'pending';

CREATE INDEX idx_email_analysis_phase ON email_analysis(training_phase, classified_by);
CREATE INDEX idx_email_analysis_retraining ON email_analysis(needs_retraining) WHERE needs_retraining = TRUE;

-- Useful views for monitoring
CREATE OR REPLACE VIEW training_progress AS
SELECT 
    ts.id,
    ts.session_type,
    ts.target_emails,
    ts.emails_processed,
    ts.emails_human_validated,
    ts.rules_created,
    ts.bert_examples_created,
    ROUND((ts.emails_processed::DECIMAL / ts.target_emails * 100), 1) as progress_percentage,
    ts.status,
    ts.started_at,
    ts.completed_at
FROM training_sessions ts
ORDER BY ts.started_at DESC;

CREATE OR REPLACE VIEW tier0_rules_summary AS
SELECT 
    rule_type,
    action,
    COUNT(*) as rule_count,
    SUM(times_matched) as total_matches,
    AVG(times_matched) as avg_matches_per_rule
FROM tier0_simple_rules 
GROUP BY rule_type, action
ORDER BY rule_type, action;

CREATE OR REPLACE VIEW bert_training_summary AS
SELECT 
    ts.session_type,
    COUNT(bte.id) as training_examples,
    COUNT(DISTINCT bte.true_category) as categories_covered,
    COUNT(CASE WHEN bte.used_for_training THEN 1 END) as examples_used,
    COUNT(CASE WHEN NOT bte.used_for_training THEN 1 END) as examples_pending
FROM training_sessions ts
LEFT JOIN bert_training_examples bte ON ts.id = bte.training_session_id
GROUP BY ts.session_type
ORDER BY ts.session_type;

CREATE OR REPLACE VIEW human_queue_summary AS
SELECT 
    status,
    added_by,
    COUNT(*) as email_count,
    AVG(priority) as avg_priority,
    MIN(added_at) as oldest_email,
    MAX(added_at) as newest_email
FROM human_review_queue 
GROUP BY status, added_by
ORDER BY status, added_by;

-- Sample queries for testing the new schema

-- Check training progress
/*
SELECT * FROM training_progress;
*/

-- Check Tier 0 rules
/*
SELECT * FROM tier0_rules_summary;
*/

-- Check BERT training data
/*
SELECT * FROM bert_training_summary;
*/

-- Check human review queue
/*
SELECT * FROM human_queue_summary;
*/

-- Get emails needing human review
/*
SELECT 
    e.id,
    e.subject,
    e.sender_email,
    hrq.added_by,
    hrq.priority,
    hrq.added_at
FROM human_review_queue hrq
JOIN emails e ON hrq.email_id = e.id
WHERE hrq.status = 'pending'
ORDER BY hrq.priority, hrq.added_at;
*/

-- Check system status
/*
SELECT 
    setting_key,
    setting_value,
    description
FROM system_settings
ORDER BY setting_key;
*/

-- Success message
SELECT 'Marin v2.0 simplified database schema created successfully!' as status,
       'Ready for new training-focused architecture' as message;