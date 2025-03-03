# AI Code Reviewer

An AI-powered code review system that integrates Groq AI and Streamlit to provide automated code analysis and security vulnerability detection.

## Features

- Code quality analysis using Groq's Mixtral model
- Security vulnerability detection
- Review history tracking with SQLite
- Interactive chat interface
- Responsive web interface using Streamlit
- Support for multiple programming languages

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ai_code_reviewer.git
cd ai_code_reviewer
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Create a `.env` file with your Groq API key:
```
GROQ_API_KEY=your_groq_api_key_here
TEST_DB=reviews.db
```

4. Run the application:
```bash
streamlit run app.py
```

## Components

- `models.py`: Database models using Peewee ORM
- `code_analyzer.py`: Groq AI integration for code analysis
- `app.py`: Streamlit web interface

## Usage

1. Open the web interface at http://localhost:8501
2. Navigate to the Code Review tab
3. Paste your code for review
4. View security and code quality analysis results
5. Use the Chat tab to ask questions about your code
6. Check review history in the History tab

## Requirements

- Python 3.8+
- Streamlit
- Peewee
- Groq
- python-dotenv

## Made with ❤️ by horsleybit.com
