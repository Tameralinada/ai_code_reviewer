import unittest
from unittest.mock import Mock, patch
from code_analyzer import CodeAnalyzer

class TestCodeAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = CodeAnalyzer()
        self.sample_code = '''
def insecure_function(user_input):
    exec(user_input)  # Security vulnerability
    return True
'''

    def test_analyze_security(self):
        """Test security analysis functionality"""
        result = self.analyzer.analyze_security(self.sample_code)
        self.assertIsInstance(result, dict)
        self.assertIn('vulnerabilities', result)
        
        # Should detect the exec() security issue
        vulns = result['vulnerabilities']
        self.assertGreater(len(vulns), 0)
        self.assertEqual(vulns[0]['type'], 'CODE_EXECUTION')

    def test_analyze_quality(self):
        """Test code quality analysis functionality"""
        result = self.analyzer.analyze_quality(self.sample_code)
        self.assertIsInstance(result, dict)
        self.assertIn('issues', result)
        
        # Should detect missing docstring
        issues = result['issues']
        self.assertGreater(len(issues), 0)
        self.assertTrue(any(issue['type'] == 'MISSING_DOCSTRING' for issue in issues))

    @patch('code_analyzer.CodeAnalyzer._get_ai_feedback')
    def test_ai_integration(self, mock_ai):
        """Test AI integration with mocked response"""
        mock_ai.return_value = {
            'suggestions': ['Add input validation'],
            'severity': 'HIGH'
        }
        
        result = self.analyzer.get_ai_review(self.sample_code)
        self.assertIn('suggestions', result)
        self.assertIn('severity', result)
        mock_ai.assert_called_once()

if __name__ == '__main__':
    unittest.main()
