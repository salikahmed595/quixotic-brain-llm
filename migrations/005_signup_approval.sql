-- Owner request (2026-10-05): people create their own account (own username + password); an administrator or manager approves it
-- and decides the role and the departments (= which knowledge the person can see).
-- Existing users are 'approved'. A pending / rejected user is also is_active = false, so no token or login works for them.
ALTER TABLE users ADD COLUMN approval_status text NOT NULL DEFAULT 'approved' CHECK (approval_status IN ('pending', 'approved', 'rejected'));
ALTER TABLE users ADD COLUMN requested_department_id uuid REFERENCES departments (id);   -- what the person asked for; the approver decides
ALTER TABLE users ADD COLUMN decided_by uuid REFERENCES users (id);
ALTER TABLE users ADD COLUMN decided_at timestamptz;
