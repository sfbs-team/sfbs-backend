"""
Sprint 4 | tests/test_integration.py
Integration tests — ISE requirement: ≥ 50% business logic coverage.
Tests the full request lifecycle: pattern wiring, RabbitMQ, Stripe scenarios.
Commit: Salma – Sprint 4
"""

import threading
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from models.booking import BookingStatus, PaymentMethod
from models.facility import FacilityType
from models.user import UserRole

from patterns.patterns import (
    AppConfig,
    BookingFactory,
    BookingEventSystem,
    EmailNotificationObserver,
    AuditLogObserver,
    FacilityFactory,
    PricingContext,
    LoyaltyPricing,
    StandardPricing,
)
from integrations.integrations import (
    JWTService,
    RabbitMQClient,
    StripePaymentService,
)


# ─────────────────────────────────────────────────────────────────────────── #
#  Helpers                                                                    #
# ─────────────────────────────────────────────────────────────────────────── #

from models.user import Customer

def _customer(**kw) -> Customer:
    d = dict(username="u", email="u@x.com", password_hash="p",
             first_name="A", last_name="B")
    d.update(kw)
    return Customer(**d)


def _booking_and_facility():
    customer = _customer()
    facility = FacilityFactory.create_indoor(
        "Court", FacilityType.TENNIS_COURT, 4, 60.0
    )
    start = datetime.utcnow() + timedelta(hours=1)
    end   = start + timedelta(hours=2)
    booking = BookingFactory.create(customer, facility, start, end)
    return customer, facility, booking


# ═══════════════════════════════════════════════════════════════════════════ #
#  JWT Auth integration                                                       #
# ═══════════════════════════════════════════════════════════════════════════ #

class TestJWTIntegration(unittest.TestCase):

    def setUp(self):
        self.jwt = JWTService("test-secret-key", expire_minutes=60)

    def test_create_and_verify_token(self):
        token = self.jwt.create_token("user-1", "user@x.com", "customer")
        payload = self.jwt.verify_token(token)
        self.assertEqual(payload["sub"],   "user-1")
        self.assertEqual(payload["email"], "user@x.com")
        self.assertEqual(payload["role"],  "customer")

    def test_expired_token_raises(self):
        jwt_short = JWTService("test-secret", expire_minutes=-1)
        token = jwt_short.create_token("u", "u@x.com", "customer")
        with self.assertRaises(ValueError):
            jwt_short.verify_token(token)

    def test_tampered_token_raises(self):
        token = self.jwt.create_token("u", "u@x.com", "customer")
        with self.assertRaises(ValueError):
            self.jwt.verify_token(token + "tampered")

    def test_admin_role_in_token(self):
        token = self.jwt.create_token("a-1", "admin@x.com", "admin")
        payload = self.jwt.verify_token(token)
        self.assertEqual(payload["role"], "admin")


# ═══════════════════════════════════════════════════════════════════════════ #
#  Booking + Observer + Queue integration                                     #
# ═══════════════════════════════════════════════════════════════════════════ #

class TestBookingEventIntegration(unittest.TestCase):

    def setUp(self):
        self.events = BookingEventSystem()
        self.email  = EmailNotificationObserver()
        self.audit  = AuditLogObserver()
        self.events.subscribe("booking.confirmed",  self.email)
        self.events.subscribe("booking.confirmed",  self.audit)
        self.events.subscribe("booking.cancelled",  self.audit)
        self.events.subscribe("payment.received",   self.audit)

    def test_full_booking_lifecycle_events(self):
        _, _, booking = _booking_and_facility()
        booking.confirm()
        self.events.publish_booking_confirmed(booking)

        # pay
        payment = BookingFactory.create_payment(booking, PaymentMethod.STRIPE)
        payment.process("txn-001")
        self.events.publish_payment_received(booking, "txn-001")

        # complete
        booking.complete()

        self.assertEqual(self.email.sent_count, 1)
        self.assertEqual(len(self.audit.log),   2)   # confirmed + payment

    def test_cancelled_booking_event(self):
        _, _, booking = _booking_and_facility()
        booking.cancel()
        self.events.publish_booking_cancelled(booking)
        self.assertIn("booking.cancelled", self.audit.log[0])

    def test_concurrent_event_publishing_thread_safety(self):
        """Multiple threads publishing events — no exceptions, correct count."""
        bookings = []
        for _ in range(10):
            _, _, b = _booking_and_facility()
            b.confirm()
            bookings.append(b)

        extra_email = EmailNotificationObserver()
        self.events.subscribe("booking.confirmed", extra_email)

        threads = [
            threading.Thread(
                target=self.events.publish_booking_confirmed, args=(b,)
            ) for b in bookings
        ]
        for t in threads: t.start()
        for t in threads: t.join()

        self.assertEqual(extra_email.sent_count, 10)


# ═══════════════════════════════════════════════════════════════════════════ #
#  Stripe payment integration                                                 #
# ═══════════════════════════════════════════════════════════════════════════ #

class TestStripeIntegration(unittest.TestCase):

    def setUp(self):
        self.stripe = StripePaymentService()

    def test_sandbox_payment_intent_succeeds(self):
        result = self.stripe.create_payment_intent(10000, "pln", "bk-001")
        self.assertTrue(result.success)
        self.assertIsNotNone(result.transaction_ref)
        self.assertIsNotNone(result.client_secret)

    def test_simulated_failed_payment(self):
        result = StripePaymentService.simulate_failed_payment("bk-002")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error_message)
        self.assertIn("declined", result.error_message)

    def test_offline_payment_request(self):
        record = self.stripe.create_offline_payment_request("bk-003", 120.0, "cust-1")
        self.assertEqual(record["status"], "awaiting_admin_approval")
        self.assertIn("offline_ref", record)
        self.assertIsNone(record["approved_by"])

    def test_offline_payment_approval(self):
        record   = self.stripe.create_offline_payment_request("bk-004", 80.0, "cust-2")
        ref      = record["offline_ref"]
        approved = self.stripe.approve_offline_payment(ref, "admin-1")
        self.assertEqual(approved["status"],      "approved")
        self.assertEqual(approved["approved_by"], "admin-1")
        self.assertIsNotNone(approved["approved_at"])

    def test_refund_sandbox(self):
        intent = self.stripe.create_payment_intent(5000, "pln", "bk-005")
        result = self.stripe.refund(intent.transaction_ref)
        self.assertTrue(result.success)


# ═══════════════════════════════════════════════════════════════════════════ #
#  RabbitMQ / in-memory queue integration                                     #
# ═══════════════════════════════════════════════════════════════════════════ #

class TestRabbitMQIntegration(unittest.TestCase):

    def setUp(self):
        self.mq      = RabbitMQClient()
        self.handler = MagicMock()
        from integrations.integrations import NotificationHandler
        self.notification_handler = NotificationHandler()

    def test_publish_booking_confirmed_delivered(self):
        self.mq.subscribe(RabbitMQClient.QUEUE_NOTIFICATIONS,
                          self.notification_handler)
        self.mq.publish_booking_confirmed("bk-1", "user@x.com")
        self.assertEqual(len(self.notification_handler.received), 1)
        msg = self.notification_handler.received[0]
        self.assertEqual(msg.event_type, "booking.confirmed")
        self.assertEqual(msg.payload["booking_id"], "bk-1")

    def test_publish_booking_cancelled_delivered(self):
        self.mq.subscribe(RabbitMQClient.QUEUE_NOTIFICATIONS,
                          self.notification_handler)
        self.mq.publish_booking_cancelled("bk-2", "user@x.com")
        self.assertEqual(len(self.notification_handler.received), 1)
        self.assertEqual(self.notification_handler.received[0].event_type,
                         "booking.cancelled")

    def test_publish_payment_failed_delivered(self):
        from integrations.integrations import PaymentStatusHandler
        handler = PaymentStatusHandler()
        self.mq.subscribe(RabbitMQClient.QUEUE_PAYMENT_STATUS, handler)
        self.mq.publish_payment_failed("bk-3", "Card declined")
        self.assertEqual(len(handler.received), 1)
        self.assertEqual(handler.received[0].event_type, "payment.failed")

    def test_message_stored_in_memory(self):
        self.mq.publish_booking_confirmed("bk-4", "x@y.com")
        msgs = self.mq.get_queued_messages(RabbitMQClient.QUEUE_NOTIFICATIONS)
        self.assertTrue(any(m.payload.get("booking_id") == "bk-4" for m in msgs))

    def test_multiple_queues_isolated(self):
        from integrations.integrations import NotificationHandler, PaymentStatusHandler
        n_handler = NotificationHandler()
        p_handler = PaymentStatusHandler()
        self.mq.subscribe(RabbitMQClient.QUEUE_NOTIFICATIONS,  n_handler)
        self.mq.subscribe(RabbitMQClient.QUEUE_PAYMENT_STATUS, p_handler)
        self.mq.publish_booking_confirmed("bk-5", "a@b.com")
        self.mq.publish_payment_failed("bk-5", "Error")
        self.assertEqual(len(n_handler.received), 1)
        self.assertEqual(len(p_handler.received), 1)


# ═══════════════════════════════════════════════════════════════════════════ #
#  Pricing strategy integration                                               #
# ═══════════════════════════════════════════════════════════════════════════ #

class TestPricingIntegration(unittest.TestCase):

    def test_loyalty_pricing_applied_at_booking(self):
        customer = _customer()
        customer.earn_points(1000)
        facility = FacilityFactory.create_indoor(
            "Pool", FacilityType.SWIMMING_POOL, 50, 100.0
        )
        ctx   = PricingContext(LoyaltyPricing())
        price = ctx.get_price(facility.hourly_rate, 2.0, customer)
        # 1000 pts → 20% off: 100×2=200 → 160
        self.assertAlmostEqual(price, 160.0)

    def test_strategy_swap_mid_session(self):
        customer = _customer()
        ctx = PricingContext(StandardPricing())
        p1  = ctx.get_price(50.0, 2.0, customer)
        ctx.strategy = LoyaltyPricing()
        p2  = ctx.get_price(50.0, 2.0, customer)
        # No points → same price; strategy swapped but tier not met
        self.assertEqual(p1, p2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
