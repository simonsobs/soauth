"""
A simple CLI for running a sample server.
"""

import os
import sys
import time
from multiprocessing import Process

import uvicorn
from testcontainers.postgres import PostgresContainer


def run_server(**kwargs):
    for k, v in kwargs.items():
        os.environ[k] = v

    uvicorn.run("soauth.api.app:app", host="0.0.0.0")


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

            environment = {
                "SOAUTH_DATABASE_TYPE": "postgres",
                "SOAUTH_DATABASE_USER": container.username,
                "SOAUTH_DATABASE_PASSWORD": container.password,
                "SOAUTH_DATABASE_PORT": str(container.get_exposed_port(container.port)),
                "SOAUTH_DATABASE_HOST": "localhost",
                "SOAUTH_DATABASE_DB": container.dbname,
                "SOAUTH_DATABASE_ECHO": "False",
                "SOAUTH_CREATE_EXAMPLE_APP_AND_USER": "True",
                # "SOAUTH_REFRESH_KEY_EXPIRY": "00:00:59",
                # "SOAUTH_ACCESS_KEY_EXPIRY": "00:00:05",
                "soauth_host_development_only_endpoint": "True",
                "SOAUTH_CREATE_ADMIN_USERS": '["jborrow"]',
            }

            background_process = Process(target=run_server, kwargs=environment)
            background_process.start()

            time.sleep(1)

            uvicorn.run("soauth.app.app:app", host="0.0.0.0", port=8001)
