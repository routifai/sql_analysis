#!/usr/bin/env python3
"""
Simple LLM Client for Text-to-SQL MCP Client
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv
import openai

load_dotenv()

logger = logging.getLogger(__name__)


class LLMClient:
    """Simple LLM client wrapper for OpenAI"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("SQL_MODEL", "gpt-4o-mini")
        self.base_url = os.getenv("OPENAI_BASE_URL")
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        # Initialize OpenAI client
        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
            
        self.client = openai.OpenAI(**client_kwargs)
        self.async_client = openai.AsyncOpenAI(**client_kwargs)
        
        logger.info(f"LLM Client initialized with model: {self.model}")
    
    def get_async_client(self):
        """Get async OpenAI client"""
        return self.async_client
    
    def is_available(self) -> bool:
        """Check if LLM client is available"""
        try:
            # Simple test call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=1
            )
            return True
        except Exception as e:
            logger.error(f"LLM availability check failed: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test connection to LLM service"""
        return self.is_available()


def get_llm_client() -> LLMClient:
    """Get LLM client instance"""
    return LLMClient()
