# utils/config.py
"""
Configuration management for Marin email system.
Handles environment variables, settings, and directory structure.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

class MarinConfig:
    """Centralized configuration management for Marin"""
    
    def __init__(self, config_dir: str = 'config', data_dir: str = 'data'):
        """
        Initialize configuration
        
        Args:
            config_dir: Directory for configuration files
            data_dir: Directory for data storage
        """
        self.config_dir = Path(config_dir)
        self.data_dir = Path(data_dir)
        
        # Load environment variables
        self._load_environment()
        
        # Ensure directories exist
        self._ensure_directories()
        
        # Load user settings
        self.settings = self._load_settings()
    
    def _load_environment(self) -> None:
        """Load environment variables from .env file"""
        env_file = self.config_dir / '.env'
        if env_file.exists():
            load_dotenv(env_file)
            print(f"✅ Loaded environment from {env_file}")
        else:
            print(f"ℹ️  No .env file found at {env_file}")
    
    def _ensure_directories(self) -> None:
        """Create necessary directories if they don't exist"""
        directories = [
            self.config_dir,
            self.data_dir,
            self.data_dir / 'attachments',
            self.data_dir / 'exports', 
            self.data_dir / 'logs',
            Path('sql'),  # For database schemas
            Path('tests'),  # For test files
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        
        print("✅ Ensured all directories exist")
    
    def _load_settings(self) -> Dict[str, Any]:
        """Load user settings from JSON file"""
        settings_file = self.config_dir / 'settings.json'
        
        if settings_file.exists():
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                print(f"✅ Loaded settings from {settings_file}")
                return settings
            except Exception as e:
                print(f"⚠️ Error loading settings: {e}")
                return self._default_settings()
        else:
            # Create default settings
            settings = self._default_settings()
            self.save_settings(settings)
            return settings
    
    def _default_settings(self) -> Dict[str, Any]:
        """Default configuration settings"""
        return {
            # AI Configuration
            "ai_models": {
                "fast": "llama3.2:3b",
                "comprehensive": "llama3.1:70b",
                "default": "llama3.2:3b"
            },
            
            # Processing Configuration
            "processing": {
                "default_batch_size": 100,
                "enable_adaptive_learning": True,
                "safety_mode": True,
                "max_emails_per_session": 10000
            },
            
            # Deletion Configuration
            "deletion": {
                "safe_categories": ["SHOPPING", "ENTERTAINMENT", "SPAM"],
                "preserve_categories": ["WORK", "FINANCIAL", "PERSONAL", "HEALTH"],
                "min_age_days": 30,  # Don't delete emails newer than 30 days
                "preview_mode": True  # Always preview before deleting
            },
            
            # Daily Digest Configuration  
            "digest": {
                "default_hours_back": 24,
                "include_categories": ["WORK", "FINANCIAL", "PERSONAL", "HEALTH"],
                "exclude_low_importance": True,
                "importance_threshold": 30
            },
            
            # Database Configuration
            "database": {
                "cleanup_old_analysis": True,
                "analysis_retention_days": 90,
                "backup_before_deletion": True
            },
            
            # Fraud Detection Configuration
            "fraud_detection": {
                "enable_ai_analysis": True,
                "strict_domain_checking": True,
                "quarantine_suspicious": True,
                "fraud_score_threshold": 70
            }
        }
    
    def save_settings(self, settings: Optional[Dict[str, Any]] = None) -> None:
        """Save settings to JSON file"""
        if settings is None:
            settings = self.settings
        
        settings_file = self.config_dir / 'settings.json'
        
        try:
            with open(settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
            print(f"✅ Saved settings to {settings_file}")
        except Exception as e:
            print(f"❌ Error saving settings: {e}")
    
    # Property accessors for common paths
    @property
    def credentials_path(self) -> str:
        """Path to Gmail OAuth credentials"""
        return str(self.config_dir / 'credentials.json')
    
    @property
    def token_path(self) -> str:
        """Path to Gmail OAuth token"""
        return str(self.config_dir / 'token.json')
    
    @property
    def database_url(self) -> str:
        """Database connection URL"""
        return os.getenv('DATABASE_URL', 'postgresql://localhost/marin_emails')
    
    @property
    def ollama_url(self) -> str:
        """Ollama API URL"""
        return os.getenv('OLLAMA_URL', 'http://localhost:11434/api/generate')
    
    @property
    def default_ai_model(self) -> str:
        """Default AI model to use"""
        return os.getenv('DEFAULT_AI_MODEL', self.settings['ai_models']['default'])
    
    @property
    def fast_ai_model(self) -> str:
        """Fast AI model for tier 2 processing"""
        return self.settings['ai_models']['fast']
    
    @property
    def comprehensive_ai_model(self) -> str:
        """Comprehensive AI model for tier 3 processing"""
        return self.settings['ai_models']['comprehensive']
    
    @property
    def default_batch_size(self) -> int:
        """Default batch size for processing"""
        return int(os.getenv('DEFAULT_BATCH_SIZE', self.settings['processing']['default_batch_size']))
    
    @property
    def safety_mode(self) -> bool:
        """Whether safety mode is enabled"""
        return os.getenv('SAFETY_MODE', 'true').lower() == 'true'
    
    @property
    def adaptive_learning_enabled(self) -> bool:
        """Whether adaptive learning is enabled"""
        return os.getenv('ENABLE_ADAPTIVE_LEARNING', 'true').lower() == 'true'
    
    # Directory accessors
    @property
    def attachments_dir(self) -> Path:
        """Directory for downloaded attachments"""
        return self.data_dir / 'attachments'
    
    @property
    def exports_dir(self) -> Path:
        """Directory for email exports"""
        return self.data_dir / 'exports'
    
    @property
    def logs_dir(self) -> Path:
        """Directory for log files"""
        return self.data_dir / 'logs'
    
    # Settings accessors
    def get_setting(self, key_path: str, default: Any = None) -> Any:
        """
        Get setting value using dot notation
        
        Args:
            key_path: Dot-separated path to setting (e.g., 'ai_models.fast')
            default: Default value if key not found
            
        Returns:
            Setting value or default
        """
        keys = key_path.split('.')
        value = self.settings
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set_setting(self, key_path: str, value: Any) -> None:
        """
        Set setting value using dot notation
        
        Args:
            key_path: Dot-separated path to setting
            value: Value to set
        """
        keys = key_path.split('.')
        target = self.settings
        
        # Navigate to parent of target key
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
        
        # Set the value
        target[keys[-1]] = value
        
        # Save settings
        self.save_settings()
    
    def get_deletion_criteria(self) -> Dict[str, Any]:
        """Get current deletion criteria settings"""
        return {
            'safe_categories': self.settings['deletion']['safe_categories'],
            'preserve_categories': self.settings['deletion']['preserve_categories'],
            'min_age_days': self.settings['deletion']['min_age_days'],
            'preview_mode': self.settings['deletion']['preview_mode']
        }
    
    def get_digest_config(self) -> Dict[str, Any]:
        """Get daily digest configuration"""
        return {
            'hours_back': self.settings['digest']['default_hours_back'],
            'include_categories': self.settings['digest']['include_categories'],
            'exclude_low_importance': self.settings['digest']['exclude_low_importance'],
            'importance_threshold': self.settings['digest']['importance_threshold']
        }
    
    def validate_configuration(self) -> Dict[str, Any]:
        """
        Validate configuration and return status
        
        Returns:
            Dict with validation results
        """
        issues = []
        warnings = []
        
        # Check required files
        if not Path(self.credentials_path).exists():
            issues.append(f"Gmail credentials not found: {self.credentials_path}")
        
        # Check database connection (would need to actually test this)
        if not self.database_url:
            issues.append("Database URL not configured")
        
        # Check Ollama connection (would need to actually test this)
        if not self.ollama_url:
            warnings.append("Ollama URL not configured - AI features will be disabled")
        
        # Check directory permissions
        for directory in [self.config_dir, self.data_dir]:
            if not os.access(directory, os.W_OK):
                issues.append(f"Directory not writable: {directory}")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings
        }
    
    def create_env_template(self) -> None:
        """Create .env.example template file"""
        template_content = """# Gmail API Configuration
GOOGLE_CREDENTIALS_PATH=config/credentials.json
GOOGLE_TOKEN_PATH=config/token.json

# Database Configuration  
DATABASE_URL=postgresql://localhost/marin_emails

# AI Configuration
OLLAMA_URL=http://localhost:11434/api/generate
DEFAULT_AI_MODEL=llama3.2:3b

# Processing Configuration
DEFAULT_BATCH_SIZE=100
ENABLE_ADAPTIVE_LEARNING=true
SAFETY_MODE=true

# Development Configuration (optional)
DEBUG=false
LOG_LEVEL=INFO
"""
        
        template_file = self.config_dir / '.env.example'
        with open(template_file, 'w') as f:
            f.write(template_content)
        
        print(f"✅ Created .env template: {template_file}")

# Global configuration instance
config = MarinConfig()

# Convenience functions
def get_config() -> MarinConfig:
    """Get global configuration instance"""
    return config

def validate_setup() -> bool:
    """Validate that Marin is properly configured"""
    validation = config.validate_configuration()
    
    print("🔧 Configuration Validation")
    print("=" * 40)
    
    if validation['warnings']:
        for warning in validation['warnings']:
            print(f"⚠️  {warning}")
    
    if validation['issues']:
        for issue in validation['issues']:
            print(f"❌ {issue}")
        return False
    
    if not validation['warnings']:
        print("✅ Configuration is valid")
    
    return True

# Example usage and testing
if __name__ == "__main__":
    """Test the configuration system"""
    
    print("🔧 Testing Configuration System")
    print("=" * 50)
    
    # Test configuration loading
    config = MarinConfig()
    
    print(f"📁 Config directory: {config.config_dir}")
    print(f"📁 Data directory: {config.data_dir}")
    print(f"🔗 Database URL: {config.database_url}")
    print(f"🤖 Default AI model: {config.default_ai_model}")
    print(f"📧 Credentials path: {config.credentials_path}")
    
    # Test settings access
    print(f"\n📋 Settings:")
    print(f"   Batch size: {config.default_batch_size}")
    print(f"   Safety mode: {config.safety_mode}")
    print(f"   Adaptive learning: {config.adaptive_learning_enabled}")
    
    # Test validation
    print(f"\n🔍 Validation:")
    is_valid = validate_setup()
    
    if is_valid:
        print("🎉 Configuration test completed successfully!")
    else:
        print("❌ Configuration issues found - see above")
