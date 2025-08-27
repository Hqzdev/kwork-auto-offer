"""Database module for Kwork Auto Offer Bot."""

import asyncio
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite
from cryptography.fernet import Fernet


class Database:
    """SQLite database manager with encryption support."""

    def __init__(self, db_path: str, encryption_key: Optional[bytes] = None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.fernet = Fernet(encryption_key) if encryption_key else None

    async def init(self):
        """Initialize database tables."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS orders_seen (
                    order_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS filters (
                    name TEXT PRIMARY KEY,
                    json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS templates (
                    name TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY,
                    role TEXT DEFAULT 'admin'
                );
                
                CREATE TABLE IF NOT EXISTS blacklist (
                    pattern TEXT PRIMARY KEY,
                    type TEXT NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    enc_blob BLOB NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await db.commit()

    async def add_order_seen(self, order_id: str, title: str, url: str):
        """Add order to seen list."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO orders_seen (order_id, title, url) VALUES (?, ?, ?)",
                (order_id, title, url)
            )
            await db.commit()

    async def is_order_seen(self, order_id: str) -> bool:
        """Check if order was already seen."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM orders_seen WHERE order_id = ?",
                (order_id,)
            )
            return await cursor.fetchone() is not None

    async def cleanup_old_orders(self, days: int = 7):
        """Remove orders older than specified days."""
        cutoff_date = datetime.now() - timedelta(days=days)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM orders_seen WHERE created_at < ?",
                (cutoff_date,)
            )
            await db.commit()

    async def save_filter(self, name: str, filter_data: Dict[str, Any]):
        """Save filter configuration."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO filters (name, json) VALUES (?, ?)",
                (name, json.dumps(filter_data))
            )
            await db.commit()

    async def get_filters(self) -> List[Dict[str, Any]]:
        """Get all filters."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT name, json FROM filters")
            rows = await cursor.fetchall()
            return [{"name": row[0], **json.loads(row[1])} for row in rows]

    async def delete_filter(self, name: str):
        """Delete filter by name."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM filters WHERE name = ?", (name,))
            await db.commit()

    async def save_template(self, name: str, text: str):
        """Save reply template."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO templates (name, text) VALUES (?, ?)",
                (name, text)
            )
            await db.commit()

    async def get_templates(self) -> Dict[str, str]:
        """Get all templates."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT name, text FROM templates")
            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows}

    async def delete_template(self, name: str):
        """Delete template by name."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM templates WHERE name = ?", (name,))
            await db.commit()

    async def add_admin(self, user_id: int, role: str = "admin"):
        """Add admin user."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO admins (user_id, role) VALUES (?, ?)",
                (user_id, role)
            )
            await db.commit()

    async def is_admin(self, user_id: int) -> bool:
        """Check if user is admin."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM admins WHERE user_id = ?",
                (user_id,)
            )
            return await cursor.fetchone() is not None

    async def save_session(self, session_id: str, session_data: bytes):
        """Save encrypted session data."""
        if self.fernet:
            encrypted_data = self.fernet.encrypt(session_data)
        else:
            encrypted_data = session_data

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO sessions (id, enc_blob) VALUES (?, ?)",
                (session_id, encrypted_data)
            )
            await db.commit()

    async def get_session(self, session_id: str) -> Optional[bytes]:
        """Get decrypted session data."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT enc_blob FROM sessions WHERE id = ?",
                (session_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return None

            encrypted_data = row[0]
            if self.fernet:
                return self.fernet.decrypt(encrypted_data)
            return encrypted_data

    async def delete_session(self, session_id: str):
        """Delete session."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            await db.commit()

    async def get_setting(self, key: str) -> Optional[str]:
        """Get setting value."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT value FROM settings WHERE key = ?",
                (key,)
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_setting(self, key: str, value: str):
        """Set setting value."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, value)
            )
            await db.commit()
