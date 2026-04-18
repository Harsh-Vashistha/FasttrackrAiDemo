export interface Account {
  id: number
  account_type: string
  custodian?: string
  account_number?: string
  account_value?: number
}

export interface BankDetail {
  id: number
  bank_name?: string
  bank_type?: string
  account_number?: string
}

export interface Member {
  id: number
  first_name: string
  last_name: string
  dob?: string
  phone?: string
  email?: string
  address?: string
  occupation?: string
  employer?: string
  marital_status?: string
  accounts: Account[]
  bank_details: BankDetail[]
}

export interface Household {
  id: number
  name: string
  estimated_liquid_net_worth?: number
  estimated_total_net_worth?: number
  annual_income?: number
  tax_bracket?: string
  primary_investment_objective?: string
  risk_tolerance?: string
  time_horizon?: string
  source_of_funds?: string
  primary_use_of_funds?: string
  liquidity_needs?: string
  account_decision_making?: string
  // Present in detail view
  members?: Member[]
  accounts?: Account[]
  // Present in list view
  member_count?: number
  account_count?: number
}

export interface InsightsSummary {
  households_by_net_worth: { name: string; liquid_net_worth: number; total_net_worth: number }[]
  income_distribution: { name: string; annual_income: number }[]
  account_type_distribution: { account_type: string; count: number }[]
  tax_bracket_distribution: { bracket: string; count: number }[]
  risk_tolerance_distribution: { risk: string; count: number }[]
  members_per_household: { household_name: string; member_count: number }[]
  total_aum: number
  total_households: number
  total_members: number
}

export interface AudioInsight {
  id?: number
  insight_id?: number
  household_id?: number
  transcription?: string
  extracted_data?: {
    household_name?: string
    updates?: Record<string, unknown>
    member_updates?: { name: string; updates: Record<string, unknown> }[]
    new_accounts?: { member_name: string; account_type: string; custodian?: string; account_value?: number }[]
    key_insights?: string[]
    action_items?: string[]
    raw_response?: string
  }
  created_at?: string
}

export interface UploadResult {
  created?: number
  updated?: number
  errors?: string[]
  message?: string
}

export interface ActionItem {
  id: number
  household_id: number | null
  audio_insight_id: number | null
  description: string
  status: 'pending' | 'completed'
  created_at: string
  completed_at: string | null
}

export interface ProposedChange {
  id: number
  session_id: number
  entity_type: string
  entity_id: number | null
  entity_label: string | null
  field_name: string
  current_value: string | null
  proposed_value: string | null
  source_quote: string | null
  confidence: number | null
  reasoning: string | null
  status: 'pending' | 'approved' | 'rejected' | 'pending_revision' | 'revised' | 'dismissed'
  reviewer_feedback: string | null
  revised_value: string | null
  revised_source_quote: string | null
  revised_confidence: number | null
  agent_response: string | null
  conversation_history: any[]
  created_at: string
  reviewed_at: string | null
}

export interface ReviewSession {
  id: number
  audio_insight_id: number | null
  status: string
  matched_household_id: number | null
  proposed_household_name: string | null
  is_new_client: string | null
  agent_summary: string | null
  created_at: string
  updated_at: string
  proposed_changes: ProposedChange[]
  pending_count?: number
  approved_count?: number
  rejected_count?: number
  revised_count?: number
  dismissed_count?: number
}
