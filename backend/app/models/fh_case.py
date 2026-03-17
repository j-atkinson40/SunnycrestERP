import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)

from app.database import Base


class FHCase(Base):
    """Central funeral home case record — tracks a decedent from first call through closing."""

    __tablename__ = "fh_cases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)

    # Case info
    case_number = Column(String(30), nullable=False)
    status = Column(String(30), nullable=False, default="first_call")

    # Deceased info
    deceased_first_name = Column(String(100), nullable=False)
    deceased_middle_name = Column(String(100), nullable=True)
    deceased_last_name = Column(String(100), nullable=False)
    deceased_date_of_birth = Column(Date, nullable=True)
    deceased_date_of_death = Column(Date, nullable=False)
    deceased_place_of_death = Column(String(30), nullable=True)
    deceased_place_of_death_name = Column(String(200), nullable=True)
    deceased_place_of_death_city = Column(String(100), nullable=True)
    deceased_place_of_death_state = Column(String(2), nullable=True)
    deceased_gender = Column(String(20), nullable=True)
    deceased_age_at_death = Column(Integer, nullable=True)
    deceased_ssn_last_four = Column(String(4), nullable=True)
    deceased_veteran = Column(Boolean, default=False)

    # Disposition
    disposition_type = Column(String(30), nullable=True)
    disposition_date = Column(Date, nullable=True)
    disposition_location = Column(String(200), nullable=True)
    disposition_city = Column(String(100), nullable=True)
    disposition_state = Column(String(2), nullable=True)

    # Service
    service_type = Column(String(40), nullable=True)
    service_date = Column(Date, nullable=True)
    service_time = Column(String(10), nullable=True)
    service_location = Column(String(200), nullable=True)

    # Visitation
    visitation_date = Column(Date, nullable=True)
    visitation_start_time = Column(String(10), nullable=True)
    visitation_end_time = Column(String(10), nullable=True)
    visitation_location = Column(String(200), nullable=True)

    # Relationships
    primary_contact_id = Column(String(36), ForeignKey("fh_case_contacts.id"), nullable=True)
    assigned_director_id = Column(String(36), ForeignKey("users.id"), nullable=True)

    # Other
    referred_by = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
