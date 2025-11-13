"""
Meta functionality for the database.
"""

from .app import App
from .auth import RefreshKey
from .group import Group, GroupMembership
from .login import LoginRequest
from .members import Institution, MembershipDetails, UserInstitutionalMembership
from .user import User

ALL_TABLES = (
    App,
    RefreshKey,
    Group,
    GroupMembership,
    LoginRequest,
    MembershipDetails,
    User,
    UserInstitutionalMembership,
    Institution,
)
