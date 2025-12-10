"""Ollama LLM client wrapper with retry logic and structured output support."""

import json
import logging
from typing import Any, Type, TypeVar

import ollama
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class OllamaClient:
    """Client wrapper for Ollama LLM interactions.
    
    Provides a simplified interface for generating text and structured outputs
    from Ollama models with built-in retry logic and error handling.
    
    Example:
        >>> client = OllamaClient()
        >>> response = client.generate("What is a goblin?")
        >>> print(response)
        
        >>> # With structured output
        >>> class ActionPlan(BaseModel):
        ...     action: str
        ...     target: str
        >>> plan = client.generate("Attack the goblin", response_format=ActionPlan)
        >>> print(plan.action)
    """
    
    DEFAULT_MODEL = "mistral:7b"
    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_TIMEOUT = 30.0
    MAX_RETRIES = 3
    
    def __init__(
        self,
        model_name: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
    ):
        """Initialize the Ollama client.
        
        Args:
            model_name: The model to use. Defaults to mistral:7b.
            base_url: Ollama server URL. Defaults to http://localhost:11434.
            timeout: Request timeout in seconds. Defaults to 30.
        """
        self.model_name = model_name or self.DEFAULT_MODEL
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        
        # Initialize the ollama client with custom host
        self._client = ollama.Client(host=self.base_url, timeout=self.timeout)
        
        logger.debug(
            "Initialized OllamaClient with model=%s, base_url=%s, timeout=%s",
            self.model_name,
            self.base_url,
            self.timeout,
        )
    
    def health_check(self) -> bool:
        """Check if Ollama server is available and the model is loaded.
        
        Returns:
            True if the server is healthy and model is available, False otherwise.
        """
        try:
            models = self._client.list()
            model_names = [m.model for m in models["models"]]
            
            # Check if our model is available (handle both exact match and prefix match)
            model_base = self.model_name.split(":")[0]
            is_available = any(
                self.model_name == name or name.startswith(model_base)
                for name in model_names
            )
            
            if is_available:
                logger.debug("Health check passed. Model %s is available.", self.model_name)
            else:
                logger.warning(
                    "Model %s not found. Available models: %s",
                    self.model_name,
                    model_names,
                )
            
            return is_available
            
        except Exception as e:
            logger.error("Health check failed: %s", e)
            return False
    
    def generate(
        self,
        prompt: str,
        system: str | None = None,
        response_format: Type[T] | None = None,
    ) -> str | T:
        """Generate a response from the LLM.
        
        Args:
            prompt: The user prompt to send.
            system: Optional system prompt for context.
            response_format: Optional Pydantic model for structured output.
                If provided, the response will be parsed and validated
                into an instance of this model.
        
        Returns:
            The generated text response as a string, or a Pydantic model
            instance if response_format is provided.
        
        Raises:
            ollama.ResponseError: If the LLM request fails after all retries.
            ValueError: If response_format is provided but parsing fails.
        """
        logger.debug(
            "generate() called - prompt_len=%d, system=%s, structured=%s",
            len(prompt),
            "yes" if system else "no",
            response_format.__name__ if response_format else "no",
        )
        
        # Build message list
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        # Configure format for structured output
        format_spec = None
        if response_format is not None:
            format_spec = response_format.model_json_schema()
        
        # Attempt generation with retries
        last_error: Exception | None = None
        
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.debug("Generation attempt %d/%d", attempt, self.MAX_RETRIES)
                
                response = self._client.chat(
                    model=self.model_name,
                    messages=messages,
                    format=format_spec,
                )
                
                content = response['message']['content']
                logger.debug("Response received - length=%d", len(content))
                
                # Parse structured output if requested
                if response_format is not None:
                    return self._parse_structured_response(content, response_format)
                
                return content
                
            except ollama.ResponseError as e:
                last_error = e
                logger.warning("Attempt %d failed with ResponseError: %s", attempt, e)
                if attempt == self.MAX_RETRIES:
                    raise
                    
            except Exception as e:
                last_error = e
                logger.warning("Attempt %d failed with error: %s", attempt, e)
                if attempt == self.MAX_RETRIES:
                    raise
        
        # Should not reach here, but handle edge case
        raise last_error or RuntimeError("Generation failed after all retries")
    
    def _parse_structured_response(self, content: str, response_format: Type[T]) -> T:
        """Parse and validate a JSON response into a Pydantic model.
        
        Args:
            content: The raw JSON string from the LLM.
            response_format: The Pydantic model class to parse into.
        
        Returns:
            An instance of the response_format model.
        
        Raises:
            ValueError: If parsing or validation fails.
        """
        try:
            parsed = json.loads(content)
            result = response_format.model_validate(parsed)
            logger.debug("Successfully parsed response into %s", response_format.__name__)
            return result
        except json.JSONDecodeError as e:
            logger.error("JSON parsing failed: %s", e)
            raise ValueError(f"Invalid JSON in response: {e}") from e
        except Exception as e:
            logger.error("Validation failed for %s: %s", response_format.__name__, e)
            raise ValueError(f"Failed to validate as {response_format.__name__}: {e}") from e
    
    def generate_json(
        self,
        prompt: str,
        system: str | None = None,
    ) -> dict[str, Any]:
        """Generate a JSON response from the LLM with retry logic.
        
        This is a convenience method for when you need raw JSON dict output
        without a specific Pydantic model schema.
        
        Args:
            prompt: The user prompt to send.
            system: Optional system prompt for context.
        
        Returns:
            The parsed JSON response as a dictionary.
        
        Raises:
            ValueError: If the response cannot be parsed as valid JSON.
            ollama.ResponseError: If the LLM request fails after all retries.
        """
        logger.debug("generate_json() called - prompt_len=%d", len(prompt))
        
        # Ensure prompt asks for JSON if not already specified
        json_prompt = prompt
        if "json" not in prompt.lower():
            json_prompt = f"{prompt}\n\nRespond with valid JSON only."
        
        # Build message list
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": json_prompt})
        
        # Attempt generation with retries
        last_error: Exception | None = None
        
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.debug("JSON generation attempt %d/%d", attempt, self.MAX_RETRIES)
                
                response = self._client.chat(
                    model=self.model_name,
                    messages=messages,
                    format="json",
                )
                
                content = response['message']['content']
                logger.debug("JSON response received - length=%d", len(content))
                
                result = json.loads(content)
                logger.debug("Successfully parsed JSON response")
                return result
                
            except json.JSONDecodeError as e:
                last_error = e
                logger.warning("Attempt %d: JSON parsing failed: %s", attempt, e)
                if attempt == self.MAX_RETRIES:
                    raise ValueError(
                        f"Failed to get valid JSON after {self.MAX_RETRIES} attempts"
                    ) from e
                    
            except ollama.ResponseError as e:
                last_error = e
                logger.warning("Attempt %d failed with ResponseError: %s", attempt, e)
                if attempt == self.MAX_RETRIES:
                    raise
                    
            except Exception as e:
                last_error = e
                logger.warning("Attempt %d failed with error: %s", attempt, e)
                if attempt == self.MAX_RETRIES:
                    raise
        
        raise ValueError(f"Failed to get valid JSON after {self.MAX_RETRIES} attempts: {last_error}")