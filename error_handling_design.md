# Error Handling and Retry Logic Design

## Overview
This document outlines the design for implementing comprehensive error handling and retry logic in the hierarchical marketing agents system, ensuring resilience against failures in LLMs, external APIs, and internal components.

## Current Limitations
1. **Minimal error handling**: Basic try-catch blocks with limited recovery
2. **No retry logic**: Failures cause immediate workflow termination
3. **No circuit breakers**: Repeated failures not detected or handled
4. **No fallback strategies**: No alternative paths when primary components fail
5. **Poor error reporting**: Limited context in error messages

## Design Goals
1. **Graceful degradation**: Continue operation despite partial failures
2. **Intelligent retries**: Retry with exponential backoff and jitter
3. **Circuit breaking**: Detect and isolate failing components
4. **Fallback mechanisms**: Alternative strategies when primary fails
5. **Comprehensive logging**: Detailed error context for debugging
6. **User-friendly errors**: Clear, actionable error messages

## Architecture

### 1. Error Hierarchy

```python
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

class ErrorSeverity(Enum):
    """Error severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    """Error categories"""
    LLM_ERROR = "llm_error"
    API_ERROR = "api_error"
    NETWORK_ERROR = "network_error"
    VALIDATION_ERROR = "validation_error"
    CONFIGURATION_ERROR = "configuration_error"
    TIMEOUT_ERROR = "timeout_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    AUTHORIZATION_ERROR = "authorization_error"
    RESOURCE_ERROR = "resource_error"
    UNKNOWN_ERROR = "unknown_error"

@dataclass
class SystemError(Exception):
    """Base system error with enhanced metadata"""
    message: str
    category: ErrorCategory
    severity: ErrorSeverity = ErrorSeverity.ERROR
    component: Optional[str] = None
    operation: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    original_exception: Optional[Exception] = None
    retryable: bool = True
    suggested_action: Optional[str] = None
    
    def __str__(self) -> str:
        """Enhanced string representation"""
        base = f"[{self.category.value}] {self.message}"
        if self.component:
            base = f"{base} (component: {self.component})"
        if self.operation:
            base = f"{base} (operation: {self.operation})"
        return base
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return {
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "component": self.component,
            "operation": self.operation,
            "context": self.context,
            "retryable": self.retryable,
            "suggested_action": self.suggested_action,
            "timestamp": datetime.now().isoformat()
        }

# Specialized error types
class LLMError(SystemError):
    """LLM-related errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.LLM_ERROR, **kwargs)

class APIError(SystemError):
    """External API errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.API_ERROR, **kwargs)

class RateLimitError(APIError):
    """Rate limit errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)
        self.retryable = True
        self.suggested_action = "Wait before retrying or use alternative provider"

class TimeoutError(SystemError):
    """Timeout errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.TIMEOUT_ERROR, **kwargs)
        self.retryable = True

class ValidationError(SystemError):
    """Validation errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.VALIDATION_ERROR, **kwargs)
        self.retryable = False
        self.suggested_action = "Check input data and fix validation issues"
```

### 2. Retry Manager with Exponential Backoff

```python
import asyncio
import random
from typing import Callable, Optional, Type, Tuple, List
from datetime import datetime, timedelta
from functools import wraps

class RetryConfig:
    """Configuration for retry behavior"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,  # seconds
        max_delay: float = 60.0,  # seconds
        exponential_base: float = 2.0,
        jitter: bool = True,
        retry_on_exceptions: Tuple[Type[Exception], ...] = (Exception,),
        stop_on_exceptions: Tuple[Type[Exception], ...] = (),
        before_retry: Optional[Callable] = None,
        after_retry: Optional[Callable] = None
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retry_on_exceptions = retry_on_exceptions
        self.stop_on_exceptions = stop_on_exceptions
        self.before_retry = before_retry
        self.after_retry = after_retry

class RetryManager:
    """Manages retry logic with exponential backoff"""
    
    def __init__(self, config: RetryConfig):
        self.config = config
        self.metrics = {
            "total_retries": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "total_delay_time": 0.0
        }
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt"""
        delay = self.config.base_delay * (self.config.exponential_base ** (attempt - 1))
        
        # Apply jitter
        if self.config.jitter:
            jitter_factor = random.uniform(0.5, 1.5)
            delay *= jitter_factor
        
        # Cap at max delay
        return min(delay, self.config.max_delay)
    
    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """Determine if operation should be retried"""
        # Check max attempts
        if attempt >= self.config.max_attempts:
            return False
        
        # Check if exception is in stop list
        if any(isinstance(exception, exc_type) for exc_type in self.config.stop_on_exceptions):
            return False
        
        # Check if exception is in retry list
        if any(isinstance(exception, exc_type) for exc_type in self.config.retry_on_exceptions):
            return True
        
        # For SystemError, check retryable flag
        if isinstance(exception, SystemError):
            return exception.retryable
        
        return False
    
    async def execute_with_retry(
        self, 
        operation: Callable,
        operation_name: str,
        *args,
        **kwargs
    ) -> Any:
        """Execute operation with retry logic"""
        last_exception = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                # Execute operation
                result = await operation(*args, **kwargs)
                
                # Record success on retry
                if attempt > 1:
                    self.metrics["successful_retries"] += 1
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Check if we should retry
                if not self.should_retry(e, attempt):
                    break
                
                # Calculate and apply delay
                delay = self.calculate_delay(attempt)
                self.metrics["total_delay_time"] += delay
                
                # Call before_retry hook
                if self.config.before_retry:
                    await self.config.before_retry(
                        operation_name=operation_name,
                        exception=e,
                        attempt=attempt,
                        delay=delay
                    )
                
                # Wait before retry
                await asyncio.sleep(delay)
                
                # Call after_retry hook
                if self.config.after_retry:
                    await self.config.after_retry(
                        operation_name=operation_name,
                        attempt=attempt
                    )
        
        # All attempts failed
        self.metrics["failed_retries"] += 1
        self.metrics["total_retries"] += self.config.max_attempts - 1
        
        # Wrap exception if needed
        if not isinstance(last_exception, SystemError):
            last_exception = SystemError(
                message=f"Operation '{operation_name}' failed after {self.config.max_attempts} attempts",
                category=ErrorCategory.UNKNOWN_ERROR,
                component=operation_name,
                original_exception=last_exception,
                retryable=False
            )
        
        raise last_exception
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get retry metrics"""
        return self.metrics.copy()

# Decorator for easy retry application
def with_retry(config: RetryConfig):
    """Decorator to add retry logic to async functions"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            retry_manager = RetryManager(config)
            operation_name = func.__name__
            return await retry_manager.execute_with_retry(
                func, operation_name, *args, **kwargs
            )
        return wrapper
    return decorator
```

### 3. Circuit Breaker Pattern

```python
from typing import Optional, Callable
from datetime import datetime, timedelta
from enum import Enum

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit open, failing fast
    HALF_OPEN = "half_open" # Testing if service recovered

class CircuitBreaker:
    """Implements circuit breaker pattern"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,  # seconds
        half_open_max_attempts: int = 3,
        name: str = "default"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_attempts = half_open_max_attempts
        self.name = name
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_attempts = 0
        self.metrics = {
            "total_requests": 0,
            "failed_requests": 0,
            "circuit_opens": 0,
            "circuit_closes": 0
        }
    
    def can_execute(self) -> bool:
        """Check if operation can be executed"""
        self.metrics["total_requests"] += 1
        
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self.last_failure_time and \
               datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                self.state = CircuitState.HALF_OPEN
                self.half_open_attempts = 0
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_attempts < self.half_open_max_attempts:
                self.half_open_attempts += 1
                return True
            return False
        
        return False
    
    def record_success(self):
        """Record successful execution"""
        if self.state == CircuitState.HALF_OPEN:
            # Success in half-open state, close circuit
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.half_open_attempts = 0
            self.metrics["circuit_closes"] += 1
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success streak
            self.failure_count = max(0, self.failure_count - 1)
    
    def record_failure(self):
        """Record failed execution"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        self.metrics["failed_requests"] += 1
        
        if self.state == CircuitState.HALF_OPEN:
            # Failure in half-open state, open circuit again
            self.state = CircuitState.OPEN
            self.metrics["circuit_opens"] += 1
        elif self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
            # Too many failures, open circuit
            self.state = CircuitState.OPEN
            self.metrics["circuit_opens"] += 1
    
    async def execute(
        self,
        operation: Callable,
        fallback: Optional[Callable] = None,
        *args,
        **kwargs
    ) -> Any:
        """Execute operation with circuit breaker"""
        if not self.can_execute():
            if fallback:
                return await fallback(*args, **kwargs)
            raise SystemError(
                message=f"Circuit breaker '{self.name}' is OPEN",
                category=ErrorCategory.RESOURCE_ERROR,
                component=self.name,
                retryable=True,
                suggested_action=f"Wait {self.recovery_timeout} seconds before retrying"
            )
        
        try:
            result = await operation(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            
            # Try fallback if available
            if fallback:
                try:
                    return await fallback(*args, **kwargs)
                except Exception as fallback_error:
                    raise SystemError(
                        message=f"Primary operation and fallback both failed",
                        category=ErrorCategory.RESOURCE_ERROR,
                        component=self.name,
                        original_exception=e,
                        context={"fallback_error": str(fallback_error)}
                    )
            
            raise
    
    def get_state_info(self) -> Dict[str, Any]:
        """Get circuit breaker state information"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "half_open_attempts": self.half_open_attempts,
            "metrics": self.metrics
        }
```

### 4. Fallback Strategy Manager

```python
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum

class FallbackStrategy(Enum):
    """Fallback strategies"""
    USE_ALTERNATIVE_PROVIDER = "use_alternative_provider"
    USE_CACHED_RESULT = "use_cached_result"
    USE_SIMPLIFIED_LOGIC = "use_simplified_logic"
    RETURN_DEFAULT_VALUE = "return_default_value"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    FAIL_GRACEFULLY = "fail_gracefully"

@dataclass
class FallbackOption:
    """Fallback option configuration"""
    strategy: FallbackStrategy
    priority: int  # Lower number = higher priority
    condition: Optional[Callable[[Exception], bool]] = None
    implementation: Callable
    description: str = ""

class FallbackManager:
    """Manages fallback strategies for failed operations"""
    
    def __init__(self):
        self.strategies: Dict[str, List[FallbackOption]] = {}
        self.cache = {}  # Simple cache for fallback results
    
    def register_fallback(
        self,
        operation_name: str,
        strategy: FallbackStrategy,
        implementation: Callable,
        priority: int = 1,
        condition: Optional[Callable[[Exception], bool]] = None,
        description: str = ""
    ):
        """Register a fallback strategy for an operation"""
        if operation_name not in self.strategies:
            self.strategies[operation_name] = []
        
        option = FallbackOption(
            strategy=strategy,
            priority=priority,
            condition=condition,
            implementation=implementation,
            description=description
        )
        
        self.strategies[operation_name].append(option)
        # Sort by priority
        self.strategies[operation_name].sort(key=lambda x: x.priority)
    
    async def execute_with_fallback(
        self,
        operation_name: str,
        primary_operation: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute operation with fallback strategies"""
        try:
            return await primary_operation(*args, **kwargs)
        except Exception as primary_error:
            # Get available fallbacks for this operation
            fallback_options = self.strategies.get(operation_name, [])
            
            if not fallback_options:
                raise primary_error
            
            # Try fallbacks in priority order
            for option in fallback_options:
                # Check condition if specified
                if option.condition and not option.condition(primary_error):
                    continue
                
                try:
                    result = await option.implementation(*args, **kwargs)
                    
                    # Log fallback usage
                    self._log_fallback_usage(
                        operation_name=operation_name,
                        strategy=option.strategy,
                        primary_error=primary_error,
                        success=True
                    )
                    
                    return result
                    
                except Exception as fallback_error:
                    # Fallback also failed, try next one
                    self._log_fallback_usage(
                        operation_name=operation_name,
                        strategy=option.strategy,
                        primary_error=primary_error,
                        success=False,
                        fallback_error=fallback_error
                    )
