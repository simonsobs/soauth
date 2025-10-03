"""
Meta functionality for the database.
"""

from .app import App
from .auth import RefreshKey
from .group import Group, GroupMembership
from .login import LoginRequest
from .user import User
from .members import MembershipDetails, UserInstitutionalMembership, Institution

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
