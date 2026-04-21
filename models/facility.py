"""
Sprint 1 | models/facility.py
Facility hierarchy: BaseEntity → Facility → IndoorFacility / OutdoorFacility
Commit: Mohab Commit 1
"""

from enum import Enum
from typing import List, Optional

from models.base_entity import BaseEntity


# ======================================================================= #
#  Enumerations                                                            #
# ======================================================================= #

class FacilityType(Enum):
    FOOTBALL_PITCH   = "football_pitch"
    BASKETBALL_COURT = "basketball_court"
    TENNIS_COURT     = "tennis_court"
    SWIMMING_POOL    = "swimming_pool"
    GYM              = "gym"
    BADMINTON_COURT  = "badminton_court"
    VOLLEYBALL_COURT = "volleyball_court"
    MULTIPURPOSE     = "multipurpose"


class FacilityStatus(Enum):
    AVAILABLE    = "available"
    BOOKED       = "booked"
    MAINTENANCE  = "maintenance"
    CLOSED       = "closed"


# ======================================================================= #
#  Base Facility                                                           #
# ======================================================================= #

class Facility(BaseEntity):
    """
    Core facility entity.
    Encapsulates name, capacity, hourly rate, and operational status.
    Subclasses add environment-specific attributes.
    """

    def __init__(
        self,
        name:          str,
        facility_type: FacilityType,
        capacity:      int,
        hourly_rate:   float,
        description:   str = "",
    ) -> None:
        super().__init__()
        if capacity <= 0:
            raise ValueError("Capacity must be a positive integer.")
        if hourly_rate < 0:
            raise ValueError("Hourly rate cannot be negative.")

        self._name:          str            = name
        self._facility_type: FacilityType   = facility_type
        self._capacity:      int            = capacity
        self._hourly_rate:   float          = hourly_rate
        self._description:   str            = description
        self._status:        FacilityStatus = FacilityStatus.AVAILABLE
        self._amenities:     List[str]      = []

    # ------------------------------------------------------------------ #
    #  Properties                                                          #
    # ------------------------------------------------------------------ #

    @property
    def name(self) -> str:
        return self._name

    @property
    def facility_type(self) -> FacilityType:
        return self._facility_type

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def hourly_rate(self) -> float:
        return self._hourly_rate

    @hourly_rate.setter
    def hourly_rate(self, value: float) -> None:
        if value < 0:
            raise ValueError("Hourly rate cannot be negative.")
        self._hourly_rate = value
        self.touch()

    @property
    def description(self) -> str:
        return self._description

    @property
    def status(self) -> FacilityStatus:
        return self._status

    @property
    def amenities(self) -> List[str]:
        return list(self._amenities)

    # ------------------------------------------------------------------ #
    #  Behaviour                                                           #
    # ------------------------------------------------------------------ #

    def is_available(self) -> bool:
        return self._status == FacilityStatus.AVAILABLE

    def mark_booked(self)      -> None: self._status = FacilityStatus.BOOKED;      self.touch()
    def mark_available(self)   -> None: self._status = FacilityStatus.AVAILABLE;   self.touch()
    def mark_maintenance(self) -> None: self._status = FacilityStatus.MAINTENANCE; self.touch()
    def mark_closed(self)      -> None: self._status = FacilityStatus.CLOSED;      self.touch()

    def add_amenity(self, amenity: str) -> None:
        if amenity not in self._amenities:
            self._amenities.append(amenity)
            self.touch()

    def remove_amenity(self, amenity: str) -> None:
        if amenity in self._amenities:
            self._amenities.remove(amenity)
            self.touch()

    def calculate_cost(self, hours: float) -> float:
        """Return total rental cost for a given number of hours."""
        if hours <= 0:
            raise ValueError("Hours must be positive.")
        return round(self._hourly_rate * hours, 2)

    # ------------------------------------------------------------------ #
    #  Validation & Serialisation                                          #
    # ------------------------------------------------------------------ #

    def validate(self) -> bool:
        return (
            bool(self._name.strip()) and
            self._capacity > 0       and
            self._hourly_rate >= 0
        )

    def to_dict(self) -> dict:
        return {
            "id":            self._id,
            "name":          self._name,
            "facility_type": self._facility_type.value,
            "capacity":      self._capacity,
            "hourly_rate":   self._hourly_rate,
            "description":   self._description,
            "status":        self._status.value,
            "amenities":     list(self._amenities),
            "created_at":    self._created_at.isoformat(),
        }


# ======================================================================= #
#  IndoorFacility                                                          #
# ======================================================================= #

class IndoorFacility(Facility):
    """
    An enclosed facility with climate-control attributes.
    Examples: gym, basketball court, badminton hall.
    """

    def __init__(
        self,
        name:              str,
        facility_type:     FacilityType,
        capacity:          int,
        hourly_rate:       float,
        description:       str   = "",
        has_ac:            bool  = False,
        floor_area_sqm:    float = 0.0,
    ) -> None:
        super().__init__(name, facility_type, capacity, hourly_rate, description)
        self._has_ac:         bool  = has_ac
        self._floor_area_sqm: float = floor_area_sqm

    @property
    def has_ac(self) -> bool:
        return self._has_ac

    @property
    def floor_area_sqm(self) -> float:
        return self._floor_area_sqm

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({
            "environment":     "indoor",
            "has_ac":          self._has_ac,
            "floor_area_sqm":  self._floor_area_sqm,
        })
        return d


# ======================================================================= #
#  OutdoorFacility                                                         #
# ======================================================================= #

class OutdoorFacility(Facility):
    """
    An open-air facility that may have a weather-dependent schedule.
    Examples: football pitch, tennis court, running track.
    """

    def __init__(
        self,
        name:           str,
        facility_type:  FacilityType,
        capacity:       int,
        hourly_rate:    float,
        description:    str  = "",
        has_floodlights: bool = False,
        surface_type:   str  = "grass",
    ) -> None:
        super().__init__(name, facility_type, capacity, hourly_rate, description)
        self._has_floodlights: bool = has_floodlights
        self._surface_type:    str  = surface_type

    @property
    def has_floodlights(self) -> bool:
        return self._has_floodlights

    @property
    def surface_type(self) -> str:
        return self._surface_type

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({
            "environment":     "outdoor",
            "has_floodlights": self._has_floodlights,
            "surface_type":    self._surface_type,
        })
        return d
