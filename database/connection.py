# Sprint 2 - Mohab Tawfik: Singleton DB connection and repository layer

"""
Sprint 2 | database/connection.py  +  repositories/
Singleton database connection manager and full CRUD repository layer.
Commit: Mohab – Sprint 2  (connection + base repo)
Commit: Salma – Sprint 2  (user / facility / booking repos)
"""

# ─────────────────────────────────────────────────────────────────────────── #
#  connection.py  –  Singleton pattern (SE2 design-pattern requirement)       #
# ─────────────────────────────────────────────────────────────────────────── #

import threading
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from database.config import DatabaseConfig
from database.orm_models import Base


class DatabaseConnection:
    """
    Thread-safe Singleton database connection manager.
    Ensures a single SQLAlchemy engine + session factory is shared
    across the entire application (satisfies SE2 Singleton pattern requirement).
    """

    _instance: Optional["DatabaseConnection"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "DatabaseConnection":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialised = False
        return cls._instance

    def initialise(self, config: Optional[DatabaseConfig] = None) -> None:
        """Idempotent initialisation — safe to call multiple times."""
        if self._initialised:
            return
        cfg = config or DatabaseConfig.from_env()
        self._engine = create_engine(
            cfg.url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,   # recycles stale connections
            echo=False,
        )
        self._SessionFactory = sessionmaker(
            bind=self._engine, autocommit=False, autoflush=False,
        )
        self._initialised = True

    def create_tables(self) -> None:
        """Create all tables defined in ORM models."""
        Base.metadata.create_all(self._engine)

    def drop_tables(self) -> None:
        """Drop all tables — used in test teardown."""
        Base.metadata.drop_all(self._engine)

    def get_session(self) -> Session:
        if not self._initialised:
            raise RuntimeError("DatabaseConnection not initialised. Call .initialise() first.")
        return self._SessionFactory()

    def health_check(self) -> bool:
        """Return True if the database is reachable."""
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    @classmethod
    def reset(cls) -> None:
        """Destroy the singleton — used in unit tests only."""
        with cls._lock:
            cls._instance = None


# ─────────────────────────────────────────────────────────────────────────── #
#  repositories/base_repository.py  –  Generic Repository pattern            #
# ─────────────────────────────────────────────────────────────────────────── #

from abc import ABC, abstractmethod
from typing import Generic, List, TypeVar

T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """
    Abstract generic repository.
    Provides the standard CRUD interface that every concrete
    repository must implement (Repository pattern for SE2 Grade 5).
    """

    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    @abstractmethod
    def get_by_id(self, entity_id: str) -> Optional[T]: ...

    @abstractmethod
    def get_all(self) -> List[T]: ...

    @abstractmethod
    def save(self, entity: T) -> T: ...

    @abstractmethod
    def delete(self, entity_id: str) -> bool: ...


# ─────────────────────────────────────────────────────────────────────────── #
#  repositories/user_repository.py                                            #
# ─────────────────────────────────────────────────────────────────────────── #

from typing import Optional as Opt
from database.orm_models import UserORM
from models.user import Customer, Admin, User, UserRole, UserStatus


class UserRepository(BaseRepository[UserORM]):
    """CRUD operations for the users table."""

    def get_by_id(self, entity_id: str) -> Opt[UserORM]:
        with self._db.get_session() as session:
            return session.query(UserORM).filter(UserORM.id == entity_id).first()

    def get_by_username(self, username: str) -> Opt[UserORM]:
        with self._db.get_session() as session:
            return (session.query(UserORM)
                    .filter(UserORM.username == username).first())

    def get_by_email(self, email: str) -> Opt[UserORM]:
        with self._db.get_session() as session:
            return (session.query(UserORM)
                    .filter(UserORM.email == email).first())

    def get_all(self) -> List[UserORM]:
        with self._db.get_session() as session:
            return session.query(UserORM).all()

    def save(self, entity: UserORM) -> UserORM:
        with self._db.get_session() as session:
            session.merge(entity)
            session.commit()
            return entity

    def delete(self, entity_id: str) -> bool:
        with self._db.get_session() as session:
            row = session.query(UserORM).filter(UserORM.id == entity_id).first()
            if row:
                session.delete(row)
                session.commit()
                return True
            return False

    # ── Domain → ORM ─────────────────────────────────────────────────────── #

    @staticmethod
    def from_domain(user: User) -> UserORM:
        orm = UserORM(
            id            = user.id,
            username      = user.username,
            email         = user.email,
            password_hash = user._password_hash,
            first_name    = user.first_name,
            last_name     = user.last_name,
            role          = user.role.value,
            status        = user.status.value,
        )
        if isinstance(user, Customer):
            orm.phone          = user.phone
            orm.loyalty_points = user.loyalty_points
        if isinstance(user, Admin):
            orm.department = user.department
        return orm


# ─────────────────────────────────────────────────────────────────────────── #
#  repositories/facility_repository.py                                        #
# ─────────────────────────────────────────────────────────────────────────── #

from database.orm_models import FacilityORM
from models.facility import Facility, IndoorFacility, OutdoorFacility, FacilityStatus


class FacilityRepository(BaseRepository[FacilityORM]):
    """CRUD operations for the facilities table."""

    def get_by_id(self, entity_id: str) -> Opt[FacilityORM]:
        with self._db.get_session() as session:
            return session.query(FacilityORM).filter(
                FacilityORM.id == entity_id).first()

    def get_all(self) -> List[FacilityORM]:
        with self._db.get_session() as session:
            return session.query(FacilityORM).all()

    def get_available(self) -> List[FacilityORM]:
        with self._db.get_session() as session:
            return (session.query(FacilityORM)
                    .filter(FacilityORM.status == "available").all())

    def save(self, entity: FacilityORM) -> FacilityORM:
        with self._db.get_session() as session:
            session.merge(entity)
            session.commit()
            return entity

    def delete(self, entity_id: str) -> bool:
        with self._db.get_session() as session:
            row = session.query(FacilityORM).filter(
                FacilityORM.id == entity_id).first()
            if row:
                session.delete(row); session.commit(); return True
            return False

    @staticmethod
    def from_domain(facility: Facility) -> FacilityORM:
        orm = FacilityORM(
            id            = facility.id,
            name          = facility.name,
            facility_type = facility.facility_type.value,
            capacity      = facility.capacity,
            hourly_rate   = facility.hourly_rate,
            description   = facility.description,
            status        = facility.status.value,
        )
        if isinstance(facility, IndoorFacility):
            orm.environment    = "indoor"
            orm.has_ac         = facility.has_ac
            orm.floor_area_sqm = facility.floor_area_sqm
        elif isinstance(facility, OutdoorFacility):
            orm.environment      = "outdoor"
            orm.has_floodlights  = facility.has_floodlights
            orm.surface_type     = facility.surface_type
        return orm


# ─────────────────────────────────────────────────────────────────────────── #
#  repositories/booking_repository.py                                         #
# ─────────────────────────────────────────────────────────────────────────── #

from database.orm_models import BookingORM, TimeSlotORM, PaymentORM
from models.booking import Booking, BookingStatus, Payment, TimeSlot


class BookingRepository(BaseRepository[BookingORM]):
    """CRUD operations for bookings, timeslots, and payments."""

    def get_by_id(self, entity_id: str) -> Opt[BookingORM]:
        with self._db.get_session() as session:
            return session.query(BookingORM).filter(
                BookingORM.id == entity_id).first()

    def get_all(self) -> List[BookingORM]:
        with self._db.get_session() as session:
            return session.query(BookingORM).all()

    def get_by_customer(self, customer_id: str) -> List[BookingORM]:
        with self._db.get_session() as session:
            return (session.query(BookingORM)
                    .filter(BookingORM.customer_id == customer_id).all())

    def get_by_facility(self, facility_id: str) -> List[BookingORM]:
        with self._db.get_session() as session:
            return (session.query(BookingORM)
                    .filter(BookingORM.facility_id == facility_id).all())

    def save(self, entity: BookingORM) -> BookingORM:
        with self._db.get_session() as session:
            session.merge(entity)
            session.commit()
            return entity

    def delete(self, entity_id: str) -> bool:
        with self._db.get_session() as session:
            row = session.query(BookingORM).filter(
                BookingORM.id == entity_id).first()
            if row:
                session.delete(row); session.commit(); return True
            return False

    def save_timeslot(self, slot: TimeSlot) -> TimeSlotORM:
        orm = TimeSlotORM(
            id          = slot.id,
            facility_id = slot.facility_id,
            start_time  = slot.start_time,
            end_time    = slot.end_time,
            is_reserved = slot.is_reserved,
        )
        with self._db.get_session() as session:
            session.merge(orm); session.commit()
        return orm

    def save_payment(self, payment: Payment) -> PaymentORM:
        orm = PaymentORM(
            id              = payment.id,
            booking_id      = payment.booking_id,
            amount          = payment.amount,
            payment_method  = payment.payment_method.value,
            status          = payment.status.value,
            transaction_ref = payment.transaction_ref,
        )
        with self._db.get_session() as session:
            session.merge(orm); session.commit()
        return orm

    @staticmethod
    def from_domain(booking: Booking) -> BookingORM:
        return BookingORM(
            id           = booking.id,
            customer_id  = booking.customer_id,
            facility_id  = booking.facility_id,
            timeslot_id  = booking.timeslot.id,
            total_amount = booking.total_amount,
            notes        = booking.notes,
            status       = booking.status.value,
            payment_id   = booking.payment_id,
        )
