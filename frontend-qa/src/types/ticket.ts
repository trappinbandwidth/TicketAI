export interface BoundingBox {
  x: number   // left edge, 0–1
  y: number   // top edge, 0–1
  w: number   // width, 0–1
  h: number   // height, 0–1
  page: number
}

export interface FieldValue {
  value: string
  confidence_score: number
  ai_reason: string
  bbox?: BoundingBox | null
}

export interface FileTypeAnalysis {
  confidence_score: number
  ai_reason: string
}

export interface CdlPointImpact {
  violation_category: string
  cdl_points: number
  severity: string
  csa_category: string
  must_appear_in_court: boolean
  attorney_recommended: boolean
}

export interface DocSeverityScore {
  doc_type: string
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  severity_score: number
  key_factors: string[]
  attorney_recommended: boolean
  action_required: string
  days_to_respond: number | null
}

export interface AttorneyMatch {
  attorney_id: string
  name: string
  email: string
  phone: string
  rating: number | null
  win_rate: number
  total_tickets: number
  match_type: 'county' | 'state'
  sf_url: string
}

export interface DocumentResult {
  file_type: string
  other_document_types: string[]
  file_type_analysis: FileTypeAnalysis
  file_name: string
  document_text_format: string

  // Shared / Ticket / Warning
  Date_of_Ticket__c: FieldValue
  Violation_Description__c: FieldValue
  Violation_Category__c: FieldValue
  Court_Date__c: FieldValue
  Accident__c: FieldValue
  Drivers_License_Type__c: FieldValue
  Ticket_Court__c: FieldValue
  Court_Phone_Number__c: FieldValue
  Ticket_City__c: FieldValue
  Ticket_County__c: FieldValue
  Ticket_State__c: FieldValue
  Insp_Report_Num__c: FieldValue
  Citation_Number__c: FieldValue

  // Inspection Report
  Inspection_Date__c?: FieldValue | null
  Inspection_Time__c?: FieldValue | null
  Inspection_State__c?: FieldValue | null
  Inspection_County__c?: FieldValue | null
  Inspection_City__c?: FieldValue | null
  Inspection_Location__c?: FieldValue | null
  DOT_Number__c?: FieldValue | null
  Inspection_Level__c?: FieldValue | null
  VIN__c?: FieldValue | null
  Unit_Make__c?: FieldValue | null
  Unit_License_Plate__c?: FieldValue | null
  Driver_OOS__c?: FieldValue | null
  Vehicle_OOS__c?: FieldValue | null
  BASIC_Categories__c?: FieldValue | null

  // Crash Report
  Crash_Report_Number__c?: FieldValue | null
  Crash_Date__c?: FieldValue | null
  Crash_State__c?: FieldValue | null
  Crash_County__c?: FieldValue | null
  Crash_City__c?: FieldValue | null
  Crash_Location__c?: FieldValue | null
  Federal_Recordable__c?: FieldValue | null
  State_Reportable__c?: FieldValue | null
  Number_of_Fatalities__c?: FieldValue | null
  Number_of_Injuries__c?: FieldValue | null
  Towaway__c?: FieldValue | null
  Citation_Issued__c?: FieldValue | null
  HM_Involved__c?: FieldValue | null

  // Civil Penalty
  Civil_Penalty_Case_Number__c?: FieldValue | null
  Civil_Penalty_Amount__c?: FieldValue | null
  Civil_Penalty_Due_Date__c?: FieldValue | null
  BASIC_Category__c?: FieldValue | null

  // CDL License
  CDL_License_Number__c?: FieldValue | null
  CDL_State__c?: FieldValue | null
  CDL_Class__c?: FieldValue | null
  CDL_Expiration__c?: FieldValue | null
  CDL_Endorsements__c?: FieldValue | null
  CDL_Restrictions__c?: FieldValue | null
  Driver_First_Name__c?: FieldValue | null
  Driver_Last_Name__c?: FieldValue | null
  Driver_DOB__c?: FieldValue | null

  // MVR
  MVR_License_Number__c?: FieldValue | null
  MVR_State__c?: FieldValue | null
  MVR_Class__c?: FieldValue | null
  MVR_Generated_Date__c?: FieldValue | null
  MVR_Violations_Summary__c?: FieldValue | null
  MVR_Total_Points__c?: FieldValue | null
  MVR_Suspension_Count__c?: FieldValue | null
}

// Backward compat alias
export type TicketResult = DocumentResult

export interface PriceEstimate {
  avg_attny_price: number
  cdl_fee: number
  driver_price_base: number
  driver_price_low: number
  driver_price_high: number
  win_rate_pct: number
  sample_size: number
  high_risk: boolean
  data_source: 'historical' | 'fallback' | 'unavailable'
  display: string
  note: string
}

export interface ProcessResponse {
  success: boolean
  mock: boolean
  filename: string
  pages_processed: number
  pass_status: 'green' | 'yellow' | 'red' | string
  low_confidence_fields: string[]
  referee_notes: string | null
  cdl_point_impact: CdlPointImpact | null
  doc_severity: DocSeverityScore | null
  escalation_reason: string | null
  queue_id: string | null
  price_estimate: PriceEstimate | null
  dual_conflicts: string[]
  attorney_matches: AttorneyMatch[]
  no_attorney_flag: boolean
  result: DocumentResult
}

export interface QueueSummary {
  id: string
  filename: string
  pass_status: string
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
}

export interface QueueItem extends QueueSummary {
  image_b64: string
  process_response: ProcessResponse
}

// Per-doc-type field display order (mirrors frontend/index.html DOC_TYPE_FIELDS)
export const DOC_TYPE_FIELDS: Record<string, (keyof DocumentResult)[]> = {
  Ticket: [
    'Date_of_Ticket__c', 'Citation_Number__c', 'Ticket_State__c', 'Ticket_County__c',
    'Ticket_City__c', 'Violation_Category__c', 'Violation_Description__c',
    'Court_Date__c', 'Ticket_Court__c', 'Court_Phone_Number__c',
    'Accident__c', 'Drivers_License_Type__c', 'Insp_Report_Num__c',
  ],
  Warning: [
    'Date_of_Ticket__c', 'Citation_Number__c', 'Ticket_State__c', 'Ticket_County__c',
    'Ticket_City__c', 'Violation_Category__c', 'Violation_Description__c',
    'Accident__c', 'Drivers_License_Type__c',
  ],
  'Inspection Report': [
    'Inspection_Date__c', 'Inspection_Time__c', 'Insp_Report_Num__c',
    'Inspection_Location__c', 'Inspection_City__c', 'Inspection_State__c', 'Inspection_County__c',
    'Violation_Description__c',
    'Driver_OOS__c', 'Vehicle_OOS__c', 'BASIC_Categories__c',
    'Inspection_Level__c', 'DOT_Number__c',
  ],
  'Crash Report': [
    'Crash_Report_Number__c', 'Crash_Date__c', 'Crash_State__c', 'Crash_County__c',
    'Crash_City__c', 'Crash_Location__c', 'Federal_Recordable__c', 'State_Reportable__c',
    'Number_of_Fatalities__c', 'Number_of_Injuries__c', 'Towaway__c',
    'HM_Involved__c', 'Citation_Issued__c', 'Violation_Description__c',
  ],
  'Civil Penalty': [
    'Civil_Penalty_Case_Number__c', 'Date_of_Ticket__c', 'Ticket_State__c',
    'Civil_Penalty_Amount__c', 'Civil_Penalty_Due_Date__c', 'BASIC_Category__c',
    'Violation_Description__c', 'DOT_Number__c',
  ],
  CDL: [
    'CDL_License_Number__c', 'CDL_State__c', 'CDL_Class__c', 'CDL_Expiration__c',
    'CDL_Endorsements__c', 'CDL_Restrictions__c',
    'Driver_First_Name__c', 'Driver_Last_Name__c', 'Driver_DOB__c',
  ],
  MVR: [
    'MVR_License_Number__c', 'MVR_State__c', 'MVR_Class__c', 'MVR_Generated_Date__c',
    'MVR_Total_Points__c', 'MVR_Suspension_Count__c', 'MVR_Violations_Summary__c',
  ],
}

export const FIELD_LABELS: Record<string, string> = {
  // Shared
  Date_of_Ticket__c: 'Ticket / Issue Date',
  Violation_Description__c: 'Violation Description',
  Violation_Category__c: 'Violation Category',
  Court_Date__c: 'Court Date',
  Accident__c: 'Accident Involved',
  Drivers_License_Type__c: 'License Type',
  Ticket_Court__c: 'Court Name',
  Court_Phone_Number__c: 'Court Phone',
  Ticket_City__c: 'City',
  Ticket_County__c: 'County',
  Ticket_State__c: 'State',
  Insp_Report_Num__c: 'Report #',
  Citation_Number__c: 'Citation Number',
  // Inspection
  Inspection_Date__c: 'Date',
  Inspection_Time__c: 'Time',
  Inspection_State__c: 'State',
  Inspection_County__c: 'County',
  Inspection_City__c: 'City',
  Inspection_Location__c: 'Location',
  DOT_Number__c: 'USDOT #',
  Inspection_Level__c: 'Inspection Level',
  VIN__c: 'VIN',
  Unit_Make__c: 'Unit Make',
  Unit_License_Plate__c: 'License Plate',
  Driver_OOS__c: 'Driver OOS',
  Vehicle_OOS__c: 'Vehicle OOS',
  BASIC_Categories__c: 'BASIC Categories',
  // Crash
  Crash_Report_Number__c: 'Crash Report #',
  Crash_Date__c: 'Crash Date',
  Crash_State__c: 'State',
  Crash_County__c: 'County',
  Crash_City__c: 'City',
  Crash_Location__c: 'Location',
  Federal_Recordable__c: 'Federal Recordable',
  State_Reportable__c: 'State Reportable',
  Number_of_Fatalities__c: 'Fatalities',
  Number_of_Injuries__c: 'Injuries',
  Towaway__c: 'Towaway',
  Citation_Issued__c: 'Citation Issued',
  HM_Involved__c: 'HazMat Involved',
  // Civil Penalty
  Civil_Penalty_Case_Number__c: 'Case Number',
  Civil_Penalty_Amount__c: 'Penalty Amount',
  Civil_Penalty_Due_Date__c: 'Due Date',
  BASIC_Category__c: 'BASIC Category',
  // CDL
  CDL_License_Number__c: 'License Number',
  CDL_State__c: 'State',
  CDL_Class__c: 'CDL Class',
  CDL_Expiration__c: 'Expiration Date',
  CDL_Endorsements__c: 'Endorsements',
  CDL_Restrictions__c: 'Restrictions',
  Driver_First_Name__c: 'First Name',
  Driver_Last_Name__c: 'Last Name',
  Driver_DOB__c: 'Date of Birth',
  // MVR
  MVR_License_Number__c: 'License Number',
  MVR_State__c: 'State',
  MVR_Class__c: 'CDL Class',
  MVR_Generated_Date__c: 'Report Date',
  MVR_Total_Points__c: 'Total Points',
  MVR_Suspension_Count__c: 'Suspensions',
  MVR_Violations_Summary__c: 'Violations Summary',
}
