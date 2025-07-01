# ===== core/human_validator.py =====
"""
Marin v2.0 - Human Validation Interface
Clean interface for human review and classification.
"""

class HumanValidator:
    """Interface for human email validation"""
    
    def __init__(self):
        """Initialize validation interface"""
        # TODO: Set up review queue management
        pass
    
    def get_next_email_for_review(self):
        """Get next email needing human review"""
        # TODO: Get from human_review_queue
        # TODO: Prioritize by importance
        pass
    
    def validate_email(self, email_id, suggestion=None):
        """Present email to human for validation"""
        # TODO: Show email content
        # TODO: Show AI suggestion if available
        # TODO: Get human decision
        pass