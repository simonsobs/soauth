"""
A simple CLI for running a sample server.
"""

import sys

from testcontainers.postgres import PostgresContainer


def main():
    try:
        run = sys[1] == "run"
        dev = sys[2] == "dev"
    except IndexError:
        print("Only supported command is soauth run dev")
        exit(1)

    if run and dev:
        with PostgresContainer() as container:
            yield {
                "database_type": "postgres",
                "database_user": container.username,
                "database_password": container.password,
                "database_port": container.get_exposed_port(container.port),
                "database_host": "localhost",
                "database_db": container.dbname,
                "database_echo": True,
            }
