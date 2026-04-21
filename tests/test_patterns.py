"""
Sprint 3 | tests/test_patterns.py
Unit tests for all four design patterns.
SE2 Grade 5: design patterns + design pattern tests.

Commit: Salma – Sprint 3
"""

import threading
import unittest
from datetime import datetime, timedelta

from models.booking import PaymentMethod, TimeSlot
from models.facility import FacilityType, IndoorFacility, OutdoorFacility
from models.user import Customer

from patterns.patterns import (
    AppConfig,
    BookingFactory,
    FacilityFactory,
    BookingEventSystem,
    BookingEvent,
    EmailNotificationObserver,
    SMSNotificationObserver,
    AuditLogObserver,
    StandardPricing,
    DiscountedPricing,
    LoyaltyPricing,
    OffPeakPricing,
    PricingContext,
)


# ─────────────────────────────── helpers ────────────────────────────────── #

def _customer(**kw) -> Customer:
    d = dict(username="jdoe", email="j@x.com", password_hash="pw",
             first_name="J", last_name="D")
    d.update(kw)
    return Customer(**d)

def _indoor(**kw):
    d = dict(name="Gym", facility_type=FacilityType.GYM, capacity=20, hourly_rate=50.0)
    d.update(kw)
    return IndoorFacility(**d)


# ═══════════════════════════════════════════════════════════════════════════ #
#  SINGLETON tests  (AppConfig)                                               #
# ═══════════════════════════════════════════════════════════════════════════ #

class TestSingleton(unittest.TestCase):

    def setUp(self):    AppConfig.reset()
    def tearDown(self): AppConfig.reset()

    def test_same_instance_returned(self):
        a, b = AppConfig(), AppConfig()
        self.assertIs(a, b)

    def test_thread_safety(self):
        """All threads must receive the same instance."""
        instances = []
        def create():
            instances.append(AppConfig())

        threads = [threading.Thread(target=create) for _ in range(20)]
        for t in threads: t.start()
        for t in threads: t.join()

        self.assertTrue(all(i is instances[0] for i in instances))

    def test_attributes_readable(self):
        cfg = AppConfig()
        self.assertIsInstance(cfg.app_name, str)
        self.assertIsInstance(cfg.jwt_expire_min, int)

    def test_reset_creates_new_instance(self):
        a = AppConfig()
        AppConfig.reset()
        b = AppConfig()
        # After reset, a new object is created (different identity)
        self.assertIsNot(a, b)


# ═══════════════════════════════════════════════════════════════════════════ #
#  FACTORY tests                                                              #
# ═══════════════════════════════════════════════════════════════════════════ #

class TestFacilityFactory(unittest.TestCase):

    def test_create_indoor_returns_indoor_facility(self):
        f = FacilityFactory.create_indoor(
            "Court A", FacilityType.BASKETBALL_COURT, 20, 60.0, has_ac=True
        )
        self.assertIsInstance(f, IndoorFacility)
        self.assertTrue(f.has_ac)

    def test_create_outdoor_returns_outdoor_facility(self):
        f = FacilityFactory.create_outdoor(
            "Pitch 1", FacilityType.FOOTBALL_PITCH, 22, 80.0,
            has_floodlights=True, surface_type="turf"
        )
        self.assertIsInstance(f, OutdoorFacility)
        self.assertEqual(f.surface_type, "turf")

    def test_generic_create_indoor(self):
        f = FacilityFactory.create(
            "indoor", name="Pool", facility_type=FacilityType.SWIMMING_POOL,
            capacity=50, hourly_rate=100.0
        )
        self.assertIsInstance(f, IndoorFacility)

    def test_generic_create_unknown_raises(self):
        with self.assertRaises(ValueError):
            FacilityFactory.create("underground", name="X",
                                   facility_type=FacilityType.GYM,
                                   capacity=10, hourly_rate=20.0)

    def test_created_facility_is_valid(self):
        f = FacilityFactory.create_indoor(
            "Main Gym", FacilityType.GYM, 30, 50.0
        )
        self.assertTrue(f.validate())


class TestBookingFactory(unittest.TestCase):

    def _slot_times(self):
        start = datetime.utcnow() + timedelta(hours=1)
        return start, start + timedelta(hours=2)

    def test_creates_booking_with_correct_amount(self):
        customer = _customer()
        facility = _indoor(hourly_rate=40.0)
        start, end = self._slot_times()
        booking = BookingFactory.create(customer, facility, start, end)
        # 2 hours × 40.0 = 80.0
        self.assertAlmostEqual(booking.total_amount, 80.0)

    def test_timeslot_reserved_after_creation(self):
        customer = _customer()
        facility = _indoor()
        start, end = self._slot_times()
        booking = BookingFactory.create(customer, facility, start, end)
        self.assertTrue(booking.timeslot.is_reserved)

    def test_unavailable_facility_raises(self):
        customer = _customer()
        facility = _indoor()
        facility.mark_maintenance()
        start, end = self._slot_times()
        with self.assertRaises(RuntimeError):
            BookingFactory.create(customer, facility, start, end)

    def test_create_payment(self):
        customer = _customer()
        facility = _indoor(hourly_rate=50.0)
        start, end = self._slot_times()
        booking = BookingFactory.create(customer, facility, start, end)
        payment = BookingFactory.create_payment(booking, PaymentMethod.CARD)
        self.assertEqual(payment.amount, booking.total_amount)
        self.assertEqual(payment.booking_id, booking.id)


# ═══════════════════════════════════════════════════════════════════════════ #
#  OBSERVER tests                                                             #
# ═══════════════════════════════════════════════════════════════════════════ #

def _make_booking():
    customer = _customer()
    facility = _indoor()
    start = datetime.utcnow() + timedelta(hours=1)
    end   = start + timedelta(hours=2)
    return BookingFactory.create(customer, facility, start, end)


class TestObserver(unittest.TestCase):

    def setUp(self):
        self.system = BookingEventSystem()
        self.email  = EmailNotificationObserver()
        self.sms    = SMSNotificationObserver()
        self.audit  = AuditLogObserver()

    def test_observer_receives_event(self):
        self.system.subscribe("booking.confirmed", self.email)
        booking = _make_booking()
        self.system.publish_booking_confirmed(booking)
        self.assertEqual(self.email.sent_count, 1)

    def test_multiple_observers_all_notified(self):
        booking = _make_booking()
        self.system.subscribe("booking.confirmed", self.email)
        self.system.subscribe("booking.confirmed", self.sms)
        self.system.subscribe("booking.confirmed", self.audit)
        self.system.publish_booking_confirmed(booking)
        self.assertEqual(self.email.sent_count, 1)
        self.assertEqual(self.sms.sent_count, 1)
        self.assertEqual(len(self.audit.log), 1)

    def test_unsubscribed_observer_not_called(self):
        self.system.subscribe("booking.confirmed", self.email)
        self.system.unsubscribe("booking.confirmed", self.email)
        self.system.publish_booking_confirmed(_make_booking())
        self.assertEqual(self.email.sent_count, 0)

    def test_different_event_types_isolated(self):
        self.system.subscribe("booking.confirmed",  self.email)
        self.system.subscribe("booking.cancelled", self.sms)
        booking = _make_booking()
        self.system.publish_booking_confirmed(booking)
        self.assertEqual(self.email.sent_count, 1)
        self.assertEqual(self.sms.sent_count,   0)

    def test_audit_log_contains_event_info(self):
        self.system.subscribe("booking.confirmed", self.audit)
        booking = _make_booking()
        self.system.publish_booking_confirmed(booking)
        self.assertTrue(len(self.audit.log) > 0)
        self.assertIn("booking.confirmed", self.audit.log[0])

    def test_payment_event_published(self):
        self.system.subscribe("payment.received", self.audit)
        booking = _make_booking()
        self.system.publish_payment_received(booking, "txn-123")
        self.assertEqual(len(self.audit.log), 1)


# ═══════════════════════════════════════════════════════════════════════════ #
#  STRATEGY tests                                                             #
# ═══════════════════════════════════════════════════════════════════════════ #

class TestPricingStrategy(unittest.TestCase):

    def _c(self, points=0) -> Customer:
        c = _customer(); c.earn_points(points)
        return c

    def test_standard_pricing(self):
        strat = StandardPricing()
        self.assertAlmostEqual(strat.calculate(50.0, 2.0, self._c()), 100.0)

    def test_discounted_pricing(self):
        strat = DiscountedPricing(20.0)
        # 50 × 2 = 100, minus 20% = 80
        self.assertAlmostEqual(strat.calculate(50.0, 2.0, self._c()), 80.0)

    def test_discounted_invalid_pct_raises(self):
        with self.assertRaises(ValueError):
            DiscountedPricing(0.0)
        with self.assertRaises(ValueError):
            DiscountedPricing(100.0)

    def test_loyalty_tier_500(self):
        strat = LoyaltyPricing()
        # 500 pts → 10% discount: 50×2=100 → 90
        self.assertAlmostEqual(strat.calculate(50.0, 2.0, self._c(500)), 90.0)

    def test_loyalty_tier_1000(self):
        strat = LoyaltyPricing()
        self.assertAlmostEqual(strat.calculate(50.0, 2.0, self._c(1000)), 80.0)

    def test_loyalty_tier_2000(self):
        strat = LoyaltyPricing()
        self.assertAlmostEqual(strat.calculate(50.0, 2.0, self._c(2000)), 70.0)

    def test_loyalty_no_tier(self):
        strat = LoyaltyPricing()
        self.assertAlmostEqual(strat.calculate(50.0, 2.0, self._c(0)), 100.0)

    def test_off_peak_pricing(self):
        strat = OffPeakPricing(25.0)
        self.assertAlmostEqual(strat.calculate(50.0, 2.0, self._c()), 75.0)

    def test_context_delegates_to_strategy(self):
        ctx = PricingContext(StandardPricing())
        self.assertAlmostEqual(ctx.get_price(50.0, 2.0, self._c()), 100.0)

    def test_context_strategy_can_be_swapped(self):
        ctx = PricingContext(StandardPricing())
        ctx.strategy = DiscountedPricing(10.0)
        # 50×2=100 → 90
        self.assertAlmostEqual(ctx.get_price(50.0, 2.0, self._c()), 90.0)

    def test_context_description(self):
        ctx = PricingContext(LoyaltyPricing())
        self.assertIn("loyalty", ctx.get_description().lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
