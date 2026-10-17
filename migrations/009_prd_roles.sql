-- M2 (docs/P0_PLAN.md): the PRD §3 roles. Mapping proposed in docs/PRD_GAPS.md §0.1 (veto if needed):
--   contributor -> employee (PRD §3 gives employees no upload right; §9 "do not allow all employees to write to the vault")
--   manager -> department_reviewer, administrator -> system_admin; knowledge_admin and founder_ceo are new.
ALTER TABLE users DROP CONSTRAINT users_role_check;
UPDATE users SET role = CASE role
    WHEN 'contributor'   THEN 'employee'
    WHEN 'manager'       THEN 'department_reviewer'
    WHEN 'administrator' THEN 'system_admin'
    ELSE role END;
ALTER TABLE users ADD CONSTRAINT users_role_check
    CHECK (role IN ('employee', 'department_reviewer', 'knowledge_admin', 'system_admin', 'founder_ceo'));

-- PRD §3 Knowledge Admin: "publish when granted publisher permission" — a separate grant, off by default.
ALTER TABLE users ADD COLUMN can_publish boolean NOT NULL DEFAULT false;
UPDATE users SET can_publish = true WHERE role = 'system_admin';

-- PRD §7 Departments: "assign members, reviewers ... and document owners". Reviewers per department (a person may review
-- several departments); the old single manager_id becomes the first reviewer.
CREATE TABLE department_reviewers (
    department_id uuid NOT NULL REFERENCES departments (id) ON DELETE CASCADE,
    user_id       uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    PRIMARY KEY (department_id, user_id)
);
INSERT INTO department_reviewers (department_id, user_id)
    SELECT id, manager_id FROM departments WHERE manager_id IS NOT NULL;
ALTER TABLE departments ADD COLUMN description text;
