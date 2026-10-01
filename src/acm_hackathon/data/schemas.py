"""Domain models for clinic data — used by tools and tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class LeadStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    BOOKED = "booked"
    CONVERTED = "converted"
    LOST = "lost"


class CarePlanStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    DROPPED = "dropped"


@dataclass(frozen=True)
class Patient:
    patient_id: str
    name: str
    email: str
    join_date: date
    lifetime_value: float
    last_visit_date: date | None


@dataclass(frozen=True)
class Lead:
    lead_id: str
    name: str
    source: str
    status: LeadStatus
    created_date: date
    estimated_value: float


@dataclass(frozen=True)
class CarePlan:
    care_plan_id: str
    patient_id: str
    visits_prescribed: int
    visits_completed: int
    status: CarePlanStatus
    start_date: date


@dataclass(frozen=True)
class Appointment:
    appointment_id: str
    patient_id: str
    service_id: str
    appointment_date: date
    revenue: float
    attended: bool
