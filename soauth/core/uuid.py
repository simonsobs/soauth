"""
UUID creation. Required because uuid7 was not part of the python standard as of 3.12
"""

from uuid import UUID as UUID

from uuid_extensions import uuid7 as uuid7

__ALL__ = ["UUID", "uuid7"]
