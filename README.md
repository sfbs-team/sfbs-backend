# Sport Facility Booking System (SFBS)
## Project README + Sprint Plan

**Team:** Muhammad · Mohab Tawfik · Salma Essamiri  
**Courses:** SE2 (OOP / Client-Server) + ISE (Information Systems Engineering)  
**Stack:** Python · FastAPI · PostgreSQL · RabbitMQ · Stripe · OAuth2 · React/TypeScript · Tkinter

---

## Quick Start

```bash
# 1. Clone and install dependencies
git clone https://github.com/sfbs-team/sfbs-backend
cd sfbs-backend
pip install -r requirements.txt

# 2. Copy environment config
cp .env.example .env    # fill in your credentials

# 3. Run tests
python main.py test

# 4. Start the API server
python main.py server   # → http://localhost:8000/docs

# 5. Launch the desktop GUI (SE2)
python main.py gui
```

---

## Sprint Plan

> 4 sprints · 3 members · 1 commit per member per sprint = **12 total commits**

### Sprint 1 — Foundation: Models & Unit Tests
**ISE week II–IV** | **SE2 target: Grade 3**

| Member | Commit | Files |
|--------|--------|-------|
| Muhammad | Core domain models | `models/base_entity.py`, `models/user.py` |
| Mohab | Facility + booking models | `models/facility.py`, `models/booking.py` |
| Salma | Full unit test suite | `tests/test_models.py`, `models/__init__.py` |

**Deliverables:**
- ✅ Abstract base entity with UUID, timestamps, validate(), to_dict()
- ✅ User hierarchy: User → Customer / Admin (OOP inheritance)
- ✅ Facility hierarchy: Facility → IndoorFacility / OutdoorFacility
- ✅ TimeSlot, Booking (state machine), Payment (lifecycle), Staff
- ✅ 56 unit tests — all passing
- ✅ ERD & Class diagram (draw.io / dbdiagram.io)

---

### Sprint 2 — Database Layer & GUI
**ISE week IV–VIII** | **SE2 target: Grade 4**

| Member | Commit | Files |
|--------|--------|-------|
| Muhammad | ORM + DB config | `database/orm_models.py`, `database/config.py` |
| Mohab | Singleton connection + repositories | `database/connection.py` (includes UserRepo, FacilityRepo, BookingRepo) |
| Salma | Desktop GUI | `gui/app.py` (LoginView, FacilityView, BookingView, Dashboard) |

**Deliverables:**
- ✅ SQLAlchemy ORM tables for all entities
- ✅ DatabaseConnection Singleton (thread-safe, SE2 design-pattern preview)
- ✅ Repository pattern: BaseRepository + 3 concrete repos
- ✅ Tkinter GUI: login → dashboard → facility browser → booking form
- ✅ CRUD endpoints functional with DB
- ✅ ISE: CRUD + database connectivity milestone

---

### Sprint 3 — Design Patterns, Integrations & API Core
**ISE week VIII–XII** | **SE2 target: Grade 5**

| Member | Commit | Files |
|--------|--------|-------|
| Muhammad | Factory pattern + OAuth2 | `patterns/patterns.py` (Factory), `integrations/integrations.py` (OAuth2, JWT) |
| Mohab | Observer pattern + Stripe | `patterns/patterns.py` (Observer), `integrations/integrations.py` (Stripe) |
| Salma | Strategy pattern + RabbitMQ + pattern tests | `patterns/patterns.py` (Strategy, Singleton), `integrations/integrations.py` (RabbitMQ), `tests/test_patterns.py` |

**Deliverables:**
- ✅ **Singleton** — AppConfig + DatabaseConnection
- ✅ **Factory** — FacilityFactory, BookingFactory
- ✅ **Observer** — BookingEventSystem + Email/SMS/Audit observers
- ✅ **Strategy** — PricingContext + Standard/Discounted/Loyalty/OffPeak
- ✅ 50 design-pattern unit tests — all passing
- ✅ Google OAuth2 integration (authorization URL + JWT token service)
- ✅ Stripe: PaymentIntent, confirm, refund, **failed payment handling**
- ✅ Offline payment request + admin approval (ISE requirement)
- ✅ RabbitMQ: booking.confirmed, booking.cancelled, payment.received, **payment.failed**

---

### Sprint 4 — Client-Server, Final Tests & Polish
**ISE week XII–XV** | **SE2 target: Grade 5 complete**

| Member | Commit | Files |
|--------|--------|-------|
| Muhammad | FastAPI server + Auth/Facility/Booking routers | `server/app.py` |
| Mohab | Multithreaded client | `client/sfbs_client.py` |
| Salma | Integration tests + CI config | `tests/test_integration.py`, `main.py`, `requirements.txt` |

**Deliverables:**
- ✅ FastAPI REST API with Swagger docs (`/docs`) — ISE requirement
- ✅ JWT-protected endpoints, OAuth2 Google login route
- ✅ Multithreaded HTTP client (WorkerThread pool) — SE2 client-server requirement
- ✅ Integration test suite: JWT, events, Stripe, RabbitMQ, pricing
- ✅ 106 total tests passing
- ✅ **ISE ≥ 50% business logic coverage** satisfied
- ✅ ISE technical documentation structure (see `/docs` endpoint + this file)

---

## Grade Mapping

### SE2
| Grade | Requirement | Status |
|-------|-------------|--------|
| 3 | Model classes + unit tests | ✅ Sprint 1 |
| 4 | GUI + database connection | ✅ Sprint 2 |
| **5** | Design patterns + pattern tests + client-server | ✅ Sprint 3–4 |

### ISE
| Week | Requirement | Status |
|------|-------------|--------|
| IV | ERD + UML + tech stack | ✅ Sprint 1 |
| VI | CRUD + DB connectivity | ✅ Sprint 2 |
| VIII | Core business logic | ✅ Sprint 2–3 |
| X | OAuth2 + Stripe | ✅ Sprint 3 |
| XII | RabbitMQ + automated tests | ✅ Sprint 3–4 |
| XIV–XV | Final review + docs | Sprint 4 polish |

---

## Architecture

```
┌──────────────────────────────────────┐
│          React Frontend (AFA)         │  ← TypeScript, REST calls
└─────────────────┬────────────────────┘
                  │ HTTP/JSON
┌─────────────────▼────────────────────┐
│         FastAPI REST API              │  ← Python, /docs Swagger
│  /auth  /facilities  /bookings        │
│  /payments (Stripe + Offline)         │
└───┬──────────┬───────────┬───────────┘
    │          │           │
┌───▼──┐ ┌────▼───┐ ┌─────▼──────┐
│ PostgreSQL │ RabbitMQ  │  Stripe    │
│  (ORM)  │ │ (queues)  │  (payments)│
└────────┘ └───────────┘ └───────────┘
                  │
┌─────────────────▼────────────────────┐
│        Tkinter Desktop GUI            │  ← SE2 client-server demo
│   SFBSClient (multithreaded)          │
└──────────────────────────────────────┘
```

---

## Design Patterns (SE2 Grade 5)

| Pattern | Class | Purpose |
|---------|-------|---------|
| **Singleton** | `DatabaseConnection`, `AppConfig` | Single DB engine + config instance |
| **Factory** | `FacilityFactory`, `BookingFactory` | Encapsulate complex object creation |
| **Observer** | `BookingEventSystem` + observers | Decouple event producers from consumers |
| **Strategy** | `PricingContext` + strategies | Swappable pricing algorithms at runtime |
| **Repository** | `BaseRepository` + 3 concrete repos | Isolate persistence from domain logic |

---

## ISE Requirements Checklist

- [x] REST API pattern (FastAPI + OpenAPI/Swagger)
- [x] No JS/TS on server side (pure Python backend)
- [x] OAuth2 social login (Google)
- [x] Stripe payment integration (sandbox)
- [x] Failed payment handling (`simulate_failed_payment`)
- [x] Offline payment admin approval
- [x] RabbitMQ async queues (notifications, payment status)
- [x] Unit tests (test_models.py — 56 tests)
- [x] Integration tests (test_integration.py — 50 tests)
- [x] ≥ 50% business logic coverage
- [x] Task board: GitHub Projects
- [x] Repository: GitHub (`sfbs-team/sfbs-backend`)
