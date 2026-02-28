
import pytest
import sqlite3
import os
import sys

# Add root to sys.path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import database
import database_schema

@pytest.fixture
def db_conn():
    """
    Creates an in-memory database with the full schema for testing.
    """
    conn = sqlite3.connect(":memory:")
    conn.isolation_level = None  # Crucial for safe_transaction's BEGIN IMMEDIATE
    conn.execute("PRAGMA journal_mode=WAL")
    # Initialize schema
    database_schema.init_db_from_conn(conn)
    yield conn
    conn.close()

@pytest.fixture
def mock_auth(mocker):
    """
    Mocks auth.get_current_user to return a default admin.
    """
    return mocker.patch('auth.get_current_user', return_value={'id': 1, 'username': 'admin', 'role': 'Admin'})
