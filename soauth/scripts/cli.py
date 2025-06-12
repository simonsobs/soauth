"""
A simple CLI for running a sample server.
"""

import os
import sys
import time
from multiprocessing import Process

import uvicorn


def run_server(**kwargs):
    for k, v in kwargs.items():
        os.environ[k] = v

    uvicorn.run("soauth.api.app:app", host="0.0.0.0")


def run_frontend(**kwargs):
    for k, v in kwargs.items():
        os.environ[k] = v

    uvicorn.run("soauth.app.app:app", host="0.0.0.0", port=8001)


def main():
    try:
        run = sys.argv[1] == "run"
        setup = sys.argv[1] == "setup"
        register = sys.argv[1] == "register"
        dev = sys.argv[2] == "dev"
        prod = sys.argv[2] == "prod"
    except IndexError:
        print(
            "Only supported command is soauth run dev, soauth run prod, or soauth setup {username}"
        )
        exit(1)

    if run and dev:
        from testcontainers.postgres import PostgresContainer

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
                "SOAUTH_HOST_DEVELOPMENT_ONLY_ENDPOINT": "True",
            }

            background_process = Process(target=run_server, kwargs=environment)
            background_process.start()

            time.sleep(1)

            frontend_process = Process(target=run_frontend, kwargs=environment)
            frontend_process.start()

            while True:
                time.sleep(1)
    if run and prod:
        from soauth.api.setup import initial_setup
        from soauth.config.settings import Settings

        settings = Settings()
        initial_setup(settings=settings)

        background_process = Process(target=run_server)
        background_process.start()
        time.sleep(1)
        uvicorn.run("soauth.app.app:app", host="0.0.0.0", port=8001)

    if setup:
        from soauth.api.setup import initial_setup
        from soauth.config.settings import Settings

        settings = Settings()
        initial_setup(settings=settings)

        print("Setup complete, please restart the container or application")
        exit(0)
    if register:
        from pathlib import Path

        from soauth.toolkit.client import TokenData

        tag = sys.argv[2]
        key = sys.argv[3]

        data = TokenData(refresh_token=key)

        storage_location = Path.home() / ".config/soauth"
        storage_location.mkdir(exist_ok=True, parents=True)
        tag_location = storage_location / tag

        with open(tag_location, "w") as handle:
            handle.write(data.model_dump_json())

        tag_location.chmod(0o600)
