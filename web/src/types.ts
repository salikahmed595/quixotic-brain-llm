export type Role = 'employee' | 'contributor' | 'manager' | 'administrator';

export interface Department { id: string; name: string; status?: string; manager_id?: string | null }

export interface Me {
  user_id: string;
  full_name: string;
  email: string;
  employee_id: string;
  role: Role;
  avatar?: string | null;
  department_ids: string[];
  departments: { id: string; name: string }[];
  preferences?: Record<string, any>;
}

export interface Chat { id: string; title: string; updated_at: string }

export interface Source { title: string; section?: string | null; version: number; updated?: string | null }

export type Msg =
  | { role: 'user'; text: string }
  | { role: 'ai'; loading: true }
  | { role: 'ai'; error: string; question: string }
  | { role: 'ai'; kind: 'search'; question: string; results: { source: string; text: string }[] }
  | {
      role: 'ai'; kind: 'ask'; question: string; query_id?: string; answer: string; confidence?: string;
      sources: Source[]; found: boolean; helpful?: boolean; reasons?: string[];
    };
