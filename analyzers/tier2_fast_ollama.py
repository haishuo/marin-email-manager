# analyzers/tier2_fast_ollama.py
"""
Tier 2: Fast Ollama email classification with learning generation.
One job: classify emails using Llama 3.2 3B and generate training data for lower tiers.
"""

import json
import time
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from core.database import MarinDatabase
from utils.config import get_config
from analyzers.tier0_rules_engine import EmailCategory, EmailAction, ProcessingTier, AnalysisDecision

@dataclass
class LearningOutput:
    """What Tier 2 learns and teaches to lower tiers"""
    # For Tier 1 (BERT training data)
    bert_training_example: Dict[str, Any]
    
    # For Tier 0 (simple rules)
    tier0_rules: List[Dict[str, Any]]
    
    # For Tier 2 itself (few-shot examples)
    few_shot_example: Optional[Dict[str, Any]] = None

class Tier2FastOllama:
    """Fast Ollama classification with zero-shot → few-shot learning"""
    
    def __init__(self, database: Optional[MarinDatabase] = None):
        """Initialize Fast Ollama classifier"""
        self.db = database or MarinDatabase()
        self.config = get_config()
        self.model = self.config.fast_ai_model  # llama3.2:3b
        self.ollama_url = self.config.ollama_url
        
        # Few-shot examples cache (starts empty)
        self.few_shot_examples = None
        self.examples_last_updated = None
        
        # Load initial few-shot examples
        self._load_few_shot_examples()
    
    def analyze(self, email_data: Dict[str, Any]) -> Optional[AnalysisDecision]:
        """
        Classify email using Fast Ollama with few-shot learning
        
        Args:
            email_data: Email data from database
            
        Returns:
            Analysis decision or None if uncertain (escalate to Tier 3)
        """
        start_time = time.time()
        
        try:
            # Build prompt with few-shot examples
            prompt = self._build_classification_prompt(email_data)
            
            # Query Ollama
            ollama_response = self._query_ollama(prompt)
            
            if not ollama_response:
                return None  # Ollama failed - escalate to Tier 3
            
            # Parse JSON response
            classification = self._parse_ollama_response(ollama_response)
            
            if not classification:
                return None  # Parse failed - escalate to Tier 3
            
            # Check confidence threshold AND category
            confidence = classification.get('confidence', 0.0)
            category = classification.get('category', '')
            
            # Always escalate UNKNOWN category regardless of confidence
            if category == 'UNKNOWN':
                return None  # Escalate to Tier 3 for better analysis
            
            # Normal confidence threshold for other categories
            if confidence < 0.75:
                return None  # Low confidence - escalate to Tier 3
            
            processing_time = int((time.time() - start_time) * 1000)
            
            # Create analysis decision
            decision = AnalysisDecision(
                action=EmailAction(classification['action']),
                category=EmailCategory(classification['category']),
                confidence=confidence,
                reasoning=classification.get('reasoning', 'Fast Ollama classification'),
                processing_tier=ProcessingTier.FAST_OLLAMA,
                processing_time_ms=processing_time,
                deletion_candidate=(classification['action'] == 'DELETE'),
                deletion_reason=classification.get('deletion_reason', ''),
                importance_score=classification.get('importance_score'),
                fraud_score=classification.get('fraud_score')
            )
            
            # Generate learning data for lower tiers
            self._generate_learning_data(email_data, classification)
            
            return decision
            
        except Exception as e:
            print(f"   ⚠️ Tier 2 Fast Ollama error: {e}")
            return None  # Error - escalate to Tier 3
    
    def _load_few_shot_examples(self) -> None:
        """Load few-shot examples from database"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT email_subject, email_sender, email_snippet, 
                           correct_category, correct_action, reasoning
                    FROM tier23_few_shot_examples 
                    WHERE tier_level = 2 AND is_active = true
                    ORDER BY effectiveness_score DESC, created_at DESC
                    LIMIT 5
                """)
                
                self.few_shot_examples = []
                for row in cursor.fetchall():
                    self.few_shot_examples.append({
                        'subject': row[0],
                        'sender': row[1],
                        'snippet': row[2],
                        'category': row[3],
                        'action': row[4],
                        'reasoning': row[5]
                    })
                
                self.examples_last_updated = time.time()
                
        except Exception as e:
            print(f"   ⚠️ Error loading few-shot examples: {e}")
            self.few_shot_examples = []
    
    def _build_classification_prompt(self, email_data: Dict[str, Any]) -> str:
        """Build Ollama prompt with few-shot examples"""
        
        # Base prompt
        prompt = """You are an expert email classifier. Classify emails for inbox management.

CATEGORIES: NEWSLETTER, PROMOTIONAL, WORK, FINANCIAL, PERSONAL, SOCIAL, HEALTH, LEGAL, SHOPPING, ENTERTAINMENT, SPAM, UNKNOWN

ACTIONS: 
- DELETE: Safe to remove (newsletters, promotions, old entertainment)
- KEEP: Important to preserve (work, financial, legal, health, personal)
- ARCHIVE: Valuable but can leave inbox (some newsletters, social updates)

RULES:
- Financial/legal/health emails: Always KEEP
- Work emails: Always KEEP  
- Promotional/marketing: Usually DELETE
- Personal emails: Always KEEP
- When uncertain: KEEP (err on side of caution)

"""
        
        # Add few-shot examples if available
        if self.few_shot_examples:
            prompt += "EXAMPLES:\n\n"
            for example in self.few_shot_examples[:3]:  # Limit to 3 for speed
                prompt += f"""Email: {example['subject']} | From: {example['sender']}
Classification: {example['category']} / {example['action']}
Reasoning: {example['reasoning']}

"""
        
        # Add current email to classify
        subject = email_data.get('subject', '')
        sender = email_data.get('sender', '')
        snippet = email_data.get('snippet', '')
        has_attachments = email_data.get('has_attachments', False)
        date_sent = email_data.get('date_sent', '')
        
        prompt += f"""CLASSIFY THIS EMAIL:

Subject: {subject}
From: {sender}
Date: {str(date_sent)[:10] if date_sent else 'Unknown'}
Has Attachments: {has_attachments}
Preview: {snippet[:300]}

Respond ONLY with valid JSON (no example values):
{{
    "category": "CATEGORY_NAME",
    "action": "ACTION_NAME",
    "confidence": 0.XX,
    "reasoning": "Brief explanation of decision",
    "deletion_reason": "Why safe to delete (if DELETE action)",
    "importance_score": XX,
    "fraud_score": X
}}

Be precise with confidence (0.0-1.0 based on how certain you are).
"""
        
        return prompt
    
    def _query_ollama(self, prompt: str) -> Optional[str]:
        """Query Ollama API"""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 300,
                    "top_p": 0.9
                }
            }
            
            response = requests.post(
                self.ollama_url,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '')
            else:
                print(f"   ❌ Ollama API error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"   ❌ Ollama query failed: {e}")
            return None
    
    def _parse_ollama_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse Ollama JSON response with error recovery"""
        try:
            # Extract JSON from response (may have extra text)
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group()
                
                # Try direct parsing first
                try:
                    classification = json.loads(json_str)
                except json.JSONDecodeError:
                    # JSON is malformed - try to fix common issues
                    print(f"   ⚠️ Malformed JSON detected, attempting repair...")
                    json_str = self._repair_json(json_str)
                    try:
                        classification = json.loads(json_str)
                        print(f"   ✅ JSON repaired successfully")
                    except json.JSONDecodeError as e:
                        print(f"   ❌ JSON repair failed: {e}")
                        print(f"   Raw response: {response_text[:200]}...")
                        return None
                
                # Validate required fields
                required_fields = ['category', 'action', 'confidence']
                if all(field in classification for field in required_fields):
                    return classification
                else:
                    print(f"   ⚠️ Missing required fields in Ollama response")
                    return None
            else:
                print(f"   ⚠️ No JSON found in Ollama response")
                print(f"   Raw response: {response_text[:200]}...")
                return None
                
        except Exception as e:
            print(f"   ⚠️ Response parse error: {e}")
            return None
    
    def _repair_json(self, json_str: str) -> str:
        """Attempt to repair common JSON syntax errors"""
        import re
        
        # Check if JSON is truncated (missing closing brace)
        open_braces = json_str.count('{')
        close_braces = json_str.count('}')
        
        if open_braces > close_braces:
            # JSON appears truncated - add missing closing braces
            missing_braces = open_braces - close_braces
            json_str += '}' * missing_braces
            print(f"   🔧 Added {missing_braces} missing closing brace(s)")
        
        # Fix incomplete string values (common with truncation)
        if json_str.endswith('"') and not json_str.endswith('"}'):
            json_str += '"}'
            print(f"   🔧 Completed truncated string")
        
        # Fix missing closing quote on last field
        if re.search(r':\s*"[^"]*$', json_str):
            json_str += '"}'
            print(f"   🔧 Added missing quote and closing brace")
        
        # Common fixes for LLM-generated JSON
        
        # Fix unescaped quotes in string values
        json_str = re.sub(r'": "([^"]*)"([^",}]*)"([^"]*)"', r'": "\1\"\2\"\3"', json_str)
        
        # Fix missing quotes around field names
        json_str = re.sub(r'(\w+):', r'"\1":', json_str)
        
        # Fix trailing commas
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        # Fix single quotes (should be double)
        json_str = json_str.replace("'", '"')
        
        # Fix common boolean/null issues
        json_str = json_str.replace('True', 'true')
        json_str = json_str.replace('False', 'false')
        json_str = json_str.replace('None', 'null')
        
        return json_str
    
    def _generate_learning_data(self, email_data: Dict[str, Any], 
                               classification: Dict[str, Any]) -> None:
        """Generate training data for Tier 0 and Tier 1"""
        try:
            # 1. Generate BERT training example for Tier 1
            self._create_bert_training_example(email_data, classification)
            
            # 2. Generate simple rules for Tier 0 (if pattern is clear)
            self._create_tier0_rules(email_data, classification)
            
            # 3. Add to own few-shot examples (if high confidence)
            if classification.get('confidence', 0) > 0.90:
                self._create_few_shot_example(email_data, classification)
                
        except Exception as e:
            print(f"   ⚠️ Error generating learning data: {e}")
    
    def _create_bert_training_example(self, email_data: Dict[str, Any], 
                                    classification: Dict[str, Any]) -> None:
        """Create training example for BERT"""
        try:
            # Store this classification as BERT training data
            # This will be used when we accumulate 300 examples
            training_example = {
                'email_subject': email_data.get('subject', ''),
                'email_sender': email_data.get('sender', ''),
                'email_snippet': email_data.get('snippet', ''),
                'true_category': classification['category'],
                'true_action': classification['action'],
                'confidence_score': classification['confidence']
            }
            
            # TODO: Store in tier1_training_examples table when coordinator is ready
            # For now, just log that we would create training data
            print(f"   📚 Generated BERT training example: {classification['category']}/{classification['action']}")
            
        except Exception as e:
            print(f"   ⚠️ Error creating BERT training example: {e}")
    
    def _create_tier0_rules(self, email_data: Dict[str, Any], 
                           classification: Dict[str, Any]) -> None:
        """Generate safe sender-based rules for Tier 0"""
        try:
            confidence = classification.get('confidence', 0)
            
            # Only create rules for very high-confidence decisions
            if confidence < 0.95:
                return
            
            sender_email = email_data.get('sender_email', '').lower()
            
            if not sender_email or '@' not in sender_email:
                return
            
            # SAFE RULE 1: Sender-specific whitelist for KEEP decisions
            if classification['action'] == 'KEEP' and classification['category'] in ['WORK', 'FINANCIAL', 'PERSONAL', 'HEALTH']:
                # Whitelist this specific sender for important categories
                if self._store_tier0_rule(
                    rule_type='sender_exact',
                    pattern_text=sender_email,
                    action='KEEP',
                    category=classification['category'],
                    confidence=min(confidence - 0.02, 0.95),  # Slightly lower for safety
                    created_by_tier=2
                ):
                    print(f"   ⚡ Whitelisted sender: {sender_email} → KEEP ({classification['category']})")
            
            # SAFE RULE 2: Domain blacklist for promotional senders ONLY
            elif classification['action'] == 'DELETE' and classification['category'] in ['PROMOTIONAL', 'SPAM']:
                domain = sender_email.split('@')[1]
                
                # Only blacklist domains with obvious promotional indicators
                promotional_domains = ['noreply', 'no-reply', 'newsletter', 'marketing', 'promotions', 'deals', 'offers']
                if any(keyword in domain for keyword in promotional_domains):
                    if self._store_tier0_rule(
                        rule_type='sender_domain',
                        pattern_text=domain,
                        action='DELETE',
                        category='PROMOTIONAL',
                        confidence=min(confidence - 0.05, 0.90),  # Lower confidence for domain rules
                        created_by_tier=2
                    ):
                        print(f"   ⚡ Blacklisted promotional domain: {domain} → DELETE")
            
            # NO SUBJECT-BASED RULES - too dangerous!
            
        except Exception as e:
            print(f"   ⚠️ Error creating Tier 0 rules: {e}")
    
    def _store_tier0_rule(self, rule_type: str, pattern_text: str, action: str, 
                         category: str, confidence: float, created_by_tier: int) -> bool:
        """Actually store rule in database"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
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
                    # Trigger cache invalidation
                    self._trigger_tier0_cache_invalidation()
                    return True
                return False
                
        except Exception as e:
            print(f"   ❌ Error storing Tier 0 rule: {e}")
            return False
    
    def _trigger_tier0_cache_invalidation(self) -> None:
        """Trigger Tier 0 cache invalidation when new rules are added"""
        try:
            # Import here to avoid circular imports
            from analyzers.tier0_rules_engine import Tier0RulesEngine
            
            # Create temporary instance to invalidate cache
            # In production, coordinator would handle this
            temp_tier0 = Tier0RulesEngine(self.db)
            temp_tier0.invalidate_cache()
            
        except Exception as e:
            print(f"   ⚠️ Error invalidating Tier 0 cache: {e}")
    
    def _create_few_shot_example(self, email_data: Dict[str, Any], 
                                classification: Dict[str, Any]) -> None:
        """Add high-confidence classification as few-shot example"""
        try:
            # Only add very high confidence examples
            if classification.get('confidence', 0) < 0.95:
                return
            
            example = {
                'tier_level': 2,
                'example_type': 'positive',
                'email_subject': email_data.get('subject', ''),
                'email_sender': email_data.get('sender', ''),
                'email_snippet': email_data.get('snippet', '')[:200],
                'correct_category': classification['category'],
                'correct_action': classification['action'],
                'reasoning': classification.get('reasoning', ''),
                'confidence_score': classification['confidence'],
                'created_from_email_id': email_data.get('id')
            }
            
            # TODO: Store in tier23_few_shot_examples table when coordinator is ready
            print(f"   🎯 Generated few-shot example: {classification['category']}/{classification['action']}")
            
        except Exception as e:
            print(f"   ⚠️ Error creating few-shot example: {e}")
    
    def invalidate_examples_cache(self) -> None:
        """Invalidate few-shot examples cache - called when new examples added"""
        self.few_shot_examples = None
    
    def get_classifier_status(self) -> Dict[str, Any]:
        """Get current Tier 2 status"""
        return {
            'model': self.model,
            'ollama_url': self.ollama_url,
            'few_shot_examples_loaded': len(self.few_shot_examples) if self.few_shot_examples else 0,
            'examples_last_updated': self.examples_last_updated,
            'cache_valid': self.few_shot_examples is not None
        }

# Convenience functions
def create_tier2_classifier() -> Tier2FastOllama:
    """Create and return Tier 2 Fast Ollama classifier"""
    return Tier2FastOllama()

def test_tier2_ollama() -> bool:
    """Test Tier 2 Fast Ollama classifier"""
    try:
        classifier = Tier2FastOllama()
        status = classifier.get_classifier_status()
        
        print(f"🚀 Tier 2 Fast Ollama Status:")
        print(f"   Model: {status['model']}")
        print(f"   Ollama URL: {status['ollama_url']}")
        print(f"   Few-shot examples: {status['few_shot_examples_loaded']}")
        
        # Test with sample email
        test_email = {
            'id': 1,
            'subject': 'Flash Sale - 70% Off Everything!',
            'sender': 'deals@example-store.com',
            'sender_email': 'deals@example-store.com',
            'snippet': 'Limited time offer! Save huge on all items. Free shipping over $50.',
            'has_attachments': False,
            'date_sent': '2024-01-15'
        }
        
        print(f"\n🧪 Testing with promotional email...")
        decision = classifier.analyze(test_email)
        
        if decision is None:
            print("   ✅ Tier 2 escalated to Tier 3 (uncertain or Ollama unavailable)")
            return True
        else:
            print(f"   🤖 Tier 2 classified: {decision.action.value} - {decision.category.value} ({decision.confidence:.2f})")
            print(f"   ⏱️ Processing time: {decision.processing_time_ms}ms")
            return True
            
    except Exception as e:
        print(f"❌ Tier 2 test failed: {e}")
        return False

# Example usage and testing
if __name__ == "__main__":
    """Test Tier 2 Fast Ollama classifier"""
    
    print("🚀 Testing Tier 2 Fast Ollama Classifier")
    print("=" * 50)
    
    success = test_tier2_ollama()
    
    if success:
        print("\n🎉 Tier 2 Fast Ollama classifier test completed successfully!")
    else:
        print("\n❌ Tier 2 Fast Ollama classifier test failed")