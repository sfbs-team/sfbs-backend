# Sprint 1 - Salma Essamiri: Full unit test suite

"""
Sprint 1 | tests/test_models.py
Unit tests for all domain model classes.
Covers: User / Customer / Admin, Facility hierarchy,
        TimeSlot, Booking state machine, Payment, Staff.

Sprint 1 Commits:
  Muhammad  → test_user.py section
  Mohab     → test_facility.py section
  Salma     → test_booking / timeslot / payment / staff sections
"""

import unittest
from datetime import datetime, timedelta

from models.user import User, Customer, Admin, UserRole, UserStatus
from models.facility import (
    Facility, IndoorFacility, OutdoorFacility,
    FacilityType, FacilityStatus,
)
from models.booking import (
    TimeSlot,
    Booking, BookingStatus,
    Payment, PaymentMethod, PaymentStatus,
    Staff, StaffRole,
)


# ─────────────────────────────── helpers ────────────────────────────────── #

def _customer(**kw) -> Customer:
    d = dict(username="jdoe", email="jdoe@example.com",
             password_hash="pw_hash", first_name="John", last_name="Doe")
    d.update(kw)
    return Customer(**d)

def _indoor(**kw) -> IndoorFacility:
    d = dict(name="Main Gym", facility_type=FacilityType.GYM,
             capacity=30, hourly_rate=50.0)
    d.update(kw)
    return IndoorFacility(**d)

def _slot(hours_from_now=1, duration=2) -> TimeSlot:
    start = datetime.utcnow() + timedelta(hours=hours_from_now)
    return TimeSlot(start_time=start,
                    end_time=start + timedelta(hours=duration),
                    facility_id="fac-001")

def _booking() -> Booking:
    return Booking(customer_id="cust-001", facility_id="fac-001",
                   timeslot=_slot(), total_amount=100.0)


# ═══════════════════════════════════════════════════════════════════════════ #
#  USER TESTS  (Muhammad – Sprint 1)                                         #
# ═══════════════════════════════════════════════════════════════════════════ #

class TestUser(unittest.TestCase):

    def test_default_role_and_status(self):
        c = _customer()
        self.assertEqual(c.role, UserRole.CUSTOMER)
        self.assertEqual(c.status, UserStatus.ACTIVE)
        self.assertTrue(c.is_active())

    def test_full_name_concatenation(self):
        c = _customer(first_name="Alice", last_name="Smith")
        self.assertEqual(c.full_name, "Alice Smith")

    def test_validate_returns_true_for_valid(self):
        self.assertTrue(_customer().validate())

    def test_validate_fails_blank_username(self):
        c = _customer(); c._username = "   "
        self.assertFalse(c.validate())

    def test_email_setter_rejects_bad_format(self):
        c = _customer()
        with self.assertRaises(ValueError):
            c.email = "not-valid"

    def test_email_setter_accepts_good_format(self):
        c = _customer()
        c.email = "new@domain.com"
        self.assertEqual(c.email, "new@domain.com")

    def test_status_transitions_full_cycle(self):
        c = _customer()
        c.deactivate(); self.assertEqual(c.status, UserStatus.INACTIVE)
        c.ban();        self.assertEqual(c.status, UserStatus.BANNED)
        c.activate();   self.assertTrue(c.is_active())

    def test_to_dict_contains_required_keys(self):
        d = _customer().to_dict()
        for k in ("id", "username", "email", "role", "status", "full_name"):
            self.assertIn(k, d)

    def test_equality_same_object(self):
        c = _customer(); self.assertEqual(c, c)

    def test_inequality_different_instances(self):
        self.assertNotEqual(_customer(), _customer())

    def test_hashable_in_set(self):
        c = _customer()
        self.assertIn(c, {c})

    def test_check_password(self):
        c = _customer(password_hash="secret")
        self.assertTrue(c.check_password("secret"))
        self.assertFalse(c.check_password("wrong"))


class TestCustomer(unittest.TestCase):

    def test_earn_and_redeem_points(self):
        c = _customer()
        c.earn_points(200); c.redeem_points(50)
        self.assertEqual(c.loyalty_points, 150)

    def test_redeem_overdraft_raises(self):
        c = _customer(); c.earn_points(10)
        with self.assertRaises(ValueError):
            c.redeem_points(20)

    def test_earn_negative_raises(self):
        with self.assertRaises(ValueError):
            _customer().earn_points(-1)

    def test_booking_list_grows(self):
        c = _customer()
        c.add_booking("bk-1"); c.add_booking("bk-2")
        self.assertEqual(len(c.get_bookings()), 2)

    def test_to_dict_includes_phone_and_points(self):
        c = _customer(phone="+48123456789")
        d = c.to_dict()
        self.assertIn("phone", d)
        self.assertIn("loyalty_points", d)


class TestAdmin(unittest.TestCase):

    def _admin(self) -> Admin:
        return Admin(username="adm", email="adm@sfbs.com",
                     password_hash="hp", first_name="Ada", last_name="L",
                     department="Operations")

    def test_role_is_admin(self):
        self.assertEqual(self._admin().role, UserRole.ADMIN)

    def test_grant_and_revoke_permission(self):
        a = self._admin()
        a.grant_permission("manage_bookings")
        self.assertTrue(a.has_permission("manage_bookings"))
        a.revoke_permission("manage_bookings")
        self.assertFalse(a.has_permission("manage_bookings"))

    def test_revoke_nonexistent_no_error(self):
        a = self._admin()
        a.revoke_permission("ghost")  # should not raise

    def test_to_dict_includes_department(self):
        self.assertIn("department", self._admin().to_dict())


# ═══════════════════════════════════════════════════════════════════════════ #
#  FACILITY TESTS  (Mohab – Sprint 1)                                        #
# ═══════════════════════════════════════════════════════════════════════════ #

class TestFacility(unittest.TestCase):

    def test_default_status_available(self):
        self.assertEqual(_indoor().status, FacilityStatus.AVAILABLE)

    def test_zero_capacity_raises(self):
        with self.assertRaises(ValueError):
            IndoorFacility(name="X", facility_type=FacilityType.GYM,
                           capacity=0, hourly_rate=10.0)

    def test_negative_rate_raises(self):
        with self.assertRaises(ValueError):
            IndoorFacility(name="X", facility_type=FacilityType.GYM,
                           capacity=5, hourly_rate=-1.0)

    def test_status_lifecycle(self):
        f = _indoor()
        f.mark_booked();      self.assertEqual(f.status, FacilityStatus.BOOKED)
        f.mark_maintenance(); self.assertEqual(f.status, FacilityStatus.MAINTENANCE)
        f.mark_available();   self.assertTrue(f.is_available())
        f.mark_closed();      self.assertEqual(f.status, FacilityStatus.CLOSED)

    def test_calculate_cost(self):
        f = _indoor(hourly_rate=40.0)
        self.assertAlmostEqual(f.calculate_cost(2.5), 100.0)

    def test_calculate_cost_zero_hours_raises(self):
        with self.assertRaises(ValueError):
            _indoor().calculate_cost(0)

    def test_amenity_add_remove(self):
        f = _indoor()
        f.add_amenity("lockers"); f.add_amenity("showers")
        self.assertIn("lockers", f.amenities)
        f.remove_amenity("lockers")
        self.assertNotIn("lockers", f.amenities)

    def test_duplicate_amenity_not_added_twice(self):
        f = _indoor()
        f.add_amenity("wifi"); f.add_amenity("wifi")
        self.assertEqual(f.amenities.count("wifi"), 1)

    def test_validate(self):
        self.assertTrue(_indoor().validate())

    def test_to_dict_keys(self):
        d = _indoor().to_dict()
        for k in ("id", "name", "facility_type", "capacity", "hourly_rate", "status"):
            self.assertIn(k, d)

    def test_hourly_rate_setter(self):
        f = _indoor()
        f.hourly_rate = 99.0
        self.assertEqual(f.hourly_rate, 99.0)

    def test_hourly_rate_setter_negative_raises(self):
        with self.assertRaises(ValueError):
            _indoor().hourly_rate = -10.0


class TestIndoorFacility(unittest.TestCase):

    def test_environment_label(self):
        self.assertEqual(_indoor().to_dict()["environment"], "indoor")

    def test_ac_attribute(self):
        f = IndoorFacility(name="Court", facility_type=FacilityType.BASKETBALL_COURT,
                           capacity=20, hourly_rate=60.0, has_ac=True,
                           floor_area_sqm=400.0)
        self.assertTrue(f.has_ac)
        self.assertEqual(f.floor_area_sqm, 400.0)


class TestOutdoorFacility(unittest.TestCase):

    def test_environment_label(self):
        f = OutdoorFacility(name="Pitch", facility_type=FacilityType.FOOTBALL_PITCH,
                            capacity=22, hourly_rate=80.0, has_floodlights=True,
                            surface_type="artificial_turf")
        self.assertEqual(f.to_dict()["environment"], "outdoor")
        self.assertTrue(f.has_floodlights)
        self.assertEqual(f.surface_type, "artificial_turf")


# ═══════════════════════════════════════════════════════════════════════════ #
#  TIMESLOT / BOOKING / PAYMENT / STAFF TESTS  (Salma – Sprint 1)            #
# ═══════════════════════════════════════════════════════════════════════════ #

class TestTimeSlot(unittest.TestCase):

    def test_not_reserved_on_creation(self):
        self.assertFalse(_slot().is_reserved)

    def test_reserve(self):
        ts = _slot(); ts.reserve()
        self.assertTrue(ts.is_reserved)

    def test_double_reserve_raises(self):
        ts = _slot(); ts.reserve()
        with self.assertRaises(RuntimeError):
            ts.reserve()

    def test_release(self):
        ts = _slot(); ts.reserve(); ts.release()
        self.assertFalse(ts.is_reserved)

    def test_duration_hours(self):
        self.assertAlmostEqual(_slot(duration=3).duration_hours(), 3.0, places=1)

    def test_invalid_times_raises(self):
        now = datetime.utcnow()
        with self.assertRaises(ValueError):
            TimeSlot(start_time=now, end_time=now - timedelta(hours=1),
                     facility_id="f1")

    def test_overlaps_true(self):
        base = datetime.utcnow()
        a = TimeSlot(base,             base + timedelta(hours=2), "f1")
        b = TimeSlot(base + timedelta(hours=1), base + timedelta(hours=3), "f1")
        self.assertTrue(a.overlaps(b))

    def test_overlaps_false(self):
        base = datetime.utcnow()
        a = TimeSlot(base,             base + timedelta(hours=2), "f1")
        b = TimeSlot(base + timedelta(hours=3), base + timedelta(hours=5), "f1")
        self.assertFalse(a.overlaps(b))

    def test_to_dict_keys(self):
        d = _slot().to_dict()
        for k in ("id", "facility_id", "start_time", "end_time", "is_reserved"):
            self.assertIn(k, d)


class TestBooking(unittest.TestCase):

    def test_default_status_pending(self):
        self.assertEqual(_booking().status, BookingStatus.PENDING)

    def test_confirm(self):
        b = _booking(); b.confirm()
        self.assertEqual(b.status, BookingStatus.CONFIRMED)

    def test_confirm_from_wrong_state_raises(self):
        b = _booking(); b.confirm()
        with self.assertRaises(RuntimeError):
            b.confirm()

    def test_cancel_from_pending(self):
        b = _booking(); b.cancel()
        self.assertEqual(b.status, BookingStatus.CANCELLED)

    def test_cancel_completed_raises(self):
        b = _booking(); b.confirm(); b.complete()
        with self.assertRaises(RuntimeError):
            b.cancel()

    def test_complete(self):
        b = _booking(); b.confirm(); b.complete()
        self.assertEqual(b.status, BookingStatus.COMPLETED)

    def test_complete_without_confirm_raises(self):
        with self.assertRaises(RuntimeError):
            _booking().complete()

    def test_mark_no_show(self):
        b = _booking(); b.confirm(); b.mark_no_show()
        self.assertEqual(b.status, BookingStatus.NO_SHOW)

    def test_attach_payment(self):
        b = _booking(); b.attach_payment("pay-001")
        self.assertEqual(b.payment_id, "pay-001")

    def test_negative_amount_raises(self):
        with self.assertRaises(ValueError):
            Booking("c", "f", _slot(), total_amount=-1.0)

    def test_validate(self):
        self.assertTrue(_booking().validate())

    def test_to_dict_keys(self):
        d = _booking().to_dict()
        for k in ("id", "customer_id", "facility_id", "timeslot",
                  "total_amount", "status"):
            self.assertIn(k, d)


class TestPayment(unittest.TestCase):

    def _pay(self) -> Payment:
        return Payment(booking_id="bk-001", amount=100.0,
                       payment_method=PaymentMethod.CARD)

    def test_default_status_pending(self):
        self.assertEqual(self._pay().status, PaymentStatus.PENDING)

    def test_process(self):
        p = self._pay(); p.process("txn-abc")
        self.assertEqual(p.status, PaymentStatus.COMPLETED)
        self.assertEqual(p.transaction_ref, "txn-abc")

    def test_fail(self):
        p = self._pay(); p.fail()
        self.assertEqual(p.status, PaymentStatus.FAILED)

    def test_refund(self):
        p = self._pay(); p.process("txn"); p.refund()
        self.assertEqual(p.status, PaymentStatus.REFUNDED)

    def test_refund_non_completed_raises(self):
        with self.assertRaises(RuntimeError):
            self._pay().refund()

    def test_zero_amount_raises(self):
        with self.assertRaises(ValueError):
            Payment("bk", 0.0, PaymentMethod.CASH)

    def test_validate(self):
        self.assertTrue(self._pay().validate())

    def test_to_dict_keys(self):
        d = self._pay().to_dict()
        for k in ("id", "booking_id", "amount", "payment_method", "status"):
            self.assertIn(k, d)


class TestStaff(unittest.TestCase):

    def _staff(self) -> Staff:
        return Staff(first_name="Tom", last_name="Jones",
                     email="tom@sfbs.com", role=StaffRole.RECEPTIONIST,
                     salary=3000.0)

    def test_active_on_creation(self):
        self.assertTrue(self._staff().is_active)

    def test_terminate(self):
        s = self._staff(); s.terminate()
        self.assertFalse(s.is_active)

    def test_hire(self):
        s = self._staff(); s.terminate(); s.hire()
        self.assertTrue(s.is_active)

    def test_give_raise(self):
        s = self._staff(); s.give_raise(500.0)
        self.assertEqual(s.salary, 3500.0)

    def test_negative_raise_raises(self):
        with self.assertRaises(ValueError):
            self._staff().give_raise(-100.0)

    def test_negative_salary_raises(self):
        with self.assertRaises(ValueError):
            Staff("A", "B", "a@b.com", StaffRole.COACH, salary=-1.0)

    def test_assign_and_unassign_facility(self):
        s = self._staff()
        s.assign_facility("fac-1"); s.assign_facility("fac-2")
        self.assertIn("fac-1", s.get_assigned_facilities())
        s.unassign_facility("fac-1")
        self.assertNotIn("fac-1", s.get_assigned_facilities())

    def test_terminate_clears_facilities(self):
        s = self._staff()
        s.assign_facility("fac-1"); s.terminate()
        self.assertEqual(s.get_assigned_facilities(), [])

    def test_full_name(self):
        self.assertEqual(self._staff().full_name, "Tom Jones")

    def test_validate(self):
        self.assertTrue(self._staff().validate())

    def test_to_dict_keys(self):
        d = self._staff().to_dict()
        for k in ("id", "full_name", "email", "role", "salary", "is_active"):
            self.assertIn(k, d)


if __name__ == "__main__":
    unittest.main(verbosity=2)
