-- Client Brain S1 (owner spec 2026-10-29 §3; docs/CLIENT_BRAIN_GAP_ANALYSIS.md). Not in the PRD (§12): docs/PRD_GAPS.md.
-- Clients belong to one department (owner default: department-wide visibility). Memories are typed, sourced facts; a newer
-- fact supersedes an older one without overwriting it, and every change is an immutable event.
CREATE TABLE clients (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       text NOT NULL DEFAULT 'quixotic',
    department_id   uuid NOT NULL REFERENCES departments (id),
    display_name    text NOT NULL,                       -- not unique: two clients may share an alias
    discord_handle  text,                                -- unique per department when given (case-insensitive)
    created_by      uuid REFERENCES users (id),
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX clients_handle ON clients (tenant_id, department_id, lower(discord_handle)) WHERE discord_handle IS NOT NULL;
CREATE INDEX clients_name ON clients (tenant_id, department_id, lower(display_name));

CREATE TABLE client_memories (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             text NOT NULL DEFAULT 'quixotic',
    client_id             uuid NOT NULL REFERENCES clients (id),
    order_ref             text,                          -- the employee's order label; NULL = applies to the client in general
    category              text NOT NULL CHECK (category IN ('art_preference', 'platform', 'game', 'communication', 'budget',
                                                            'deadline', 'commitment', 'objection', 'other')),
    statement             text NOT NULL,
    value                 text NOT NULL DEFAULT '',
    status                text NOT NULL CHECK (status IN ('confirmed', 'observed', 'tentative', 'unknown', 'disputed')),
    source_type           text NOT NULL CHECK (source_type IN ('discord_message', 'order', 'payment', 'employee_note', '')),
    source_id             text NOT NULL DEFAULT '',
    source_text           text NOT NULL DEFAULT '',      -- the exact words the fact was taken from
    observed_at           timestamptz NOT NULL DEFAULT now(),
    valid_from            timestamptz NOT NULL DEFAULT now(),
    valid_until           timestamptz,
    supersedes_memory_id  uuid REFERENCES client_memories (id),
    superseded_by         uuid REFERENCES client_memories (id),
    created_by            uuid REFERENCES users (id),
    reviewed_by           uuid REFERENCES users (id),
    created_at            timestamptz NOT NULL DEFAULT now(),
    deleted_at            timestamptz                    -- deletion request: content blanked, row and events kept
);
CREATE INDEX client_memories_current ON client_memories (client_id, category) WHERE superseded_by IS NULL AND deleted_at IS NULL;

CREATE TABLE client_memory_events (
    id          bigserial PRIMARY KEY,
    tenant_id   text NOT NULL DEFAULT 'quixotic',
    client_id   uuid NOT NULL REFERENCES clients (id),
    memory_id   uuid REFERENCES client_memories (id),
    event       text NOT NULL CHECK (event IN ('created', 'confirmed', 'superseded', 'deleted')),
    actor       uuid REFERENCES users (id),
    at          timestamptz NOT NULL DEFAULT now(),
    detail      jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX client_memory_events_client ON client_memory_events (client_id, id);
-- Events are append-only.
CREATE FUNCTION client_memory_events_immutable() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'client_memory_events are append-only'; END $$ LANGUAGE plpgsql;
CREATE TRIGGER client_memory_events_no_change BEFORE UPDATE OR DELETE ON client_memory_events
    FOR EACH ROW EXECUTE FUNCTION client_memory_events_immutable();
