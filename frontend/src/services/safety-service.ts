import apiClient from "@/lib/api-client";
import type {
  SafetyProgram,
  SafetyProgramCreate,
  SafetyProgramUpdate,
  TrainingRequirement,
  TrainingRequirementCreate,
  TrainingEvent,
  TrainingEventCreate,
  TrainingRecord,
  TrainingGap,
  InspectionTemplate,
  InspectionTemplateCreate,
  SafetyInspection,
  InspectionCreate,
  InspectionResultUpdate,
  OverdueInspection,
  SafetyChemical,
  ChemicalCreate,
  ChemicalUpdate,
  SafetyIncident,
  IncidentCreate,
  IncidentUpdate,
  OSHA300Entry,
  OSHA300ASummary,
  LOTOProcedure,
  LOTOCreate,
  LOTOUpdate,
  SafetyAlert,
  ComplianceScore,
  Paginated,
} from "@/types/safety";

const BASE = "/safety";

export const safetyService = {
  // ---------------------------------------------------------------------------
  // Programs
  // ---------------------------------------------------------------------------

  async listPrograms(status?: string): Promise<SafetyProgram[]> {
    const params = status ? { status } : {};
    const response = await apiClient.get<SafetyProgram[]>(
      `${BASE}/programs`,
      { params },
    );
    return response.data;
  },

  async getProgram(id: string): Promise<SafetyProgram> {
    const response = await apiClient.get<SafetyProgram>(
      `${BASE}/programs/${id}`,
    );
    return response.data;
  },

  async createProgram(payload: SafetyProgramCreate): Promise<SafetyProgram> {
    const response = await apiClient.post<SafetyProgram>(
      `${BASE}/programs`,
      payload,
    );
    return response.data;
  },

  async updateProgram(
    id: string,
    payload: SafetyProgramUpdate,
  ): Promise<SafetyProgram> {
    const response = await apiClient.put<SafetyProgram>(
      `${BASE}/programs/${id}`,
      payload,
    );
    return response.data;
  },

  async reviewProgram(id: string): Promise<SafetyProgram> {
    const response = await apiClient.post<SafetyProgram>(
      `${BASE}/programs/${id}/review`,
    );
    return response.data;
  },

  // ---------------------------------------------------------------------------
  // Training Requirements
  // ---------------------------------------------------------------------------

  async listTrainingRequirements(): Promise<TrainingRequirement[]> {
    const response = await apiClient.get<TrainingRequirement[]>(
      `${BASE}/training/requirements`,
    );
    return response.data;
  },

  async createTrainingRequirement(
    payload: TrainingRequirementCreate,
  ): Promise<TrainingRequirement> {
    const response = await apiClient.post<TrainingRequirement>(
      `${BASE}/training/requirements`,
      payload,
    );
    return response.data;
  },

  // ---------------------------------------------------------------------------
  // Training Events
  // ---------------------------------------------------------------------------

  async listTrainingEvents(params?: {
    training_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<Paginated<TrainingEvent>> {
    const response = await apiClient.get<Paginated<TrainingEvent>>(
      `${BASE}/training`,
      { params },
    );
    return response.data;
  },

  async createTrainingEvent(
    payload: TrainingEventCreate,
  ): Promise<TrainingEvent> {
    const response = await apiClient.post<TrainingEvent>(
      `${BASE}/training`,
      payload,
    );
    return response.data;
  },

  async recordAttendees(
    eventId: string,
    employeeIds: string[],
    completionStatus = "attended",
  ): Promise<TrainingRecord[]> {
    const response = await apiClient.post<TrainingRecord[]>(
      `${BASE}/training/${eventId}/attendees`,
      {
        training_event_id: eventId,
        employee_ids: employeeIds,
        completion_status: completionStatus,
      },
    );
    return response.data;
  },

  async getEmployeeTraining(employeeId: string): Promise<TrainingRecord[]> {
    const response = await apiClient.get<TrainingRecord[]>(
      `${BASE}/training/employee/${employeeId}`,
    );
    return response.data;
  },

  async getTrainingGaps(): Promise<TrainingGap[]> {
    const response = await apiClient.get<TrainingGap[]>(
      `${BASE}/training/gaps`,
    );
    return response.data;
  },

  // ---------------------------------------------------------------------------
  // Inspection Templates
  // ---------------------------------------------------------------------------

  async listInspectionTemplates(
    activeOnly = true,
  ): Promise<InspectionTemplate[]> {
    const response = await apiClient.get<InspectionTemplate[]>(
      `${BASE}/inspection-templates`,
      { params: { active_only: activeOnly } },
    );
    return response.data;
  },

  async createInspectionTemplate(
    payload: InspectionTemplateCreate,
  ): Promise<InspectionTemplate> {
    const response = await apiClient.post<InspectionTemplate>(
      `${BASE}/inspection-templates`,
      payload,
    );
    return response.data;
  },

  // ---------------------------------------------------------------------------
  // Inspections
  // ---------------------------------------------------------------------------

  async listInspections(params?: {
    status?: string;
    template_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<Paginated<SafetyInspection>> {
    const response = await apiClient.get<Paginated<SafetyInspection>>(
      `${BASE}/inspections`,
      { params },
    );
    return response.data;
  },

  async getInspection(id: string): Promise<SafetyInspection> {
    const response = await apiClient.get<SafetyInspection>(
      `${BASE}/inspections/${id}`,
    );
    return response.data;
  },

  async startInspection(payload: InspectionCreate): Promise<SafetyInspection> {
    const response = await apiClient.post<SafetyInspection>(
      `${BASE}/inspections`,
      payload,
    );
    return response.data;
  },

  async updateInspectionResult(
    inspectionId: string,
    itemId: string,
    payload: InspectionResultUpdate,
  ) {
    const response = await apiClient.patch(
      `${BASE}/inspections/${inspectionId}/items/${itemId}`,
      payload,
    );
    return response.data;
  },

  async completeInspection(id: string): Promise<SafetyInspection> {
    const response = await apiClient.post<SafetyInspection>(
      `${BASE}/inspections/${id}/complete`,
    );
    return response.data;
  },

  async getOverdueInspections(): Promise<OverdueInspection[]> {
    const response = await apiClient.get<OverdueInspection[]>(
      `${BASE}/inspections/overdue`,
    );
    return response.data;
  },

  async completeCorrectiveAction(inspectionId: string, resultId: string) {
    const response = await apiClient.post(
      `${BASE}/inspections/${inspectionId}/corrective-actions/${resultId}/complete`,
    );
    return response.data;
  },

  // ---------------------------------------------------------------------------
  // Chemicals / SDS
  // ---------------------------------------------------------------------------

  async listChemicals(params?: {
    active_only?: boolean;
    hazard_class?: string;
  }): Promise<SafetyChemical[]> {
    const response = await apiClient.get<SafetyChemical[]>(
      `${BASE}/chemicals`,
      { params },
    );
    return response.data;
  },

  async createChemical(payload: ChemicalCreate): Promise<SafetyChemical> {
    const response = await apiClient.post<SafetyChemical>(
      `${BASE}/chemicals`,
      payload,
    );
    return response.data;
  },

  async updateChemical(
    id: string,
    payload: ChemicalUpdate,
  ): Promise<SafetyChemical> {
    const response = await apiClient.put<SafetyChemical>(
      `${BASE}/chemicals/${id}`,
      payload,
    );
    return response.data;
  },

  async getOutdatedSDS(): Promise<SafetyChemical[]> {
    const response = await apiClient.get<SafetyChemical[]>(
      `${BASE}/chemicals/outdated`,
    );
    return response.data;
  },

  // ---------------------------------------------------------------------------
  // Incidents
  // ---------------------------------------------------------------------------

  async listIncidents(params?: {
    incident_type?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<Paginated<SafetyIncident>> {
    const response = await apiClient.get<Paginated<SafetyIncident>>(
      `${BASE}/incidents`,
      { params },
    );
    return response.data;
  },

  async getIncident(id: string): Promise<SafetyIncident> {
    const response = await apiClient.get<SafetyIncident>(
      `${BASE}/incidents/${id}`,
    );
    return response.data;
  },

  async createIncident(payload: IncidentCreate): Promise<SafetyIncident> {
    const response = await apiClient.post<SafetyIncident>(
      `${BASE}/incidents`,
      payload,
    );
    return response.data;
  },

  async updateIncident(
    id: string,
    payload: IncidentUpdate,
  ): Promise<SafetyIncident> {
    const response = await apiClient.patch<SafetyIncident>(
      `${BASE}/incidents/${id}`,
      payload,
    );
    return response.data;
  },

  async closeIncident(id: string): Promise<SafetyIncident> {
    const response = await apiClient.post<SafetyIncident>(
      `${BASE}/incidents/${id}/close`,
    );
    return response.data;
  },

  async getOSHA300Log(year?: number): Promise<OSHA300Entry[]> {
    const params = year ? { year } : {};
    const response = await apiClient.get<OSHA300Entry[]>(
      `${BASE}/incidents/osha-300`,
      { params },
    );
    return response.data;
  },

  async getOSHA300ASummary(year?: number): Promise<OSHA300ASummary> {
    const params = year ? { year } : {};
    const response = await apiClient.get<OSHA300ASummary>(
      `${BASE}/incidents/osha-300a`,
      { params },
    );
    return response.data;
  },

  // ---------------------------------------------------------------------------
  // LOTO
  // ---------------------------------------------------------------------------

  async listLOTO(activeOnly = true): Promise<LOTOProcedure[]> {
    const response = await apiClient.get<LOTOProcedure[]>(`${BASE}/loto`, {
      params: { active_only: activeOnly },
    });
    return response.data;
  },

  async getLOTO(id: string): Promise<LOTOProcedure> {
    const response = await apiClient.get<LOTOProcedure>(
      `${BASE}/loto/${id}`,
    );
    return response.data;
  },

  async createLOTO(payload: LOTOCreate): Promise<LOTOProcedure> {
    const response = await apiClient.post<LOTOProcedure>(
      `${BASE}/loto`,
      payload,
    );
    return response.data;
  },

  async updateLOTO(
    id: string,
    payload: LOTOUpdate,
  ): Promise<LOTOProcedure> {
    const response = await apiClient.put<LOTOProcedure>(
      `${BASE}/loto/${id}`,
      payload,
    );
    return response.data;
  },

  async reviewLOTO(id: string): Promise<LOTOProcedure> {
    const response = await apiClient.post<LOTOProcedure>(
      `${BASE}/loto/${id}/review`,
    );
    return response.data;
  },

  // ---------------------------------------------------------------------------
  // Alerts
  // ---------------------------------------------------------------------------

  async listAlerts(activeOnly = true): Promise<SafetyAlert[]> {
    const response = await apiClient.get<SafetyAlert[]>(`${BASE}/alerts`, {
      params: { active_only: activeOnly },
    });
    return response.data;
  },

  async acknowledgeAlert(id: string): Promise<SafetyAlert> {
    const response = await apiClient.post<SafetyAlert>(
      `${BASE}/alerts/${id}/acknowledge`,
    );
    return response.data;
  },

  // ---------------------------------------------------------------------------
  // Compliance Score
  // ---------------------------------------------------------------------------

  async getComplianceScore(): Promise<ComplianceScore> {
    const response = await apiClient.get<ComplianceScore>(
      `${BASE}/compliance-score`,
    );
    return response.data;
  },
};
