"""Local SQLite persistence for project state, the user profile, and LangGraph checkpoints."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from mythinking.state import ProjectState, UserProfile


class StateRepository:
    """Persist validated project snapshots without coupling domain state to an ORM."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def _open_connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._open_connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS project_states (
                    project_id TEXT PRIMARY KEY,
                    schema_version INTEGER NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def save(self, state: ProjectState) -> None:
        self.initialize()
        state.mark_updated()
        with self._open_connection() as connection:
            connection.execute(
                """
                INSERT INTO project_states (
                    project_id, schema_version, state_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    schema_version = excluded.schema_version,
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                """,
                (
                    state.project_id,
                    state.schema_version,
                    state.model_dump_json(),
                    state.created_at.isoformat(),
                    state.updated_at.isoformat(),
                ),
            )

    def load(self, project_id: str) -> ProjectState | None:
        self.initialize()
        with self._open_connection() as connection:
            row = connection.execute(
                "SELECT state_json FROM project_states WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        return ProjectState.model_validate_json(row["state_json"]) if row else None

    def list_project_ids(self) -> list[str]:
        self.initialize()
        with self._open_connection() as connection:
            rows = connection.execute(
                "SELECT project_id FROM project_states ORDER BY updated_at DESC, rowid DESC"
            ).fetchall()
        return [row["project_id"] for row in rows]

    def list_recent(self, limit: int = 20) -> list[ProjectState]:
        """Load the most recently updated project states, newest first.

        Ordered by `updated_at DESC, rowid DESC`: `updated_at` has only
        millisecond-ish real-world resolution, so two saves in quick
        succession (as in tests, or rapid consecutive turns) can carry the
        identical timestamp string. `rowid` -- SQLite's implicit,
        monotonically increasing insert-order column -- breaks that tie
        deterministically in save order instead of leaving it to whatever
        order SQLite happens to scan rows in.
        """

        self.initialize()
        with self._open_connection() as connection:
            rows = connection.execute(
                "SELECT state_json FROM project_states "
                "ORDER BY updated_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [ProjectState.model_validate_json(row["state_json"]) for row in rows]

    def latest_project_id(self) -> str | None:
        self.initialize()
        with self._open_connection() as connection:
            row = connection.execute(
                "SELECT project_id FROM project_states ORDER BY updated_at DESC, rowid DESC LIMIT 1"
            ).fetchone()
        return row["project_id"] if row else None

    def delete(self, project_id: str) -> bool:
        self.initialize()
        with self._open_connection() as connection:
            cursor = connection.execute(
                "DELETE FROM project_states WHERE project_id = ?",
                (project_id,),
            )
        return cursor.rowcount > 0


class ProfileRepository:
    """Persist the single cross-project user profile (M6c, off by default)."""

    _SINGLETON_ID = "singleton"

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @contextmanager
    def _open_connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._open_connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS user_profile (
                    id TEXT PRIMARY KEY,
                    profile_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def load(self) -> UserProfile:
        self.initialize()
        with self._open_connection() as connection:
            row = connection.execute(
                "SELECT profile_json FROM user_profile WHERE id = ?",
                (self._SINGLETON_ID,),
            ).fetchone()
        return UserProfile.model_validate_json(row["profile_json"]) if row else UserProfile()

    def save(self, profile: UserProfile) -> None:
        self.initialize()
        with self._open_connection() as connection:
            connection.execute(
                """
                INSERT INTO user_profile (id, profile_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    profile_json = excluded.profile_json,
                    updated_at = excluded.updated_at
                """,
                (
                    self._SINGLETON_ID,
                    profile.model_dump_json(),
                    profile.updated_at.isoformat(),
                ),
            )


@contextmanager
def open_sqlite_checkpointer(database_path: Path) -> Iterator[SqliteSaver]:
    """Open the checkpointer that future LangGraph workflows will compile with."""

    database_path.parent.mkdir(parents=True, exist_ok=True)
    with SqliteSaver.from_conn_string(str(database_path)) as checkpointer:
        yield checkpointer
