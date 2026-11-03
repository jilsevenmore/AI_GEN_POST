"""Security utilities and validation."""
import re
import html
import logging
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Prompt injection patterns to detect
PROMPT_INJECTION_PATTERNS = [
    r"(?i)ignore\s+(?:previous|above|all)\s+(?:instructions?|prompts?|rules?)",
    r"(?i)forget\s+(?:everything|all)\s+(?:you\s+)?(?:know|learned)",
    r"(?i)you\s+are\s+now\s+(?:a|an)\s+\w+",
    r"(?i)pretend\s+(?:to\s+be|you\s+are)",
    r"(?i)roleplay\s+as",
    r"(?i)system\s*:",
    r"(?i)user\s*:",
    r"(?i)assistant\s*:",
    r"(?i)<\|.*?\|>",
    r"(?i)###\s*(?:instruction|prompt|system)",
    r"(?i)output\s+(?:only|just)\s+(?:the|in)\s+(?:json|xml|yaml)",
    r"(?i)do\s+not\s+(?:include|output|show)",
    r"(?i)repeat\s+(?:the\s+)?(?:above|previous)",
    r"(?i)what\s+(?:is\s+)?(?:your\s+)?(?:prompt|instruction)",
    r"(?i)show\s+me\s+(?:your\s+)?(?:prompt|instruction|system)",
    r"(?i)reveal\s+(?:your\s+)?(?:prompt|instruction|system)",
    r"(?i)print\s+(?:your\s+)?(?:prompt|instruction)",
]

# PII patterns
PII_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "phone_us": r"\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
    "ipv4": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
}

# Maximum input lengths
MAX_INPUT_LENGTHS = {
    "topic": 500,
    "title": 200,
    "image_description": 1000,
    "feedback": 1000,
    "keywords_single": 50,
    "company_name": 100,
    "tagline": 200,
    "address": 500,
    "tone": 50,
}


def sanitize_html(text: str) -> str:
    """Sanitize HTML to prevent XSS."""
    return html.escape(text)


def sanitize_for_logging(text: str, max_length: int = 200) -> str:
    """Sanitize text for safe logging (truncate, remove newlines)."""
    if not text:
        return ""
    # Remove control characters except newlines/tabs
    cleaned = "".join(c for c in text if c.isprintable() or c in "\n\t")
    # Truncate
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length] + "..."
    return cleaned


def detect_prompt_injection(text: str) -> List[str]:
    """Detect potential prompt injection attempts."""
    detected = []
    text_lower = text.lower()
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, text_lower):
            detected.append(pattern)
    return detected


def detect_pii(text: str) -> Dict[str, List[str]]:
    """Detect personally identifiable information."""
    found = {}
    for pii_type, pattern in PII_PATTERNS.items():
        matches = re.findall(pattern, text)
        if matches:
            found[pii_type] = matches
    return found


def validate_input_length(field: str, value: str) -> bool:
    """Validate input doesn't exceed maximum length."""
    max_len = MAX_INPUT_LENGTHS.get(field)
    if max_len and len(value) > max_len:
        return False
    return True


def sanitize_user_input(text: str, field: str = "general") -> str:
    """Comprehensive input sanitization."""
    if not text:
        return ""
    
    # Check length
    if not validate_input_length(field, text):
        logger.warning(f"Input exceeds max length for {field}: {len(text)} chars")
        # Truncate to max
        max_len = MAX_INPUT_LENGTHS.get(field, 1000)
        text = text[:max_len]
    
    # Remove null bytes
    text = text.replace("\x00", "")
    
    # Normalize whitespace
    text = " ".join(text.split())
    
    return text


def is_safe_url(url: str, allowed_domains: Optional[List[str]] = None) -> bool:
    """Validate URL is safe (HTTPS, allowed domains)."""
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return False
        if allowed_domains:
            if parsed.netloc not in allowed_domains:
                return False
        return True
    except Exception:
        return False


def mask_secrets(text: str) -> str:
    """Mask potential secrets in text for logging."""
    # Mask API keys (sk-..., Bearer ..., etc.)
    patterns = [
        (r"(sk-[a-zA-Z0-9]{32,})", "sk-***"),
        (r"(Bearer\s+[a-zA-Z0-9._-]{20,})", "Bearer ***"),
        (r"(api[_-]?key['\"]?\s*[:=]\s*['\"]?[a-zA-Z0-9._-]{20,})", "api_key=***"),
        (r"(secret[_-]?key['\"]?\s*[:=]\s*['\"]?[a-zA-Z0-9._-]{20,})", "secret_key=***"),
        (r"(password['\"]?\s*[:=]\s*['\"]?[^\s'\"]{8,})", "password=***"),
    ]
    result = text
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


class InputValidator:
    """Comprehensive input validation for API endpoints."""
    
    def __init__(self):
        self.errors: List[str] = []
    
    def validate(self, field: str, value: Any, rules: Dict) -> bool:
        """Validate a field against rules."""
        self.errors = []
        
        # Required
        if rules.get("required", False) and (value is None or value == ""):
            self.errors.append(f"{field} is required")
            return False
        
        if value is None:
            return True
        
        # Type
        expected_type = rules.get("type")
        if expected_type and not isinstance(value, expected_type):
            self.errors.append(f"{field} must be {expected_type.__name__}")
            return False
        
        # String-specific
        if isinstance(value, str):
            # Length
            if "max_length" in rules and len(value) > rules["max_length"]:
                self.errors.append(f"{field} exceeds maximum length of {rules['max_length']}")
                return False
            if "min_length" in rules and len(value) < rules["min_length"]:
                self.errors.append(f"{field} must be at least {rules['min_length']} characters")
                return False
            
            # Pattern
            if "pattern" in rules:
                if not re.match(rules["pattern"], value):
                    self.errors.append(f"{field} format is invalid")
                    return False
            
            # Prompt injection check
            if rules.get("check_injection", True):
                injections = detect_prompt_injection(value)
                if injections:
                    logger.warning(f"Prompt injection detected in {field}: {injections}")
                    self.errors.append(f"{field} contains potentially malicious content")
                    return False
            
            # PII check
            if rules.get("check_pii", False):
                pii = detect_pii(value)
                if pii:
                    logger.warning(f"PII detected in {field}: {list(pii.keys())}")
                    self.errors.append(f"{field} contains personally identifiable information")
                    return False
        
        # Numeric range
        if isinstance(value, (int, float)):
            if "min" in rules and value < rules["min"]:
                self.errors.append(f"{field} must be at least {rules['min']}")
                return False
            if "max" in rules and value > rules["max"]:
                self.errors.append(f"{field} must be at most {rules['max']}")
                return False
        
        # Enum
        if "enum" in rules and value not in rules["enum"]:
            self.errors.append(f"{field} must be one of: {', '.join(rules['enum'])}")
            return False
        
        return True
    
    def get_errors(self) -> List[str]:
        return self.errors


# Rate limiting helpers
class RateLimiter:
    """In-memory rate limiter (use Redis in production)."""
    
    def __init__(self):
        self.requests: Dict[str, List[float]] = {}
    
    def is_allowed(self, key: str, limit: int, window_seconds: int) -> bool:
        import time
        now = time.time()
        
        if key not in self.requests:
            self.requests[key] = []
        
        # Remove old requests outside window
        self.requests[key] = [t for t in self.requests[key] if now - t < window_seconds]
        
        if len(self.requests[key]) >= limit:
            return False
        
        self.requests[key].append(now)
        return True
    
    def get_remaining(self, key: str, limit: int, window_seconds: int) -> int:
        import time
        now = time.time()
        if key not in self.requests:
            return limit
        current = len([t for t in self.requests[key] if now - t < window_seconds])
        return max(0, limit - current)