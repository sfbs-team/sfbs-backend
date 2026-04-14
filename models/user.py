"""
Sprint 1 | models/user.py
User hierarchy: BaseEntity → User → Customer / Admin
Commit: Muhammad Commit 1
"""

import re
from enum import Enum
from typing import List, Optional

from models.base_entity import BaseEntity


# ======================================================================= #
#  Enumerations                                                            #
# ======================================================================= #

class UserRole(Enum):
    CUSTOMER = "customer"
    ADMIN    = "admin"
    STAFF    = "staff"


class UserStatus(Enum):
    ACTIVE   = "active"
    INACTIVE = "inactive"
    BANNED   = "banned"


# ======================================================================= #
#  Base User                                                               #
# ======================================================================= #

class User(BaseEntity):
    """
    Core user entity.  Stores credentials and shared profile data.
    Subclasses specialise behaviour via role-specific extensions.
    """

    _EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    )

    def __init__(
        self,
        username:      str,
        email:         str,
        password_hash: str,
        first_name:    str,
        last_name:     str,
    ) -> None:
        super().__init__()
        self._username      = username
        self._email         = email
        self._password_hash = password_hash
        self._first_name    = first_name
        self._last_name     = last_name
        self._status        = UserStatus.ACTIVE
        self._role          = UserRole.CUSTOMER

    # ------------------------------------------------------------------ #
    #  Properties                                                          #
    # ------------------------------------------------------------------ #

    @property
    def username(self) -> str:
        return self._username

    @property
    def email(self) -> str:
        return self._email

    @email.setter
    def email(self, value: str) -> None:
        if not self._is_valid_email(value):
            raise ValueError(f"Invalid email address: {value!r}")
        self._email = value
        self.touch()

    @property
    def first_name(self) -> str:
        return self._first_name

    @property
    def last_name(self) -> str:
        return self._last_name

    @property
    def full_name(self) -> str:
        return f"{self._first_name} {self._last_name}"

    @property
    def role(self) -> UserRole:
        return self._role

    @property
    def status(self) -> UserStatus:
        return self._status

    # ------------------------------------------------------------------ #
    #  Behaviour                                                           #
    # ------------------------------------------------------------------ #

    def activate(self)   -> None: self._status = UserStatus.ACTIVE;    self.touch()
    def deactivate(self) -> None: self._status = UserStatus.INACTIVE;  self.touch()
    def ban(self)        -> None: self._status = UserStatus.BANNED;    self.touch()

    def is_active(self) -> bool:
        return self._status == UserStatus.ACTIVE

    def check_password(self, password_hash: str) -> bool:
        """Simple hash comparison (real app would use bcrypt)."""
        return self._password_hash == password_hash

    # ------------------------------------------------------------------ #
    #  Validation                                                          #
    # ------------------------------------------------------------------ #

    @classmethod
    def _is_valid_email(cls, email: str) -> bool:
        return bool(cls._EMAIL_PATTERN.match(email))

    def validate(self) -> bool:
        return (
            bool(self._username.strip()) and
            bool(self._email.strip())    and
            self._is_valid_email(self._email) and
            bool(self._first_name.strip()) and
            bool(self._last_name.strip())
        )

    # ------------------------------------------------------------------ #
    #  Serialisation                                                       #
    # ------------------------------------------------------------------ #

    def to_dict(self) -> dict:
        return {
            "id":         self._id,
            "username":   self._username,
            "email":      self._email,
            "first_name": self._first_name,
            "last_name":  self._last_name,
            "full_name":  self.full_name,
            "role":       self._role.value,
            "status":     self._status.value,
            "created_at": self._created_at.isoformat(),
            "updated_at": self._updated_at.isoformat(),
        }


# ======================================================================= #
#  Customer                                                                #
# ======================================================================= #

class Customer(User):
    """
    End-user who can browse facilities and create bookings.
    Extends User with phone, loyalty points, and booking history.
    """

    def __init__(
        self,
        username:      str,
        email:         str,
        password_hash: str,
        first_name:    str,
        last_name:     str,
        phone:         str = "",
    ) -> None:
        super().__init__(username, email, password_hash, first_name, last_name)
        self._role            = UserRole.CUSTOMER
        self._phone:    str   = phone
        self._bookings: List  = []
        self._loyalty_points: int = 0

    @property
    def phone(self) -> str:
        return self._phone

    @property
    def loyalty_points(self) -> int:
        return self._loyalty_points

    def add_booking(self, booking) -> None:
        self._bookings.append(booking)

    def get_bookings(self) -> list:
        return list(self._bookings)

    def earn_points(self, points: int) -> None:
        if points < 0:
            raise ValueError("Points earned cannot be negative.")
        self._loyalty_points += points

    def redeem_points(self, points: int) -> None:
        if points > self._loyalty_points:
            raise ValueError(
                f"Insufficient points: have {self._loyalty_points}, need {points}."
            )
        self._loyalty_points -= points

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({
            "phone":          self._phone,
            "loyalty_points": self._loyalty_points,
            "total_bookings": len(self._bookings),
        })
        return d


# ======================================================================= #
#  Admin                                                                   #
# ======================================================================= #

class Admin(User):
    """
    Administrative user with fine-grained permission control.
    Inherits full User behaviour and adds department + permission set.
    """

    def __init__(
        self,
        username:      str,
        email:         str,
        password_hash: str,
        first_name:    str,
        last_name:     str,
        department:    str = "General",
    ) -> None:
        super().__init__(username, email, password_hash, first_name, last_name)
        self._role        = UserRole.ADMIN
        self._department  = department
        self._permissions: set = set()

    @property
    def department(self) -> str:
        return self._department

    def grant_permission(self, permission: str)  -> None: self._permissions.add(permission)
    def revoke_permission(self, permission: str) -> None: self._permissions.discard(permission)

    def has_permission(self, permission: str) -> bool:
        return permission in self._permissions

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({
            "department":  self._department,
            "permissions": sorted(self._permissions),
        })
        return d
