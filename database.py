# database.py

import sqlite3
from typing import List, Tuple

DB_NAME = "fencing_alerts.db"

def initialize_database():
    """Creates the tables if they don't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Main alerts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            coach_name TEXT NOT NULL,
            days_of_week TEXT NOT NULL,
            time_range TEXT NOT NULL
        );
    """)
    # New table to prevent duplicate notifications
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sent_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            notification_key TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(chat_id, notification_key)
        );
    """)
    conn.commit()
    conn.close()

def add_alert(chat_id: int, coach: str, days: str, time_range: str):
    """Adds a new alert to the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO alerts (chat_id, coach_name, days_of_week, time_range) VALUES (?, ?, ?, ?)",
        (chat_id, coach, days, time_range)
    )
    conn.commit()
    conn.close()

def get_user_alerts(chat_id: int) -> List[Tuple]:
    """Retrieves all alerts for a specific user."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, coach_name, days_of_week, time_range FROM alerts WHERE chat_id = ?", (chat_id,))
    alerts = cursor.fetchall()
    conn.close()
    return alerts

def get_all_alerts() -> List[Tuple]:
    """Retrieves all alerts from the database for the scheduler."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, chat_id, coach_name, days_of_week, time_range FROM alerts")
    all_alerts = cursor.fetchall()
    conn.close()
    return all_alerts

def delete_alert(alert_id: int):
    """Deletes a specific alert by its ID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
    conn.commit()
    conn.close()

# --- New Functions for Duplicate Prevention ---

def add_sent_notification(chat_id: int, notification_key: str):
    """Records that a notification has been sent to a user."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO sent_notifications (chat_id, notification_key) VALUES (?, ?)",
        (chat_id, notification_key)
    )
    conn.commit()
    conn.close()

def has_notification_been_sent(chat_id: int, notification_key: str) -> bool:
    """Checks if a specific notification has already been sent to a user."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM sent_notifications WHERE chat_id = ? AND notification_key = ?",
        (chat_id, notification_key)
    )
    result = cursor.fetchone()
    conn.close()
    return result is not None

# Initialize the database when the module is first imported
initialize_database()