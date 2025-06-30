-- Marin Learning System Database Updates
-- Additional tables and columns for tiered AI learning system

-- Add learning tracking columns to existing email_analysis table
ALTER TABLE email_analysis ADD COLUMN IF NOT EXISTS used_for_training BOOLEAN DEFAULT FALSE;
ALTER TABLE email_analysis ADD COLUMN IF NOT EXISTS training_batch_id INTEGER;
ALTER TABLE email_analysis ADD COLUMN IF NOT EXISTS tier_decision_confidence DECIMAL(3,2); -- 0.00-1.00

-- Tier 0: Learned rules storage
CREATE TABLE IF NOT EXISTS tier0_rules (
    id SERIAL PRIMARY KEY,
    rule_type VARCHAR(50) NOT NULL,           -- 'sender_domain', 'subject_pattern', 'sender_exact'
    pattern_text TEXT NOT NULL,               -- The actual pattern (e.g., 'noreply@groupon.com')
    action VARCHAR(20) NOT NULL,              -- 'DELETE', 'KEEP', 'ARCHIVE'
    category VARCHAR(50) NOT NULL,            -- Email category
    confidence DECIMAL(3,2) NOT NULL,         -- How confident we are in this rule
    learned_from_emails INTEGER DEFAULT 1,    -- How many emails contributed to this rule
    times_matched INTEGER DEFAULT 0,          -- How many times this rule has been applied
    times_correct INTEGER DEFAULT 0,          -- How many times it was correct (when checked)
    first_learned TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,           -- Can be disabled if performance drops
    created_by_tier INTEGER NOT NULL,        -- Which tier created this rule (2, 3, or 4)
    
    UNIQUE(rule_type, pattern_text, action)
);

-- Tier 1: BERT training batches and model versions
CREATE TABLE IF NOT EXISTS tier1_training_batches (
    id SERIAL PRIMARY KEY,
    batch_number INTEGER UNIQUE NOT NULL,
    total_examples INTEGER NOT NULL,
    training_started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    training_completed_at TIMESTAMP WITH TIME ZONE,
    model_version VARCHAR(50),                -- e.g., 'bert_v1.2'
    training_accuracy DECIMAL(4,2),          -- Training accuracy percentage
    validation_accuracy DECIMAL(4,2),        -- Validation accuracy percentage
    model_file_path TEXT,                     -- Where the trained model is stored
    is_active BOOLEAN DEFAULT FALSE,          -- Is this the currently active model
    training_status VARCHAR(20) DEFAULT 'pending' -- 'pending', 'training', 'completed', 'failed'
);

-- Track which emails were used in which training batch
CREATE TABLE IF NOT EXISTS tier1_training_examples (
    id SERIAL PRIMARY KEY,
    training_batch_id INTEGER REFERENCES tier1_training_batches(id),
    email_analysis_id INTEGER REFERENCES email_analysis(id),
    email_subject TEXT,                       -- Copy for training (may truncate email later)
    email_sender TEXT,
    email_snippet TEXT,
    true_category VARCHAR(50),                -- What it was classified as
    true_action VARCHAR(20),                  -- What action was decided
    split_type VARCHAR(10) DEFAULT 'train'   -- 'train', 'validation', 'test'
);

-- Tier 2/3: Few-shot learning examples and prompt evolution
CREATE TABLE IF NOT EXISTS tier23_few_shot_examples (
    id SERIAL PRIMARY KEY,
    tier_level INTEGER NOT NULL,             -- 2 or 3
    example_type VARCHAR(20) NOT NULL,       -- 'positive', 'negative', 'edge_case'
    email_subject TEXT,
    email_sender TEXT,
    email_snippet TEXT,
    email_body_preview TEXT,                 -- First 500 chars (tier 3 only)
    correct_category VARCHAR(50),
    correct_action VARCHAR(20),
    reasoning TEXT,                          -- Why this classification is correct
    confidence_score DECIMAL(3,2),
    times_used_in_prompt INTEGER DEFAULT 0,
    effectiveness_score DECIMAL(3,2),       -- How well this example helps the model
    created_from_email_id INTEGER REFERENCES emails(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- Track global learning progress
CREATE TABLE IF NOT EXISTS learning_progress (
    id SERIAL PRIMARY KEY,
    total_classifications INTEGER DEFAULT 0,
    last_training_batch INTEGER DEFAULT 0,
    next_training_threshold INTEGER DEFAULT 300,
    tier0_rules_count INTEGER DEFAULT 0,
    tier1_model_version VARCHAR(50),
    tier23_examples_count INTEGER DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert initial learning progress record
INSERT INTO learning_progress (total_classifications, last_training_batch, next_training_threshold)
VALUES (0, 0, 300)
ON CONFLICT DO NOTHING;

-- Performance tracking for each tier
CREATE TABLE IF NOT EXISTS tier_performance (
    id SERIAL PRIMARY KEY,
    date DATE DEFAULT CURRENT_DATE,
    tier_level INTEGER NOT NULL,             -- 0, 1, 2, 3, 4
    emails_processed INTEGER DEFAULT 0,
    emails_correct INTEGER DEFAULT 0,        -- When we can verify correctness
    avg_processing_time_ms INTEGER,
    avg_confidence DECIMAL(3,2),
    escalations_to_next_tier INTEGER DEFAULT 0,
    
    UNIQUE(date, tier_level)
);

-- Learning feedback loop tracking
CREATE TABLE IF NOT EXISTS learning_feedback (
    id SERIAL PRIMARY KEY,
    email_analysis_id INTEGER REFERENCES email_analysis(id),
    feedback_type VARCHAR(20) NOT NULL,      -- 'rule_generated', 'example_added', 'training_triggered'
    tier_affected INTEGER NOT NULL,          -- Which tier was updated
    feedback_data JSONB,                     -- Specific details about what was learned
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_tier0_rules_pattern ON tier0_rules(rule_type, pattern_text);
CREATE INDEX IF NOT EXISTS idx_tier0_rules_active ON tier0_rules(is_active);
CREATE INDEX IF NOT EXISTS idx_training_batches_active ON tier1_training_batches(is_active);
CREATE INDEX IF NOT EXISTS idx_few_shot_active ON tier23_few_shot_examples(tier_level, is_active);
CREATE INDEX IF NOT EXISTS idx_email_analysis_training ON email_analysis(used_for_training, training_batch_id);

-- Useful views for monitoring
CREATE OR REPLACE VIEW tier_efficiency AS
SELECT 
    tier_level,
    SUM(emails_processed) as total_processed,
    ROUND(AVG(CASE 
        WHEN emails_processed > 0 
        THEN (emails_correct::decimal / emails_processed * 100) 
        ELSE 0 
    END), 1) as accuracy_percentage,
    AVG(avg_processing_time_ms) as avg_time_ms,
    AVG(avg_confidence) as avg_confidence
FROM tier_performance 
GROUP BY tier_level 
ORDER BY tier_level;

CREATE OR REPLACE VIEW learning_status AS
SELECT 
    lp.total_classifications,
    lp.next_training_threshold,
    lp.total_classifications % lp.next_training_threshold as progress_in_current_batch,
    lp.tier0_rules_count,
    lp.tier1_model_version,
    lp.tier23_examples_count,
    lp.last_updated,
    CASE 
        WHEN lp.total_classifications >= lp.next_training_threshold 
        THEN 'READY_FOR_TRAINING'
        ELSE 'ACCUMULATING'
    END as training_status
FROM learning_progress lp
ORDER BY lp.id DESC 
LIMIT 1;

-- Sample queries for monitoring learning progress

-- Show rule effectiveness
/*
SELECT 
    rule_type,
    pattern_text,
    action,
    times_matched,
    CASE 
        WHEN times_matched > 0 
        THEN ROUND((times_correct::decimal / times_matched * 100), 1)
        ELSE 0
    END as accuracy_percentage
FROM tier0_rules 
WHERE is_active = true 
ORDER BY times_matched DESC;
*/

-- Show training batch history
/*
SELECT 
    batch_number,
    total_examples,
    training_accuracy,
    validation_accuracy,
    is_active,
    training_completed_at
FROM tier1_training_batches 
ORDER BY batch_number DESC;
*/

-- Show tier performance over time
/*
SELECT 
    date,
    tier_level,
    emails_processed,
    ROUND(CASE 
        WHEN emails_processed > 0 
        THEN (emails_correct::decimal / emails_processed * 100)
        ELSE 0
    END, 1) as accuracy_pct,
    avg_processing_time_ms
FROM tier_performance 
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY date DESC, tier_level;
*/

COMMENT ON TABLE tier0_rules IS 'Lightning-fast pattern matching rules learned from higher tiers';
COMMENT ON TABLE tier1_training_batches IS 'BERT model training history and versions';
COMMENT ON TABLE tier23_few_shot_examples IS 'Few-shot examples for Ollama prompt engineering';
COMMENT ON TABLE learning_progress IS 'Global learning system progress tracking';
COMMENT ON TABLE tier_performance IS 'Daily performance metrics for each processing tier';
