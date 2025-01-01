import sqlite3
from typing import Any, List, Tuple, Union

class DB:
    def __init__(self, db_path: str):
        """Initialize the database connection."""
        self.db_path = db_path
        self.connection = None
        self.connect()

    def connect(self):
        """Establish a connection to the SQLite database."""
        if not self.connection:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row  # Optional: Enables dictionary-like row access

    def close(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def execute_query(self, query: str, params: Union[Tuple, List] = ()) -> sqlite3.Cursor:
        """
        Execute a query and return the cursor.
        Useful for creating tables, inserting, updating, or deleting records.
        """
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        self.connection.commit()
        return cursor

    def fetch_all(self, query: str, params: Union[Tuple, List] = ()) -> List[sqlite3.Row]:
        """Fetch all rows from the result of a SELECT query."""
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

    def fetch_one(self, query: str, params: Union[Tuple, List] = ()) -> Union[sqlite3.Row, None]:
        """Fetch a single row from the result of a SELECT query."""
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()

    def insert(self, table: str, data: dict) -> int:
        """
        Insert a row into a table.
        :param table: Table name
        :param data: Dictionary of column-value pairs
        :return: The last row ID of the inserted row
        """
        keys = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        query = f"INSERT INTO {table} ({keys}) VALUES ({placeholders})"
        cursor = self.execute_query(query, tuple(data.values()))
        return cursor.lastrowid

    def update(self, table: str, data: dict, where_clause: str, where_params: Tuple) -> int:
        """
        Update rows in a table.
        :param table: Table name
        :param data: Dictionary of column-value pairs
        :param where_clause: WHERE clause to filter rows
        :param where_params: Parameters for the WHERE clause
        :return: Number of rows updated
        """
        set_clause = ", ".join([f"{key} = ?" for key in data.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        params = tuple(data.values()) + where_params
        cursor = self.execute_query(query, params)
        return cursor.rowcount

    def delete(self, table: str, where_clause: str, where_params: Tuple) -> int:
        """
        Delete rows from a table.
        :param table: Table name
        :param where_clause: WHERE clause to filter rows
        :param where_params: Parameters for the WHERE clause
        :return: Number of rows deleted
        """
        query = f"DELETE FROM {table} WHERE {where_clause}"
        cursor = self.execute_query(query, where_params)
        return cursor.rowcount

    def __enter__(self):
        """Support for context manager."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Ensure the connection is closed when exiting a context."""
        self.close()