import peewee
from peewee import *
import datetime
import os
from typing import List
from contextlib import contextmanager

# Database configuration
db_path = os.getenv('TEST_DB', 'reviews.db')
db = SqliteDatabase(db_path, pragmas={
    'journal_mode': 'wal',
    'cache_size': -1024 * 64,  # 64MB
    'foreign_keys': 1,
    'ignore_check_constraints': 0,
    'synchronous': 0
})

@contextmanager
def get_connection():
    """Get a database connection context."""
    try:
        db.connect(reuse_if_open=True)
        yield db
    finally:
        if not db.is_closed():
            db.close()

class BaseModel(Model):
    """Base model class."""
    class Meta:
        database = db

class CodeReview(BaseModel):
    """Model for storing code review data."""
    file_name = CharField()
    code_content = TextField(null=True)
    status = CharField(default="IN_PROGRESS")
    review_date = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = 'codereviews'

class Issue(BaseModel):
    """Model for storing code issues."""
    review = ForeignKeyField(CodeReview, backref='issues')
    severity = CharField()
    description = TextField()
    line_number = IntegerField()

    class Meta:
        table_name = 'issues'

class Metrics(BaseModel):
    """Model for storing code metrics."""
    review = ForeignKeyField(CodeReview, backref='metrics')
    complexity = IntegerField(default=0)
    maintainability = IntegerField(default=0)
    security_score = IntegerField(default=0)

    class Meta:
        table_name = 'metrics'

class ReviewHistory(BaseModel):
    """Model for storing review history."""
    review = ForeignKeyField(CodeReview, backref='history')
    action = CharField()
    details = TextField(null=True)
    timestamp = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = 'reviewhistory'

def initialize_db():
    """Initialize database and create tables."""
    with get_connection():
        db.create_tables([CodeReview, ReviewHistory, Issue, Metrics], safe=True)

def get_recent_reviews(limit: int = 5) -> List[CodeReview]:
    """Get recent code reviews ordered by review_date."""
    with get_connection():
        return list(CodeReview
                .select()
                .order_by(CodeReview.review_date.desc())
                .limit(limit))
