import unittest
from utils import sanitize_filename, parse_code_blocks, format_duration

class TestUtils(unittest.TestCase):
    def test_sanitize_filename(self):
        """Test filename sanitization"""
        test_cases = [
            # Basic sanitization
            ("test.py", "test.py"),
            ("test?.py", "test.py"),
            ("test/file.py", "test_file.py"),
            
            # Length limiting
            ("a" * 200 + ".py", "a" * 96 + ".py"),  # 100 char limit
            
            # Special characters
            ('test<>:"/\\|?*.py', "test.py"),
            
            # Empty filename
            ("", "unnamed_file"),
            (" ", "unnamed_file"),
            
            # Path components
            ("path/to/file.py", "path_to_file.py"),
            ("C:\\path\\to\\file.py", "C_path_to_file.py")
        ]
        
        for input_name, expected in test_cases:
            with self.subTest(input_name=input_name):
                result = sanitize_filename(input_name)
                self.assertEqual(result, expected)
                
    def test_parse_code_blocks(self):
        """Test markdown code block parsing"""
        markdown = '''
        Some text
        ```python
        def test():
            pass
        ```
        More text
        ```javascript
        function test() {
            return true;
        }
        ```
        '''
        
        blocks = parse_code_blocks(markdown)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]['language'], 'python')
        self.assertEqual(blocks[1]['language'], 'javascript')
        
    def test_format_duration(self):
        """Test duration formatting"""
        test_cases = [
            (30, "30.0s"),      # Seconds
            (90, "1.5m"),       # Minutes
            (3600, "1.0h"),     # Hours
            (5400, "1.5h")      # Hours with fraction
        ]
        
        for seconds, expected in test_cases:
            with self.subTest(seconds=seconds):
                result = format_duration(seconds)
                self.assertEqual(result, expected)

if __name__ == '__main__':
    unittest.main()
