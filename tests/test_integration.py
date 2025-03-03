import unittest
import streamlit as st
from unittest.mock import patch, MagicMock
from app import analyze_code, display_chat_history, analyze_and_store, add_chat_message
from models import CodeReview, ReviewComment, SecurityIssue, ReviewHistory, Issue, Metrics, initialize_db, get_recent_reviews
import tempfile
import os
import json
import datetime

class MockStreamlitContainer:
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

@patch('streamlit.runtime.scriptrunner.add_script_run_ctx', MagicMock())
class TestIntegration(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        # Use temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.original_db_path = 'reviews.db'
        os.environ['TEST_DB'] = self.temp_db.name
        initialize_db()
        
        # Mock Streamlit session state
        class SessionState:
            def __init__(self):
                self.analyzer = MagicMock()
                self.messages = []
                self.start_time = None
                self.chat = []
                self.chat_input = ""
                self.selected_review = None
                self.active_tab = "Code Review"
                self.memories = {}
        
        st.session_state = SessionState()
        
        # Mock Streamlit components
        self.mock_container = MockStreamlitContainer()
        self.mock_expander = MockStreamlitContainer()
        
        # Setup common patches
        self.addCleanup(patch.stopall)
        patch('streamlit.container', return_value=self.mock_container).start()
        patch('streamlit.expander', return_value=self.mock_expander).start()
        patch('streamlit.markdown').start()
        patch('streamlit.metric').start()
        patch('streamlit.progress').start()
        patch('streamlit.spinner', return_value=self.mock_container).start()

    def tearDown(self):
        """Clean up test environment"""
        self.temp_db.close()
        os.unlink(self.temp_db.name)

    @patch('streamlit.empty')
    def test_end_to_end_review(self, mock_empty):
        """Test complete flow from code input to database storage"""
        # Mock progress bar and status
        progress_mock = MagicMock()
        mock_progress = patch('streamlit.progress')
        mock_progress.return_value = progress_mock
        mock_progress.start()
        self.addCleanup(mock_progress.stop)
        
        mock_empty.return_value = MagicMock()
        
        # Sample code for testing
        test_code = """
        def insecure_function():
            password = "hardcoded_password"
            return password
        """
        
        # Create a new review
        review = CodeReview.create(
            file_name="test.py",
            code_content=test_code,
            status="IN_PROGRESS",
            timestamp=datetime.datetime.now()
        )
        
        # Mock analyzer response
        mock_analysis = {
            "issues": [
                {
                    "severity": "HIGH",
                    "description": "Hardcoded password detected",
                    "line_number": 3
                }
            ],
            "metrics": {
                "complexity": 1,
                "maintainability": 80,
                "security_score": 60
            },
            "summary": "Code contains security issues"
        }
        
        st.session_state.analyzer.analyze_code.return_value = mock_analysis
        
        # Call analyze_and_store
        analyze_and_store(test_code, review)
        
        # Verify database entries
        stored_review = CodeReview.get(CodeReview.id == review.id)
        self.assertEqual(stored_review.status, "COMPLETED")
        
        stored_issues = list(Issue.select().where(Issue.review == review))
        self.assertEqual(len(stored_issues), 1)
        self.assertEqual(stored_issues[0].severity, "HIGH")
        
        stored_metrics = list(Metrics.select().where(Metrics.review == review))
        self.assertEqual(len(stored_metrics), 1)
        self.assertEqual(stored_metrics[0].complexity, 1)
        
        # Test review history
        history = list(ReviewHistory.select().where(ReviewHistory.review == review))
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].action, "STATUS_CHANGE")

    def test_concurrent_reviews(self):
        """Test handling multiple code reviews simultaneously"""
        test_files = [
            ("test1.py", "def func1(): pass"),
            ("test2.py", "def func2(): return None"),
            ("test3.py", "class TestClass: pass")
        ]
        
        results = []
        for filename, code in test_files:
            results.append(analyze_code(code, filename))
            
        # Verify all reviews were stored
        self.assertEqual(CodeReview.select().count(), len(test_files))
        
        # Verify each file has its own review
        for filename, _ in test_files:
            self.assertTrue(
                CodeReview.select()
                .where(CodeReview.file_name == filename)
                .exists()
            )

    @patch('streamlit.error')
    def test_error_handling(self, mock_error):
        """Test error handling in the integration flow"""
        # Test with invalid Python code
        invalid_code = "def invalid_syntax:"
        
        result = analyze_code(invalid_code, "invalid.py")
            
        # Verify error is stored in review
        review = CodeReview.select().order_by(CodeReview.review_date.desc()).first()
        self.assertIn("error", review.ai_feedback.lower())
        mock_error.assert_called()

    def test_review_persistence(self):
        """Test that reviews persist correctly with all related data"""
        test_code = '''
        def insecure_function(user_input):
            query = f"SELECT * FROM users WHERE id = {user_input}"
            return execute_query(query)
        '''
        
        # Create a review
        result = analyze_code(test_code, "security_test.py")
        
        # Get the review from database
        review = CodeReview.select().order_by(CodeReview.review_date.desc()).first()
        
        # Verify review data
        self.assertEqual(review.file_name, "security_test.py")
        self.assertIsNotNone(review.review_date)
        
        # Verify security issues
        security_issues = list(review.security_issues)
        self.assertGreater(len(security_issues), 0)
        
        # Verify comments
        comments = list(review.comments)
        self.assertGreater(len(comments), 0)
        
        # Verify history
        history = list(review.history)
        self.assertGreater(len(history), 0)
        
        # Verify metrics
        metrics = review.get_metrics()
        self.assertIsInstance(metrics, dict)
        self.assertGreater(len(metrics), 0)

    def test_review_history_tracking(self):
        """Test that review history is tracked correctly"""
        test_code = "def test(): pass"
        
        # Create initial review
        result = analyze_code(test_code, "history_test.py")
        review = CodeReview.select().order_by(CodeReview.review_date.desc()).first()
        
        # Update review status
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.datetime.now()
            review.review_status = "IN_PROGRESS"
            review.save()
            
            ReviewHistory.create(
                review=review,
                action="STATUS_CHANGE",
                details_json=json.dumps({"old_status": "OPEN", "new_status": "IN_PROGRESS"})
            )
        
        # Verify history entries
        history = list(review.history.order_by(ReviewHistory.timestamp.desc()))
        self.assertEqual(len(history), 2)  # Initial creation + status change
        self.assertEqual(history[0].action, "STATUS_CHANGE")
        
    @patch('streamlit.sidebar')
    def test_sidebar_recent_reviews(self, mock_sidebar):
        """Test recent reviews sidebar functionality"""
        # Setup mock returns
        mock_sidebar.return_value.__enter__.return_value = MagicMock()
        
        # Create multiple reviews
        reviews = []
        for i in range(3):
            review = CodeReview.create(
                file_name=f"recent{i+1}.py",
                code_content=f"test code {i+1}",
                status="COMPLETED",
                timestamp=datetime.datetime.now() - datetime.timedelta(minutes=i)
            )
            reviews.append(review)
        
        # Get recent reviews
        recent_reviews = list(get_recent_reviews())
        
        # Verify recent reviews
        self.assertEqual(len(recent_reviews), 3)
        self.assertEqual(recent_reviews[0].file_name, "recent1.py")
        self.assertEqual(recent_reviews[1].file_name, "recent2.py")
        self.assertEqual(recent_reviews[2].file_name, "recent3.py")
        
    @patch('streamlit.chat_message')
    def test_chat_integration(self, mock_chat_message):
        """Test chat functionality integration"""
        # Setup mock returns
        mock_chat_message.return_value.__enter__.return_value = MagicMock()
        
        # Initialize chat state
        if 'chat' not in st.session_state:
            st.session_state.chat = []
        
        # Test adding messages
        message = "Please review my code"
        add_chat_message("user", message)
        
        # Verify message was added
        self.assertEqual(len(st.session_state.chat), 1)
        self.assertEqual(st.session_state.chat[0]["role"], "user")
        self.assertEqual(st.session_state.chat[0]["content"], message)
        
        # Test assistant response
        response = "I'll analyze your code"
        add_chat_message("assistant", response)
        
        # Verify response was added
        self.assertEqual(len(st.session_state.chat), 2)
        self.assertEqual(st.session_state.chat[1]["role"], "assistant")
        self.assertEqual(st.session_state.chat[1]["content"], response)
        
        # Verify chat display
        display_chat_history()
        mock_chat_message.assert_called()

if __name__ == '__main__':
    unittest.main()
