"""Pydantic schemas for the Safety Management module."""

from datetime import date, datetime, time
from pydantic import BaseModel, ConfigDict


# ---- Safety Programs ----

class SafetyProgramCreate(BaseModel):
    program_name: str
    osha_standard: str | None = None
    osha_standard_code: str | None = None
    description: str | None = None
    content: str | None = None
    status: str = "draft"
    applicable_job_roles: list[str] | None = None  # stored as JSON

class SafetyProgramUpdate(BaseModel):
    program_name: str | None = None
    osha_standard: str | None = None
    osha_standard_code: str | None = None
    description: str | None = None
    content: str | None = None
    status: str | None = None
    applicable_job_roles: list[str] | None = None

class SafetyProgramResponse(BaseModel):
    id: str
    company_id: str
    program_name: str
    osha_standard: str | None = None
    osha_standard_code: str | None = None
    description: str | None = None
    content: str | None = None
    version: int
    status: str
    last_reviewed_at: datetime | None = None
    next_review_due_at: datetime | None = None
    reviewed_by: str | None = None
    applicable_job_roles: list[str] | None = None  # parsed from JSON
    created_at: datetime
    updated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


# ---- Training Requirements ----

class TrainingRequirementCreate(BaseModel):
    training_topic: str
    osha_standard_code: str | None = None
    applicable_roles: list[str] | None = None
    initial_training_required: bool = True
    refresher_frequency_months: int | None = None
    new_hire_deadline_days: int | None = None

class TrainingRequirementResponse(BaseModel):
    id: str
    company_id: str
    training_topic: str
    osha_standard_code: str | None = None
    applicable_roles: list[str] | None = None
    initial_training_required: bool
    refresher_frequency_months: int | None = None
    new_hire_deadline_days: int | None = None
    created_at: datetime
    updated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


# ---- Training Events ----

class TrainingEventCreate(BaseModel):
    training_topic: str
    osha_standard_code: str | None = None
    training_type: str  # initial/annual_refresher/new_hire/incident_triggered/toolbox_talk
    trainer_name: str
    trainer_type: str  # internal/external_consultant/online_course
    training_date: date
    duration_minutes: int
    content_summary: str | None = None
    training_materials_url: str | None = None

class TrainingEventResponse(BaseModel):
    id: str
    company_id: str
    training_topic: str
    osha_standard_code: str | None = None
    training_type: str
    trainer_name: str
    trainer_type: str
    training_date: date
    duration_minutes: int
    content_summary: str | None = None
    training_materials_url: str | None = None
    created_by: str | None = None
    created_at: datetime
    attendee_count: int | None = None  # computed
    model_config = ConfigDict(from_attributes=True)


# ---- Employee Training Records ----

class TrainingRecordCreate(BaseModel):
    employee_id: str
    training_event_id: str
    completion_status: str = "attended"
    test_score: float | None = None
    expiry_date: date | None = None
    certificate_url: str | None = None
    notes: str | None = None

class TrainingRecordBulkCreate(BaseModel):
    """Record attendance for multiple employees at once."""
    training_event_id: str
    employee_ids: list[str]
    completion_status: str = "attended"

class TrainingRecordResponse(BaseModel):
    id: str
    company_id: str
    employee_id: str
    training_event_id: str
    completion_status: str
    test_score: float | None = None
    expiry_date: date | None = None
    certificate_url: str | None = None
    notes: str | None = None
    created_at: datetime
    # Joined fields
    employee_name: str | None = None
    training_topic: str | None = None
    model_config = ConfigDict(from_attributes=True)


# ---- Training Gaps ----

class TrainingGap(BaseModel):
    employee_id: str
    employee_name: str
    job_role: str | None = None
    required_training: str
    osha_standard_code: str | None = None
    status: str  # missing / expired / expiring_soon
    expiry_date: date | None = None
    days_overdue: int | None = None


# ---- Inspection Templates ----

class InspectionItemCreate(BaseModel):
    item_order: int
    item_text: str
    response_type: str = "pass_fail"
    required: bool = False
    failure_action: str | None = None
    osha_reference: str | None = None

class InspectionTemplateCreate(BaseModel):
    template_name: str
    inspection_type: str
    equipment_type: str | None = None
    frequency_days: int | None = None
    description: str | None = None
    items: list[InspectionItemCreate] | None = None

class InspectionTemplateUpdate(BaseModel):
    template_name: str | None = None
    inspection_type: str | None = None
    equipment_type: str | None = None
    frequency_days: int | None = None
    description: str | None = None
    active: bool | None = None

class InspectionItemResponse(BaseModel):
    id: str
    template_id: str
    item_order: int
    item_text: str
    response_type: str
    required: bool
    failure_action: str | None = None
    osha_reference: str | None = None
    model_config = ConfigDict(from_attributes=True)

class InspectionTemplateResponse(BaseModel):
    id: str
    company_id: str
    template_name: str
    inspection_type: str
    equipment_type: str | None = None
    frequency_days: int | None = None
    description: str | None = None
    active: bool
    items: list[InspectionItemResponse] = []
    created_at: datetime
    updated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


# ---- Inspections ----

class InspectionCreate(BaseModel):
    template_id: str
    equipment_id: str | None = None
    equipment_identifier: str | None = None
    inspection_date: date
    notes: str | None = None

class InspectionResultUpdate(BaseModel):
    result: str | None = None
    finding_notes: str | None = None
    corrective_action_required: bool = False
    corrective_action_description: str | None = None
    corrective_action_due_date: date | None = None
    photo_urls: list[str] | None = None

class InspectionResultResponse(BaseModel):
    id: str
    inspection_id: str
    item_id: str
    result: str | None = None
    finding_notes: str | None = None
    corrective_action_required: bool
    corrective_action_description: str | None = None
    corrective_action_due_date: date | None = None
    corrective_action_completed_at: datetime | None = None
    corrective_action_completed_by: str | None = None
    photo_urls: list[str] | None = None
    created_at: datetime
    # Joined
    item_text: str | None = None
    item_order: int | None = None
    response_type: str | None = None
    required: bool | None = None
    model_config = ConfigDict(from_attributes=True)

class InspectionResponse(BaseModel):
    id: str
    company_id: str
    template_id: str
    template_name: str | None = None
    equipment_id: str | None = None
    equipment_identifier: str | None = None
    inspector_id: str
    inspector_name: str | None = None
    inspection_date: date
    status: str
    overall_result: str | None = None
    notes: str | None = None
    results: list[InspectionResultResponse] = []
    created_at: datetime
    completed_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)

class OverdueInspection(BaseModel):
    template_id: str
    template_name: str
    equipment_type: str | None = None
    frequency_days: int
    last_inspection_date: date | None = None
    days_overdue: int


# ---- Chemicals / SDS ----

class ChemicalCreate(BaseModel):
    chemical_name: str
    manufacturer: str | None = None
    product_number: str | None = None
    cas_number: str | None = None
    location: str | None = None
    quantity_on_hand: float | None = None
    unit_of_measure: str | None = None
    hazard_class: list[str] | None = None
    ppe_required: list[str] | None = None
    sds_url: str | None = None
    sds_date: date | None = None

class ChemicalUpdate(BaseModel):
    chemical_name: str | None = None
    manufacturer: str | None = None
    product_number: str | None = None
    cas_number: str | None = None
    location: str | None = None
    quantity_on_hand: float | None = None
    unit_of_measure: str | None = None
    hazard_class: list[str] | None = None
    ppe_required: list[str] | None = None
    sds_url: str | None = None
    sds_date: date | None = None
    active: bool | None = None

class ChemicalResponse(BaseModel):
    id: str
    company_id: str
    chemical_name: str
    manufacturer: str | None = None
    product_number: str | None = None
    cas_number: str | None = None
    location: str | None = None
    quantity_on_hand: float | None = None
    unit_of_measure: str | None = None
    hazard_class: list[str] | None = None
    ppe_required: list[str] | None = None
    sds_url: str | None = None
    sds_date: date | None = None
    sds_review_due_at: date | None = None
    active: bool
    created_at: datetime
    updated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


# ---- Incidents ----

class IncidentCreate(BaseModel):
    incident_type: str
    incident_date: date
    incident_time: time | None = None
    location: str
    involved_employee_id: str | None = None
    witnesses: str | None = None
    description: str
    immediate_cause: str | None = None
    body_part_affected: str | None = None
    injury_type: str | None = None
    medical_treatment: str = "none"

class IncidentUpdate(BaseModel):
    incident_type: str | None = None
    location: str | None = None
    involved_employee_id: str | None = None
    witnesses: str | None = None
    description: str | None = None
    immediate_cause: str | None = None
    root_cause: str | None = None
    body_part_affected: str | None = None
    injury_type: str | None = None
    medical_treatment: str | None = None
    days_away_from_work: int | None = None
    days_on_restricted_duty: int | None = None
    investigated_by: str | None = None
    corrective_actions: str | None = None

class IncidentResponse(BaseModel):
    id: str
    company_id: str
    incident_type: str
    incident_date: date
    incident_time: time | None = None
    location: str
    involved_employee_id: str | None = None
    involved_employee_name: str | None = None
    witnesses: str | None = None
    description: str
    immediate_cause: str | None = None
    root_cause: str | None = None
    body_part_affected: str | None = None
    injury_type: str | None = None
    medical_treatment: str
    days_away_from_work: int
    days_on_restricted_duty: int
    osha_recordable: bool
    osha_300_case_number: int | None = None
    reported_by: str | None = None
    investigated_by: str | None = None
    corrective_actions: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


# ---- OSHA 300 Log ----

class OSHA300Entry(BaseModel):
    case_number: int
    employee_name: str
    job_title: str | None = None
    incident_date: date
    location: str
    description: str
    injury_type: str | None = None
    days_away_from_work: int
    days_on_restricted_duty: int
    medical_treatment: str
    incident_type: str

class OSHA300AEntry(BaseModel):
    year: int
    total_cases: int
    total_deaths: int
    total_days_away: int
    total_days_restricted: int
    total_other_recordable: int
    injury_count: int
    skin_disorder_count: int
    respiratory_count: int
    poisoning_count: int
    hearing_loss_count: int
    other_illness_count: int


# ---- LOTO Procedures ----

class EnergySource(BaseModel):
    type: str  # electrical/hydraulic/pneumatic/gravitational/thermal/chemical
    location: str | None = None
    magnitude: str | None = None
    isolation_device: str | None = None
    isolation_location: str | None = None
    verification_method: str | None = None

class LOTOStep(BaseModel):
    step_number: int
    action: str
    photo_url: str | None = None

class LOTOCreate(BaseModel):
    machine_name: str
    machine_location: str | None = None
    machine_id: str | None = None
    procedure_number: str
    energy_sources: list[EnergySource]
    ppe_required: list[str] | None = None
    steps: list[LOTOStep]
    estimated_time_minutes: int | None = None
    authorized_employees: list[str] | None = None
    affected_employees: list[str] | None = None

class LOTOUpdate(BaseModel):
    machine_name: str | None = None
    machine_location: str | None = None
    machine_id: str | None = None
    procedure_number: str | None = None
    energy_sources: list[EnergySource] | None = None
    ppe_required: list[str] | None = None
    steps: list[LOTOStep] | None = None
    estimated_time_minutes: int | None = None
    authorized_employees: list[str] | None = None
    affected_employees: list[str] | None = None
    active: bool | None = None

class LOTOResponse(BaseModel):
    id: str
    company_id: str
    machine_name: str
    machine_location: str | None = None
    machine_id: str | None = None
    procedure_number: str
    energy_sources: list[EnergySource] = []
    ppe_required: list[str] | None = None
    steps: list[LOTOStep] = []
    estimated_time_minutes: int | None = None
    authorized_employees: list[str] | None = None
    affected_employees: list[str] | None = None
    last_reviewed_at: datetime | None = None
    next_review_due_at: datetime | None = None
    active: bool
    created_at: datetime
    updated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


# ---- Alerts ----

class AlertResponse(BaseModel):
    id: str
    company_id: str
    alert_type: str
    severity: str
    reference_id: str | None = None
    reference_type: str | None = None
    message: str
    due_date: date | None = None
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---- Compliance Score ----

class ComplianceCategory(BaseModel):
    category: str
    weight: float
    score: float
    max_score: float
    items_total: int
    items_compliant: int
    gaps: list[str] = []

class ComplianceScoreResponse(BaseModel):
    overall_score: float
    categories: list[ComplianceCategory]
    generated_at: datetime


# ---- Paginated ----

class PaginatedPrograms(BaseModel):
    items: list[SafetyProgramResponse]
    total: int

class PaginatedTrainingEvents(BaseModel):
    items: list[TrainingEventResponse]
    total: int

class PaginatedInspections(BaseModel):
    items: list[InspectionResponse]
    total: int

class PaginatedChemicals(BaseModel):
    items: list[ChemicalResponse]
    total: int

class PaginatedIncidents(BaseModel):
    items: list[IncidentResponse]
    total: int

class PaginatedAlerts(BaseModel):
    items: list[AlertResponse]
    total: int
