import type { ExecutionMode, ResourceValidation } from "./index";

export type UserRole = "ADMIN" | "SUPERVISOR" | "GANG" | "MATE" | "GANGMAN";

export interface AuthUser {
  employee_id: string;
  full_name: string;
  role: UserRole;
  primary_skill?: string;
  availability?: string;
  department_id?: string | null;
  provider_type?: string | null;
  provider_id?: string | null;
  is_active?: boolean;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  crew: Pick<AuthUser, "employee_id" | "full_name" | "role">;
}

export interface CrewMember extends AuthUser {
  email?: string;
  secondary_skills?: string[];
  created_at?: string;
}

export type WorkOrderStatus =
  | "DRAFT"
  | "ASSIGNED"
  | "ACKNOWLEDGED"
  | "IN_PROGRESS"
  | "PAUSED"
  | "COMPLETED"
  | "VERIFIED"
  | "REJECTED";

export interface WorkOrder {
  id: string;
  work_order_number: string;
  plan_id: string;
  maintenance_id: string;
  title: string;
  section_id: string;
  asset_id: string;
  asset_type?: string | null;
  required_skill: string;
  priority: string;
  status: WorkOrderStatus;
  execution_mode: ExecutionMode;
  department_id?: string | null;
  contract_id?: string | null;
  amc_id?: string | null;
  oem_service_id?: string | null;
  assigned_crew_id?: string | null;
  supervisor_id?: string | null;
  planned_start?: string | null;
  planned_end?: string | null;
  actual_start?: string | null;
  actual_end?: string | null;
  estimated_duration_min?: number | null;
  actual_duration_min?: number | null;
  variance_minutes?: number | null;
  overtime_minutes?: number | null;
  gps_start?: Record<string, number> | null;
  gps_end?: Record<string, number> | null;
  material_cost?: number;
  equipment_cost?: number;
  notes?: string | null;
  rejection_reason?: string | null;
}

export interface ExecutionSummary {
  work_order: WorkOrder;
  who: {
    crew: { id: string; employee_id: string; name: string } | null;
    supervisor: { id: string; employee_id: string; name: string } | null;
    department_id?: string | null;
    provider_reference?: string | null;
  };
  what: { activity: string; instructions?: string };
  where: { asset_id: string; section_id: string; location?: string | null; chainage?: string | null };
  when: { reporting_time?: string | null; planned_start?: string | null; planned_end?: string | null };
  how: { instructions?: string; safety_requirements?: string };
  resources: ResourceValidation;
  execution_status: {
    execution_mode: ExecutionMode;
    approval_status: string;
    recommendation_reasons: string[];
    executable: boolean;
    safety_validation?: { valid: boolean; safety_conflicts?: number | null };
    simulation_summary?: unknown;
  };
}

export interface ChecklistItem {
  id: string;
  text: string;
  required?: boolean;
}

export interface Checklist {
  id: string;
  work_order_id: string;
  type: string;
  items: ChecklistItem[];
  completed_items: Record<string, boolean | { value?: boolean; note?: string }>;
  is_mandatory: boolean;
  signed_at?: string | null;
  signed_off_at?: string | null;
}

export interface NotificationRecord {
  id: string;
  type: string;
  title: string;
  message: string;
  payload: Record<string, unknown>;
  priority: string;
  read_at?: string | null;
  created_at?: string | null;
}
