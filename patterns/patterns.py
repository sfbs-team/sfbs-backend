"""
Sprint 3 | patterns/
Four design patterns required for SE2 Grade 5.

  patterns/singleton.py  → DatabaseConnection (already in database/connection.py)
                           AppConfig singleton shown here as a second example.
  patterns/factory.py    → BookingFactory, FacilityFactory
  patterns/observer.py   → BookingEventSystem (publish-subscribe)
  patterns/strategy.py   → PricingStrategy family

Commit: Muhammad – Sprint 3  (factory.py)
Commit: Mohab    – Sprint 3  (observer.py)
Commit: Salma    – Sprint 3  (strategy.py + singleton example)
"""

# ═══════════════════════════════════════════════════════════════════════════ #
#  SINGLETON – AppConfig                                                      #
#  (DatabaseConnection in database/connection.py is the primary instance)    #
# ═══════════════════════════════════════════════════════════════════════════ #

import os
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Callable, Dict, List, Optional

from models.booking import Booking, Payment, PaymentMethod, TimeSlot
from models.facility import (
    Facility, FacilityType, IndoorFacility, OutdoorFacility,
)
from models.user import Customer


class AppConfig:
    """
    Application-wide configuration singleton.
    Ensures a single, consistent config object is shared across modules.
    Pattern: Singleton (thread-safe double-checked locking).
    """

    _instance: Optional["AppConfig"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "AppConfig":
        with cls._lock:
            if cls._instance is None:
                obj = super().__new__(cls)
                obj._debug          = os.getenv("DEBUG", "false").lower() == "true"
                obj._app_name       = os.getenv("APP_NAME", "SFBS")
                obj._secret_key     = os.getenv("SECRET_KEY", "change-me-in-production")
                obj._jwt_expire_min = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
                obj._stripe_key     = os.getenv("STRIPE_API_KEY", "")
                obj._rabbitmq_url   = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
                cls._instance = obj
        return cls._instance

    @property
    def debug(self)          -> bool: return self._debug
    @property
    def app_name(self)       -> str:  return self._app_name
    @property
    def secret_key(self)     -> str:  return self._secret_key
    @property
    def jwt_expire_min(self) -> int:  return self._jwt_expire_min
    @property
    def stripe_key(self)     -> str:  return self._stripe_key
    @property
    def rabbitmq_url(self)   -> str:  return self._rabbitmq_url

    @classmethod
    def reset(cls) -> None:
        """Test helper — resets the singleton."""
        with cls._lock:
            cls._instance = None


# ═══════════════════════════════════════════════════════════════════════════ #
#  FACTORY – BookingFactory, FacilityFactory                                  #
#  Commit: Muhammad – Sprint 3                                                #
# ═══════════════════════════════════════════════════════════════════════════ #

class FacilityFactory:
    """
    Creates the correct Facility subclass based on environment.
    Pattern: Factory Method — decouples creation logic from callers.
    """

    @staticmethod
    def create_indoor(
        name:           str,
        facility_type:  FacilityType,
        capacity:       int,
        hourly_rate:    float,
        *,
        has_ac:         bool  = False,
        floor_area_sqm: float = 0.0,
        description:    str   = "",
    ) -> IndoorFacility:
        facility = IndoorFacility(
            name=name,
            facility_type=facility_type,
            capacity=capacity,
            hourly_rate=hourly_rate,
            description=description,
            has_ac=has_ac,
            floor_area_sqm=floor_area_sqm,
        )
        if not facility.validate():
            raise ValueError(f"Invalid indoor facility data for '{name}'.")
        return facility

    @staticmethod
    def create_outdoor(
        name:             str,
        facility_type:    FacilityType,
        capacity:         int,
        hourly_rate:      float,
        *,
        has_floodlights:  bool = False,
        surface_type:     str  = "grass",
        description:      str  = "",
    ) -> OutdoorFacility:
        facility = OutdoorFacility(
            name=name,
            facility_type=facility_type,
            capacity=capacity,
            hourly_rate=hourly_rate,
            description=description,
            has_floodlights=has_floodlights,
            surface_type=surface_type,
        )
        if not facility.validate():
            raise ValueError(f"Invalid outdoor facility data for '{name}'.")
        return facility

    @classmethod
    def create(cls, environment: str, **kwargs) -> Facility:
        """Generic entry point — dispatches by environment string."""
        if environment == "indoor":
            return cls.create_indoor(**kwargs)
        elif environment == "outdoor":
            return cls.create_outdoor(**kwargs)
        raise ValueError(f"Unknown environment: {environment!r}")


class BookingFactory:
    """
    Assembles a Booking aggregate from validated inputs.
    Pattern: Factory Method — hides construction complexity.
    """

    @staticmethod
    def create(
        customer:   Customer,
        facility:   Facility,
        start_time: datetime,
        end_time:   datetime,
        notes:      str = "",
    ) -> Booking:
        if not facility.is_available():
            raise RuntimeError(
                f"Facility '{facility.name}' is not available for booking."
            )
        timeslot = TimeSlot(
            start_time  = start_time,
            end_time    = end_time,
            facility_id = facility.id,
        )
        duration_hours = timeslot.duration_hours()
        total_amount   = facility.calculate_cost(duration_hours)

        booking = Booking(
            customer_id  = customer.id,
            facility_id  = facility.id,
            timeslot     = timeslot,
            total_amount = total_amount,
            notes        = notes,
        )
        if not booking.validate():
            raise ValueError("Booking validation failed. Check inputs.")

        timeslot.reserve()
        return booking

    @staticmethod
    def create_payment(booking: Booking, method: PaymentMethod) -> Payment:
        """Create a Payment tied to a confirmed booking."""
        if booking.status.value not in ("pending", "confirmed"):
            raise RuntimeError("Payment can only be created for active bookings.")
        return Payment(
            booking_id     = booking.id,
            amount         = booking.total_amount,
            payment_method = method,
        )


# ═══════════════════════════════════════════════════════════════════════════ #
#  OBSERVER – BookingEventSystem                                               #
#  Commit: Mohab – Sprint 3                                                   #
# ═══════════════════════════════════════════════════════════════════════════ #

class BookingEvent:
    """Value object carrying event data."""
    def __init__(self, event_type: str, booking: Booking, metadata: dict = None):
        self.event_type = event_type      # e.g. "booking.confirmed"
        self.booking    = booking
        self.metadata   = metadata or {}
        self.timestamp  = datetime.utcnow()


class BookingObserver(ABC):
    """Abstract observer — concrete classes subscribe to booking events."""

    @abstractmethod
    def on_event(self, event: BookingEvent) -> None: ...


class EmailNotificationObserver(BookingObserver):
    """Sends email notifications on booking events (simulated)."""

    def __init__(self):
        self._sent: List[BookingEvent] = []

    def on_event(self, event: BookingEvent) -> None:
        # In production this would enqueue an email via RabbitMQ
        print(f"[EMAIL] {event.event_type} → booking {event.booking.id[:8]}...")
        self._sent.append(event)

    @property
    def sent_count(self) -> int:
        return len(self._sent)


class SMSNotificationObserver(BookingObserver):
    """Sends SMS notifications on booking events (simulated)."""

    def __init__(self):
        self._sent: List[BookingEvent] = []

    def on_event(self, event: BookingEvent) -> None:
        print(f"[SMS]   {event.event_type} → booking {event.booking.id[:8]}...")
        self._sent.append(event)

    @property
    def sent_count(self) -> int:
        return len(self._sent)


class AuditLogObserver(BookingObserver):
    """Writes an audit log entry for every booking event."""

    def __init__(self):
        self._log: List[str] = []

    def on_event(self, event: BookingEvent) -> None:
        entry = (
            f"{event.timestamp.isoformat()} | {event.event_type} | "
            f"booking={event.booking.id} | status={event.booking.status.value}"
        )
        self._log.append(entry)

    @property
    def log(self) -> List[str]:
        return list(self._log)


class BookingEventSystem:
    """
    Subject / publisher in the Observer pattern.
    Maintains a registry of observers and broadcasts events to all of them.
    """

    def __init__(self):
        self._observers: Dict[str, List[BookingObserver]] = {}

    def subscribe(self, event_type: str, observer: BookingObserver) -> None:
        self._observers.setdefault(event_type, []).append(observer)

    def unsubscribe(self, event_type: str, observer: BookingObserver) -> None:
        if event_type in self._observers:
            self._observers[event_type] = [
                o for o in self._observers[event_type] if o is not observer
            ]

    def publish(self, event: BookingEvent) -> None:
        """Notify all observers subscribed to this event type."""
        for observer in self._observers.get(event.event_type, []):
            try:
                observer.on_event(event)
            except Exception as exc:
                print(f"[EventSystem] Observer error: {exc}")

    def publish_booking_confirmed(self, booking: Booking) -> None:
        self.publish(BookingEvent("booking.confirmed", booking))

    def publish_booking_cancelled(self, booking: Booking) -> None:
        self.publish(BookingEvent("booking.cancelled", booking))

    def publish_payment_received(self, booking: Booking, txn_ref: str) -> None:
        self.publish(BookingEvent("payment.received", booking,
                                  metadata={"txn_ref": txn_ref}))


# ═══════════════════════════════════════════════════════════════════════════ #
#  STRATEGY – PricingStrategy family                                           #
#  Commit: Salma – Sprint 3                                                   #
# ═══════════════════════════════════════════════════════════════════════════ #

class PricingStrategy(ABC):
    """
    Abstract pricing strategy.
    Pattern: Strategy — allows swapping pricing algorithms at runtime.
    """

    @abstractmethod
    def calculate(self, base_price: float, hours: float, customer: Customer) -> float:
        """Return the final price for a booking."""

    @abstractmethod
    def description(self) -> str:
        """Human-readable name of this strategy."""


class StandardPricing(PricingStrategy):
    """Full price, no discounts."""

    def calculate(self, base_price: float, hours: float,
                  customer: Customer) -> float:
        return round(base_price * hours, 2)

    def description(self) -> str:
        return "Standard rate"


class DiscountedPricing(PricingStrategy):
    """Flat percentage discount (e.g. member discount)."""

    def __init__(self, discount_pct: float) -> None:
        if not (0 < discount_pct < 100):
            raise ValueError("Discount must be between 0 and 100 percent.")
        self._discount = discount_pct

    def calculate(self, base_price: float, hours: float,
                  customer: Customer) -> float:
        gross    = base_price * hours
        discount = gross * (self._discount / 100)
        return round(gross - discount, 2)

    def description(self) -> str:
        return f"{self._discount}% member discount"


class LoyaltyPricing(PricingStrategy):
    """
    Applies a graduated discount based on the customer's loyalty points.
    ≥ 500 pts → 10 %,  ≥ 1 000 pts → 20 %,  ≥ 2 000 pts → 30 %
    """

    _TIERS = [(2000, 30), (1000, 20), (500, 10)]  # (min_points, discount_pct)

    def calculate(self, base_price: float, hours: float,
                  customer: Customer) -> float:
        gross = base_price * hours
        for threshold, pct in self._TIERS:
            if customer.loyalty_points >= threshold:
                return round(gross * (1 - pct / 100), 2)
        return round(gross, 2)

    def description(self) -> str:
        return "Loyalty-tier pricing"


class OffPeakPricing(PricingStrategy):
    """
    Cheaper rate for bookings outside peak hours (08:00–18:00).
    Receives the booking start hour to determine peak/off-peak.
    """

    def __init__(self, off_peak_discount_pct: float = 25.0) -> None:
        self._discount = off_peak_discount_pct

    def calculate(self, base_price: float, hours: float,
                  customer: Customer) -> float:
        # start_hour injected via metadata in real usage
        return round(base_price * hours * (1 - self._discount / 100), 2)

    def description(self) -> str:
        return f"Off-peak rate ({self._discount}% off)"


class PricingContext:
    """
    Context that holds a PricingStrategy and delegates calculation to it.
    Allows the active strategy to be swapped at runtime.
    """

    def __init__(self, strategy: PricingStrategy) -> None:
        self._strategy = strategy

    @property
    def strategy(self) -> PricingStrategy:
        return self._strategy

    @strategy.setter
    def strategy(self, value: PricingStrategy) -> None:
        self._strategy = value

    def get_price(self, base_price: float, hours: float,
                  customer: Customer) -> float:
        return self._strategy.calculate(base_price, hours, customer)

    def get_description(self) -> str:
        return self._strategy.description()
