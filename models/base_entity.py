"""
Sprint 1 | models/base_entity.py
Abstract base class shared by all domain entities.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import uuid4


class BaseEntity(ABC):
    """
    Abstract base for every domain object.
    Enforces a common identity contract (id, timestamps) and
    requires subclasses to implement validate() and to_dict().
    """

    def __init__(self) -> None:
        self._id: str = str(uuid4())
        self._created_at: datetime = datetime.utcnow()
        self._updated_at: datetime = datetime.utcnow()

    # ------------------------------------------------------------------ #
    #  Properties                                                          #
    # ------------------------------------------------------------------ #

    @property
    def id(self) -> str:
        return self._id

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    # ------------------------------------------------------------------ #
    #  Mutation helpers                                                    #
    # ------------------------------------------------------------------ #

    def touch(self) -> None:
        """Update the last-modified timestamp."""
        self._updated_at = datetime.utcnow()

    # ------------------------------------------------------------------ #
    #  Abstract interface                                                  #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def validate(self) -> bool:
        """Return True if the entity is in a valid state."""

    @abstractmethod
    def to_dict(self) -> dict:
        """Serialise the entity to a plain dictionary."""

    # ------------------------------------------------------------------ #
    #  Dunder helpers                                                      #
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self._id!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseEntity):
            return NotImplemented
        return self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)
