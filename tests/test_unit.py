import unittest
from unittest.mock import patch, MagicMock, ANY
import tempfile
import os
import json
from datetime import datetime, timedelta
from peewee import SqliteDatabase
from models import (
    CodeReview, ReviewComment, SecurityIssue, ReviewHistory,
    initialize_db, safely_remove_db, get_review_history
)
from code_analyzer import CodeAnalyzer, RateLimiter, CodeMetrics

class TestDatabase(unittest.TestCase):
    def setUp(self):
        """Set up test environment with temporary database"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.original_db_path = 'reviews.db'
        os.environ['TEST_DB'] = self.temp_db.name
        initialize_db()

    def tearDown(self):
        """Clean up test environment"""
        self.temp_db.close()
        os.unlink(self.temp_db.name)

    def test_database_initialization(self):
        """Test database initialization and table creation"""
        # Verify all tables exist
        tables = [CodeReview, ReviewComment, SecurityIssue, ReviewHistory]
        for table in tables:
            self.assertTrue(
                table._meta.database.table_exists(table._meta.table_name),
                f"Table {table._meta.table_name} not created"
            )

    def test_database_relationships(self):
        """Test relationships between database tables"""
        # Create test data
        review = CodeReview.create(
            file_name="test.py",
            severity_level="MEDIUM",
            review_status="OPEN",
            ai_feedback="Test feedback"
        )

        comment = ReviewComment.create(
            review=review,
            line_number=1,
            comment="Test comment",
            category="STYLE"
        )

        security = SecurityIssue.create(
            review=review,
            issue_type="SQL_INJECTION",
            description="Test description",
            severity="HIGH"
        )

        history = ReviewHistory.create(
            review=review,
            action="CREATE",
            details_json=json.dumps({"test": "data"})
        )

        # Test relationships
        self.assertEqual(review.comments.count(), 1)
        self.assertEqual(review.security_issues.count(), 1)
        self.assertEqual(review.history.count(), 1)
        self.assertEqual(comment.review, review)
        self.assertEqual(security.review, review)
        self.assertEqual(history.review, review)

    def test_review_history_filtering(self):
        """Test review history filtering functionality"""
        # Create test reviews with different dates
        dates = [
            datetime.now(),
            datetime.now() - timedelta(days=5),
            datetime.now() - timedelta(days=10)
        ]

        for i, date in enumerate(dates):
            CodeReview.create(
                file_name=f"test{i}.py",
                severity_level="MEDIUM",
                review_status="OPEN",
                ai_feedback="Test feedback",
                review_date=date
            )

        # Test filtering
        recent_reviews = get_review_history(days=7)
        self.assertEqual(len(recent_reviews), 2)

        all_reviews = get_review_history()
        self.assertEqual(len(all_reviews), 3)

        team_reviews = get_review_history(team_id="team1")
        self.assertEqual(len(team_reviews), 0)

class TestAIModel(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.analyzer = CodeAnalyzer()

    def test_rate_limiter(self):
        """Test rate limiter functionality"""
        limiter = RateLimiter(calls_per_minute=2)
        start_time = datetime.now()

        # Make calls
        for _ in range(3):
            limiter.wait_if_needed()

        duration = (datetime.now() - start_time).total_seconds()
        self.assertGreaterEqual(duration, 30)  # Should wait at least 30 seconds

    def test_code_metrics(self):
        """Test code metrics calculation"""
        test_code = """
def function1():
    # This is a comment
    pass

class TestClass:
    def method1(self):
        pass
    
    def method2(self):
        # Another comment
        return True
"""
        metrics = CodeMetrics.calculate_complexity(test_code)
        
        self.assertEqual(metrics["functions"], 3)  # Including methods
        self.assertEqual(metrics["classes"], 1)
        self.assertEqual(metrics["comments"], 2)

    @patch('groq.Groq')
    def test_security_analysis(self, mock_groq):
        """Test security analysis functionality"""
        # Mock AI response
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps({
                        "vulnerabilities": [{
                            "type": "SQL_INJECTION",
                            "description": "Test vulnerability",
                            "severity": "HIGH"
                        }]
                    })
                )
            )
        ]
        mock_groq.return_value.chat.completions.create.return_value = mock_response

        # Test code with potential security issue
        test_code = """
def unsafe_query(user_input):
    query = f"SELECT * FROM users WHERE id = {user_input}"
    return db.execute(query)
"""
        result = self.analyzer.analyze_security(test_code)
        
        self.assertIn("vulnerabilities", result)
        self.assertEqual(len(result["vulnerabilities"]), 1)
        self.assertEqual(result["vulnerabilities"][0]["type"], "SQL_INJECTION")

    @patch('groq.Groq')
    def test_quality_analysis(self, mock_groq):
        """Test code quality analysis functionality"""
        # Mock AI response
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps({
                        "issues": [{
                            "type": "COMPLEXITY",
                            "line_number": 1,
                            "description": "Function is too complex",
                            "priority": "HIGH"
                        }],
                        "metrics": {
                            "maintainability_index": 65,
                            "cognitive_complexity": 15
                        }
                    })
                )
            )
        ]
        mock_groq.return_value.chat.completions.create.return_value = mock_response

        # Test code with quality issues
        test_code = """
def complex_function(a, b, c):
    if a > 0:
        if b > 0:
            if c > 0:
                return a + b + c
            return a + b
        return a
    return 0
"""
        result = self.analyzer.analyze_quality(test_code)
        
        self.assertIn("issues", result)
        self.assertEqual(len(result["issues"]), 1)
        self.assertEqual(result["issues"][0]["type"], "COMPLEXITY")
        self.assertIn("metrics", result)

    def test_quick_analysis(self):
        """Test quick analysis functionality"""
        test_code = """
def test_function():
    # TODO: Implement this
    pass
"""
        result = self.analyzer.quick_analyze(test_code)
        
        self.assertIn("suggestions", result)
        self.assertIn("metrics", result)

if __name__ == '__main__':
    unittest.main()
