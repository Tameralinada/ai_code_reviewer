import streamlit as st
import datetime
from typing import Optional, List
from models import CodeReview, Issue, Metrics, initialize_db, get_connection
from code_analyzer import CodeAnalyzer
from peewee import SqliteDatabase

# Configure page and theme first
st.set_page_config(
    page_title="AI Code Assistant",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/yourusername/ai_code_reviewer',
        'Report a bug': 'https://github.com/yourusername/ai_code_reviewer/issues',
        'About': '''
            # AI Code Review Assistant
            A powerful tool for code analysis and review.
            
            Version: 1.0.0
            Made with ❤️ by Your Team
        '''
    }
)

def get_recent_reviews() -> List[CodeReview]:
    """Get list of recent code reviews."""
    try:
        with get_connection():
            return list(CodeReview.select().order_by(CodeReview.review_date.desc()).limit(10))
    except Exception as e:
        st.error(f"Failed to fetch reviews: {str(e)}")
        return []

def perform_code_review(code: str) -> Optional[dict]:
    """Perform code review and save results."""
    try:
        # Create analyzer instance
        analyzer = CodeAnalyzer()
        
        # Analyze code
        analysis = analyzer.analyze_code(code)
        
        with get_connection():
            # Save review to database
            review = CodeReview.create(
                code_content=code,
                file_name='code_snippet.py',
                status='COMPLETED',
                review_date=datetime.datetime.now()
            )
            
            # Save issues
            for issue in analysis.get('issues', []):
                Issue.create(
                    review=review,
                    severity=issue['severity'],
                    description=issue['description'],
                    line_number=issue.get('line_number', 0)
                )
            
            # Save metrics
            Metrics.create(
                review=review,
                complexity=analysis.get('metrics', {}).get('complexity', 0),
                maintainability=analysis.get('metrics', {}).get('maintainability', 0),
                security_score=analysis.get('metrics', {}).get('security_score', 0)
            )
        
        return analysis
    except Exception as e:
        st.error(f"Failed to perform review: {str(e)}")
        return None

def display_review(review: CodeReview):
    """Display a code review with metrics and issues."""
    st.title(f"Code Review #{review.id}")
    
    # Code section
    with st.expander("📝 Reviewed Code", expanded=True):
        st.code(review.code_content, language="python")
    
    # Metrics
    if review.metrics:
        cols = st.columns(3)
        with cols[0]:
            st.metric("Complexity", f"{review.metrics.complexity:.1f}")
        with cols[1]:
            st.metric("Maintainability", f"{review.metrics.maintainability:.1f}")
        with cols[2]:
            st.metric("Security Score", f"{review.metrics.security_score:.1f}")
    
    # Issues
    if review.issues:
        st.subheader("🔍 Issues Found")
        for issue in review.issues:
            with st.container():
                severity_color = {
                    "high": "🔴",
                    "medium": "🟡",
                    "low": "🟢"
                }.get(issue.severity.lower(), "⚪")
                
                st.markdown(f"""
                    {severity_color} **{issue.severity}** (Line {issue.line_number})  
                    {issue.description}
                """)
    else:
        st.success("No issues found! Your code looks good! 🎉")

def display_review_history(review: CodeReview):
    """Display historical data for a review."""
    st.title(f"Review History #{review.id}")
    
    # Review metadata
    st.info(f"Created on: {review.review_date.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Display metrics trend
    if review.metrics:
        st.subheader("📊 Metrics History")
        metrics_data = {
            "Complexity": [review.metrics.complexity],
            "Maintainability": [review.metrics.maintainability],
            "Security": [review.metrics.security_score]
        }
        st.line_chart(metrics_data)
    
    # Display past issues
    if review.issues:
        st.subheader("🔍 Past Issues")
        for issue in review.issues:
            st.markdown(f"""
                - **{issue.severity}** ({issue.severity})
                - Line {issue.line_number}: {issue.description}
            """)

def render_chat_interface():
    """Render the chat interface with message history and input."""
    st.markdown("""
        <style>
        .chat-container {
            background: var(--background-color);
            border-radius: 10px;
            padding: 20px;
            margin: 10px 0;
            height: calc(100vh - 200px);
            display: flex;
            flex-direction: column;
        }
        .chat-messages {
            flex-grow: 1;
            overflow-y: auto;
            margin-bottom: 20px;
        }
        .chat-input {
            background: white;
            border-radius: 8px;
            padding: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        </style>
    """, unsafe_allow_html=True)

    # Initialize chat history if not exists
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Chat container
    with st.container():
        # Message display area
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Chat input
        if prompt := st.chat_input("Ask me anything about your code..."):
            # Add user message to chat
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # Process the message
            try:
                # Add assistant response
                with st.chat_message("assistant"):
                    response = st.session_state.analyzer.process_chat(prompt)
                    st.session_state.chat_history.append({"role": "assistant", "content": response})
                    st.markdown(response)
            except Exception as e:
                st.error(f"Failed to process message: {str(e)}")

def apply_custom_theme():
    """Apply custom theme and styling."""
    # Custom theme CSS
    st.markdown("""
        <style>
        /* Main theme colors */
        :root {
            --primary-color: #2E86C1;
            --secondary-color: #3498DB;
            --background-color: #F8F9F9;
            --text-color: #2C3E50;
            --accent-color: #E74C3C;
        }
        
        /* Header styling */
        .stApp header {
            background-color: var(--primary-color);
        }
        
        /* Sidebar styling */
        .css-1d391kg {
            background-color: #FFFFFF;
            border-right: 1px solid #E0E0E0;
        }
        
        /* Button styling */
        .stButton>button {
            border-radius: 8px;
            transition: all 0.3s ease;
        }
        .stButton>button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        
        /* Chat message styling */
        .stChatMessage {
            border-radius: 15px;
            padding: 10px;
            margin: 5px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        
        /* Code block styling */
        .stCodeBlock {
            border-radius: 8px;
            border: 1px solid #E0E0E0;
        }
        
        /* Metric styling */
        .stMetric {
            background-color: #FFFFFF;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        
        /* Tab styling */
        .stTab {
            border-radius: 8px 8px 0 0;
        }
        
        /* Alert/Info box styling */
        .stAlert {
            border-radius: 8px;
            border: none;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        
        /* Custom scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: #F1F1F1;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb {
            background: #C0C0C0;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #A0A0A0;
        }
        
        /* Custom animations */
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        .stMarkdown {
            animation: fadeIn 0.5s ease-in;
        }
        </style>
    """, unsafe_allow_html=True)

def get_theme_colors(theme: str) -> dict:
    """Get color scheme for the selected theme."""
    themes = {
        "light": {
            "primary": "#2E86C1",
            "secondary": "#3498DB",
            "background": "#F8F9F9",
            "text": "#2C3E50",
            "accent": "#E74C3C",
            "success": "#27AE60",
            "warning": "#F1C40F",
            "error": "#C0392B"
        },
        "dark": {
            "primary": "#3498DB",
            "secondary": "#2980B9",
            "background": "#2C3E50",
            "text": "#ECF0F1",
            "accent": "#E74C3C",
            "success": "#2ECC71",
            "warning": "#F1C40F",
            "error": "#E74C3C"
        }
    }
    return themes.get(theme.lower(), themes["light"])

def apply_theme_colors(colors: dict):
    """Apply theme colors to components."""
    st.markdown(f"""
        <style>
        :root {{
            --primary-color: {colors['primary']};
            --secondary-color: {colors['secondary']};
            --background-color: {colors['background']};
            --text-color: {colors['text']};
            --accent-color: {colors['accent']};
            --success-color: {colors['success']};
            --warning-color: {colors['warning']};
            --error-color: {colors['error']};
        }}
        
        /* Text colors */
        .main-text {{
            color: var(--text-color);
        }}
        
        /* Button colors */
        .primary-button {{
            background-color: var(--primary-color);
            color: white;
        }}
        .secondary-button {{
            background-color: var(--secondary-color);
            color: white;
        }}
        
        /* Alert colors */
        .success-alert {{
            background-color: var(--success-color);
            color: white;
        }}
        .warning-alert {{
            background-color: var(--warning-color);
            color: black;
        }}
        .error-alert {{
            background-color: var(--error-color);
            color: white;
        }}
        
        /* Custom component styling */
        .metric-card {{
            background-color: var(--background-color);
            border: 1px solid var(--primary-color);
            border-radius: 10px;
            padding: 15px;
            margin: 10px 0;
        }}
        
        .chat-message {{
            background-color: var(--background-color);
            border-left: 4px solid var(--primary-color);
            padding: 10px;
            margin: 5px 0;
            border-radius: 0 10px 10px 0;
        }}
        
        .code-block {{
            background-color: var(--background-color);
            border: 1px solid var(--secondary-color);
            border-radius: 8px;
            padding: 15px;
        }}
        </style>
    """, unsafe_allow_html=True)

def display_review_results(analysis: dict):
    """Display the results of a code review analysis."""
    # Display summary
    st.subheader("📝 Summary")
    st.write(analysis.get('summary', 'No summary available'))
    
    # Display metrics
    st.subheader("📊 Metrics")
    cols = st.columns(3)
    with cols[0]:
        st.metric("Complexity", f"{analysis.get('metrics', {}).get('complexity', 0):.1f}")
    with cols[1]:
        st.metric("Maintainability", f"{analysis.get('metrics', {}).get('maintainability', 0):.1f}")
    with cols[2]:
        st.metric("Security Score", f"{analysis.get('metrics', {}).get('security_score', 0):.1f}")
    
    # Display issues
    st.subheader("🔍 Issues Found")
    issues = analysis.get('issues', [])
    if issues:
        for issue in issues:
            with st.container():
                severity_color = {
                    "high": "🔴",
                    "medium": "🟡",
                    "low": "🟢"
                }.get(issue.get('severity', '').lower(), "⚪")
                
                st.markdown(f"""
                    {severity_color} **{issue.get('severity', 'Unknown')}** (Line {issue.get('line_number', 'N/A')})  
                    {issue.get('description', 'No description')}
                """)
    else:
        st.success("No issues found! Your code looks good! 🎉")

def main():
    """Main function to render the Streamlit app."""
    try:
        # Initialize database tables
        initialize_db()
        
        # Initialize session state
        if 'analyzer' not in st.session_state:
            st.session_state.analyzer = CodeAnalyzer()
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
            
        # Apply theme
        apply_custom_theme()
        
        # Sidebar navigation
        st.sidebar.title("🔍 AI Code Assistant")
        page = st.sidebar.radio("Navigation", ["Code Review", "Chat", "History"])
        
        if page == "Code Review":
            st.title("Code Review")
            code = st.text_area("Enter your code here:", height=300)
            
            if st.button("Review Code"):
                if code:
                    with st.spinner("Analyzing code..."):
                        analysis = perform_code_review(code)
                        if analysis:
                            st.success("Code review completed!")
                            display_review_results(analysis)
                else:
                    st.warning("Please enter some code to review.")
                    
        elif page == "Chat":
            st.title("Chat with AI Assistant")
            render_chat_interface()
            
        else:  # History page
            st.title("Review History")
            reviews = get_recent_reviews()
            if reviews:
                for review in reviews:
                    st.subheader(f"Review {review.id} - {review.review_date.strftime('%Y-%m-%d %H:%M')}")
                    st.code(review.code_content[:100] + "..." if len(review.code_content) > 100 else review.code_content, language="python")
                    
                    # Display metrics in columns
                    if review.metrics:
                        cols = st.columns(3)
                        with cols[0]:
                            st.metric("Complexity", f"{review.metrics.complexity:.1f}")
                        with cols[1]:
                            st.metric("Maintainability", f"{review.metrics.maintainability:.1f}")
                        with cols[2]:
                            st.metric("Security Score", f"{review.metrics.security_score:.1f}")
                    
                    # Display issues as markdown
                    if review.issues:
                        st.markdown("**🔍 Issues Found:**")
                        for issue in review.issues:
                            severity_color = {
                                "high": "🔴",
                                "medium": "🟡",
                                "low": "🟢"
                            }.get(issue.severity.lower(), "⚪")
                            
                            st.markdown(f"{severity_color} **{issue.severity}** (Line {issue.line_number}): {issue.description}")
                    else:
                        st.success("No issues found in this review.")
                    
                    st.markdown("---")
            else:
                st.info("No reviews found in the database.")
                    
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
