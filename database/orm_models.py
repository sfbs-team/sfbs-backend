"""
Sprint 2 | database/config.py + orm_models.py
Database configuration and SQLAlchemy ORM table definitions.
Commit: Muhammad – Sprint 2
"""

# ─────────────────────────────────────────────────────────────────────────── #
#  database/config.py                                                         #
# ─────────────────────────────────────────────────────────────────────────── #

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseConfig:
    """Immutable database connection configuration read from environment."""
    host:     str
    port:     int
    name:     str
    user:     str
    password: str

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        return cls(
            host     = os.getenv("DB_HOST",     "localhost"),
            port     = int(os.getenv("DB_PORT", "5432")),
            name     = os.getenv("DB_NAME",     "sfbs_db"),
            user     = os.getenv("DB_USER",     "sfbs_user"),
            password = os.getenv("DB_PASSWORD", "sfbs_pass"),
        )

    @property
    def url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )

    @property
    def async_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


# ─────────────────────────────────────────────────────────────────────────── #
#  database/orm_models.py  (SQLAlchemy declarative ORM)                       #
# ─────────────────────────────────────────────────────────────────────────── #

from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, Enum as SAEnum,
    Float, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


class UserORM(Base):
    __tablename__ = "users"

    id             = Column(String(36),  primary_key=True)
    username       = Column(String(64),  unique=True, nullable=False, index=True)
    email          = Column(String(254), unique=True, nullable=False, index=True)
    password_hash  = Column(String(256), nullable=False)
    first_name     = Column(String(64),  nullable=False)
    last_name      = Column(String(64),  nullable=False)
    phone          = Column(String(32),  nullable=True)
    role           = Column(SAEnum("customer", "admin", "staff", name="user_role"),
                            nullable=False, default="customer")
    status         = Column(SAEnum("active", "inactive", "banned", name="user_status"),
                            nullable=False, default="active")
    loyalty_points = Column(Integer, nullable=False, default=0)
    department     = Column(String(64),  nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at     = Column(DateTime, default=datetime.utcnow,
                            onupdate=datetime.utcnow, nullable=False)

    bookings = relationship("BookingORM", back_populates="customer",
                            foreign_keys="BookingORM.customer_id")


class FacilityORM(Base):
    __tablename__ = "facilities"

    id            = Column(String(36), primary_key=True)
    name          = Column(String(128), nullable=False)
    facility_type = Column(String(64),  nullable=False)
    environment   = Column(SAEnum("indoor", "outdoor", name="facility_env"),
                           nullable=False, default="indoor")
    capacity      = Column(Integer, nullable=False)
    hourly_rate   = Column(Float,   nullable=False)
    description   = Column(Text,    nullable=True)
    status        = Column(SAEnum("available", "booked", "maintenance", "closed",
                                  name="facility_status"),
                           nullable=False, default="available")
    has_ac            = Column(Boolean, nullable=True)
    floor_area_sqm    = Column(Float,   nullable=True)
    has_floodlights   = Column(Boolean, nullable=True)
    surface_type      = Column(String(64), nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at    = Column(DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow, nullable=False)

    bookings  = relationship("BookingORM",  back_populates="facility")
    timeslots = relationship("TimeSlotORM", back_populates="facility")


class TimeSlotORM(Base):
    __tablename__ = "timeslots"

    id          = Column(String(36), primary_key=True)
    facility_id = Column(String(36), ForeignKey("facilities.id"), nullable=False)
    start_time  = Column(DateTime,   nullable=False)
    end_time    = Column(DateTime,   nullable=False)
    is_reserved = Column(Boolean,    default=False)

    facility = relationship("FacilityORM", back_populates="timeslots")
    booking  = relationship("BookingORM",  back_populates="timeslot", uselist=False)


class BookingORM(Base):
    __tablename__ = "bookings"

    id           = Column(String(36), primary_key=True)
    customer_id  = Column(String(36), ForeignKey("users.id"),      nullable=False)
    facility_id  = Column(String(36), ForeignKey("facilities.id"), nullable=False)
    timeslot_id  = Column(String(36), ForeignKey("timeslots.id"),  nullable=False, unique=True)
    total_amount = Column(Float,      nullable=False)
    notes        = Column(Text,       nullable=True)
    status       = Column(SAEnum("pending", "confirmed", "cancelled",
                                 "completed", "no_show", name="booking_status"),
                          nullable=False, default="pending")
    payment_id   = Column(String(36), ForeignKey("payments.id"),   nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at   = Column(DateTime, default=datetime.utcnow,
                          onupdate=datetime.utcnow, nullable=False)

    customer = relationship("UserORM",     back_populates="bookings",
                            foreign_keys=[customer_id])
    facility = relationship("FacilityORM", back_populates="bookings")
    timeslot = relationship("TimeSlotORM", back_populates="booking")
    payment  = relationship("PaymentORM",  back_populates="booking",
                            foreign_keys=[payment_id], uselist=False)


class PaymentORM(Base):
    __tablename__ = "payments"

    id              = Column(String(36), primary_key=True)
    booking_id      = Column(String(36), ForeignKey("bookings.id"), nullable=False)
    amount          = Column(Float,      nullable=False)
    payment_method  = Column(SAEnum("card", "cash", "stripe", "loyalty_points",
                                    name="payment_method"), nullable=False)
    status          = Column(SAEnum("pending", "completed", "failed", "refunded",
                                    name="payment_status"),
                             nullable=False, default="pending")
    transaction_ref = Column(String(128), nullable=True)
    is_offline      = Column(Boolean, default=False)   # ISE: offline admin approval
    approved_by     = Column(String(36), nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at      = Column(DateTime, default=datetime.utcnow,
                             onupdate=datetime.utcnow, nullable=False)

    booking = relationship("BookingORM", back_populates="payment",
                           foreign_keys=[booking_id])


class StaffORM(Base):
    __tablename__ = "staff"

    id          = Column(String(36), primary_key=True)
    first_name  = Column(String(64), nullable=False)
    last_name   = Column(String(64), nullable=False)
    email       = Column(String(254), unique=True, nullable=False)
    role        = Column(SAEnum("manager", "receptionist", "maintenance", "coach",
                                name="staff_role"), nullable=False)
    salary      = Column(Float,   nullable=False)
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at  = Column(DateTime, default=datetime.utcnow,
                         onupdate=datetime.utcnow, nullable=False)
