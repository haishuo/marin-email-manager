# analyzers/tier4_human_interface.py
"""
Tier 4: Human classification interface for uncertain cases.
One job: present emails to human for manual classification and capture decisions.
"""

import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from core.database import MarinDatabase
from analyzers.tier0_rules_engine import EmailCategory, EmailAction, ProcessingTier, AnalysisDecision

class Tier4HumanInterface:
    """Human classification interface for complex/uncertain emails"""
    
    def __init__(self, database: Optional[MarinDatabase] = None):
        """Initialize human interface"""
        self.db = database or MarinDatabase()
        
        # Available categories and actions for human selection
        self.categories = {
            '1': EmailCategory.WORK,
            '2': EmailCategory.FINANCIAL, 
            '3': EmailCategory.PERSONAL,
            '4': EmailCategory.HEALTH,
            '5': EmailCategory.LEGAL,
            '6': EmailCategory.NEWSLETTER,
            '7': EmailCategory.PROMOTIONAL,
            '8': EmailCategory.SHOPPING,
            '9': EmailCategory.SOCIAL,
            '10': EmailCategory.ENTERTAINMENT,
            '11': EmailCategory.SPAM,
            '12': EmailCategory.UNKNOWN
        }
        
        self.actions = {
            '1': EmailAction.KEEP,
            '2': EmailAction.DELETE,
            '3': EmailAction.ARCHIVE
        }
    
    def analyze(self, email_data: Dict[str, Any]) -> Optional[AnalysisDecision]:
        """
        Present email to human for classification
        
        Args:
            email_data: Email data from database
            
        Returns:
            Human classification decision or None if skipped
        """
        start_time = time.time()
        
        try:
            # Display email for human review
            self._display_email_for_review(email_data)
            
            # Get human classification
            human_decision = self._get_human_classification()
            
            if not human_decision:
                return None  # Human skipped this email
            
            processing_time = int((time.time() - start_time) * 1000)
            
            # Create analysis decision from human input
            decision = AnalysisDecision(
                action=human_decision['action'],
                category=human_decision['category'],
                confidence=1.0,  # Human decisions are 100% confident
                reasoning=f"Human classification: {human_decision['reasoning']}",
                processing_tier=ProcessingTier.HUMAN_REVIEW,
                processing_time_ms=processing_time,
                deletion_candidate=(human_decision['action'] == EmailAction.DELETE),
                deletion_reason=human_decision.get('deletion_reason', ''),
                importance_score=human_decision.get('importance_score'),
                fraud_score=human_decision.get('fraud_score')
            )
            
            # Generate premium learning data for all lower tiers
            self._generate_human_learning_data(email_data, human_decision)
            
            return decision
            
        except KeyboardInterrupt:
            print("\n⏹️ Human classification interrupted")
            return None
        except Exception as e:
            print(f"\n❌ Human interface error: {e}")
            return None
    
    def _display_email_for_review(self, email_data: Dict[str, Any]) -> None:
        """Display email information for human review"""
        
        print("\n" + "="*80)
        print("🧑 HUMAN REVIEW REQUIRED - AI TIERS UNCERTAIN")
        print("="*80)
        
        # Basic email info
        print(f"📧 EMAIL DETAILS:")
        print(f"   Subject: {email_data.get('subject', 'No Subject')}")
        print(f"   From: {email_data.get('sender', 'Unknown Sender')}")
        print(f"   Date: {str(email_data.get('date_sent', 'Unknown'))[:19]}")
        print(f"   Has Attachments: {email_data.get('has_attachments', False)}")
        if email_data.get('has_attachments'):
            print(f"   Attachment Count: {email_data.get('attachment_count', 0)}")
        
        # Gmail labels if available
        labels = email_data.get('labels', [])
        if labels:
            print(f"   Gmail Labels: {', '.join(labels)}")
        
        print(f"\n📝 EMAIL PREVIEW:")
        print("-" * 60)
        
        # Show snippet first
        snippet = email_data.get('snippet', '')
        if snippet:
            print(f"Preview: {snippet}")
            print()
        
        # Show body text if available (truncated)
        body_text = email_data.get('body_text', '')
        if body_text:
            # Show first 1000 characters of body
            body_preview = body_text[:1000]
            if len(body_text) > 1000:
                body_preview += "\n\n[... EMAIL TRUNCATED ...]"
            
            print("Full Content:")
            print(body_preview)
        elif not snippet:
            print("No content preview available")
        
        print("-" * 60)
    
    def _get_human_classification(self) -> Optional[Dict[str, Any]]:
        """Get classification decision from human"""
        
        # Display category options
        print(f"\n📂 SELECT CATEGORY:")
        print("   1. WORK                 7. PROMOTIONAL")
        print("   2. FINANCIAL            8. SHOPPING")  
        print("   3. PERSONAL             9. SOCIAL")
        print("   4. HEALTH              10. ENTERTAINMENT")
        print("   5. LEGAL               11. SPAM")
        print("   6. NEWSLETTER          12. UNKNOWN")
        
        while True:
            try:
                category_choice = input("\nCategory (1-12): ").strip()
                if category_choice in self.categories:
                    selected_category = self.categories[category_choice]
                    break
                elif category_choice.lower() in ['s', 'skip']:
                    return None  # Skip this email
                elif category_choice.lower() in ['q', 'quit']:
                    raise KeyboardInterrupt()
                else:
                    print("❌ Invalid choice. Enter 1-12, 's' to skip, or 'q' to quit.")
            except EOFError:
                raise KeyboardInterrupt()
        
        # Display action options
        print(f"\n⚡ SELECT ACTION:")
        print("   1. KEEP    - Important to preserve")
        print("   2. DELETE  - Safe to remove")
        print("   3. ARCHIVE - Keep but move out of inbox")
        
        while True:
            try:
                action_choice = input("\nAction (1-3): ").strip()
                if action_choice in self.actions:
                    selected_action = self.actions[action_choice]
                    break
                elif action_choice.lower() in ['s', 'skip']:
                    return None  # Skip this email
                elif action_choice.lower() in ['q', 'quit']:
                    raise KeyboardInterrupt()
                else:
                    print("❌ Invalid choice. Enter 1-3, 's' to skip, or 'q' to quit.")
            except EOFError:
                raise KeyboardInterrupt()
        
        # Get reasoning
        print(f"\n💭 WHY this classification? (optional)")
        try:
            reasoning = input("Reasoning: ").strip()
            if not reasoning:
                reasoning = f"Human classified as {selected_category.value}/{selected_action.value}"
        except EOFError:
            reasoning = f"Human classified as {selected_category.value}/{selected_action.value}"
        
        # Get additional details for DELETE action
        deletion_reason = ""
        if selected_action == EmailAction.DELETE:
            print(f"\n🗑️ Why is this safe to delete?")
            try:
                deletion_reason = input("Deletion reason: ").strip()
                if not deletion_reason:
                    deletion_reason = "Human determined safe to delete"
            except EOFError:
                deletion_reason = "Human determined safe to delete"
        
        # Get importance score (optional)
        importance_score = None
        if selected_action == EmailAction.KEEP:
            print(f"\n⭐ Importance (1-100, or Enter to skip): ", end="")
            try:
                importance_input = input().strip()
                if importance_input:
                    importance_score = max(1, min(100, int(importance_input)))
            except (ValueError, EOFError):
                pass
        
        # Get fraud score if suspicious
        fraud_score = None
        if selected_category == EmailCategory.SPAM:
            print(f"\n🚨 Fraud risk (0-100, or Enter for 50): ", end="")
            try:
                fraud_input = input().strip()
                if fraud_input:
                    fraud_score = max(0, min(100, int(fraud_input)))
                else:
                    fraud_score = 50
            except (ValueError, EOFError):
                fraud_score = 50
        
        return {
            'category': selected_category,
            'action': selected_action,
            'reasoning': reasoning,
            'deletion_reason': deletion_reason,
            'importance_score': importance_score,
            'fraud_score': fraud_score
        }
    
    def _generate_human_learning_data(self, email_data: Dict[str, Any], 
                                    human_decision: Dict[str, Any]) -> None:
        """Generate premium learning data from human decisions"""
        try:
            # Human decisions are the highest quality training data
            print(f"\n📚 Generating premium learning data for all tiers...")
            
            # 1. Create gold-standard BERT training example
            self._create_gold_bert_training_example(email_data, human_decision)
            
            # 2. Create high-confidence rules for Tier 0
            self._create_human_validated_rules(email_data, human_decision)
            
            # 3. Update few-shot examples for Tier 2 and 3
            self._create_human_few_shot_examples(email_data, human_decision)
            
            print(f"   ✅ Generated learning data from human decision")
            
        except Exception as e:
            print(f"   ⚠️ Error generating human learning data: {e}")
    
    def _create_gold_bert_training_example(self, email_data: Dict[str, Any], 
                                         human_decision: Dict[str, Any]) -> None:
        """Create gold-standard training example for BERT"""
        try:
            # Human-validated training examples are the most valuable
            training_example = {
                'email_subject': email_data.get('subject', ''),
                'email_sender': email_data.get('sender', ''),
                'email_snippet': email_data.get('snippet', ''),
                'true_category': human_decision['category'].value,
                'true_action': human_decision['action'].value,
                'confidence_score': 1.0,  # Human decisions are 100% confident
                'human_reasoning': human_decision['reasoning'],
                'quality_tier': 'gold_standard'  # Mark as highest quality
            }
            
            # TODO: Store in tier1_training_examples with gold_standard flag
            print(f"   📚 Created gold-standard BERT example: {human_decision['category'].value}/{human_decision['action'].value}")
            
        except Exception as e:
            print(f"   ⚠️ Error creating gold BERT example: {e}")
    
    def _create_human_validated_rules(self, email_data: Dict[str, Any], 
                                    human_decision: Dict[str, Any]) -> None:
        """Create high-confidence rules validated by human"""
        try:
            sender_email = email_data.get('sender_email', '').lower()
            
            # Create domain-based rules for clear patterns
            if '@' in sender_email and human_decision['action'] in [EmailAction.DELETE, EmailAction.KEEP]:
                domain = sender_email.split('@')[1]
                
                # Only create rules for very clear cases
                if (human_decision['action'] == EmailAction.DELETE and 
                    human_decision['category'] in [EmailCategory.PROMOTIONAL, EmailCategory.SPAM]):
                    
                    rule = {
                        'rule_type': 'sender_domain',
                        'pattern_text': domain,
                        'action': human_decision['action'].value,
                        'category': human_decision['category'].value,
                        'confidence': 0.98,  # Very high confidence for human-validated rules
                        'created_by_tier': 4
                    }
                    
                    # TODO: Store rule when coordinator is ready
                    print(f"   ⚡ Created human-validated rule: {domain} → {human_decision['action'].value}")
                
        except Exception as e:
            print(f"   ⚠️ Error creating human-validated rules: {e}")
    
    def _create_human_few_shot_examples(self, email_data: Dict[str, Any], 
                                      human_decision: Dict[str, Any]) -> None:
        """Create few-shot examples for Tier 2 and 3 from human decisions"""
        try:
            # Create examples for both Tier 2 and Tier 3
            for tier_level in [2, 3]:
                example = {
                    'tier_level': tier_level,
                    'example_type': 'human_validated',
                    'email_subject': email_data.get('subject', ''),
                    'email_sender': email_data.get('sender', ''),
                    'email_snippet': email_data.get('snippet', '')[:200],
                    'correct_category': human_decision['category'].value,
                    'correct_action': human_decision['action'].value,
                    'reasoning': human_decision['reasoning'],
                    'confidence_score': 1.0,  # Human decisions are perfectly confident
                    'created_from_email_id': email_data.get('id')
                }
                
                # Add body preview for Tier 3
                if tier_level == 3:
                    example['email_body_preview'] = email_data.get('body_text', '')[:500]
                
                # TODO: Store in tier23_few_shot_examples table
                print(f"   🎯 Created Tier {tier_level} few-shot example: {human_decision['category'].value}/{human_decision['action'].value}")
                
        except Exception as e:
            print(f"   ⚠️ Error creating human few-shot examples: {e}")
    
    def batch_classify_emails(self, email_list: List[Dict[str, Any]]) -> List[Optional[AnalysisDecision]]:
        """Classify multiple emails in batch with human interface"""
        decisions = []
        
        print(f"\n🧑 HUMAN BATCH CLASSIFICATION")
        print(f"📧 {len(email_list)} emails need human review")
        print(f"💡 Commands: 's' = skip email, 'q' = quit batch")
        print("=" * 80)
        
        for i, email_data in enumerate(email_list):
            print(f"\n📊 Email {i+1} of {len(email_list)}")
            
            try:
                decision = self.analyze(email_data)
                decisions.append(decision)
                
                if decision:
                    print(f"✅ Classified: {decision.category.value} / {decision.action.value}")
                else:
                    print(f"⏭️ Skipped")
                    
            except KeyboardInterrupt:
                print(f"\n⏹️ Batch classification stopped at email {i+1}")
                break
        
        completed = len([d for d in decisions if d is not None])
        print(f"\n📊 Batch Summary: {completed} classified, {len(decisions) - completed} skipped")
        
        return decisions
    
    def get_interface_status(self) -> Dict[str, Any]:
        """Get human interface status"""
        return {
            'available_categories': len(self.categories),
            'available_actions': len(self.actions),
            'interface_ready': True
        }

# Convenience functions
def create_tier4_interface() -> Tier4HumanInterface:
    """Create and return Tier 4 human interface"""
    return Tier4HumanInterface()

def test_tier4_human_interface() -> bool:
    """Test Tier 4 human interface (non-interactive test)"""
    try:
        interface = Tier4HumanInterface()
        status = interface.get_interface_status()
        
        print(f"🧑 Tier 4 Human Interface Status:")
        print(f"   Available categories: {status['available_categories']}")
        print(f"   Available actions: {status['available_actions']}")
        print(f"   Interface ready: {status['interface_ready']}")
        
        print(f"\n✅ Human interface initialized successfully")
        print(f"📝 Note: Interactive testing requires running with real emails")
        
        return True
        
    except Exception as e:
        print(f"❌ Tier 4 test failed: {e}")
        return False

# Example usage and testing
if __name__ == "__main__":
    """Test Tier 4 human interface"""
    
    print("🧑 Testing Tier 4 Human Interface")
    print("=" * 50)
    
    success = test_tier4_human_interface()
    
    if success:
        print("\n🎉 Tier 4 human interface test completed successfully!")
    else:
        print("\n❌ Tier 4 human interface test failed")
