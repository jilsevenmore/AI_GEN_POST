"""Model router with free-first OpenRouter + OpenAI fallback."""
import os
import time
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock

from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult, ChatGeneration

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ModelProvider(str, Enum):
    OPENROUTER_FREE = "openrouter_free"
    OPENROUTER_PAID = "openrouter_paid"
    OPENAI = "openai"


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    name: str
    provider: ModelProvider
    api_key: str
    base_url: str
    supports_json: bool = True
    supports_tools: bool = True
    max_tokens: int = 4096
    temperature: float = 0.7


@dataclass
class CircuitBreakerState:
    """Circuit breaker state for a model/provider."""
    failure_count: int = 0
    last_failure_time: float = 0
    is_open: bool = False
    lock: Lock = field(default_factory=Lock)


class ModelRouter:
    """
    Routes requests to models with free-first strategy, fallback, and circuit breaker.
    
    Priority:
    1. Free OpenRouter models (pinned list + router)
    2. OpenAI (fallback on 429, timeout, bad JSON)
    3. Circuit breaker opens after N failures -> routes all to OpenAI for T minutes
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._circuit_breakers: Dict[str, CircuitBreakerState] = {}
        self._global_circuit_open = False
        self._global_circuit_open_time = 0
        self._lock = Lock()
        
        # Initialize model configs
        self._free_models = self._init_free_models()
        self._openai_model = self._init_openai_model()
        
        # Metrics
        self.metrics = {
            "free_requests": 0,
            "openai_fallbacks": 0,
            "circuit_breaker_triggers": 0,
            "errors": 0,
        }
    
    def _init_free_models(self) -> List[ModelConfig]:
        """Initialize free OpenRouter model configs."""
        models = []
        api_key = self.settings.OPENROUTER_API_KEY
        base_url = self.settings.OPENROUTER_BASE_URL
        
        # Pinned free models
        for model_name in self.settings.OPENROUTER_FREE_MODELS:
            models.append(ModelConfig(
                name=model_name,
                provider=ModelProvider.OPENROUTER_FREE,
                api_key=api_key,
                base_url=base_url,
                supports_json=True,
                supports_tools=True,
            ))
        
        # Free router (OpenRouter picks best free model)
        models.append(ModelConfig(
            name=self.settings.OPENROUTER_FREE_ROUTER,
            provider=ModelProvider.OPENROUTER_FREE,
            api_key=api_key,
            base_url=base_url,
            supports_json=True,
            supports_tools=True,
        ))
        
        return models
    
    def _init_openai_model(self) -> Optional[ModelConfig]:
        """Initialize OpenAI fallback model config."""
        if not self.settings.OPENAI_API_KEY or not self.settings.OPENAI_FALLBACK_ENABLED:
            return None
        
        return ModelConfig(
            name=self.settings.OPENAI_MODEL,
            provider=ModelProvider.OPENAI,
            api_key=self.settings.OPENAI_API_KEY,
            base_url="https://api.openai.com/v1",
            supports_json=True,
            supports_tools=True,
        )
    
    def _get_circuit_breaker(self, key: str) -> CircuitBreakerState:
        """Get or create circuit breaker for a key."""
        if key not in self._circuit_breakers:
            self._circuit_breakers[key] = CircuitBreakerState()
        return self._circuit_breakers[key]
    
    def _record_failure(self, key: str) -> None:
        """Record a failure for circuit breaker."""
        cb = self._get_circuit_breaker(key)
        with cb.lock:
            cb.failure_count += 1
            cb.last_failure_time = time.time()
            
            # Open circuit after 3 failures
            if cb.failure_count >= 3:
                cb.is_open = True
                logger.warning(f"Circuit breaker opened for {key}")
                
                # Check if global circuit should open
                open_count = sum(1 for cb in self._circuit_breakers.values() if cb.is_open)
                if open_count >= 2:  # Multiple models failing
                    self._open_global_circuit()
    
    def _record_success(self, key: str) -> None:
        """Record a success, potentially closing circuit."""
        cb = self._get_circuit_breaker(key)
        with cb.lock:
            cb.failure_count = 0
            cb.is_open = False
    
    def _open_global_circuit(self) -> None:
        """Open global circuit breaker - route all to OpenAI."""
        with self._lock:
            if not self._global_circuit_open:
                self._global_circuit_open = True
                self._global_circuit_open_time = time.time()
                self.metrics["circuit_breaker_triggers"] += 1
                logger.warning("Global circuit breaker opened - routing all to OpenAI")
    
    def _check_global_circuit(self) -> bool:
        """Check if global circuit is still open (auto-close after 5 min)."""
        with self._lock:
            if self._global_circuit_open:
                if time.time() - self._global_circuit_open_time > 300:  # 5 minutes
                    self._global_circuit_open = False
                    # Reset all individual circuits
                    for cb in self._circuit_breakers.values():
                        with cb.lock:
                            cb.failure_count = 0
                            cb.is_open = False
                    logger.info("Global circuit breaker closed")
                    return False
                return True
            return False
    
    def _create_chat_model(self, config: ModelConfig) -> ChatOpenAI:
        """Create a LangChain ChatOpenAI instance (works for OpenRouter too)."""
        return ChatOpenAI(
            model=config.name,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            model_kwargs={
                "response_format": {"type": "json_object"} if config.supports_json else None,
            } if config.supports_json else {},
        )
    
    async def ainvoke(
        self,
        messages: List[BaseMessage],
        require_json: bool = False,
        require_tools: bool = False,
        company_openai_only: bool = False,
    ) -> ChatResult:
        """
        Invoke with automatic fallback.
        
        Args:
            messages: Chat messages
            require_json: Need JSON response
            require_tools: Need tool calling
            company_openai_only: Company setting to force OpenAI
        """
        # If company forces OpenAI or global circuit open, use OpenAI directly
        if company_openai_only or self._check_global_circuit():
            if self._openai_model:
                self.metrics["openai_fallbacks"] += 1
                return await self._try_model(self._openai_model, messages, require_json, require_tools)
            raise RuntimeError("OpenAI fallback not configured")
        
        # Try free models first
        for model_config in self._free_models:
            # Skip if circuit breaker open for this model
            cb = self._get_circuit_breaker(model_config.name)
            if cb.is_open:
                continue
            
            try:
                result = await self._try_model(model_config, messages, require_json, require_tools)
                self._record_success(model_config.name)
                self.metrics["free_requests"] += 1
                return result
            except Exception as e:
                logger.warning(f"Free model {model_config.name} failed: {e}")
                self._record_failure(model_config.name)
                self.metrics["errors"] += 1
                
                # Check if we should fallback to OpenAI
                if self._should_fallback(e):
                    if self._openai_model:
                        logger.info(f"Falling back to OpenAI after free model failure")
                        self.metrics["openai_fallbacks"] += 1
                        return await self._try_model(self._openai_model, messages, require_json, require_tools)
        
        # All free models failed, try OpenAI
        if self._openai_model:
            self.metrics["openai_fallbacks"] += 1
            return await self._try_model(self._openai_model, messages, require_json, require_tools)
        
        raise RuntimeError("All models failed and no OpenAI fallback available")
    
    def _should_fallback(self, error: Exception) -> bool:
        """Determine if error should trigger fallback."""
        error_str = str(error).lower()
        # Fallback on rate limit, timeout, or JSON parsing errors
        fallback_indicators = [
            "429", "rate limit", "rate_limit",
            "timeout", "timed out",
            "json", "parse", "decoding",
            "context length", "max tokens",
        ]
        return any(indicator in error_str for indicator in fallback_indicators)
    
    async def _try_model(
        self,
        config: ModelConfig,
        messages: List[BaseMessage],
        require_json: bool,
        require_tools: bool,
    ) -> ChatResult:
        """Try a specific model with timeout."""
        model = self._create_chat_model(config)
        
        # Add timeout via asyncio
        import asyncio
        try:
            return await asyncio.wait_for(
                model.ainvoke(messages),
                timeout=60.0,  # 60 second timeout
            )
        except asyncio.TimeoutError:
            raise RuntimeError(f"Model {config.name} timed out")
    
    def get_metrics(self) -> Dict[str, int]:
        """Get router metrics."""
        return self.metrics.copy()


# Singleton instance
_router_instance: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    """Get or create the singleton model router."""
    global _router_instance
    if _router_instance is None:
        _router_instance = ModelRouter()
    return _router_instance