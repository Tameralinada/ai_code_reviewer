from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from dotenv import load_dotenv
import groq
import os
import json
import time
from functools import lru_cache
import logging
from typing import Dict, List, Optional, Any

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
    """Analyzes code using Groq AI."""
    
    def __init__(self, model: str = "mixtral-8x7b-32768", cache_size: int = 100):
        load_dotenv()
        self.client = groq.Client(api_key=os.getenv('GROQ_API_KEY'))
        self.model = model
        self.rate_limiter = RateLimiter()
        self.metrics = CodeMetrics()
        
        # Initialize prompts
        self._init_prompts()
        
    def _init_prompts(self):
        """Initialize analysis prompts"""
        self.security_prompt = """You are a code security expert. Analyze the following code for security vulnerabilities:

{code}

Provide a JSON response with the following structure:
{
    "vulnerabilities": [
        {
            "type": "vulnerability type",
            "description": "detailed description",
            "severity": "HIGH/MEDIUM/LOW",
            "remediation": "how to fix",
            "cwe_id": "CWE identifier if applicable"
        }
    ]
}

Focus on important security issues like:
- SQL injection
- XSS vulnerabilities
- Unsafe deserialization
- Command injection
- Hardcoded credentials
- Insecure cryptographic implementations
- Input validation
- Authentication issues
- Authorization flaws

Return ONLY the JSON response, nothing else."""
        
        self.code_quality_prompt = """You are a code quality expert. Review the following code for quality and best practices:

{code}

Provide a JSON response with the following structure:
{
    "issues": [
        {
            "type": "issue type",
            "line_number": number,
            "description": "detailed description",
            "suggestion": "how to improve",
            "priority": "HIGH/MEDIUM/LOW",
            "category": "READABILITY/PERFORMANCE/MAINTAINABILITY"
        }
    ],
    "metrics": {
        "maintainability_index": number,
        "cognitive_complexity": number
    }
}

Focus on:
- Code readability
- Performance issues
- Error handling
- Code duplication
- Naming conventions
- Function complexity
- SOLID principles
- Design patterns
- Testing considerations

Return ONLY the JSON response, nothing else."""

        self.chat_prompt = """You are an AI Code Review Assistant, an expert in software development, code quality, and best practices. 
Your role is to help developers understand and improve their code. When responding to questions:

1. Be concise but informative
2. Use markdown formatting for code examples
3. Focus on practical, actionable advice
4. Reference industry best practices and standards when relevant
5. If discussing code issues, explain both the 'what' and the 'why'

User Question: {question}

Provide a helpful, professional response focusing on code review and development best practices."""

        self.quick_analysis_prompt = """Analyze this code snippet quickly and provide immediate feedback:

{code}

Return a JSON response with this structure:
{
    "suggestions": [
        {
            "title": "Brief suggestion title",
            "description": "Detailed explanation with improvement suggestions",
            "code_example": "Optional example of improved code"
        }
    ],
    "metrics": {
        "complexity_score": "1-10 score",
        "readability": "1-10 score",
        "maintainability": "1-10 score"
    }
}

Focus on quick, actionable feedback about:
1. Code structure and organization
2. Obvious improvements
3. Best practices
4. Common patterns and anti-patterns

Keep the analysis fast and focused. Return ONLY the JSON response."""

    @lru_cache(maxsize=100)
    def _get_cached_analysis(self, code: str, analysis_type: str) -> Dict:
        """Cached analysis to avoid repeated API calls"""
        if analysis_type == "security":
            return self._analyze_security_internal(code)
        return self._analyze_quality_internal(code)

    def _analyze_with_retry(self, prompt: str, max_retries: int = 3) -> Dict:
        """Execute analysis with retry logic"""
        for attempt in range(max_retries):
            try:
                self.rate_limiter.wait_if_needed()
                completion = self.client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.model,
                    temperature=0.1,
                    max_tokens=4000
                )
                return json.loads(completion.choices[0].message.content)
            except Exception as e:
                logger.error(f"Analysis attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff

    def _analyze_security_internal(self, code: str) -> Dict:
        """Internal method for security analysis"""
        try:
            return self._analyze_with_retry(self.security_prompt.format(code=code))
        except Exception as e:
            logger.error(f"Security analysis failed: {str(e)}")
            return {"vulnerabilities": []}

    def _analyze_quality_internal(self, code: str) -> Dict:
        """Internal method for quality analysis"""
        try:
            result = self._analyze_with_retry(self.code_quality_prompt.format(code=code))
            # Add code metrics
            result["code_metrics"] = self.metrics.calculate_complexity(code)
            return result
        except Exception as e:
            logger.error(f"Quality analysis failed: {str(e)}")
            return {"issues": [], "metrics": {}, "code_metrics": {}}

    def analyze_security(self, code: str) -> Dict:
        """Public method for security analysis with caching"""
        return self._get_cached_analysis(code, "security")

    def analyze_quality(self, code: str) -> Dict:
        """Public method for quality analysis with caching"""
        return self._get_cached_analysis(code, "quality")

    def quick_analyze(self, code: str) -> Dict:
        """Perform a quick analysis of code for real-time feedback"""
        try:
            self.rate_limiter.wait_if_needed()
            completion = self.client.chat.completions.create(
                messages=[{"role": "user", "content": self.quick_analysis_prompt.format(code=code)}],
                model=self.model,
                temperature=0.1,
                max_tokens=1000
            )
            return json.loads(completion.choices[0].message.content)
        except Exception as e:
            logger.error(f"Quick analysis failed: {str(e)}")
            return {
                "suggestions": [],
                "metrics": {
                    "complexity_score": "N/A",
                    "readability": "N/A",
                    "maintainability": "N/A"
                }
            }

    def analyze_async(self, code: str) -> Dict:
        """Perform security and quality analysis asynchronously"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            security_future = executor.submit(self.analyze_security, code)
            quality_future = executor.submit(self.analyze_quality, code)
            
            return {
                "security": security_future.result(),
                "quality": quality_future.result()
            }

    def get_code_review_response(self, question: str) -> str:
        """Generate a response to a code review related question"""
        try:
            self.rate_limiter.wait_if_needed()
            completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert code reviewer and programming assistant. 
                        Provide clear, concise, and helpful responses to code-related questions. 
                        Focus on best practices, security, and code quality."""
                    },
                    {
                        "role": "user",
                        "content": question
                    }
                ],
                model=self.model,
                temperature=0.7,
                max_tokens=2000
            )
            
            # Extract and return the response
            return completion.choices[0].message.content
            
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    def analyze_code(self, code: str) -> Dict[str, Any]:
        """Analyze code and return insights."""
        try:
            # Create chat completion for code analysis
            completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert code analyzer. Analyze the given code and return ONLY a JSON object with this EXACT structure (no other text):
{
    "issues": [
        {
            "severity": "HIGH|MEDIUM|LOW",
            "description": "Issue description here",
            "line_number": 1
        }
    ],
    "metrics": {
        "complexity": 50,
        "maintainability": 50,
        "security_score": 50
    },
    "suggestions": [
        {
            "title": "Suggestion title",
            "description": "Suggestion details",
            "priority": "HIGH|MEDIUM|LOW"
        }
    ]
}

Rules:
1. Return ONLY the JSON object, no other text
2. Use the EXACT structure shown above
3. All numbers must be integers 0-100
4. Severity/priority must be HIGH, MEDIUM, or LOW
5. Line numbers must be positive integers"""
                    },
                    {
                        "role": "user",
                        "content": f"Analyze this code:\n{code}"
                    }
                ],
                model=self.model,
                temperature=0.1,
                max_tokens=2048,
            )
            
            # Get the response text and clean it
            response_text = completion.choices[0].message.content.strip()
            
            # Try to parse as JSON
            try:
                import json
                analysis = json.loads(response_text)
                
                # Validate required fields
                if not isinstance(analysis, dict):
                    raise ValueError("Analysis must be a dictionary")
                    
                # Ensure required sections exist with defaults
                analysis = {
                    "issues": analysis.get("issues", []),
                    "metrics": {
                        "complexity": analysis.get("metrics", {}).get("complexity", 50),
                        "maintainability": analysis.get("metrics", {}).get("maintainability", 50),
                        "security_score": analysis.get("metrics", {}).get("security_score", 50)
                    },
                    "suggestions": analysis.get("suggestions", [])
                }
                
                return {
                    "success": True,
                    "analysis": analysis
                }
                
            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "error": f"Invalid JSON response: {str(e)}\nResponse was: {response_text[:100]}..."
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
