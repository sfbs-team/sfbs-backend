"""
Sprint 4 | server/
FastAPI REST API — satisfies both ISE (REST API pattern) and SE2 (client-server).
Includes OAuth2, Stripe webhook, offline approval, and booking CRUD.

Commit: Muhammad – Sprint 4  (app.py + auth router)
Commit: Mohab    – Sprint 4  (facilities + bookings routers)
Commit: Salma    – Sprint 4  (payments router + integration tests)
"""

# ═══════════════════════════════════════════════════════════════════════════ #
#  server/schemas.py  –  Pydantic request/response models                    #
# ═══════════════════════════════════════════════════════════════════════════ #

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    username:   str        = Field(..., min_length=3, max_length=64)
    email:      EmailStr
    password:   str        = Field(..., min_length=8)
    first_name: str        = Field(..., min_length=1, max_length=64)
    last_name:  str        = Field(..., min_length=1, max_length=64)
    phone:      Optional[str] = ""


class UserResponse(BaseModel):
    id:             str
    username:       str
    email:          str
    full_name:      str
    role:           str
    status:         str
    loyalty_points: int = 0
    created_at:     str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         UserResponse


class OAuthCallbackRequest(BaseModel):
    code:  str
    state: str


class FacilityCreate(BaseModel):
    name:            str   = Field(..., min_length=1, max_length=128)
    facility_type:   str
    environment:     str   = Field(..., pattern="^(indoor|outdoor)$")
    capacity:        int   = Field(..., gt=0)
    hourly_rate:     float = Field(..., ge=0)
    description:     str   = ""
    has_ac:          Optional[bool]  = None
    floor_area_sqm:  Optional[float] = None
    has_floodlights: Optional[bool]  = None
    surface_type:    Optional[str]   = None


class FacilityResponse(BaseModel):
    id:           str
    name:         str
    facility_type: str
    environment:  str
    capacity:     int
    hourly_rate:  float
    status:       str
    description:  str


class BookingCreate(BaseModel):
    facility_id: str
    start_time:  datetime
    end_time:    datetime
    notes:       str = ""

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v, info):
        if "start_time" in info.data and v <= info.data["start_time"]:
            raise ValueError("end_time must be after start_time")
        return v


class BookingResponse(BaseModel):
    id:           str
    customer_id:  str
    facility_id:  str
    total_amount: float
    status:       str
    notes:        str
    created_at:   str


class PaymentCreate(BaseModel):
    booking_id:     str
    payment_method: str = Field(..., pattern="^(card|cash|stripe|loyalty_points)$")


class PaymentResponse(BaseModel):
    id:              str
    booking_id:      str
    amount:          float
    payment_method:  str
    status:          str
    transaction_ref: Optional[str] = None
    client_secret:   Optional[str] = None


class OfflinePaymentRequest(BaseModel):
    booking_id: str
    amount:     float


class OfflineApprovalRequest(BaseModel):
    offline_ref: str


# ═══════════════════════════════════════════════════════════════════════════ #
#  server/app.py  –  FastAPI application factory                              #
# ═══════════════════════════════════════════════════════════════════════════ #

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from database.connection import DatabaseConnection
from database.config import DatabaseConfig
from integrations.integrations import JWTService, RabbitMQClient


# ── Shared singletons ──────────────────────────────────────────────────── #

_db      = DatabaseConnection()
_jwt     = JWTService(secret_key=os.getenv("SECRET_KEY", "dev-secret"), expire_minutes=60)
_mq      = RabbitMQClient()
_bearer  = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    _db.initialise(DatabaseConfig.from_env())
    _db.create_tables()
    _mq.connect()
    yield
    _mq.disconnect()


def create_app() -> FastAPI:
    app = FastAPI(
        title       = "Sport Facility Booking System",
        description = "REST API for SFBS — ISE + SE2 project",
        version     = "1.0.0",
        lifespan    = lifespan,
        docs_url    = "/docs",      # Swagger UI (ISE requirement)
        redoc_url   = "/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins     = ["*"],
        allow_credentials = True,
        allow_methods     = ["*"],
        allow_headers     = ["*"],
    )

    # Routers registered in separate sections below
    _register_auth_router(app)
    _register_facility_router(app)
    _register_booking_router(app)
    _register_payment_router(app)

    return app


# ── Dependency: current user from JWT ─────────────────────────────────── #

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Not authenticated")
    try:
        return _jwt.verify_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=str(exc))


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Admin access required")
    return user


# ═══════════════════════════════════════════════════════════════════════════ #
#  AUTH ROUTER  –  /auth                                                      #
# ═══════════════════════════════════════════════════════════════════════════ #

import hashlib as _hl
from fastapi import APIRouter as _Router
from database.connection import UserRepository
from database.orm_models import UserORM
from integrations.integrations import GoogleOAuth2Provider


def _register_auth_router(app: FastAPI) -> None:
    router = _Router(prefix="/auth", tags=["Authentication"])

    @router.post("/register", response_model=UserResponse, status_code=201)
    def register(body: UserCreate):
        repo = UserRepository(_db)
        if repo.get_by_username(body.username):
            raise HTTPException(400, "Username already taken")
        if repo.get_by_email(body.email):
            raise HTTPException(400, "Email already registered")
        user = UserORM(
            id            = str(__import__("uuid").uuid4()),
            username      = body.username,
            email         = body.email,
            password_hash = _hl.sha256(body.password.encode()).hexdigest(),
            first_name    = body.first_name,
            last_name     = body.last_name,
            phone         = body.phone or "",
            role          = "customer",
            status        = "active",
            loyalty_points= 0,
        )
        repo.save(user)
        return _orm_user_to_response(user)

    @router.post("/login", response_model=TokenResponse)
    def login(body: LoginRequest):
        repo = UserRepository(_db)
        user = repo.get_by_username(body.username)
        pw   = _hl.sha256(body.password.encode()).hexdigest()
        if not user or user.password_hash != pw:
            raise HTTPException(401, "Invalid credentials")
        if user.status != "active":
            raise HTTPException(403, "Account is not active")
        token = _jwt.create_token(user.id, user.email, user.role)
        return TokenResponse(access_token=token, user=_orm_user_to_response(user))

    @router.get("/google/login")
    def google_login(redirect_uri: str = "http://localhost:8000/auth/google/callback"):
        import secrets
        state    = secrets.token_urlsafe(16)
        provider = GoogleOAuth2Provider()
        url      = provider.get_authorization_url(redirect_uri, state)
        return {"authorization_url": url, "state": state}

    @router.get("/google/callback")
    def google_callback(code: str, state: str):
        # In production: exchange code, upsert user, return JWT
        return {"detail": "Google OAuth2 callback — connect GoogleOAuth2Provider.exchange_code()"}

    @router.get("/me", response_model=UserResponse)
    def me(current_user: dict = Depends(get_current_user)):
        repo = UserRepository(_db)
        user = repo.get_by_id(current_user["sub"])
        if not user:
            raise HTTPException(404, "User not found")
        return _orm_user_to_response(user)

    app.include_router(router)


def _orm_user_to_response(u: UserORM) -> UserResponse:
    return UserResponse(
        id             = u.id,
        username       = u.username,
        email          = u.email,
        full_name      = f"{u.first_name} {u.last_name}",
        role           = u.role,
        status         = u.status,
        loyalty_points = u.loyalty_points or 0,
        created_at     = u.created_at.isoformat() if u.created_at else "",
    )


# ═══════════════════════════════════════════════════════════════════════════ #
#  FACILITY ROUTER  –  /facilities                                             #
# ═══════════════════════════════════════════════════════════════════════════ #

def _register_facility_router(app: FastAPI) -> None:
    router = _Router(prefix="/facilities", tags=["Facilities"])
    from database.connection import FacilityRepository
    from database.orm_models import FacilityORM
    import uuid as _uuid

    @router.get("", response_model=List[FacilityResponse])
    def list_facilities(available_only: bool = False):
        repo = FacilityRepository(_db)
        rows = repo.get_available() if available_only else repo.get_all()
        return [_orm_facility_to_response(r) for r in rows]

    @router.get("/{facility_id}", response_model=FacilityResponse)
    def get_facility(facility_id: str):
        repo = FacilityRepository(_db)
        row  = repo.get_by_id(facility_id)
        if not row:
            raise HTTPException(404, "Facility not found")
        return _orm_facility_to_response(row)

    @router.post("", response_model=FacilityResponse, status_code=201)
    def create_facility(body: FacilityCreate, _=Depends(require_admin)):
        repo = FacilityRepository(_db)
        row  = FacilityORM(
            id            = str(_uuid.uuid4()),
            name          = body.name,
            facility_type = body.facility_type,
            environment   = body.environment,
            capacity      = body.capacity,
            hourly_rate   = body.hourly_rate,
            description   = body.description,
            status        = "available",
            has_ac            = body.has_ac,
            floor_area_sqm    = body.floor_area_sqm,
            has_floodlights   = body.has_floodlights,
            surface_type      = body.surface_type,
        )
        repo.save(row)
        return _orm_facility_to_response(row)

    @router.put("/{facility_id}/status")
    def update_status(facility_id: str, new_status: str, _=Depends(require_admin)):
        repo = FacilityRepository(_db)
        row  = repo.get_by_id(facility_id)
        if not row:
            raise HTTPException(404, "Facility not found")
        row.status = new_status
        repo.save(row)
        return {"id": facility_id, "status": new_status}

    @router.delete("/{facility_id}", status_code=204)
    def delete_facility(facility_id: str, _=Depends(require_admin)):
        repo = FacilityRepository(_db)
        if not repo.delete(facility_id):
            raise HTTPException(404, "Facility not found")

    app.include_router(router)


def _orm_facility_to_response(r) -> FacilityResponse:
    return FacilityResponse(
        id            = r.id,
        name          = r.name,
        facility_type = r.facility_type,
        environment   = r.environment or "indoor",
        capacity      = r.capacity,
        hourly_rate   = r.hourly_rate,
        status        = r.status,
        description   = r.description or "",
    )


# ═══════════════════════════════════════════════════════════════════════════ #
#  BOOKING ROUTER  –  /bookings                                                #
# ═══════════════════════════════════════════════════════════════════════════ #

def _register_booking_router(app: FastAPI) -> None:
    router = _Router(prefix="/bookings", tags=["Bookings"])
    from database.connection import FacilityRepository, BookingRepository
    from database.orm_models import BookingORM, TimeSlotORM
    import uuid as _uuid

    @router.get("", response_model=List[BookingResponse])
    def list_bookings(current_user: dict = Depends(get_current_user)):
        repo = BookingRepository(_db)
        rows = repo.get_by_customer(current_user["sub"])
        return [_orm_booking_to_response(r) for r in rows]

    @router.get("/{booking_id}", response_model=BookingResponse)
    def get_booking(booking_id: str, current_user: dict = Depends(get_current_user)):
        repo = BookingRepository(_db)
        row  = repo.get_by_id(booking_id)
        if not row or row.customer_id != current_user["sub"]:
            raise HTTPException(404, "Booking not found")
        return _orm_booking_to_response(row)

    @router.post("", response_model=BookingResponse, status_code=201)
    def create_booking(body: BookingCreate, current_user: dict = Depends(get_current_user)):
        f_repo = FacilityRepository(_db)
        b_repo = BookingRepository(_db)
        facility = f_repo.get_by_id(body.facility_id)
        if not facility:
            raise HTTPException(404, "Facility not found")
        if facility.status != "available":
            raise HTTPException(409, "Facility is not available")
        duration_h   = (body.end_time - body.start_time).total_seconds() / 3600
        total_amount = round(facility.hourly_rate * duration_h, 2)
        slot_id      = str(_uuid.uuid4())
        booking_id   = str(_uuid.uuid4())
        slot = TimeSlotORM(
            id=slot_id, facility_id=body.facility_id,
            start_time=body.start_time, end_time=body.end_time, is_reserved=True,
        )
        booking = BookingORM(
            id=booking_id, customer_id=current_user["sub"],
            facility_id=body.facility_id, timeslot_id=slot_id,
            total_amount=total_amount, notes=body.notes, status="pending",
        )
        b_repo.save_timeslot_orm(slot)
        b_repo.save(booking)
        _mq.publish_booking_confirmed(booking_id, current_user["email"])
        return _orm_booking_to_response(booking)

    @router.post("/{booking_id}/confirm")
    def confirm_booking(booking_id: str, _=Depends(require_admin)):
        repo = BookingRepository(_db)
        row  = repo.get_by_id(booking_id)
        if not row: raise HTTPException(404, "Booking not found")
        row.status = "confirmed"
        repo.save(row)
        return {"id": booking_id, "status": "confirmed"}

    @router.post("/{booking_id}/cancel")
    def cancel_booking(booking_id: str, current_user: dict = Depends(get_current_user)):
        repo = BookingRepository(_db)
        row  = repo.get_by_id(booking_id)
        if not row or row.customer_id != current_user["sub"]:
            raise HTTPException(404, "Booking not found")
        if row.status in ("completed", "cancelled"):
            raise HTTPException(409, f"Cannot cancel a {row.status} booking")
        row.status = "cancelled"
        repo.save(row)
        _mq.publish_booking_cancelled(booking_id, current_user["email"])
        return {"id": booking_id, "status": "cancelled"}

    app.include_router(router)


def _orm_booking_to_response(r) -> BookingResponse:
    return BookingResponse(
        id           = r.id,
        customer_id  = r.customer_id,
        facility_id  = r.facility_id,
        total_amount = r.total_amount,
        status       = r.status,
        notes        = r.notes or "",
        created_at   = r.created_at.isoformat() if r.created_at else "",
    )


# ═══════════════════════════════════════════════════════════════════════════ #
#  PAYMENT ROUTER  –  /payments                                               #
# ═══════════════════════════════════════════════════════════════════════════ #

def _register_payment_router(app: FastAPI) -> None:
    router = _Router(prefix="/payments", tags=["Payments"])
    from database.connection import BookingRepository
    from integrations.integrations import StripePaymentService
    import uuid as _uuid

    stripe_svc = StripePaymentService()

    @router.post("/stripe/create-intent", response_model=PaymentResponse)
    def create_stripe_intent(body: PaymentCreate,
                             current_user: dict = Depends(get_current_user)):
        repo    = BookingRepository(_db)
        booking = repo.get_by_id(body.booking_id)
        if not booking or booking.customer_id != current_user["sub"]:
            raise HTTPException(404, "Booking not found")
        amount_cents = int(booking.total_amount * 100)
        result = stripe_svc.create_payment_intent(amount_cents, "pln", booking.id)
        if not result.success:
            # ISE: handle negative scenario — failed payment
            _mq.publish_payment_failed(booking.id, result.error_message or "Unknown error")
            raise HTTPException(402, f"Payment failed: {result.error_message}")
        _mq.publish_payment_received(booking.id, booking.total_amount,
                                      result.transaction_ref)
        return PaymentResponse(
            id=str(_uuid.uuid4()), booking_id=booking.id,
            amount=booking.total_amount, payment_method="stripe",
            status="pending", transaction_ref=result.transaction_ref,
            client_secret=result.client_secret,
        )

    @router.post("/offline/request", response_model=dict)
    def request_offline_payment(body: OfflinePaymentRequest,
                                current_user: dict = Depends(get_current_user)):
        """ISE requirement: offline payment option for administrators."""
        result = stripe_svc.create_offline_payment_request(
            booking_id  = body.booking_id,
            amount      = body.amount,
            customer_id = current_user["sub"],
        )
        return result

    @router.post("/offline/approve", response_model=dict)
    def approve_offline_payment(body: OfflineApprovalRequest,
                                admin: dict = Depends(require_admin)):
        """Admin approves a pending offline payment."""
        result = stripe_svc.approve_offline_payment(body.offline_ref, admin["sub"])
        return result

    app.include_router(router)


# ── App instance ──────────────────────────────────────────────────────── #

app = create_app()
