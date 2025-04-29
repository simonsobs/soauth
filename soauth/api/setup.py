"""
This file contains code to perform initial setup of the API. If things like the
default app and public key do not exist on disk, they are created.
"""

from datetime import datetime, timezone

from soauth.config.settings import Settings
from soauth.core.cryptography import generate_key_pair


def initial_setup(settings: Settings):
    """
    Performs the initial setup of our 'own' app to authenticate against the auth service.
    """
    if settings.app_id_filename.exists():
        return

    if not settings.create_files:
        return

    # If the file does not exist, we must create it. And the database tables!
    from soauth.database.app import App
    from soauth.database.group import Group
    from soauth.database.meta import ALL_TABLES
    from soauth.database.user import User

    # Ensure ruff doesn't get rid of import
    ALL_TABLES[1]

    manager = settings.sync_manager()
    manager.create_all()

    with manager.session() as conn:
        user = User(user_name=settings.initial_admin, grants="admin")

        group = Group(
            group_name=user.user_name,
            created_by_user_id=user.user_id,
            created_by=user,
            created_at=datetime.now(timezone.utc),
            members=[user],
        )

        public, private = generate_key_pair(
            key_pair_type=settings.key_pair_type, key_password=settings.key_password
        )

        app = App(
            app_name="SOAuth Internal Service",
            api_access=False,
            created_by_user_id=user.user_id,
            created_by=user,
            created_at=datetime.now(timezone.utc),
            domain=settings.hostname,
            key_pair_type=settings.key_pair_type,
            public_key=public,
            private_key=private,
            redirect_url=f"{settings.management_hostname}{settings.management_path}/callback",
        )

        conn.add_all([user, group, app])

        with open(settings.app_id_filename, "w") as handle:
            handle.write(str(app.app_id))

        settings.app_id_filename.chmod(0o600)
        print("Wrote app ID")

        with open(settings.client_secret_filename, "w") as handle:
            handle.write(app.client_secret)
        print("Wrote client secret")

        settings.client_secret_filename.chmod(0o600)

        with open(settings.public_key_filename, "w") as handle:
            handle.write(public.decode("utf-8"))
        print("Wrote public key")

        settings.public_key_filename.chmod(0o600)

        conn.commit()

    return


def example_setup(settings: Settings):
    """
    Performs the 'example' setup where we create fake apps and users.
    """

    if not settings.create_example_app_and_user:
        return {}

    from soauth.database.app import App
    from soauth.database.group import Group
    from soauth.database.meta import ALL_TABLES
    from soauth.database.user import User

    ALL_TABLES[1]

    manager = settings.sync_manager()

    manager.create_all()

    with manager.session() as conn:
        user = User(
            full_name="Example User",
            user_name="example_user",
            email="no@email",
            grants="admin",
        )

        group = Group(
            group_name="example_user",
            created_by_user_id=user.user_id,
            created_by=user,
            created_at=datetime.now(timezone.utc),
            members=[user],
        )

        public, private = generate_key_pair(
            key_pair_type=settings.key_pair_type, key_password=settings.key_password
        )
        app = App(
            app_name="SOAuth Internal Service",
            api_access=False,
            created_by_user_id=user.user_id,
            created_by=user,
            created_at=datetime.now(timezone.utc),
            domain="http://localhost:8001",
            key_pair_type=settings.key_pair_type,
            public_key=public,
            private_key=private,
            redirect_url="http://localhost:8001/callback",
        )

        conn.add_all([user, group, app])

        for admin_user in settings.create_admin_users:
            new_user = User(
                user_name=admin_user, grants="admin", full_name="TBD", email="TBD"
            )
            new_group = Group(
                group_name=admin_user,
                created_by_user_id=new_user.user_id,
                created_by=new_user,
                created_at=datetime.now(timezone.utc),
                members=[new_user],
            )
            conn.add_all([new_user, new_group])

        second_demo_app = App(
            app_name="Simons Observatory",
            api_access=True,
            created_by_user_id=user.user_id,
            created_by=user,
            created_at=datetime.now(timezone.utc),
            domain="http://simonsobs.org",
            key_pair_type=settings.key_pair_type,
            public_key=public,
            private_key=private,
            redirect_url="http://simonsobs.org/callback",
        )

        conn.add(second_demo_app)

        conn.commit()
        print(f"Created example, app_id: {app.app_id}")

        return {
            "created_app_id": app.app_id,
            "created_app_public_key": app.public_key,
            "created_app_client_secret": app.client_secret,
        }
