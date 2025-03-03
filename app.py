import streamlit as st
from code_analyzer import CodeAnalyzer
from models import *
from utils import parse_code_blocks, format_duration, count_lines, sanitize_filename
import datetime
import time
import os
import difflib
from typing import Dict, List
import plotly.graph_objects as go
import plotly.express as px
import groq
import os
import json

# Initialize session state keys
def init_session_state():
    """Initialize essential session state keys."""
    defaults = {
        'analyzer': CodeAnalyzer(),
        'chat_messages': [],
        'start_time': None,
        'active_tab': "Chat",
        'selected_review': None,
        'db_error_shown': False,
        'current_review': None
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    try:
        initialize_db()
    except Exception as e:
        st.error(f"Database initialization error: {str(e)}")
        if not st.session_state.get('db_error_shown'):
            st.warning("Please refresh the page to retry database connection.")
            st.session_state.db_error_shown = True
    
def simulate_processing(duration: float = 0.5):
    """Simulate processing delay for better UX."""
    time.sleep(duration)

def display_code_input() -> str:
    """Display and handle code input section."""
    st.subheader("📝 Code Input")
    code = st.text_area("Enter your code here", height=200, key="code_input")
    filename = st.text_input("Filename (optional)", key="filename_input")
    
    if not filename and code:
        filename = "unnamed_file.py"
    
    return code, filename

def analyze_and_store(code: str, review: CodeReview) -> Dict:
    """Analyze code and store results in database."""
    with st.spinner("Analyzing code..."):
        simulate_processing()
        analysis = st.session_state.analyzer.analyze_code(code)
        
        # Store issues
        for issue in analysis.get("issues", []):
            Issue.create(
                review=review,
                severity=issue["severity"],
                description=issue["description"],
                line_number=issue["line_number"]
            )
        
        # Store metrics
        metrics = analysis.get("metrics", {})
        Metrics.create(
            review=review,
            complexity=metrics.get("complexity", 0),
            maintainability=metrics.get("maintainability", 0),
            security_score=metrics.get("security_score", 0)
        )
        
        # Update review status
        review.status = "COMPLETED"
        review.save()
        
        # Record history
        ReviewHistory.create(
            review=review,
            action="STATUS_CHANGE",
            details="Review completed"
        )
        
        return analysis

def display_analysis_results(analysis: Dict):
    """Display code analysis results."""
    if not analysis:
        st.error("No analysis results available.")
        return
        
    st.subheader("🔍 Code Analysis Results")
    
    # Display issues
    if issues := analysis.get("issues", []):
        st.write("Found issues:")
        for issue in issues:
            severity_color = {
                "HIGH": "🔴",
                "MEDIUM": "🟡",
                "LOW": "🟢"
            }.get(issue["severity"], "⚪")
            
            st.markdown(f"""
                {severity_color} **{issue['severity']}** (Line {issue['line_number']})  
                {issue['description']}
            """)
    else:
        st.success("No issues found!")
    
    # Display metrics
    if metrics := analysis.get("metrics"):
        st.subheader("📊 Code Metrics")
        cols = st.columns(3)
        with cols[0]:
            st.metric("Code Quality", f"{metrics.get('maintainability', 0)}%")
        with cols[1]:
            st.metric("Security Score", f"{metrics.get('security_score', 0)}%")
        with cols[2]:
            st.metric("Complexity", f"{metrics.get('complexity', 0)}%")
    
    # Display summary
    if summary := analysis.get("summary"):
        st.subheader("📋 Summary")
        st.write(summary)

def display_metrics(metrics: Dict):
    """Display code metrics using Plotly."""
    st.subheader("📊 Code Metrics")
    
    # Create radar chart
    fig = go.Figure(data=go.Scatterpolar(
        r=[
            metrics.get("complexity", 0),
            metrics.get("maintainability", 0),
            metrics.get("security_score", 0)
        ],
        theta=['Complexity', 'Maintainability', 'Security Score'],
        fill='toself'
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100]
            )
        ),
        showlegend=False
    )
    
    st.plotly_chart(fig)

def display_sidebar():
    """Display sidebar with code review and navigation."""
    with st.sidebar:
        st.title("🔍 AI Code Reviewer")
        st.markdown("---")
        
        # Code Review Section
        st.subheader("Code Review")
        code = st.text_area("Enter your code:", height=200)
        if st.button("Review Code", type="primary"):
            if not code:
                st.error("Please enter some code to review.")
                return
            simulate_processing()
            perform_code_review(code)
        
        # Display review results if available
        if 'current_review' in st.session_state:
            display_review_results(st.session_state.current_review)
        
        st.markdown("---")
        
        # Navigation
        selected_tab = st.radio("Navigation", ["Chat", "Review History"])
        st.session_state.active_tab = selected_tab
        
        if selected_tab == "Review History":
            display_review_history()
        
        st.markdown("---")
        
        # Recent Reviews Section
        st.subheader("Recent Reviews")
        try:
            recent_reviews = get_recent_reviews()
            
            if not recent_reviews:
                st.info("No reviews yet. Start by submitting some code!")
                return
                
            for review in recent_reviews:
                content = review.code_content or ""
                preview = content[:200] + "..." if len(content) > 200 else content
                with st.expander(f"{review.file_name} ({review.review_date.strftime('%H:%M:%S')})"):
                    st.code(preview)
                    if st.button("View Full Review", key=f"view_{review.id}"):
                        st.session_state.selected_review = review
                        st.session_state.active_tab = "Review History"
        except Exception as e:
            st.error("Error loading reviews. Please try refreshing the page.")
            st.error(str(e))

def display_chat():
    """Display chat interface in the main area."""
    st.title("💬 AI Code Assistant")
    st.markdown("Chat with our AI to get help with your code!")
    
    # Initialize chat if empty
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
    
    # Display chat history
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask me anything about your code..."):
        # Add user message
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        
        # Generate AI response
        with st.chat_message("assistant"):
            response = st.session_state.analyzer.get_code_review_response(prompt)
            st.markdown(response)
        st.session_state.chat_messages.append({"role": "assistant", "content": response})

def display_review_history():
    """Display review history in the sidebar."""
    st.subheader("📚 Review History")
    
    if st.session_state.selected_review:
        review = st.session_state.selected_review
        st.markdown(f"### {review.file_name}")
        st.markdown(f"*Reviewed on: {review.review_date.strftime('%Y-%m-%d %H:%M:%S')}*")
        st.code(review.code_content)
        
        # Display metrics and issues
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 📊 Metrics")
            for metric in review.metrics:
                st.metric(metric.name, metric.value)
        with col2:
            st.markdown("#### ⚠️ Issues")
            for issue in review.issues:
                st.error(f"Line {issue.line_number}: {issue.description}")

def add_chat_message(role: str, content: str) -> None:
    """Add a message to the chat history."""
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
    
    st.session_state.chat_messages.append({
        "role": role,
        "content": content,
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
    })

def generate_review_markdown(review: CodeReview) -> str:
    """Generate markdown formatted review content."""
    try:
        metrics = Metrics.get_or_none(review=review)
        issues = Issue.select().where(Issue.review == review)
        
        # Header
        md = f"""
# Code Review Report
**File:** `{review.file_name}`  
**Review Date:** {review.review_date.strftime('%Y-%m-%d %H:%M:%S')}

## 📊 Quality Metrics
| Metric | Score | Status |
|--------|--------|--------|
| Code Quality | {metrics.maintainability}% | {'✅ Good' if metrics.maintainability > 70 else '⚠️ Fair' if metrics.maintainability > 50 else '❌ Needs Work'} |
| Security | {metrics.security_score}% | {'✅ Good' if metrics.security_score > 70 else '⚠️ Fair' if metrics.security_score > 50 else '❌ Needs Work'} |
| Complexity | {metrics.complexity}% | {'✅ Good' if metrics.complexity < 30 else '⚠️ Fair' if metrics.complexity < 50 else '❌ High'} |

## 💡 Key Insights

### ✅ Strengths
- Clean code structure and organization
- Good variable naming conventions
- Proper error handling implementation
- Consistent coding style

### ⚠️ Areas for Improvement
- Missing function documentation
- Complex code sections
- Potential security vulnerabilities
- Limited test coverage

## 🔒 Security Analysis
"""
        # Add security issues
        security_issues = [i for i in issues if i.severity in ["HIGH", "MEDIUM"]]
        if security_issues:
            for issue in security_issues:
                severity_icon = "🔴" if issue.severity == "HIGH" else "🟡"
                md += f"\n{severity_icon} **{issue.severity} Risk** (Line {issue.line_number})  \n"
                md += f"  {issue.description}\n"
        else:
            md += "\n✅ No major security issues found!\n"

        # Add improvement suggestions
        md += """
## 🛠️ Recommended Actions

### High Priority
1. 🔴 Implement input validation
   - Add proper validation for all user inputs
   - Sanitize data before processing

### Medium Priority
1. 🟡 Add type hints
   - Improve code maintainability
   - Catch potential type-related bugs early

2. 🟡 Increase test coverage
   - Add unit tests for core functions
   - Implement integration tests

### Code Samples
```python
# Before
def process_data(data):
    result = data.process()
    return result

# After
from typing import Dict, Any

def process_data(data: Dict[str, Any]) -> Dict[str, Any]:
    \"\"\"Process input data and return results.
    
    Args:
        data: Input dictionary containing data to process
        
    Returns:
        Processed data dictionary
    \"\"\"
    if not isinstance(data, dict):
        raise ValueError("Input must be a dictionary")
    
    result = data.process()
    return result
```
"""
        return md
        
    except Exception as e:
        return f"Error generating review: {str(e)}"

def display_review_results(review: CodeReview):
    """Display review results."""
    if not review:
        return
    
    # Generate and display markdown
    markdown_content = generate_review_markdown(review)
    st.markdown(markdown_content)
    
    # Add download button for markdown
    st.download_button(
        label="📥 Download Review Report",
        data=markdown_content,
        file_name=f"code_review_{review.review_date.strftime('%Y%m%d_%H%M%S')}.md",
        mime="text/markdown"
    )

def perform_code_review(code: str):
    """Perform code review."""
    try:
        # Create review record
        review = CodeReview.create(
            file_name="unnamed_file.py",
            code_content=code,
            status="IN_PROGRESS"
        )
        
        # Get AI analysis
        analysis = st.session_state.analyzer.analyze_code(code)
        if not analysis["success"]:
            st.error(f"Analysis failed: {analysis.get('error')}")
            review.status = "FAILED"
            review.save()
            return
            
        # Process analysis results
        results = analysis["analysis"]
        
        # Store issues
        if issues := results.get("issues", []):
            for issue_data in issues:
                Issue.create(
                    review=review,
                    severity=issue_data["severity"],
                    description=issue_data["description"],
                    line_number=issue_data["line_number"]
                )
        
        # Store metrics
        metrics_data = results.get("metrics", {})
        Metrics.create(
            review=review,
            complexity=metrics_data.get("complexity", 50),
            maintainability=metrics_data.get("maintainability", 50),
            security_score=metrics_data.get("security_score", 50)
        )
        
        # Update review status
        review.status = "COMPLETED"
        review.save()
        
        # Store in session state
        st.session_state.current_review = review
        
        # Display results
        display_analysis_results(results)
        
    except Exception as e:
        st.error(f"Error performing code review: {str(e)}")
        if 'review' in locals():
            review.status = "FAILED"
            review.save()

def display_analysis_results(analysis: dict):
    """Display analysis results in a clean format."""
    if not analysis:
        st.error("No analysis results available.")
        return
        
    st.subheader("🔍 Code Analysis Results")
    
    # Display issues
    if issues := analysis.get("issues", []):
        st.write("Found issues:")
        for issue in issues:
            severity_color = {
                "HIGH": "🔴",
                "MEDIUM": "🟡",
                "LOW": "🟢"
            }.get(issue.get("severity", ""), "⚪")
            
            st.markdown(f"""
                {severity_color} **{issue.get('severity', 'UNKNOWN')}** (Line {issue.get('line_number', '?')})  
                {issue.get('description', 'No description available')}
            """)
    else:
        st.success("No issues found!")
    
    # Display metrics
    if metrics := analysis.get("metrics", {}):
        st.subheader("📊 Code Metrics")
        cols = st.columns(3)
        with cols[0]:
            st.metric("Code Quality", f"{metrics.get('maintainability', 0)}%")
        with cols[1]:
            st.metric("Security Score", f"{metrics.get('security_score', 0)}%")
        with cols[2]:
            st.metric("Complexity", f"{metrics.get('complexity', 0)}%")
    
    # Display suggestions
    if suggestions := analysis.get("suggestions", []):
        st.subheader("💡 Suggestions")
        for suggestion in suggestions:
            priority_color = {
                "HIGH": "🔴",
                "MEDIUM": "🟡",
                "LOW": "🟢"
            }.get(suggestion.get("priority", ""), "⚪")
            
            st.markdown(f"""
                {priority_color} **{suggestion.get('title', 'Suggestion')}**  
                {suggestion.get('description', 'No description available')}
            """)
    
def main():
    """Main function to run the Streamlit app."""
    st.set_page_config(page_title="AI Code Reviewer", layout="wide")
    init_session_state()
    
    # Display sidebar with code review and navigation
    display_sidebar()
    
    # Main chat interface
    display_chat()

if __name__ == "__main__":
    main()
