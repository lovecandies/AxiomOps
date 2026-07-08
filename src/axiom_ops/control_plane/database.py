from collections.abc import Iterator
from contextlib import contextmanager

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import DictCursor

from axiom_ops.control_plane.config import ControlPlaneSettings


class Database:
    def __init__(self, settings: ControlPlaneSettings) -> None:
        self.settings = settings

    def connect(self) -> Connection:
        return pymysql.connect(
            host=self.settings.mysql_host,
            port=self.settings.mysql_port,
            user=self.settings.mysql_user,
            password=self.settings.mysql_password,
            database=self.settings.mysql_database,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
            init_command="SET time_zone = '+00:00'",
        )

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        connection = self.connect()
        try:
            connection.begin()
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def verify_schema(self) -> None:
        connection = self.connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM incidents LIMIT 1")
                cursor.execute("SELECT 1 FROM evidence LIMIT 1")
                cursor.execute("SELECT 1 FROM agent_runs LIMIT 1")
                cursor.execute("SELECT 1 FROM agent_run_contexts LIMIT 1")
        finally:
            connection.close()
