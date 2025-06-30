# analyzers/tier1_bert_classifier.py
"""
Tier 1: BERT-based email classification with training state awareness.
One job: fast email classification using fine-tuned BERT model.
"""

import json
import torch
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from core.database import MarinDatabase
from analyzers.tier0_rules_engine import EmailCategory, EmailAction, ProcessingTier, AnalysisDecision

# Try to import transformers, handle gracefully if not available
try:
    from transformers import (
        AutoTokenizer, AutoModelForSequenceClassification, 
        Trainer, TrainingArguments, pipeline
    )
    import numpy as np
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("⚠️ Transformers not available - BERT classifier will escalate all emails")

class BERTModelState(Enum):
    """BERT model training states"""
    NOT_INITIALIZED = "not_initialized"
    READY = "ready"
    TRAINING = "training"
    FAILED = "failed"
    LOADING = "loading"

@dataclass
class BERTClassificationResult:
    """BERT classification result in pure JSON format"""
    category: str
    action: str
    confidence: float
    model_version: str
    processing_time_ms: int

class Tier1BERTClassifier:
    """BERT-based email classifier with training state management"""
    
    def __init__(self, database: Optional[MarinDatabase] = None):
        """Initialize BERT classifier"""
        self.db = database or MarinDatabase()
        self.model = None
        self.tokenizer = None
        self.classifier_pipeline = None
        self.model_state = BERTModelState.NOT_INITIALIZED
        self.current_model_version = None
        self.model_base_path = Path("models/tier1_bert")
        self.model_base_path.mkdir(parents=True, exist_ok=True)
        
        # Category and action mappings for BERT output
        self.categories = [cat.value for cat in EmailCategory]
        self.actions = [action.value for action in EmailAction]
        
        # Load model if available
        self._initialize_model()
    
    def analyze(self, email_data: Dict[str, Any]) -> Optional[AnalysisDecision]:
        """
        Classify email using BERT model
        
        Args:
            email_data: Email data from database
            
        Returns:
            Analysis decision or None if uncertain/training (escalate to Tier 2)
        """
        start_time = time.time()
        
        # Check if BERT is available and ready
        if not TRANSFORMERS_AVAILABLE:
            return None  # Escalate - no BERT available
        
        if self.model_state != BERTModelState.READY:
            # BERT is training, loading, or failed - escalate to Tier 2
            return None
        
        try:
            # Prepare input text for BERT
            input_text = self._prepare_input_text(email_data)
            
            # Get BERT classification
            bert_result = self._classify_with_bert(input_text)
            
            if not bert_result:
                return None  # Classification failed - escalate
            
            # Check confidence threshold
            if bert_result.confidence < 0.75:  # Low confidence - escalate
                return None
            
            processing_time = int((time.time() - start_time) * 1000)
            
            return AnalysisDecision(
                action=EmailAction(bert_result.action),
                category=EmailCategory(bert_result.category),
                confidence=bert_result.confidence,
                reasoning=f"BERT classification ({bert_result.model_version})",
                processing_tier=ProcessingTier.BERT_CLASSIFIER,
                processing_time_ms=processing_time,
                deletion_candidate=(bert_result.action == "DELETE"),
                deletion_reason=f"BERT classified as {bert_result.category}"
            )
            
        except Exception as e:
            print(f"   ⚠️ BERT classification error: {e}")
            return None  # Error - escalate to Tier 2
    
    def _initialize_model(self) -> None:
        """Initialize BERT model from latest training batch"""
        if not TRANSFORMERS_AVAILABLE:
            self.model_state = BERTModelState.FAILED
            return
        
        try:
            self.model_state = BERTModelState.LOADING
            
            # Get latest trained model
            latest_model_info = self._get_latest_model()
            
            if not latest_model_info:
                # No trained model - use base BERT
                self._load_base_model()
            else:
                # Load trained model
                self._load_trained_model(latest_model_info)
            
            self.model_state = BERTModelState.READY
            
        except Exception as e:
            print(f"❌ BERT model initialization failed: {e}")
            self.model_state = BERTModelState.FAILED
    
    def _get_latest_model(self) -> Optional[Dict[str, Any]]:
        """Get information about the latest trained model"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT model_version, model_file_path, validation_accuracy
                    FROM tier1_training_batches 
                    WHERE is_active = true AND training_status = 'completed'
                    ORDER BY batch_number DESC 
                    LIMIT 1
                """)
                
                result = cursor.fetchone()
                if result:
                    return {
                        'model_version': result[0],
                        'model_file_path': result[1],
                        'validation_accuracy': result[2]
                    }
                else:
                    return None
                    
        except Exception as e:
            print(f"   ⚠️ Error getting latest model: {e}")
            return None
    
    def _load_base_model(self) -> None:
        """Load base BERT model for initial use"""
        print("   📦 Loading base BERT model (bert-base-uncased)")
        
        # Use a classification pipeline for simplicity
        self.tokenizer = AutoTokenizer.from_pretrained('bert-base-uncased')
        
        # Create a simple text classification setup
        # Note: This is a placeholder - in practice, we'd need a model trained for our specific task
        self.classifier_pipeline = pipeline(
            "text-classification",
            model='bert-base-uncased',
            tokenizer=self.tokenizer,
            top_k=None  # Get all scores (replaces deprecated return_all_scores=True)
        )
        
        self.current_model_version = "base_bert_v1.0"
        print(f"   ✅ Base BERT model loaded: {self.current_model_version}")
    
    def _load_trained_model(self, model_info: Dict[str, Any]) -> None:
        """Load a previously trained BERT model"""
        model_path = model_info['model_file_path']
        model_version = model_info['model_version']
        
        print(f"   📦 Loading trained BERT model: {model_version}")
        
        if not Path(model_path).exists():
            print(f"   ⚠️ Model file not found: {model_path}, falling back to base model")
            self._load_base_model()
            return
        
        try:
            # Load the fine-tuned model
            self.model = AutoModelForSequenceClassification.from_pretrained(model_path)
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            
            # Create pipeline with loaded model
            self.classifier_pipeline = pipeline(
                "text-classification",
                model=self.model,
                tokenizer=self.tokenizer,
                top_k=None  # Get all scores (replaces deprecated return_all_scores=True)
            )
            
            self.current_model_version = model_version
            print(f"   ✅ Trained BERT model loaded: {model_version}")
            
        except Exception as e:
            print(f"   ❌ Failed to load trained model: {e}")
            print("   🔄 Falling back to base model")
            self._load_base_model()
    
    def _prepare_input_text(self, email_data: Dict[str, Any]) -> str:
        """Prepare email data for BERT input"""
        # Combine key email fields for classification
        # BERT gets subject + sender + snippet (no body for speed)
        
        subject = email_data.get('subject', '').strip()
        sender = email_data.get('sender', '').strip()
        snippet = email_data.get('snippet', '').strip()
        
        # Format for BERT: "Subject: ... | From: ... | Preview: ..."
        input_parts = []
        
        if subject:
            input_parts.append(f"Subject: {subject}")
        
        if sender:
            input_parts.append(f"From: {sender}")
        
        if snippet:
            # Limit snippet to avoid token limits
            snippet_short = snippet[:200]
            input_parts.append(f"Preview: {snippet_short}")
        
        return " | ".join(input_parts)
    
    def _classify_with_bert(self, input_text: str) -> Optional[BERTClassificationResult]:
        """
        Classify text using BERT and return structured JSON result
        
        Note: This is a simplified implementation. In practice, we'd need:
        1. A BERT model specifically trained on email classification
        2. Proper label mapping for our categories/actions
        3. Multi-label classification for category + action
        """
        
        try:
            if not self.classifier_pipeline:
                return None
            
            start_time = time.time()
            
            # Get BERT predictions
            # Note: This is using a generic text classifier as placeholder
            # Real implementation would use our fine-tuned model
            predictions = self.classifier_pipeline(input_text)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            # For now, use heuristics to map BERT output to our categories
            # This would be replaced with proper multi-label classification
            category, action, confidence = self._map_bert_output_to_categories(
                input_text, predictions
            )
            
            return BERTClassificationResult(
                category=category,
                action=action,
                confidence=confidence,
                model_version=self.current_model_version,
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            print(f"   ❌ BERT classification failed: {e}")
            return None
    
    def _map_bert_output_to_categories(self, input_text: str, 
                                     predictions: List[Dict]) -> Tuple[str, str, float]:
        """
        Map BERT output to our email categories/actions
        
        Note: Until we have a properly trained model, this always returns
        low confidence to force escalation to Tier 2.
        """
        
        # For untrained BERT: ALWAYS escalate by returning low confidence
        if self.current_model_version == "base_bert_v1.0":
            return "UNKNOWN", "KEEP", 0.30  # Below 0.75 threshold = escalate
        
        # TODO: For trained models, implement proper multi-label classification
        # This would parse the actual BERT predictions and map to our categories
        # For now, even trained models escalate until we implement proper mapping
        return "UNKNOWN", "KEEP", 0.30  # Always escalate until trained
    
    def get_model_status(self) -> Dict[str, Any]:
        """Get current BERT model status"""
        return {
            'state': self.model_state.value,
            'model_version': self.current_model_version,
            'transformers_available': TRANSFORMERS_AVAILABLE,
            'model_ready': (self.model_state == BERTModelState.READY),
            'can_classify': (
                TRANSFORMERS_AVAILABLE and 
                self.model_state == BERTModelState.READY and 
                self.classifier_pipeline is not None
            )
        }
    
    def set_training_state(self, training: bool) -> None:
        """Set training state - called by training coordinator"""
        if training:
            self.model_state = BERTModelState.TRAINING
            print("   🔄 BERT model entering training mode - escalating all emails")
        else:
            print("   ✅ BERT training completed - reloading model")
            self._initialize_model()
    
    def is_ready_for_training(self) -> bool:
        """Check if BERT is ready for training (not currently training)"""
        return (
            TRANSFORMERS_AVAILABLE and 
            self.model_state in [BERTModelState.READY, BERTModelState.NOT_INITIALIZED]
        )

# Convenience functions
def create_tier1_classifier() -> Tier1BERTClassifier:
    """Create and return Tier 1 BERT classifier"""
    return Tier1BERTClassifier()

def test_tier1_bert() -> bool:
    """Test BERT classifier initial state"""
    try:
        classifier = Tier1BERTClassifier()
        status = classifier.get_model_status()
        
        print(f"🤖 BERT Classifier Status:")
        print(f"   State: {status['state']}")
        print(f"   Model version: {status['model_version']}")
        print(f"   Transformers available: {status['transformers_available']}")
        print(f"   Can classify: {status['can_classify']}")
        
        if not status['transformers_available']:
            print("   ⚠️ Transformers not installed - BERT will escalate all emails")
            return True  # This is expected behavior
        
        # Test with sample email
        test_email = {
            'subject': 'Test promotional email - 50% off everything!',
            'sender': 'deals@example.com',
            'snippet': 'Limited time offer - save big on all items'
        }
        
        decision = classifier.analyze(test_email)
        
        if decision is None:
            print("   ✅ BERT correctly escalates when uncertain/not trained")
            return True
        else:
            print(f"   🤖 BERT made decision: {decision.action.value} - {decision.category.value} ({decision.confidence:.2f})")
            return True
            
    except Exception as e:
        print(f"❌ BERT test failed: {e}")
        return False

# Example usage and testing
if __name__ == "__main__":
    """Test Tier 1 BERT classifier"""
    
    print("🤖 Testing Tier 1 BERT Classifier")
    print("=" * 50)
    
    success = test_tier1_bert()
    
    if success:
        print("\n🎉 Tier 1 BERT classifier test completed successfully!")
    else:
        print("\n❌ Tier 1 BERT classifier test failed")
