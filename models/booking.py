# Sprint 1 - Mohab Tawfik: Booking, Payment, Staff, TimeSlot models


"""
Sprint 1 | models/booking.py  +  timeslot.py  +  payment.py  +  staff.py
All remaining domain models for Sprint 1.
Commit: Salma Commit 1
"""

# ============================================================= #
#  timeslot.py content (inlined)                                 #
# ============================================================= #

from datetime import datetime
from enum import Enum
from typing import Optional

from models.base_entity import BaseEntity


class TimeSlot(BaseEntity):
    """
    Represents a contiguous block of time on a specific date.
    Used to define available booking windows for a facility.
    """

    def __init__(
        self,
        start_time:  datetime,
        end_time:    datetime,
        facility_id: str,
    ) -> None:
        super().__init__()
        if end_time <= start_time:
            raise ValueError("end_time must be after start_time.")
        self._start_time:  datetime = start_time
        self._end_time:    datetime = end_time
        self._facility_id: str      = facility_id
        self._is_reserved: bool     = False

    @property
    def start_time(self) -> datetime:
        return self._start_time

    @property
    def end_time(self) -> datetime:
        return self._end_time

    @property
    def facility_id(self) -> str:
        return self._facility_id

    @property
    def is_reserved(self) -> bool:
        return self._is_reserved

    def duration_hours(self) -> float:
        delta = self._end_time - self._start_time
        return round(delta.total_seconds() / 3600, 2)

    def reserve(self) -> None:
        if self._is_reserved:
            raise RuntimeError("Time slot is already reserved.")
        self._is_reserved = True
        self.touch()

    def release(self) -> None:
        self._is_reserved = False
        self.touch()

    def overlaps(self, other: "TimeSlot") -> bool:
        """Return True if this slot overlaps with another."""
        return self._start_time < other._end_time and self._end_time > other._start_time

    def validate(self) -> bool:
        return self._end_time > self._start_time and bool(self._facility_id)

    def to_dict(self) -> dict:
        return {
            "id":          self._id,
            "facility_id": self._facility_id,
            "start_time":  self._start_time.isoformat(),
            "end_time":    self._end_time.isoformat(),
            "duration_h":  self.duration_hours(),
            "is_reserved": self._is_reserved,
        }


# ============================================================= #
#  Booking                                                       #
# ============================================================= #

class BookingStatus(Enum):
    PENDING   = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW   = "no_show"


class Booking(BaseEntity):
    """
    Central aggregate that connects a Customer, a Facility, and a TimeSlot.
    Manages its own status lifecycle and links to a Payment once settled.
    """

    def __init__(
        self,
        customer_id:  str,
        facility_id:  str,
        timeslot:     TimeSlot,
        total_amount: float,
        notes:        str = "",
    ) -> None:
        super().__init__()
        if total_amount < 0:
            raise ValueError("Total amount cannot be negative.")
        self._customer_id:  str           = customer_id
        self._facility_id:  str           = facility_id
        self._timeslot:     TimeSlot      = timeslot
        self._total_amount: float         = total_amount
        self._notes:        str           = notes
        self._status:       BookingStatus = BookingStatus.PENDING
        self._payment_id:   Optional[str] = None

    # ---------------------------------------------------------------- #
    #  Properties                                                        #
    # ---------------------------------------------------------------- #

    @property
    def customer_id(self)  -> str:           return self._customer_id
    @property
    def facility_id(self)  -> str:           return self._facility_id
    @property
    def timeslot(self)     -> TimeSlot:      return self._timeslot
    @property
    def total_amount(self) -> float:         return self._total_amount
    @property
    def notes(self)        -> str:           return self._notes
    @property
    def status(self)       -> BookingStatus: return self._status
    @property
    def payment_id(self)   -> Optional[str]: return self._payment_id

    # ---------------------------------------------------------------- #
    #  State machine                                                     #
    # ---------------------------------------------------------------- #

    def confirm(self) -> None:
        if self._status != BookingStatus.PENDING:
            raise RuntimeError(f"Cannot confirm a booking in {self._status.value} state.")
        self._status = BookingStatus.CONFIRMED
        self.touch()

    def cancel(self) -> None:
        if self._status in (BookingStatus.COMPLETED, BookingStatus.CANCELLED):
            raise RuntimeError(f"Cannot cancel a booking in {self._status.value} state.")
        self._status = BookingStatus.CANCELLED
        self._timeslot.release()
        self.touch()

    def complete(self) -> None:
        if self._status != BookingStatus.CONFIRMED:
            raise RuntimeError("Only confirmed bookings can be completed.")
        self._status = BookingStatus.COMPLETED
        self.touch()

    def mark_no_show(self) -> None:
        if self._status != BookingStatus.CONFIRMED:
            raise RuntimeError("Only confirmed bookings can be marked as no-show.")
        self._status = BookingStatus.NO_SHOW
        self.touch()

    def attach_payment(self, payment_id: str) -> None:
        self._payment_id = payment_id
        self.touch()

    # ---------------------------------------------------------------- #
    #  Validation & Serialisation                                        #
    # ---------------------------------------------------------------- #

    def validate(self) -> bool:
        return (
            bool(self._customer_id) and
            bool(self._facility_id) and
            self._timeslot.validate() and
            self._total_amount >= 0
        )

    def to_dict(self) -> dict:
        return {
            "id":           self._id,
            "customer_id":  self._customer_id,
            "facility_id":  self._facility_id,
            "timeslot":     self._timeslot.to_dict(),
            "total_amount": self._total_amount,
            "notes":        self._notes,
            "status":       self._status.value,
            "payment_id":   self._payment_id,
            "created_at":   self._created_at.isoformat(),
        }


# ============================================================= #
#  Payment                                                       #
# ============================================================= #

class PaymentMethod(Enum):
    CARD   = "card"
    CASH   = "cash"
    STRIPE = "stripe"
    POINTS = "loyalty_points"


class PaymentStatus(Enum):
    PENDING   = "pending"
    COMPLETED = "completed"
    FAILED    = "failed"
    REFUNDED  = "refunded"


class Payment(BaseEntity):
    """
    Records a financial transaction tied to a Booking.
    Tracks amount, method, and current status.
    """

    def __init__(
        self,
        booking_id:     str,
        amount:         float,
        payment_method: PaymentMethod,
    ) -> None:
        super().__init__()
        if amount <= 0:
            raise ValueError("Payment amount must be positive.")
        self._booking_id:     str           = booking_id
        self._amount:         float         = amount
        self._payment_method: PaymentMethod = payment_method
        self._status:         PaymentStatus = PaymentStatus.PENDING
        self._transaction_ref: Optional[str] = None

    @property
    def booking_id(self)      -> str:           return self._booking_id
    @property
    def amount(self)          -> float:         return self._amount
    @property
    def payment_method(self)  -> PaymentMethod: return self._payment_method
    @property
    def status(self)          -> PaymentStatus: return self._status
    @property
    def transaction_ref(self) -> Optional[str]: return self._transaction_ref

    def process(self, transaction_ref: str) -> None:
        self._transaction_ref = transaction_ref
        self._status = PaymentStatus.COMPLETED
        self.touch()

    def fail(self) -> None:
        self._status = PaymentStatus.FAILED
        self.touch()

    def refund(self) -> None:
        if self._status != PaymentStatus.COMPLETED:
            raise RuntimeError("Only completed payments can be refunded.")
        self._status = PaymentStatus.REFUNDED
        self.touch()

    def validate(self) -> bool:
        return bool(self._booking_id) and self._amount > 0

    def to_dict(self) -> dict:
        return {
            "id":              self._id,
            "booking_id":      self._booking_id,
            "amount":          self._amount,
            "payment_method":  self._payment_method.value,
            "status":          self._status.value,
            "transaction_ref": self._transaction_ref,
            "created_at":      self._created_at.isoformat(),
        }


# ============================================================= #
#  Staff                                                         #
# ============================================================= #

class StaffRole(Enum):
    MANAGER     = "manager"
    RECEPTIONIST = "receptionist"
    MAINTENANCE = "maintenance"
    COACH       = "coach"


class Staff(BaseEntity):
    """
    Represents an employee who manages or operates facilities.
    Tracks role, salary, and assigned facilities.
    """

    def __init__(
        self,
        first_name: str,
        last_name:  str,
        email:      str,
        role:       StaffRole,
        salary:     float,
    ) -> None:
        super().__init__()
        if salary < 0:
            raise ValueError("Salary cannot be negative.")
        self._first_name:         str       = first_name
        self._last_name:          str       = last_name
        self._email:              str       = email
        self._role:               StaffRole = role
        self._salary:             float     = salary
        self._is_active:          bool      = True
        self._assigned_facilities: list     = []

    @property
    def full_name(self) -> str:
        return f"{self._first_name} {self._last_name}"

    @property
    def email(self)    -> str:       return self._email
    @property
    def role(self)     -> StaffRole: return self._role
    @property
    def salary(self)   -> float:     return self._salary
    @property
    def is_active(self)-> bool:      return self._is_active

    def hire(self) -> None:
        self._is_active = True
        self.touch()

    def terminate(self) -> None:
        self._is_active = False
        self._assigned_facilities.clear()
        self.touch()

    def give_raise(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Raise amount must be positive.")
        self._salary += amount
        self.touch()

    def assign_facility(self, facility_id: str) -> None:
        if facility_id not in self._assigned_facilities:
            self._assigned_facilities.append(facility_id)
            self.touch()

    def unassign_facility(self, facility_id: str) -> None:
        if facility_id in self._assigned_facilities:
            self._assigned_facilities.remove(facility_id)
            self.touch()

    def get_assigned_facilities(self) -> list:
        return list(self._assigned_facilities)

    def validate(self) -> bool:
        return (
            bool(self._first_name.strip()) and
            bool(self._last_name.strip())  and
            bool(self._email.strip())      and
            self._salary >= 0
        )

    def to_dict(self) -> dict:
        return {
            "id":                   self._id,
            "full_name":            self.full_name,
            "email":                self._email,
            "role":                 self._role.value,
            "salary":               self._salary,
            "is_active":            self._is_active,
            "assigned_facilities":  list(self._assigned_facilities),
            "created_at":           self._created_at.isoformat(),
        }
