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

from app.core.config import get_settings, init_langsmith
from app.core.logging import (
    RequestContext,
    log_llm_call,
    log_llm_error,
    log_llm_fallback,
    log_llm_response,
)

# Initialize LangSmith tracing before any LLM is instantiated
init_langsmith()

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
    max_tokens: int = 8192
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
        request_id = RequestContext.get_request_id()

        # If company forces OpenAI or global circuit open, use OpenAI directly
        if company_openai_only or self._check_global_circuit():
            if self._openai_model:
                self.metrics["openai_fallbacks"] += 1
                logger.info(
                    "Routing to OpenAI (company_openai_only=%s, global_circuit=%s)",
                    company_openai_only,
                    self._global_circuit_open,
                )
                return await self._invoke_with_logging(
                    self._openai_model, messages, require_json, require_tools, request_id
                )
            raise RuntimeError("OpenAI fallback not configured")

        # Try free models first
        last_model: Optional[str] = None
        for model_config in self._free_models:
            # Skip if circuit breaker open for this model
            cb = self._get_circuit_breaker(model_config.name)
            if cb.is_open:
                continue
            last_model = model_config.name

            try:
                return await self._invoke_with_logging(
                    model_config, messages, require_json, require_tools, request_id
                )
            except Exception as e:
                logger.warning("Free model %s failed: %s", model_config.name, e)
                self._record_failure(model_config.name)
                self.metrics["errors"] += 1

                # Check if we should fallback to OpenAI
                if self._should_fallback(e):
                    if self._openai_model:
                        log_llm_fallback(
                            model_config.name,
                            self._openai_model.name,
                            str(e),
                            request_id=request_id,
                        )
                        logger.info("Falling back to OpenAI after free model failure")
                        self.metrics["openai_fallbacks"] += 1
                        return await self._invoke_with_logging(
                            self._openai_model, messages, require_json, require_tools, request_id
                        )

        # All free models failed, try OpenAI
        if self._openai_model:
            log_llm_fallback(
                last_model or "free_models",
                self._openai_model.name,
                "all free models failed or circuit open",
                request_id=request_id,
            )
            self.metrics["openai_fallbacks"] += 1
            return await self._invoke_with_logging(
                self._openai_model, messages, require_json, require_tools, request_id
            )

        raise RuntimeError("All models failed and no OpenAI fallback available")

    def _last_message_text(self, messages: List[BaseMessage]) -> str:
        """Extract text from the last message for LLM call logging."""
        if not messages:
            return ""
        content = getattr(messages[-1], "content", "")
        if isinstance(content, list):
            content = " ".join(str(part) for part in content)
        return str(content)

    async def _invoke_with_logging(
        self,
        config: ModelConfig,
        messages: List[BaseMessage],
        require_json: bool,
        require_tools: bool,
        request_id: Optional[str],
    ) -> ChatResult:
        """Invoke a single model with structured LLM call/response/error logging."""
        provider = config.provider.value
        model = config.name
        prompt = self._last_message_text(messages)

        log_llm_call(
            provider,
            model,
            prompt=prompt,
            request_id=request_id,
            require_json=require_json,
        )

        start = time.perf_counter()
        try:
            result = await self._try_model(config, messages, require_json, require_tools)
            response_text = result.generations[0].text if result.generations else ""
            log_llm_response(
                provider,
                model,
                response=response_text,
                latency_ms=(time.perf_counter() - start) * 1000,
                request_id=request_id,
            )
            self._record_success(config.name)
            if config.provider == ModelProvider.OPENROUTER_FREE:
                self.metrics["free_requests"] += 1
            return result
        except Exception as e:
            log_llm_error(
                provider,
                model,
                e,
                latency_ms=(time.perf_counter() - start) * 1000,
                request_id=request_id,
            )
            raise

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
            # ainvoke returns AIMessage in newer LangChain, wrap in ChatResult for compatibility
            response = await asyncio.wait_for(
                model.ainvoke(messages),
                timeout=60.0,  # 60 second timeout
            )
            # Wrap AIMessage in ChatResult format expected by nodes
            return ChatResult(generations=[ChatGeneration(message=response)])
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