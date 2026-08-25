import sqlite3
import json
import logging
import threading
from datetime import datetime
from typing import Any, Optional, Dict, Tuple
from Core import name

logger = logging.getLogger(__name__)


class DB:
	_instance = None
	_lock = threading.Lock()

	def __new__(cls, db_path: str = f"Assets/{name}.db"):
		with cls._lock:
			if cls._instance is None:
				cls._instance = super(DB, cls).__new__(cls)
				cls._instance._initialized = False
			return cls._instance

	def __init__(self, db_path: str = f"Assets/{name}.db"):
		if self._initialized:
			return

		self.db_path = db_path
		self._initialized = True
		self._initialize_database()

	def _initialize_database(self) -> None:
		conn = None
		try:
			conn = sqlite3.connect(self.db_path)
			cursor = conn.cursor()

			cursor.execute("""
				CREATE TABLE IF NOT EXISTS data (
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					key TEXT NOT NULL UNIQUE,
					value TEXT,
					created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
					updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
				)
			""")

			cursor.execute("""
				CREATE TABLE IF NOT EXISTS subdata (
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					parent_key TEXT NOT NULL,
					subkey TEXT NOT NULL,
					subvalue TEXT,
					created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
					updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
					FOREIGN KEY (parent_key) REFERENCES data (key) ON DELETE CASCADE,
					UNIQUE (parent_key, subkey)
				)
			""")

			cursor.execute("PRAGMA foreign_keys = ON")
			conn.commit()

		except sqlite3.Error as e:
			logger.error(f"Database initialization error: {e}")
		finally:
			if conn:
				conn.close()

	def _get_connection(self) -> sqlite3.Connection:
		conn = sqlite3.connect(self.db_path)
		conn.execute("PRAGMA foreign_keys = ON")
		return conn

	def _execute_operation(self, operation, *args) -> Any:
		conn = None
		try:
			conn = self._get_connection()
			cursor = conn.cursor()
			result = operation(cursor, *args)
			conn.commit()
			return result
		except (sqlite3.Error, json.JSONDecodeError) as e:
			logger.error(f"Database operation error: {e}")
			if conn:
				conn.rollback()
			raise
		finally:
			if conn:
				conn.close()

	def _serialize_value(self, value: Any) -> str:
		return json.dumps(value)

	def _deserialize_value(self, value_str: Optional[str]) -> Any:
		if value_str is None:
			return None
		return json.loads(value_str)

	def check(self) -> Any:
		def op(cursor):
			cursor.execute("SELECT value FROM data WHERE key = 'done'")
			result = cursor.fetchone()
			if not result:
				return False
			done_value = self._deserialize_value(result[0])
			if done_value and done_value.get("status"):
				return done_value.get("name")
			return False

		try:
			return self._execute_operation(op)
		except (sqlite3.Error, json.JSONDecodeError):
			return False

	def setup(self, done: bool = True, name: str = name) -> bool:
		def op(cursor):
			serialized_done = self._serialize_value({"status": done, "name": name})
			cursor.execute(
				"INSERT OR REPLACE INTO data (key, value, updated_at) VALUES (?, ?, ?)",
				('done', serialized_done, datetime.now().isoformat())
			)
			return True

		try:
			return self._execute_operation(op)
		except sqlite3.Error:
			return False

	def add(self, key: str, value: Any) -> bool:
		def op(cursor):
			serialized_value = self._serialize_value(value)
			cursor.execute(
				"INSERT OR REPLACE INTO data (key, value, updated_at) VALUES (?, ?, ?)",
				(key, serialized_value, datetime.now().isoformat())
			)
			return True

		try:
			return self._execute_operation(op)
		except sqlite3.Error:
			return False

	def subadd(self, key: str, subkey: str, subvalue: Any) -> bool:
		def op(cursor):
			cursor.execute("SELECT 1 FROM data WHERE key = ?", (key,))
			if not cursor.fetchone():
				cursor.execute(
					"INSERT INTO data (key, value, updated_at) VALUES (?, ?, ?)",
					(key, self._serialize_value({}), datetime.now().isoformat())
				)

			serialized_subvalue = self._serialize_value(subvalue)
			cursor.execute(
				"""INSERT OR REPLACE INTO subdata
				   (parent_key, subkey, subvalue, updated_at)
				   VALUES (?, ?, ?, ?)""",
				(key, subkey, serialized_subvalue, datetime.now().isoformat())
			)
			return True

		try:
			return self._execute_operation(op)
		except sqlite3.Error:
			return False

	def get(self, key: str) -> Optional[Any]:
		def op(cursor):
			cursor.execute("SELECT value FROM data WHERE key = ?", (key,))
			result = cursor.fetchone()
			return self._deserialize_value(result[0]) if result else None

		try:
			return self._execute_operation(op)
		except (sqlite3.Error, json.JSONDecodeError):
			return None

	def subget(self, key: str, subkey: str) -> Optional[Any]:
		def op(cursor):
			cursor.execute(
				"SELECT subvalue FROM subdata WHERE parent_key = ? AND subkey = ?",
				(key, subkey)
			)
			result = cursor.fetchone()
			return self._deserialize_value(result[0]) if result else None

		try:
			return self._execute_operation(op)
		except (sqlite3.Error, json.JSONDecodeError):
			return None

	def get_all_subdata(self, key: str) -> Dict[str, Any]:
		def op(cursor):
			cursor.execute(
				"SELECT subkey, subvalue FROM subdata WHERE parent_key = ?",
				(key,)
			)
			return {subkey: self._deserialize_value(subvalue) for subkey, subvalue in cursor.fetchall()}

		try:
			return self._execute_operation(op) or {}
		except (sqlite3.Error, json.JSONDecodeError):
			return {}

	def update(self, update_data: Dict[str, Any]) -> bool:
		def op(cursor):
			for key, value in update_data.items():
				if isinstance(value, dict):
					cursor.execute("SELECT 1 FROM data WHERE key = ?", (key,))
					if not cursor.fetchone():
						cursor.execute(
							"INSERT INTO data (key, value, updated_at) VALUES (?, ?, ?)",
							(key, self._serialize_value({}), datetime.now().isoformat())
						)

					for subkey, subvalue in value.items():
						cursor.execute(
							"""INSERT OR REPLACE INTO subdata
							   (parent_key, subkey, subvalue, updated_at)
							   VALUES (?, ?, ?, ?)""",
							(key, subkey, self._serialize_value(subvalue), datetime.now().isoformat())
						)
				else:
					cursor.execute(
						"INSERT OR REPLACE INTO data (key, value, updated_at) VALUES (?, ?, ?)",
						(key, self._serialize_value(value), datetime.now().isoformat())
					)
			return True

		try:
			return self._execute_operation(op)
		except sqlite3.Error:
			return False

	def fetchall(self) -> Dict[str, Any]:
		def op(cursor):
			cursor.execute("SELECT key, value FROM data")
			main_data = {key: self._deserialize_value(value) for key, value in cursor.fetchall()}

			cursor.execute("SELECT parent_key, subkey, subvalue FROM subdata")
			for parent_key, subkey, subvalue in cursor.fetchall():
				deserialized = self._deserialize_value(subvalue)
				if isinstance(main_data.get(parent_key), dict):
					main_data[parent_key][subkey] = deserialized
				else:
					main_data[parent_key] = {subkey: deserialized}

			return main_data

		try:
			return self._execute_operation(op) or {}
		except (sqlite3.Error, json.JSONDecodeError):
			return {}

	def remove(self, key: str, subkey: Optional[str] = None) -> bool:
		def op(cursor):
			if subkey:
				cursor.execute(
					"DELETE FROM subdata WHERE parent_key = ? AND subkey = ?",
					(key, subkey)
				)
			else:
				cursor.execute("DELETE FROM subdata WHERE parent_key = ?", (key,))
				cursor.execute("DELETE FROM data WHERE key = ?", (key,))
			return cursor.rowcount > 0

		try:
			return self._execute_operation(op)
		except sqlite3.Error:
			return False

	def exists(self, key: str, subkey: Optional[str] = None) -> bool:
		def op(cursor):
			if subkey:
				cursor.execute(
					"SELECT 1 FROM subdata WHERE parent_key = ? AND subkey = ?",
					(key, subkey)
				)
			else:
				cursor.execute("SELECT 1 FROM data WHERE key = ?", (key,))
			return cursor.fetchone() is not None

		try:
			return self._execute_operation(op)
		except sqlite3.Error:
			return False

	def count(self) -> Tuple[int, int]:
		def op(cursor):
			cursor.execute("SELECT COUNT(*) FROM data")
			main_count = cursor.fetchone()[0]
			cursor.execute("SELECT COUNT(*) FROM subdata")
			sub_count = cursor.fetchone()[0]
			return main_count, sub_count

		try:
			return self._execute_operation(op)
		except sqlite3.Error:
			return (0, 0)
