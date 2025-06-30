# core/analysis_coordinator.py
"""
Analysis Coordinator: Orchestrates 5-tier email classification system.
One job: route emails through tiers and manage learning feedback loops.
"""

import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from core.database import MarinDatabase
from utils.config import get_config

# Import all tier analyzers
from analyzers.tier0_rules_engine import Tier0RulesEngine, AnalysisDecision
from analyzers.tier1_bert_classifier import Tier1BERTClassifier
from analyzers.tier2_fast_ollama import Tier2FastOllama
from analyzers.tier3_deep_ollama import Tier3DeepOllama
from analyzers.tier4_human_interface import Tier4HumanInterface

@dataclass
class CoordinatorStats:
    """Statistics for coordinator performance tracking"""
    emails_processed: int = 0
    tier0_handled: int = 0
    tier1_handled: int = 0
    tier2_handled: int = 0
    tier3_handled: int = 0
    tier4_handled: int = 0
    total_processing_time_ms: int = 0
    learning_events_triggered: int = 0

class AnalysisCoordinator:
    """Orchestrates 5-tier email analysis and learning system"""
    
    def __init__(self, database: Optional[MarinDatabase] = None, dry_run: bool = False):
        """
        Initialize analysis coordinator
        
        Args:
            database: Database connection
            dry_run: If True, don't store results (for testing)
        """
        self.db = database or MarinDatabase()
        self.config = get_config()
        self.dry_run = dry_run
        
        # Initialize all tiers
        self.tier0_rules = Tier0RulesEngine(self.db)
        self.tier1_bert = Tier1BERTClassifier(self.db)
        self.tier2_fast_ollama = Tier2FastOllama(self.db)
        self.tier3_deep_ollama = Tier3DeepOllama(self.db)
        self.tier4_human = Tier4HumanInterface(self.db)
        
        # Statistics tracking
        self.stats = CoordinatorStats()
        
        # Learning state
        self.classification_count = 0
        self.training_threshold = 300  # Trigger BERT training every 300 classifications
        
        print(f"🎯 Analysis Coordinator initialized")
        print(f"   Dry run mode: {self.dry_run}")
        print(f"   Training threshold: {self.training_threshold} classifications")
    
    def analyze_email(self, email_data: Dict[str, Any]) -> Optional[AnalysisDecision]:
        """
        Route email through 5-tier analysis system
        
        Args:
            email_data: Email data from database
            
        Returns:
            Final analysis decision or None if analysis failed
        """
        start_time = time.time()
        email_id = email_data.get('id', 'unknown')
        subject = email_data.get('subject', '')[:50] + '...' if len(email_data.get('subject', '')) > 50 else email_data.get('subject', '')
        
        print(f"🔍 Analyzing email {email_id}: {subject}")
        
        # Tier 0: Rules Engine (Lightning Fast)
        decision = self.tier0_rules.analyze(email_data)
        if decision:
            print(f"   ⚡ Tier 0 (Rules): {decision.action.value} - {decision.category.value} ({decision.confidence:.2f})")
            self.stats.tier0_handled += 1
            self._finalize_decision(email_data, decision, start_time)
            return decision
        
        # Tier 1: BERT Classifier (Fast AI)
        decision = self.tier1_bert.analyze(email_data)
        if decision:
            print(f"   🤖 Tier 1 (BERT): {decision.action.value} - {decision.category.value} ({decision.confidence:.2f})")
            self.stats.tier1_handled += 1
            self._finalize_decision(email_data, decision, start_time)
            return decision
        
        # Tier 2: Fast Ollama (Quick Analysis)
        decision = self.tier2_fast_ollama.analyze(email_data)
        if decision:
            print(f"   🚀 Tier 2 (Fast AI): {decision.action.value} - {decision.category.value} ({decision.confidence:.2f})")
            self.stats.tier2_handled += 1
            self._finalize_decision(email_data, decision, start_time)
            return decision
        
        # Tier 3: Deep Ollama (Comprehensive Analysis)
        decision = self.tier3_deep_ollama.analyze(email_data)
        if decision:
            print(f"   🧠 Tier 3 (Deep AI): {decision.action.value} - {decision.category.value} ({decision.confidence:.2f})")
            self.stats.tier3_handled += 1
            self._finalize_decision(email_data, decision, start_time)
            return decision
        
        # Tier 4: Human Review (Final Escalation)
        print(f"   👤 Tier 4 (Human): All AI tiers uncertain - human review required")
        decision = self.tier4_human.analyze(email_data)
        if decision:
            print(f"   🧑 Human classified: {decision.action.value} - {decision.category.value}")
            self.stats.tier4_handled += 1
            self._finalize_decision(email_data, decision, start_time)
            return decision
        else:
            print(f"   ⏭️ Human skipped email - no classification")
            return None
    
    def _finalize_decision(self, email_data: Dict[str, Any], 
                          decision: AnalysisDecision, start_time: float) -> None:
        """Finalize analysis decision and trigger learning events"""
        
        # Update statistics
        self.stats.emails_processed += 1
        total_time = int((time.time() - start_time) * 1000)
        self.stats.total_processing_time_ms += total_time
        
        # Store analysis result in database
        if not self.dry_run:
            self._store_analysis_result(email_data, decision)
        else:
            print(f"   💾 DRY RUN: Would store {decision.category.value}/{decision.action.value}")
        
        # Update classification count and check for learning triggers
        self.classification_count += 1
        self._check_learning_triggers()
    
    def _store_analysis_result(self, email_data: Dict[str, Any], 
                              decision: AnalysisDecision) -> None:
        """Store analysis result in database"""
        try:
            analysis_data = {
                'email_id': email_data['id'],
                'analysis_version': 'v1.0',
                'ai_model': self.config.default_ai_model,
                'category': decision.category.value,
                'summary': decision.reasoning,
                'fraud_score': decision.fraud_score,
                'fraud_flags': '[]',  # TODO: Implement fraud flags
                'deletion_candidate': decision.deletion_candidate,
                'deletion_reason': decision.deletion_reason,
                'importance_score': decision.importance_score,
                'confidence_score': int(decision.confidence * 100),
                'processing_time_ms': decision.processing_time_ms,
                'processing_tier': decision.processing_tier.value,
                'tier_decision_confidence': decision.confidence
            }
            
            self.db.insert_analysis(analysis_data)
            
        except Exception as e:
            print(f"   ⚠️ Error storing analysis result: {e}")
    
    def _check_learning_triggers(self) -> None:
        """Check if learning events should be triggered"""
        
        # Trigger BERT training every 300 classifications
        if self.classification_count % self.training_threshold == 0:
            print(f"\n🎓 LEARNING TRIGGER: {self.classification_count} classifications reached")
            self._trigger_bert_training()
            self._trigger_cache_invalidation()
            self.stats.learning_events_triggered += 1
    
    def _trigger_bert_training(self) -> None:
        """Trigger BERT retraining with accumulated examples"""
        try:
            print(f"   🤖 Triggering BERT training with last {self.training_threshold} examples...")
            
            # Set BERT to training mode (escalates all emails)
            self.tier1_bert.set_training_state(training=True)
            
            # TODO: Implement actual BERT training
            # This would:
            # 1. Get last 300 classifications from database
            # 2. Format as BERT training data
            # 3. Fine-tune BERT model
            # 4. Save new model version
            # 5. Load new model and set ready state
            
            print(f"   📚 BERT training initiated (TODO: implement actual training)")
            
            # Simulate training completion
            self.tier1_bert.set_training_state(training=False)
            
        except Exception as e:
            print(f"   ❌ BERT training trigger failed: {e}")
    
    def _trigger_cache_invalidation(self) -> None:
        """Invalidate all tier caches when learning occurs"""
        try:
            print(f"   🔄 Invalidating tier caches for new learning data...")
            
            # Invalidate Tier 0 rules cache
            self.tier0_rules.invalidate_cache()
            
            # Invalidate Tier 2 few-shot examples cache
            self.tier2_fast_ollama.invalidate_examples_cache()
            
            # Invalidate Tier 3 few-shot examples cache
            self.tier3_deep_ollama.invalidate_examples_cache()
            
            # Force Tier 0 to check for new rules immediately
            self.tier0_rules._check_for_new_rules()
            
            print(f"   ✅ All caches invalidated - fresh learning data loaded")
            
        except Exception as e:
            print(f"   ⚠️ Cache invalidation failed: {e}")
    
    def analyze_batch(self, email_list: List[Dict[str, Any]], 
                     batch_name: str = "batch") -> Dict[str, Any]:
        """
        Analyze a batch of emails through the tier system
        
        Args:
            email_list: List of email data dictionaries
            batch_name: Name for this batch (for logging)
            
        Returns:
            Batch processing summary
        """
        print(f"\n🚀 Starting batch analysis: {batch_name}")
        print(f"📧 Processing {len(email_list)} emails")
        print("=" * 60)
        
        batch_start_time = time.time()
        successful_analyses = 0
        failed_analyses = 0
        human_escalations = 0
        
        for i, email_data in enumerate(email_list):
            try:
                if (i + 1) % 10 == 0:
                    print(f"\n📈 Progress: {i + 1}/{len(email_list)} ({((i + 1)/len(email_list)*100):.1f}%)")
                
                decision = self.analyze_email(email_data)
                
                if decision:
                    successful_analyses += 1
                    if decision.processing_tier.value == 4:  # Human tier
                        human_escalations += 1
                else:
                    failed_analyses += 1
                
                # Brief pause between emails
                time.sleep(0.01)
                
            except KeyboardInterrupt:
                print(f"\n⏹️ Batch analysis interrupted at email {i + 1}")
                break
            except Exception as e:
                print(f"   ❌ Error analyzing email {email_data.get('id', 'unknown')}: {e}")
                failed_analyses += 1
                continue
        
        batch_duration = time.time() - batch_start_time
        
        # Print batch summary
        self._print_batch_summary(batch_name, len(email_list), successful_analyses, 
                                failed_analyses, human_escalations, batch_duration)
        
        return {
            'batch_name': batch_name,
            'total_emails': len(email_list),
            'successful_analyses': successful_analyses,
            'failed_analyses': failed_analyses,
            'human_escalations': human_escalations,
            'duration_minutes': batch_duration / 60,
            'emails_per_minute': successful_analyses / (batch_duration / 60) if batch_duration > 0 else 0,
            'learning_events': self.stats.learning_events_triggered
        }
    
    def _print_batch_summary(self, batch_name: str, total: int, successful: int, 
                           failed: int, human: int, duration: float) -> None:
        """Print comprehensive batch analysis summary"""
        
        print(f"\n🎉 Batch Analysis Complete: {batch_name}")
        print("=" * 60)
        
        print(f"📊 Processing Summary:")
        print(f"   Total emails: {total}")
        print(f"   Successfully analyzed: {successful}")
        print(f"   Failed/skipped: {failed}")
        print(f"   Human escalations: {human}")
        print(f"   Duration: {duration/60:.1f} minutes")
        
        if duration > 0:
            print(f"   Rate: {successful/(duration/60):.1f} emails/minute")
        
        print(f"\n🏆 Tier Performance:")
        if successful > 0:
            print(f"   Tier 0 (Rules): {self.stats.tier0_handled} ({self.stats.tier0_handled/successful*100:.1f}%)")
            print(f"   Tier 1 (BERT): {self.stats.tier1_handled} ({self.stats.tier1_handled/successful*100:.1f}%)")
            print(f"   Tier 2 (Fast AI): {self.stats.tier2_handled} ({self.stats.tier2_handled/successful*100:.1f}%)")
            print(f"   Tier 3 (Deep AI): {self.stats.tier3_handled} ({self.stats.tier3_handled/successful*100:.1f}%)")
            print(f"   Tier 4 (Human): {self.stats.tier4_handled} ({self.stats.tier4_handled/successful*100:.1f}%)")
        
        print(f"\n📚 Learning Events:")
        print(f"   Training triggers: {self.stats.learning_events_triggered}")
        print(f"   Total classifications: {self.classification_count}")
        print(f"   Next training at: {((self.classification_count // self.training_threshold) + 1) * self.training_threshold}")
        
        # Efficiency analysis
        ai_handled = (self.stats.tier0_handled + self.stats.tier1_handled + 
                     self.stats.tier2_handled + self.stats.tier3_handled)
        if successful > 0:
            automation_rate = (ai_handled / successful) * 100
            print(f"\n⚡ Efficiency:")
            print(f"   AI automation rate: {automation_rate:.1f}%")
            print(f"   Human review rate: {(human/successful)*100:.1f}%")
            
            if automation_rate > 95:
                print(f"   Status: 🌟 Excellent automation")
            elif automation_rate > 85:
                print(f"   Status: ✅ Good automation")
            else:
                print(f"   Status: 📈 Learning in progress")
    
    def get_coordinator_status(self) -> Dict[str, Any]:
        """Get current coordinator status"""
        return {
            'emails_processed': self.stats.emails_processed,
            'classification_count': self.classification_count,
            'next_training_at': ((self.classification_count // self.training_threshold) + 1) * self.training_threshold,
            'learning_events_triggered': self.stats.learning_events_triggered,
            'tier_performance': {
                'tier0': self.stats.tier0_handled,
                'tier1': self.stats.tier1_handled,
                'tier2': self.stats.tier2_handled,
                'tier3': self.stats.tier3_handled,
                'tier4': self.stats.tier4_handled
            },
            'dry_run_mode': self.dry_run
        }

# Convenience functions
def create_analysis_coordinator(dry_run: bool = False) -> AnalysisCoordinator:
    """Create and return analysis coordinator"""
    return AnalysisCoordinator(dry_run=dry_run)

def test_analysis_coordinator() -> bool:
    """Test analysis coordinator initialization"""
    try:
        coordinator = AnalysisCoordinator(dry_run=True)
        status = coordinator.get_coordinator_status()
        
        print(f"🎯 Analysis Coordinator Status:")
        print(f"   Emails processed: {status['emails_processed']}")
        print(f"   Classification count: {status['classification_count']}")
        print(f"   Next training at: {status['next_training_at']}")
        print(f"   Dry run mode: {status['dry_run_mode']}")
        
        print(f"\n🏭 All tiers initialized successfully:")
        print(f"   ⚡ Tier 0: Rules Engine")
        print(f"   🤖 Tier 1: BERT Classifier") 
        print(f"   🚀 Tier 2: Fast Ollama")
        print(f"   🧠 Tier 3: Deep Ollama")
        print(f"   🧑 Tier 4: Human Interface")
        
        return True
        
    except Exception as e:
        print(f"❌ Coordinator test failed: {e}")
        return False

# Example usage and testing
if __name__ == "__main__":
    """Test analysis coordinator"""
    
    print("🎯 Testing Analysis Coordinator")
    print("=" * 50)
    
    success = test_analysis_coordinator()
    
    if success:
        print("\n🎉 Analysis coordinator test completed successfully!")
    else:
        print("\n❌ Analysis coordinator test failed")
