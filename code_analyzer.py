import groq
import os
import json
import time
from functools import lru_cache
import logging
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, calls_per_minute: int = 50):
        self.calls_per_minute = calls_per_minute
        self.calls = []
        
    def wait_if_needed(self):
        now = time.time()
        # Remove calls older than 1 minute
        self.calls = [call for call in self.calls if now - call < 60]
        
        if len(self.calls) >= self.calls_per_minute:
            sleep_time = 60 - (now - self.calls[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        self.calls.append(now)

class CodeMetrics:
    @staticmethod
    def calculate_complexity(code: str) -> Dict[str, int]:
        """Calculate code complexity metrics"""
        metrics = {
            "lines": len(code.splitlines()),
            "functions": len([l for l in code.splitlines() if l.strip().startswith("def ")]),
            "classes": len([l for l in code.splitlines() if l.strip().startswith("class ")]),
            "comments": len([l for l in code.splitlines() if l.strip().startswith("#")])
        }
        return metrics

class CodeAnalyzer:
    """Analyzer for code review and chat functionality."""
    
    def __init__(self):
        """Initialize the analyzer with API key."""
        load_dotenv()
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            logger.warning("GROQ_API_KEY not found in environment variables")
            api_key = "demo_key"  # Fallback for development only
        self.client = groq.Client(api_key=api_key)
        self.model = "mixtral-8x7b-32768"  # Using Mixtral for better context handling
        self.chat_context = []
        self.rate_limiter = RateLimiter()
        self.metrics = CodeMetrics()
        
    def analyze_code(self, code: str) -> Dict[str, Any]:
        """Analyze code and return review results."""
        try:
            # Prepare the prompt
            prompt = f"""
            Please review the following Python code and provide:
            1. A brief summary
            2. List of issues (with severity and line numbers)
            3. Code quality metrics
            
            Code to review:
            ```python
            {code}
            ```
            
            Please format your response as JSON with the following structure:
            {{
                "summary": "Brief overview of the code",
                "issues": [
                    {{
                        "description": "detailed description",
                        "severity": "high/medium/low",
                        "line_number": line number
                    }}
                ],
                "metrics": {{
                    "complexity": float score,
                    "maintainability": float score,
                    "security_score": float score
                }}
            }}
            """
            
            # Get AI response
            self.rate_limiter.wait_if_needed()
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2000
            )
            
            # Parse and return the response
            result = response.choices[0].message.content
            try:
                # Safely parse JSON instead of using eval
                return json.loads(result)
            except json.JSONDecodeError:
                # Fallback if AI doesn't return valid JSON
                logger.error("Failed to parse AI response as JSON")
                return {
                    "summary": "Failed to parse AI response",
                    "issues": [],
                    "metrics": {"complexity": 0, "maintainability": 0, "security_score": 0}
                }
            
        except Exception as e:
            logger.error(f"Code analysis failed: {str(e)}")
            return {
                "summary": f"Analysis error: {str(e)}",
                "issues": [],
                "metrics": {"complexity": 0, "maintainability": 0, "security_score": 0}
            }
    
    def process_chat(self, message: str) -> str:
        """Process chat messages and return responses."""
        try:
            # Add user message to context
            self.chat_context.append({"role": "user", "content": message})
            
            # Get AI response
            self.rate_limiter.wait_if_needed()
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.chat_context,
                temperature=0.7,
                max_tokens=2000
            )
            
            # Get assistant response
            assistant_message = response.choices[0].message.content
            
            # Add to context
            self.chat_context.append({"role": "assistant", "content": assistant_message})
            
            # Trim context if too long
            if len(self.chat_context) > 10:
                self.chat_context = self.chat_context[-10:]
            
            return assistant_message
            
        except Exception as e:
            logger.error(f"Chat processing failed: {str(e)}")
            return f"Sorry, I encountered an error: {str(e)}"
    
    def clear_chat_context(self):
        """Clear the chat context history."""
        self.chat_context = []
