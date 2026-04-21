"""
Sprint 3 | integrations/
ISE Requirements:
  - OAuth2 social login (Google)
  - Stripe payment integration with failed payment handling
  - Offline payment admin approval
  - RabbitMQ async message queues

Commit: Muhammad – Sprint 3  (oauth2.py)
Commit: Mohab    – Sprint 3  (stripe_payment.py)
Commit: Salma    – Sprint 3  (rabbitmq.py)
"""

# ─────────────────────────────────────────────────────────────────────────── #
#  oauth2.py  –  Google OAuth2 social login                                   #
# ─────────────────────────────────────────────────────────────────────────── #

import hashlib
import hmac
import json
import os
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

import jwt  # PyJWT


@dataclass
class OAuthUserInfo:
    """Normalised user info returned after OAuth2 token exchange."""
    provider:    str
    provider_id: str
    email:       str
    first_name:  str
    last_name:   str
    picture_url: str = ""


class OAuth2Provider(ABC):
    """Abstract OAuth2 provider."""

    @abstractmethod
    def get_authorization_url(self, redirect_uri: str, state: str) -> str: ...

    @abstractmethod
    def exchange_code(self, code: str, redirect_uri: str) -> OAuthUserInfo: ...


class GoogleOAuth2Provider(OAuth2Provider):
    """
    Google OAuth2 integration.
    Uses google-auth library; token verification is done server-side.
    """

    AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    SCOPE     = "openid email profile"

    def __init__(self) -> None:
        self._client_id     = os.getenv("GOOGLE_CLIENT_ID",     "")
        self._client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        params = (
            f"client_id={self._client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&scope={self.SCOPE.replace(' ', '+')}"
            f"&state={state}"
            f"&access_type=offline"
        )
        return f"{self.AUTH_URL}?{params}"

    def exchange_code(self, code: str, redirect_uri: str) -> OAuthUserInfo:
        """
        In production this calls TOKEN_URL and then Google's userinfo endpoint.
        Here we raise NotImplementedError to mark the integration point.
        Wire in `requests` + `google-auth` in production.
        """
        raise NotImplementedError(
            "Connect to https://oauth2.googleapis.com/token to exchange the code."
        )


class JWTService:
    """
    Issues and validates JWT access tokens.
    Used as the auth layer after OAuth2 login succeeds.
    """

    def __init__(self, secret_key: str, expire_minutes: int = 60) -> None:
        self._secret         = secret_key
        self._expire_minutes = expire_minutes

    def create_token(self, user_id: str, email: str, role: str) -> str:
        payload = {
            "sub":   user_id,
            "email": email,
            "role":  role,
            "iat":   datetime.utcnow(),
            "exp":   datetime.utcnow() + timedelta(minutes=self._expire_minutes),
            "jti":   str(uuid4()),
        }
        return jwt.encode(payload, self._secret, algorithm="HS256")

    def verify_token(self, token: str) -> dict:
        try:
            return jwt.decode(token, self._secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired.")
        except jwt.InvalidTokenError as exc:
            raise ValueError(f"Invalid token: {exc}")


# ─────────────────────────────────────────────────────────────────────────── #
#  stripe_payment.py  –  Stripe integration                                   #
# ─────────────────────────────────────────────────────────────────────────── #

@dataclass
class StripeResult:
    success:         bool
    transaction_ref: Optional[str]
    error_message:   Optional[str]
    requires_action: bool = False   # e.g. 3D Secure
    client_secret:   Optional[str] = None


class StripePaymentService:
    """
    Stripe payment gateway integration.
    Handles: charge, refund, offline approval, and negative scenarios.

    ISE requirement: Sandbox/dev account + failed payment handling.
    """

    def __init__(self) -> None:
        self._api_key = os.getenv("STRIPE_API_KEY", "sk_test_placeholder")
        self._configured = bool(self._api_key and
                                not self._api_key.endswith("placeholder"))

    # ── Online payment ─────────────────────────────────────────────────── #

    def create_payment_intent(
        self,
        amount_cents: int,
        currency:     str = "pln",
        booking_id:   str = "",
    ) -> StripeResult:
        """
        Create a Stripe PaymentIntent.
        Returns client_secret for the frontend to complete 3DS if needed.
        """
        if not self._configured:
            # Sandbox simulation when no real key is set
            return self._simulate_intent(amount_cents, booking_id)
        try:
            import stripe
            stripe.api_key = self._api_key
            intent = stripe.PaymentIntent.create(
                amount   = amount_cents,
                currency = currency,
                metadata = {"booking_id": booking_id},
            )
            return StripeResult(
                success         = True,
                transaction_ref = intent.id,
                error_message   = None,
                requires_action = intent.status == "requires_action",
                client_secret   = intent.client_secret,
            )
        except Exception as exc:
            return StripeResult(success=False, transaction_ref=None,
                                error_message=str(exc))

    def confirm_payment(self, payment_intent_id: str) -> StripeResult:
        """Confirm a PaymentIntent after 3DS completion."""
        if not self._configured:
            return StripeResult(success=True,
                                transaction_ref=payment_intent_id,
                                error_message=None)
        try:
            import stripe
            stripe.api_key = self._api_key
            intent = stripe.PaymentIntent.confirm(payment_intent_id)
            succeeded = intent.status == "succeeded"
            return StripeResult(
                success         = succeeded,
                transaction_ref = intent.id,
                error_message   = None if succeeded else f"Status: {intent.status}",
            )
        except Exception as exc:
            return StripeResult(success=False, transaction_ref=None,
                                error_message=str(exc))

    def refund(self, transaction_ref: str, amount_cents: Optional[int] = None) -> StripeResult:
        """Full or partial refund of a completed charge."""
        if not self._configured:
            return StripeResult(success=True, transaction_ref=f"re_{uuid4().hex[:16]}",
                                error_message=None)
        try:
            import stripe
            stripe.api_key = self._api_key
            kwargs = {"payment_intent": transaction_ref}
            if amount_cents:
                kwargs["amount"] = amount_cents
            refund = stripe.Refund.create(**kwargs)
            return StripeResult(success=refund.status == "succeeded",
                                transaction_ref=refund.id, error_message=None)
        except Exception as exc:
            return StripeResult(success=False, transaction_ref=None,
                                error_message=str(exc))

    # ── Offline payment (ISE: admin approval) ──────────────────────────── #

    def create_offline_payment_request(
        self,
        booking_id:  str,
        amount:      float,
        customer_id: str,
    ) -> dict:
        """
        Generate an offline payment record for admin approval.
        Admin approves via a separate endpoint (no Stripe involved).
        """
        return {
            "offline_ref":   f"OFFLINE-{uuid4().hex[:8].upper()}",
            "booking_id":    booking_id,
            "customer_id":   customer_id,
            "amount":        amount,
            "status":        "awaiting_admin_approval",
            "created_at":    datetime.utcnow().isoformat(),
            "approved_by":   None,
            "approved_at":   None,
        }

    def approve_offline_payment(
        self, offline_ref: str, admin_id: str
    ) -> dict:
        """Admin marks an offline payment as approved."""
        return {
            "offline_ref": offline_ref,
            "status":      "approved",
            "approved_by": admin_id,
            "approved_at": datetime.utcnow().isoformat(),
        }

    # ── Simulation helpers (no real Stripe key) ────────────────────────── #

    @staticmethod
    def _simulate_intent(amount_cents: int, booking_id: str) -> StripeResult:
        """Return a fake successful intent for sandbox / CI testing."""
        return StripeResult(
            success         = True,
            transaction_ref = f"pi_sim_{uuid4().hex[:16]}",
            error_message   = None,
            requires_action = False,
            client_secret   = f"pi_sim_secret_{uuid4().hex[:8]}",
        )

    @staticmethod
    def simulate_failed_payment(booking_id: str) -> StripeResult:
        """
        Explicitly simulate a card decline for testing failed-payment handling.
        ISE requirement: negative scenarios must be handled.
        """
        return StripeResult(
            success         = False,
            transaction_ref = None,
            error_message   = "Your card was declined. (simulated)",
        )


# ─────────────────────────────────────────────────────────────────────────── #
#  rabbitmq.py  –  Async message queue with RabbitMQ / aio-pika               #
# ─────────────────────────────────────────────────────────────────────────── #

@dataclass
class Message:
    """A message sent through the queue."""
    queue:      str
    event_type: str
    payload:    Dict[str, Any]
    message_id: str = ""
    timestamp:  str = ""

    def __post_init__(self):
        if not self.message_id:
            self.message_id = str(uuid4())
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def to_json(self) -> str:
        return json.dumps({
            "message_id": self.message_id,
            "event_type": self.event_type,
            "payload":    self.payload,
            "timestamp":  self.timestamp,
        })


class MessageHandler(ABC):
    """Abstract handler — implement to process incoming messages."""

    @abstractmethod
    def handle(self, message: Message) -> None: ...


class NotificationHandler(MessageHandler):
    """Handles booking notification messages."""

    def __init__(self):
        self.received: List[Message] = []

    def handle(self, message: Message) -> None:
        self.received.append(message)
        event = message.event_type
        payload = message.payload
        print(f"[NOTIFICATION] {event}: booking={payload.get('booking_id', 'n/a')}")


class PaymentStatusHandler(MessageHandler):
    """Handles async payment status update messages."""

    def __init__(self):
        self.received: List[Message] = []

    def handle(self, message: Message) -> None:
        self.received.append(message)
        print(f"[PAYMENT STATUS] {message.payload}")


class RabbitMQClient:
    """
    RabbitMQ client using the pika library.

    ISE requirement: asynchronous message queues for background processes
    (sending notifications, processing payment statuses).

    Uses a thread-safe in-memory fallback when RABBITMQ_URL is not set,
    so the rest of the system works without a running broker in dev/CI.
    """

    QUEUE_NOTIFICATIONS    = "sfbs.notifications"
    QUEUE_PAYMENT_STATUS   = "sfbs.payment_status"
    QUEUE_BOOKING_EVENTS   = "sfbs.booking_events"

    def __init__(self) -> None:
        self._url        = os.getenv("RABBITMQ_URL", "")
        self._handlers:  Dict[str, List[MessageHandler]] = {}
        self._in_memory: Dict[str, List[Message]] = {}   # fallback store
        self._lock       = threading.Lock()
        self._connected  = False
        self._connection = None
        self._channel    = None

    # ── Connection ─────────────────────────────────────────────────────── #

    def connect(self) -> bool:
        if not self._url:
            print("[RabbitMQ] No RABBITMQ_URL set — using in-memory fallback.")
            return False
        try:
            import pika
            params = pika.URLParameters(self._url)
            self._connection = pika.BlockingConnection(params)
            self._channel    = self._connection.channel()
            for queue in (self.QUEUE_NOTIFICATIONS,
                          self.QUEUE_PAYMENT_STATUS,
                          self.QUEUE_BOOKING_EVENTS):
                self._channel.queue_declare(queue=queue, durable=True)
            self._connected = True
            print("[RabbitMQ] Connected.")
            return True
        except Exception as exc:
            print(f"[RabbitMQ] Connection failed: {exc}. Using in-memory fallback.")
            return False

    def disconnect(self) -> None:
        if self._connection and self._connection.is_open:
            self._connection.close()
        self._connected = False

    # ── Publishing ─────────────────────────────────────────────────────── #

    def publish(self, message: Message) -> bool:
        if self._connected:
            try:
                import pika
                self._channel.basic_publish(
                    exchange    = "",
                    routing_key = message.queue,
                    body        = message.to_json().encode(),
                    properties  = pika.BasicProperties(
                        delivery_mode = 2,  # persistent
                        content_type  = "application/json",
                        message_id    = message.message_id,
                    ),
                )
                return True
            except Exception as exc:
                print(f"[RabbitMQ] Publish failed: {exc}")
                return False
        # In-memory fallback
        with self._lock:
            self._in_memory.setdefault(message.queue, []).append(message)
        self._dispatch_in_memory(message)
        return True

    # ── High-level helpers ─────────────────────────────────────────────── #

    def publish_booking_confirmed(self, booking_id: str, customer_email: str) -> None:
        self.publish(Message(
            queue      = self.QUEUE_NOTIFICATIONS,
            event_type = "booking.confirmed",
            payload    = {"booking_id": booking_id, "email": customer_email},
        ))

    def publish_booking_cancelled(self, booking_id: str, customer_email: str) -> None:
        self.publish(Message(
            queue      = self.QUEUE_NOTIFICATIONS,
            event_type = "booking.cancelled",
            payload    = {"booking_id": booking_id, "email": customer_email},
        ))

    def publish_payment_received(self, booking_id: str, amount: float,
                                  transaction_ref: str) -> None:
        self.publish(Message(
            queue      = self.QUEUE_PAYMENT_STATUS,
            event_type = "payment.received",
            payload    = {"booking_id":    booking_id,
                          "amount":        amount,
                          "txn_ref":       transaction_ref,
                          "status":        "completed"},
        ))

    def publish_payment_failed(self, booking_id: str, reason: str) -> None:
        """ISE: negative scenario — failed payment notification."""
        self.publish(Message(
            queue      = self.QUEUE_PAYMENT_STATUS,
            event_type = "payment.failed",
            payload    = {"booking_id": booking_id, "reason": reason},
        ))

    # ── Consuming ──────────────────────────────────────────────────────── #

    def subscribe(self, queue: str, handler: MessageHandler) -> None:
        self._handlers.setdefault(queue, []).append(handler)

    def start_consuming(self) -> None:
        """Start blocking consume loop (run in a dedicated thread)."""
        if not self._connected:
            return
        def callback(ch, method, props, body):
            data    = json.loads(body.decode())
            message = Message(
                queue      = method.routing_key,
                event_type = data["event_type"],
                payload    = data["payload"],
                message_id = data.get("message_id", ""),
                timestamp  = data.get("timestamp", ""),
            )
            for handler in self._handlers.get(message.queue, []):
                handler.handle(message)
            ch.basic_ack(delivery_tag=method.delivery_tag)

        for queue in self._handlers:
            self._channel.basic_consume(queue=queue, on_message_callback=callback)

        self._channel.start_consuming()

    def _dispatch_in_memory(self, message: Message) -> None:
        for handler in self._handlers.get(message.queue, []):
            handler.handle(message)

    # ── Inspection (testing / admin) ───────────────────────────────────── #

    def get_queued_messages(self, queue: str) -> List[Message]:
        with self._lock:
            return list(self._in_memory.get(queue, []))
