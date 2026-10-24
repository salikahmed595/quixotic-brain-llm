/* PRD §3 roles */
export type Role = 'employee' | 'department_reviewer' | 'knowledge_admin' | 'system_admin' | 'founder_ceo';

export interface Department { id: string; name: string; status?: string; manager_id?: string | null }

export interface Me {
  user_id: string;
  full_name: string;
  email: string;
  phone?: string | null;
  employee_id: string;
  role: Role;
  role_label: string;
  /** server-side permissions (PRD §3, §7); the UI only uses them to choose what to show */
  permissions: string[];
  can_publish: boolean;
  can_translate?: boolean;   // owner-approved addition: Translate for client (upsellers, fresh sellers)
  account_status: string;
  email_verified: boolean;
  mfa_enabled: boolean;
  avatar?: string | null;
  department_ids: string[];
  departments: { id: string; name: string }[];
  /** departments this person may search (PRD §6 FR-CHAT-06) */
  scope: { id: string; name: string }[];
  /** true only when the scope is every active department (PRD §4.2, §15) */
  company_wide: boolean;
  reviews_department_ids: string[];
  preferences?: Record<string, any>;
}

export interface Chat { id: string; title: string; updated_at: string }

export interface Source { title: string; section?: string | null; version: number; updated?: string | null; document_id?: string; version_id?: string }

export type Msg =
  | { role: 'user'; text: string; images?: string[] }
  | { role: 'ai'; kind: 'image'; question: string; image: string }
  | { role: 'ai'; loading: true }
  | { role: 'ai'; error: string; question: string }
  | { role: 'ai'; kind: 'search'; question: string; results: { source: string; text: string }[] }
  | { role: 'ai'; kind: 'translate'; question: string; english: string; target?: string }
  | {
      role: 'ai'; kind: 'ask'; question: string; query_id?: string; answer: string; confidence?: string; web_sources?: { title: string; url: string }[];
      sources: Source[]; found: boolean; helpful?: boolean; reasons?: string[]; gap_id?: string;
    };
