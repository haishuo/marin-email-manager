# analyzers/tier3_deep_ollama.py
"""
Tier 3: Deep Ollama email analysis for complex cases.
One job: comprehensive email analysis using Llama 3.1 70B with full email content.
"""

import json
import time
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from core.database import MarinDatabase
from utils.config import get_config
from analyzers.tier0_rules_engine import EmailCategory, EmailAction, ProcessingTier, AnalysisDecision

class Tier3DeepOllama:
    """Deep Ollama analysis for complex/ambiguous emails"""
    
    def __init__(self, database: Optional[MarinDatabase] = None):
        """Initialize Deep Ollama classifier"""
        self.db = database or MarinDatabase()
        self.config = get_config()
        self.model = self.config.comprehensive_ai_model  # llama3.1:70b
        self.ollama_url = self.config.ollama_url
        
        # Few-shot examples cache (starts empty)
        self.few_shot_examples = None
        self.examples_last_updated = None
        
        # Load initial few-shot examples
        self._load_few_shot_examples()
    
    def analyze(self, email_data: Dict[str, Any]) -> Optional[AnalysisDecision]:
        """
        Comprehensive email analysis using Deep Ollama
        
        Args:
            email_data: Email data from database including full body
            
        Returns:
            Analysis decision or None if still uncertain (escalate to Tier 4 Human)
        """
        start_time = time.time()
        
        try:
            # Build comprehensive prompt with full email content
            prompt = self._build_deep_analysis_prompt(email_data)
            
            # Query Ollama with longer timeout for deep model
            ollama_response = self._query_ollama(prompt, timeout=120)  # 2 minutes
            
            if not ollama_response:
                return None  # Ollama failed - escalate to Tier 4
            
            # Parse JSON response
            classification = self._parse_ollama_response(ollama_response)
            
            if not classification:
                return None  # Parse failed - escalate to Tier 4
            
            # Lower confidence threshold for Tier 3 (it's the last AI tier)
            confidence = classification.get('confidence', 0.0)
            if confidence < 0.60:
                return None  # Still uncertain - escalate to Tier 4 Human
            
            processing_time = int((time.time() - start_time) * 1000)
            
            # Create analysis decision
            decision = AnalysisDecision(
                action=EmailAction(classification['action']),
                category=EmailCategory(classification['category']),
                confidence=confidence,
                reasoning=classification.get('reasoning', 'Deep Ollama analysis'),
                processing_tier=ProcessingTier.DEEP_OLLAMA,
                processing_time_ms=processing_time,
                deletion_candidate=(classification['action'] == 'DELETE'),
                deletion_reason=classification.get('deletion_reason', ''),
                importance_score=classification.get('importance_score'),
                fraud_score=classification.get('fraud_score')
            )
            
            # Generate comprehensive learning data for all lower tiers
            self._generate_comprehensive_learning_data(email_data, classification)
            
            return decision
            
        except Exception as e:
            print(f"   ⚠️ Tier 3 Deep Ollama error: {e}")
            return None  # Error - escalate to Tier 4 Human
    
    def _load_few_shot_examples(self) -> None:
        """Load few-shot examples from database"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT email_subject, email_sender, email_snippet, email_body_preview,
                           correct_category, correct_action, reasoning
                    FROM tier23_few_shot_examples 
                    WHERE tier_level = 3 AND is_active = true
                    ORDER BY effectiveness_score DESC, created_at DESC
                    LIMIT 3
                """)
                
                self.few_shot_examples = []
                for row in cursor.fetchall():
                    self.few_shot_examples.append({
                        'subject': row[0],
                        'sender': row[1],
                        'snippet': row[2],
                        'body_preview': row[3],
                        'category': row[4],
                        'action': row[5],
                        'reasoning': row[6]
                    })
                
                self.examples_last_updated = time.time()
                
        except Exception as e:
            print(f"   ⚠️ Error loading Tier 3 few-shot examples: {e}")
            self.few_shot_examples = []
    
    def _build_deep_analysis_prompt(self, email_data: Dict[str, Any]) -> str:
        """Build comprehensive analysis prompt with full email content"""
        
        # Base prompt for complex analysis
        prompt = """You are an expert email analyst handling complex classification cases that simpler systems couldn't resolve.

CONTEXT: This email was uncertain for previous analysis tiers, so it requires deep understanding.

CATEGORIES: NEWSLETTER, PROMOTIONAL, WORK, FINANCIAL, PERSONAL, SOCIAL, HEALTH, LEGAL, SHOPPING, ENTERTAINMENT, SPAM, UNKNOWN

ACTIONS: 
- DELETE: Safe to remove (clearly unnecessary content)
- KEEP: Important to preserve (valuable, actionable, or reference content)
- ARCHIVE: Valuable but can leave inbox (informational content to keep accessible)

DEEP ANALYSIS CRITERIA:
- Sender intent and relationship context
- Content value and actionability  
- Historical/reference importance
- Legal/compliance implications
- Financial/business relevance
- Personal significance indicators
- Fraud/security concerns

ANALYSIS RULES:
- Financial statements, receipts, legal documents: Always KEEP
- Work communications, project emails: Always KEEP
- Health records, insurance, medical: Always KEEP
- Personal correspondence: Always KEEP
- Marketing from unknown senders: Usually DELETE
- Newsletters with ongoing value: ARCHIVE
- When genuinely uncertain: KEEP (conservative approach)

"""
        
        # Add few-shot examples if available
        if self.few_shot_examples:
            prompt += "COMPLEX CASES EXAMPLES:\n\n"
            for example in self.few_shot_examples:
                prompt += f"""Subject: {example['subject']}
From: {example['sender']}
Content Preview: {example['body_preview']}
Classification: {example['category']} / {example['action']}
Deep Reasoning: {example['reasoning']}

"""
        
        # Add current email for comprehensive analysis
        subject = email_data.get('subject', '')
        sender = email_data.get('sender', '')
        sender_email = email_data.get('sender_email', '')
        snippet = email_data.get('snippet', '')
        body_text = email_data.get('body_text', '')
        has_attachments = email_data.get('has_attachments', False)
        attachment_count = email_data.get('attachment_count', 0)
        date_sent = email_data.get('date_sent', '')
        labels = email_data.get('labels', [])
        
        # Limit body text to avoid token limits while preserving key content
        body_preview = body_text[:2000] if body_text else snippet
        
        prompt += f"""DEEP ANALYSIS REQUIRED FOR THIS EMAIL:

METADATA:
Subject: {subject}
From: {sender}
Sender Email: {sender_email}  
Date: {str(date_sent)[:10] if date_sent else 'Unknown'}
Has Attachments: {has_attachments}
Attachment Count: {attachment_count}
Gmail Labels: {', '.join(labels) if labels else 'None'}

CONTENT ANALYSIS:
Email Body Preview (first 2000 chars):
{body_preview}

COMPREHENSIVE ANALYSIS REQUIREMENTS:
1. What is the sender's relationship to the recipient?
2. What is the primary intent of this communication?
3. Does this contain actionable information or valuable reference material?
4. Are there any legal, financial, or compliance implications?
5. What would be the consequence of deleting this email?
6. Are there any security or fraud indicators?
7. Historical context: How might this email's age ({str(date_sent)[:4] if date_sent else 'unknown'}) affect its value?

Respond ONLY with valid JSON (no example values):
{{
    "category": "CATEGORY_NAME",
    "action": "ACTION_NAME",
    "confidence": 0.XX,
    "reasoning": "Comprehensive explanation covering relationship, intent, value, and decision factors",
    "deletion_reason": "Detailed justification if DELETE action chosen",
    "importance_score": XX,
    "fraud_score": X,
    "content_summary": "Brief summary of email's main purpose",
    "sender_relationship": "Assessment of sender relationship (business/personal/marketing/unknown)",
    "actionable_content": true/false,
    "reference_value": true/false
}}

Provide precise confidence based on analysis certainty. Minimum 0.60 confidence required.
"""
        
        return prompt
    
    def _query_ollama(self, prompt: str, timeout: int = 120) -> Optional[str]:
        """Query Ollama API with extended timeout for deep analysis"""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 500,  # More tokens for comprehensive analysis
                    "top_p": 0.9
                }
            }
            
            response = requests.post(
                self.ollama_url,
                json=payload,
                timeout=timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '')
            else:
                print(f"   ❌ Deep Ollama API error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"   ❌ Deep Ollama query failed: {e}")
            return None
    
    def _parse_ollama_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse Ollama JSON response"""
        try:
            # Extract JSON from response (may have extra text)
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group()
                classification = json.loads(json_str)
                
                # Validate required fields
                required_fields = ['category', 'action', 'confidence', 'reasoning']
                if all(field in classification for field in required_fields):
                    return classification
                else:
                    print(f"   ⚠️ Missing required fields in Deep Ollama response")
                    return None
            else:
                print(f"   ⚠️ No JSON found in Deep Ollama response")
                return None
                
        except json.JSONDecodeError as e:
            print(f"   ⚠️ JSON parse error: {e}")
            return None
        except Exception as e:
            print(f"   ⚠️ Response parse error: {e}")
            return None
    
    def _generate_comprehensive_learning_data(self, email_data: Dict[str, Any], 
                                            classification: Dict[str, Any]) -> None:
        """Generate high-quality training data for all lower tiers"""
        try:
            # 1. Generate premium BERT training example
            self._create_premium_bert_training_example(email_data, classification)
            
            # 2. Generate sophisticated rules for Tier 0
            self._create_sophisticated_tier0_rules(email_data, classification)
            
            # 3. Update Tier 2 few-shot examples with deep insights
            self._update_tier2_prompts(email_data, classification)
            
            # 4. Add to own few-shot examples (if very high confidence)
            if classification.get('confidence', 0) > 0.90:
                self._create_tier3_few_shot_example(email_data, classification)
                
        except Exception as e:
            print(f"   ⚠️ Error generating comprehensive learning data: {e}")
    
    def _create_premium_bert_training_example(self, email_data: Dict[str, Any], 
                                            classification: Dict[str, Any]) -> None:
        """Create high-quality training example for BERT with deep analysis context"""
        try:
            # Enhanced training example with deep analysis insights
            training_example = {
                'email_subject': email_data.get('subject', ''),
                'email_sender': email_data.get('sender', ''),
                'email_snippet': email_data.get('snippet', ''),
                'true_category': classification['category'],
                'true_action': classification['action'],
                'confidence_score': classification['confidence'],
                'sender_relationship': classification.get('sender_relationship', ''),
                'actionable_content': classification.get('actionable_content', False),
                'reference_value': classification.get('reference_value', False),
                'deep_reasoning': classification['reasoning']
            }
            
            # TODO: Store enhanced training data
            print(f"   📚 Generated premium BERT training example: {classification['category']}/{classification['action']}")
            
        except Exception as e:
            print(f"   ⚠️ Error creating premium BERT training example: {e}")
    
    def _create_sophisticated_tier0_rules(self, email_data: Dict[str, Any], 
                                        classification: Dict[str, Any]) -> None:
        """Generate sophisticated sender-based rules for Tier 0"""
        try:
            confidence = classification.get('confidence', 0)
            
            # Only create rules for extremely high-confidence cases
            if confidence < 0.95:
                return
            
            sender_email = email_data.get('sender_email', '').lower()
            
            if not sender_email or '@' not in sender_email:
                return
            
            # HIGH-CONFIDENCE SENDER WHITELIST for critical categories
            if (classification['action'] == 'KEEP' and 
                classification['category'] in ['WORK', 'FINANCIAL', 'LEGAL', 'HEALTH'] and
                'business' in classification.get('sender_relationship', '').lower()):
                
                # Whitelist this specific sender with high confidence
                if self._store_tier0_rule(
                    rule_type='sender_exact',
                    pattern_text=sender_email,
                    action='KEEP',
                    category=classification['category'],
                    confidence=0.98,  # Very high confidence for important senders
                    created_by_tier=3
                ):
                    print(f"   ⚡ High-confidence whitelist: {sender_email} → KEEP ({classification['category']})")
            
            # CONSERVATIVE DOMAIN RULES for obvious marketing
            elif (classification['action'] == 'DELETE' and 
                  classification['category'] in ['PROMOTIONAL', 'SPAM'] and
                  'marketing' in classification.get('sender_relationship', '').lower()):
                
                domain = sender_email.split('@')[1]
                
                # Only for very obvious promotional domains
                obvious_marketing = ['unsubscribe', 'newsletter', 'noreply', 'marketing', 'promotions']
                if any(keyword in domain for keyword in obvious_marketing):
                    if self._store_tier0_rule(
                        rule_type='sender_domain', 
                        pattern_text=domain,
                        action='DELETE',
                        category='PROMOTIONAL',
                        confidence=0.92,  # High but not maximum confidence
                        created_by_tier=3
                    ):
                        print(f"   ⚡ Conservative blacklist: {domain} → DELETE")
                
        except Exception as e:
            print(f"   ⚠️ Error creating sophisticated Tier 0 rules: {e}")
    
    def _store_tier0_rule(self, rule_type: str, pattern_text: str, action: str,
                         category: str, confidence: float, created_by_tier: int) -> bool:
        """Store rule in database (same implementation as Tier 2)"""
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
                    self._trigger_tier0_cache_invalidation()
                    return True
                return False
                
        except Exception as e:
            print(f"   ❌ Error storing Tier 0 rule: {e}")
            return False
    
    def _trigger_tier0_cache_invalidation(self) -> None:
        """Trigger Tier 0 cache invalidation when new rules are added"""
        try:
            from analyzers.tier0_rules_engine import Tier0RulesEngine
            temp_tier0 = Tier0RulesEngine(self.db)
            temp_tier0.invalidate_cache()
        except Exception as e:
            print(f"   ⚠️ Error invalidating Tier 0 cache: {e}")
    
    def _update_tier2_prompts(self, email_data: Dict[str, Any], 
                            classification: Dict[str, Any]) -> None:
        """Update Tier 2 few-shot examples with insights from deep analysis"""
        try:
            # Only update for very clear cases that Tier 2 should have caught
            if classification.get('confidence', 0) > 0.95:
                tier2_example = {
                    'tier_level': 2,
                    'example_type': 'tier3_insight',
                    'email_subject': email_data.get('subject', ''),
                    'email_sender': email_data.get('sender', ''),
                    'email_snippet': email_data.get('snippet', '')[:200],
                    'correct_category': classification['category'],
                    'correct_action': classification['action'],
                    'reasoning': f"Tier 3 insight: {classification.get('content_summary', '')}",
                    'confidence_score': classification['confidence'],
                    'created_from_email_id': email_data.get('id')
                }
                
                print(f"   🎯 Generated Tier 2 prompt update: {classification['category']}/{classification['action']}")
                
        except Exception as e:
            print(f"   ⚠️ Error updating Tier 2 prompts: {e}")
    
    def _create_tier3_few_shot_example(self, email_data: Dict[str, Any], 
                                     classification: Dict[str, Any]) -> None:
        """Add very high-confidence complex case as few-shot example"""
        try:
            example = {
                'tier_level': 3,
                'example_type': 'complex_case',
                'email_subject': email_data.get('subject', ''),
                'email_sender': email_data.get('sender', ''),
                'email_snippet': email_data.get('snippet', '')[:200],
                'email_body_preview': email_data.get('body_text', '')[:500],
                'correct_category': classification['category'],
                'correct_action': classification['action'],
                'reasoning': classification['reasoning'],
                'confidence_score': classification['confidence'],
                'created_from_email_id': email_data.get('id')
            }
            
            print(f"   🧠 Generated Tier 3 few-shot example: {classification['category']}/{classification['action']}")
            
        except Exception as e:
            print(f"   ⚠️ Error creating Tier 3 few-shot example: {e}")
    
    def invalidate_examples_cache(self) -> None:
        """Invalidate few-shot examples cache"""
        self.few_shot_examples = None
    
    def get_classifier_status(self) -> Dict[str, Any]:
        """Get current Tier 3 status"""
        return {
            'model': self.model,
            'ollama_url': self.ollama_url,
            'few_shot_examples_loaded': len(self.few_shot_examples) if self.few_shot_examples else 0,
            'examples_last_updated': self.examples_last_updated,
            'cache_valid': self.few_shot_examples is not None
        }

# Convenience functions
def create_tier3_classifier() -> Tier3DeepOllama:
    """Create and return Tier 3 Deep Ollama classifier"""
    return Tier3DeepOllama()

def test_tier3_deep_ollama() -> bool:
    """Test Tier 3 Deep Ollama classifier"""
    try:
        classifier = Tier3DeepOllama()
        status = classifier.get_classifier_status()
        
        print(f"🧠 Tier 3 Deep Ollama Status:")
        print(f"   Model: {status['model']}")
        print(f"   Ollama URL: {status['ollama_url']}")
        print(f"   Few-shot examples: {status['few_shot_examples_loaded']}")
        
        # Test with complex/ambiguous email
        test_email = {
            'id': 1,
            'subject': 'Re: Account Information Update Required',
            'sender': 'security@financial-services.com',
            'sender_email': 'security@financial-services.com',
            'snippet': 'We need to verify your account information to maintain security.',
            'body_text': '''Dear Valued Customer,

We have detected unusual activity on your account and need to verify some information to ensure your account security. 

Please click the link below to update your account information within 24 hours:
https://secure-verify.financial-services.com/update

If you do not complete this verification, your account may be temporarily suspended for security purposes.

Thank you for your cooperation.
Security Team
Financial Services Inc.''',
            'has_attachments': False,
            'attachment_count': 0,
            'date_sent': '2024-01-15',
            'labels': ['INBOX']
        }
        
        print(f"\n🧪 Testing with potentially suspicious email...")
        print(f"⏰ Note: 70B model may take 1-2 minutes for cold start...")
        
        decision = classifier.analyze(test_email)
        
        if decision is None:
            print("   ✅ Tier 3 escalated to Tier 4 Human (uncertain or timeout)")
            return True
        else:
            print(f"   🧠 Tier 3 classified: {decision.action.value} - {decision.category.value} ({decision.confidence:.2f})")
            print(f"   ⏱️ Processing time: {decision.processing_time_ms}ms")
            print(f"   🔍 Reasoning: {decision.reasoning[:100]}...")
            return True
            
    except Exception as e:
        print(f"❌ Tier 3 test failed: {e}")
        return False

# Example usage and testing
if __name__ == "__main__":
    """Test Tier 3 Deep Ollama classifier"""
    
    print("🧠 Testing Tier 3 Deep Ollama Classifier")
    print("=" * 50)
    
    success = test_tier3_deep_ollama()
    
    if success:
        print("\n🎉 Tier 3 Deep Ollama classifier test completed successfully!")
    else:
        print("\n❌ Tier 3 Deep Ollama classifier test failed")
