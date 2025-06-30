# analyzers/tier0_rules_engine.py
"""
Tier 0: Lightning-fast rules-based email classification.
One job: apply learned patterns for instant email decisions.
"""

import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from core.database import MarinDatabase

class EmailCategory(Enum):
    """Email categories for classification"""
    NEWSLETTER = "NEWSLETTER"
    PROMOTIONAL = "PROMOTIONAL"
    WORK = "WORK"
    FINANCIAL = "FINANCIAL"
    PERSONAL = "PERSONAL"
    SOCIAL = "SOCIAL"
    HEALTH = "HEALTH"
    LEGAL = "LEGAL"
    SHOPPING = "SHOPPING"
    ENTERTAINMENT = "ENTERTAINMENT"
    SPAM = "SPAM"
    UNKNOWN = "UNKNOWN"

class EmailAction(Enum):
    """Actions to take on emails"""
    KEEP = "KEEP"
    DELETE = "DELETE"
    ARCHIVE = "ARCHIVE"

class ProcessingTier(Enum):
    """Processing tiers for email analysis"""
    RULES_ENGINE = 0
    BERT_CLASSIFIER = 1
    FAST_OLLAMA = 2
    DEEP_OLLAMA = 3
    HUMAN_REVIEW = 4

@dataclass
class AnalysisDecision:
    """Email analysis decision result"""
    action: EmailAction
    category: EmailCategory
    confidence: float  # 0.0 to 1.0
    reasoning: str
    processing_tier: ProcessingTier
    processing_time_ms: int
    deletion_candidate: bool = False
    deletion_reason: str = ""
    importance_score: Optional[int] = None
    fraud_score: Optional[int] = None

class Tier0RulesEngine:
    """Lightning-fast pattern matching using learned rules"""
    
    def __init__(self, database: Optional[MarinDatabase] = None):
        """Initialize rules engine with database connection"""
        self.db = database or MarinDatabase()
        self.rules_cache = None
        
        # Check for new rules immediately on initialization
        self._check_for_new_rules()
    
    def _check_for_new_rules(self) -> None:
        """Check if new rules have been added since last cache load"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*), MAX(first_learned) 
                    FROM tier0_rules 
                    WHERE is_active = true
                """)
                
                result = cursor.fetchone()
                current_count = result[0]
                latest_rule_time = result[1]
                
                # Always load rules if cache is empty
                if self.rules_cache is None:
                    if current_count > 0:
                        print(f"   📋 Loading {current_count} existing rules into Tier 0")
                        self._load_rules_from_database()
                    else:
                        print(f"   📋 No rules in database yet - Tier 0 will escalate all emails")
                        self.rules_cache = []
                
        except Exception as e:
            print(f"   ⚠️ Error checking for new rules: {e}")
            self.rules_cache = []
    
    def _load_rules_from_database(self) -> None:
        """Force reload rules from database"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, rule_type, pattern_text, action, category, confidence,
                           times_matched, times_correct
                    FROM tier0_rules 
                    WHERE is_active = true
                    ORDER BY confidence DESC, times_matched DESC
                """)
                
                self.rules_cache = []
                for row in cursor.fetchall():
                    self.rules_cache.append({
                        'id': row[0],
                        'rule_type': row[1],
                        'pattern_text': row[2],
                        'action': row[3],
                        'category': row[4],
                        'confidence': float(row[5]),
                        'times_matched': row[6],
                        'times_correct': row[7]
                    })
                
                if self.rules_cache:
                    print(f"   ✅ Loaded {len(self.rules_cache)} rules into Tier 0 cache")
                
        except Exception as e:
            print(f"   ⚠️ Error loading rules from database: {e}")
            self.rules_cache = []
        
    def analyze(self, email_data: Dict[str, Any]) -> Optional[AnalysisDecision]:
        """
        Apply learned rules for instant email classification
        
        Args:
            email_data: Email data from database
            
        Returns:
            Analysis decision or None if no rules match (escalate to Tier 1)
        """
        start_time = time.time()
        
        # Load active rules (with caching)
        rules = self._get_active_rules()
        
        # If no rules exist (initial state), escalate immediately
        if not rules:
            return None
        
        # Extract email fields for pattern matching
        sender = email_data.get('sender', '').lower()
        subject = email_data.get('subject', '').lower()
        sender_email = email_data.get('sender_email', '').lower()
        
        # Try to match against learned rules
        for rule in rules:
            match_result = self._check_rule_match(rule, sender, subject, sender_email)
            
            if match_result:
                # Update rule usage statistics
                self._update_rule_usage(rule['id'])
                
                processing_time = int((time.time() - start_time) * 1000)
                
                return AnalysisDecision(
                    action=EmailAction(rule['action']),
                    category=EmailCategory(rule['category']),
                    confidence=rule['confidence'],
                    reasoning=f"Rule match: {rule['pattern_text']} ({rule['rule_type']})",
                    processing_tier=ProcessingTier.RULES_ENGINE,
                    processing_time_ms=processing_time,
                    deletion_candidate=(rule['action'] == 'DELETE'),
                    deletion_reason=f"Learned pattern: {rule['pattern_text']}"
                )
        
        # No rules matched - escalate to Tier 1
        return None
    
    def _get_active_rules(self) -> List[Dict[str, Any]]:
        """Get active rules from database with event-driven caching"""
        try:
            # Only reload if cache was explicitly invalidated by learning events
            if self.rules_cache is None:
                self._load_rules_from_database()
            
            return self.rules_cache
                
        except Exception as e:
            print(f"   ⚠️ Error loading rules: {e}")
            return []
    
    def _check_rule_match(self, rule: Dict[str, Any], sender: str, 
                         subject: str, sender_email: str) -> bool:
        """Check if a rule matches the given email"""
        pattern = rule['pattern_text'].lower()
        rule_type = rule['rule_type']
        
        if rule_type == 'sender_domain':
            # Match domain in sender email
            return pattern in sender_email
        
        elif rule_type == 'sender_exact':
            # Exact sender match
            return pattern == sender_email
        
        elif rule_type == 'subject_pattern':
            # Subject contains pattern
            return pattern in subject
        
        elif rule_type == 'sender_pattern':
            # Sender (display name) contains pattern
            return pattern in sender
        
        else:
            # Unknown rule type - skip
            return False
    
    def _update_rule_usage(self, rule_id: int) -> None:
        """Update rule usage statistics"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE tier0_rules 
                    SET times_matched = times_matched + 1,
                        last_used = NOW()
                    WHERE id = %s
                """, (rule_id,))
                conn.commit()
        except Exception as e:
            print(f"   ⚠️ Error updating rule usage: {e}")
    
    def add_learned_rule(self, rule_type: str, pattern_text: str, 
                        action: str, category: str, confidence: float,
                        created_by_tier: int) -> bool:
        """
        Add a new learned rule from higher tiers
        
        Args:
            rule_type: Type of rule ('sender_domain', 'subject_pattern', etc.)
            pattern_text: The pattern to match
            action: Action to take ('DELETE', 'KEEP', 'ARCHIVE')
            category: Email category
            confidence: Confidence in this rule (0.0-1.0)
            created_by_tier: Which tier created this rule (2, 3, or 4)
            
        Returns:
            True if rule was added successfully
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Insert new rule (ON CONFLICT updates confidence if higher)
                cursor.execute("""
                    INSERT INTO tier0_rules 
                    (rule_type, pattern_text, action, category, confidence, 
                     learned_from_emails, created_by_tier, first_learned)
                    VALUES (%s, %s, %s, %s, %s, 1, %s, NOW())
                    ON CONFLICT (rule_type, pattern_text, action) 
                    DO UPDATE SET
                        confidence = CASE 
                            WHEN EXCLUDED.confidence > tier0_rules.confidence 
                            THEN EXCLUDED.confidence 
                            ELSE tier0_rules.confidence 
                        END,
                        learned_from_emails = tier0_rules.learned_from_emails + 1,
                        is_active = true
                    RETURNING id
                """, (rule_type, pattern_text, action, category, confidence, created_by_tier))
                
                result = cursor.fetchone()
                conn.commit()
                
                if result:
                    rule_id = result[0]
                    # Invalidate cache so new rule gets loaded on next access
                    self.invalidate_cache()
                    return True
                else:
                    return False
                    
        except Exception as e:
            print(f"   ❌ Error adding rule: {e}")
            return False
    
    def invalidate_cache(self) -> None:
        """
        Invalidate rules cache - called by learning coordinator when new rules available
        
        This is called when:
        - New rules are added by higher tiers
        - BERT retraining completes (every 300 emails)
        - Learning batch processing finishes
        """
        self.rules_cache = None
    
    def get_rules_summary(self) -> Dict[str, Any]:
        """Get summary of current rules for monitoring"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get rule counts by type and action
                cursor.execute("""
                    SELECT 
                        rule_type,
                        action,
                        COUNT(*) as rule_count,
                        AVG(confidence) as avg_confidence,
                        SUM(times_matched) as total_matches
                    FROM tier0_rules 
                    WHERE is_active = true
                    GROUP BY rule_type, action
                    ORDER BY rule_type, action
                """)
                
                rules_breakdown = []
                for row in cursor.fetchall():
                    rules_breakdown.append({
                        'rule_type': row[0],
                        'action': row[1],
                        'count': row[2],
                        'avg_confidence': float(row[3]) if row[3] else 0,
                        'total_matches': row[4]
                    })
                
                # Get total active rules
                cursor.execute("SELECT COUNT(*) FROM tier0_rules WHERE is_active = true")
                total_active = cursor.fetchone()[0]
                
                # Get most effective rules
                cursor.execute("""
                    SELECT rule_type, pattern_text, action, times_matched, confidence
                    FROM tier0_rules 
                    WHERE is_active = true AND times_matched > 0
                    ORDER BY times_matched DESC
                    LIMIT 10
                """)
                
                top_rules = []
                for row in cursor.fetchall():
                    top_rules.append({
                        'rule_type': row[0],
                        'pattern': row[1],
                        'action': row[2],
                        'matches': row[3],
                        'confidence': float(row[4])
                    })
                
                return {
                    'total_active_rules': total_active,
                    'rules_breakdown': rules_breakdown,
                    'top_performing_rules': top_rules
                }
                
        except Exception as e:
            return {'error': f'Failed to get rules summary: {e}'}

# Convenience functions
def create_tier0_engine() -> Tier0RulesEngine:
    """Create and return Tier 0 rules engine"""
    return Tier0RulesEngine()

def test_tier0_empty() -> bool:
    """Test that Tier 0 correctly handles empty rules (escalates everything)"""
    try:
        engine = Tier0RulesEngine()
        
        # Test email data
        test_email = {
            'sender': 'John Doe <john@example.com>',
            'subject': 'Test email subject',
            'sender_email': 'john@example.com'
        }
        
        # Should return None (escalate) since no rules exist
        decision = engine.analyze(test_email)
        
        if decision is None:
            print("✅ Tier 0 correctly escalates when no rules exist")
            return True
        else:
            print(f"❌ Tier 0 made unexpected decision: {decision}")
            return False
            
    except Exception as e:
        print(f"❌ Tier 0 test failed: {e}")
        return False

# Example usage and testing
if __name__ == "__main__":
    """Test Tier 0 rules engine"""
    
    print("⚡ Testing Tier 0 Rules Engine")
    print("=" * 50)
    
    # Test empty rules behavior
    success = test_tier0_empty()
    
    if success:
        # Show rules summary (should be empty)
        engine = create_tier0_engine()
        summary = engine.get_rules_summary()
        
        print(f"\n📊 Rules Summary:")
        print(f"   Total active rules: {summary.get('total_active_rules', 0)}")
        
        if summary.get('total_active_rules', 0) == 0:
            print("   (No rules learned yet - system will escalate all emails)")
        
        print("\n🎉 Tier 0 engine test completed successfully!")
    else:
        print("\n❌ Tier 0 engine test failed")
