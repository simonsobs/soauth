"""
A simple CLI for running a sample server.
"""

import os
import sys

import uvicorn
from testcontainers.postgres import PostgresContainer


def main():
    try:
        run = sys.argv[1] == "run"
        dev = sys.argv[2] == "dev"
    except IndexError:
        print("Only supported command is soauth run dev")
        exit(1)

    if run and dev:
        with PostgresContainer() as container:
            print(
                f"Container details: username={container.username}, password={container.password}, port={container.get_exposed_port(container.port)}"
            )
            os.environ["SOAUTH_DATABASE_TYPE"] = "postgres"
            os.environ["SOAUTH_DATABASE_USER"] = container.username
            os.environ["SOAUTH_DATABASE_PASSWORD"] = container.password
            os.environ["SOAUTH_DATABASE_PORT"] = str(
                container.get_exposed_port(container.port)
            )
            os.environ["SOAUTH_DATABASE_HOST"] = "localhost"
            os.environ["SOAUTH_DATABASE_DB"] = container.dbname
            os.environ["SOAUTH_DATABASE_ECHO"] = "False"
            os.environ["SOAUTH_CREATE_EXAMPLE_APP_AND_USER"] = "True"

            os.environ["SOAUTH_REFRESH_KEY_EXPIRY"] = "00:01:00"
            os.environ["SOAUTH_AUTH_KEY_EXPIRY"] = "00:00:15"

            uvicorn.run("soauth.api.app:app")
