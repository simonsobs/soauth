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


def main():
    try:
        run = sys.argv[1] == "run"
        setup = sys.argv[1] == "setup"
        dev = sys.argv[2] == "dev"
        prod = sys.argv[2] == "prod"
        username = sys.argv[2]
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
                "soauth_host_development_only_endpoint": "True",
                "SOAUTH_CREATE_ADMIN_USERS": '["jborrow"]',
            }

            background_process = Process(target=run_server, kwargs=environment)
            background_process.start()

            time.sleep(1)

            uvicorn.run("soauth.app.app:app", host="0.0.0.0", port=8001)

    if run and prod:
        background_process = Process(target=run_server)
        background_process.start()
        time.sleep(1)
        uvicorn.run("soauth.app.app:app", host="0.0.0.0", port=8001)

    if setup:
        import datetime

        from soauth.config.settings import Settings
        from soauth.core.cryptography import generate_key_pair
        from soauth.database.app import App
        from soauth.database.group import Group
        from soauth.database.meta import ALL_TABLES
        from soauth.database.user import User

        settings = Settings()

        ALL_TABLES[1]

        manager = settings.sync_manager()
        manager.create_all()

        with manager.session() as conn:
            user = User(
                full_name="TBD",
                user_name=username,
                email="TBD",
                grants="admin",
            )

            group = Group(
                group_name=username,
                created_by_user_id=user.user_id,
                created_by=user,
                created_at=datetime.datetime.now(datetime.timezone.utc),
                members=[user],
            )

            public, private = generate_key_pair(
                key_pair_type=settings.key_pair_type, key_password=settings.key_password
            )
            app = App(
                created_by_user_id=user.user_id,
                created_by=user,
                created_at=datetime.datetime.now(datetime.timezone.utc),
                domain=settings.hostname,
                redirect_url=f"{settings.hostname}/management/redirect",
                key_pair_type=settings.key_pair_type,
                public_key=public,
                private_key=private,
            )

            conn.add_all([user, group, app])

            conn.commit()
            settings.created_app_id = app.app_id
            settings.created_app_public_key = app.public_key
            print(f"Created base app_id: {app.app_id}")
            print(f"Public key: {app.public_key.decode('utf-8')}")
            print(f"Secret: {app.client_secret}")
            print(f"Key pair type: {app.key_pair_type}")
