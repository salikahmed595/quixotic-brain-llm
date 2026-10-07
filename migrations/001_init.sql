-- Quixotic Brain schema. Source: PRODUCT.md §9, §10, §12–§17, §21, §40, §45, §47, §53, §66.
-- Embedding vectors are 1024-d (BGE-M3, §24.1). Changing the model = new migration + re-index (§24.2).
-- tenant_id on every business table (§66: "introduced early ... even if Quixotic is the only initial tenant").

CREATE EXTENSION IF NOT EXISTS vector;

-- §10 departments -------------------------------------------------------------------------
CREATE TABLE departments (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   text NOT NULL DEFAULT 'quixotic',
    name        text NOT NULL,
    status      text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    manager_id  uuid,                                   -- "Set department managers" (§10)
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

-- §9 users & roles, §41 email or employee ID + password -----------------------------------
CREATE TABLE users (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      text NOT NULL DEFAULT 'quixotic',
    employee_id    text NOT NULL,                       -- e.g. emp_104 (§38)
    email          text NOT NULL,
    full_name      text NOT NULL,
    password_hash  text NOT NULL,
    role           text NOT NULL CHECK (role IN ('employee', 'contributor', 'manager', 'administrator')),
    is_active      boolean NOT NULL DEFAULT true,
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, employee_id),
    UNIQUE (tenant_id, email)
);
ALTER TABLE departments ADD FOREIGN KEY (manager_id) REFERENCES users (id);

-- §42 RBAC: user -> role -> department -> permissions
CREATE TABLE user_departments (
    user_id        uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    department_id  uuid NOT NULL REFERENCES departments (id),
    PRIMARY KEY (user_id, department_id)
);

-- §12 knowledge: logical item + versions (§15) ---------------------------------------------
CREATE TABLE knowledge_items (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      text NOT NULL DEFAULT 'quixotic',
    title          text NOT NULL,
    category       text,
    document_type  text,                                -- §14 metadata "document_type"
    created_by     uuid REFERENCES users (id),
    created_at     timestamptz NOT NULL DEFAULT now()
);

-- §10 "Assign knowledge to one or more departments"
CREATE TABLE item_departments (
    item_id        uuid NOT NULL REFERENCES knowledge_items (id) ON DELETE CASCADE,
    department_id  uuid NOT NULL REFERENCES departments (id),
    PRIMARY KEY (item_id, department_id)
);

CREATE TABLE source_files (                              -- §13, §46 raw originals live in S3
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         text NOT NULL DEFAULT 'quixotic',
    filename          text NOT NULL,
    extension         text NOT NULL,
    size_bytes        bigint NOT NULL,
    s3_key            text NOT NULL,
    uploaded_by       uuid REFERENCES users (id),
    uploaded_at       timestamptz NOT NULL DEFAULT now(),
    processing_status text NOT NULL DEFAULT 'pending'
        CHECK (processing_status IN ('pending', 'processing', 'ready', 'failed')),
    processing_error  text
);

CREATE TABLE knowledge_versions (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id        uuid NOT NULL REFERENCES knowledge_items (id) ON DELETE CASCADE,
    version        integer NOT NULL,                     -- §14: integer version
    -- §12.3 workflow + alternative states
    status         text NOT NULL DEFAULT 'draft' CHECK (status IN
        ('draft', 'submitted', 'pending_review', 'approved', 'active', 'rejected', 'archived', 'expired')),
    body           text,
    language       text,
    access_level   text,                                 -- §14 metadata "access_level" (label)
    source_file_id uuid REFERENCES source_files (id),
    -- §12.3 tracked fields
    created_by     uuid REFERENCES users (id),
    created_at     timestamptz NOT NULL DEFAULT now(),
    reviewed_by    uuid REFERENCES users (id),
    reviewed_at    timestamptz,
    updated_by     uuid REFERENCES users (id),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (item_id, version)
);
-- §15 "Current information must always override old information": one active version per item.
CREATE UNIQUE INDEX one_active_version_per_item ON knowledge_versions (item_id) WHERE status = 'active';
CREATE INDEX knowledge_versions_status ON knowledge_versions (status);

CREATE TABLE knowledge_status_history (
    id          bigserial PRIMARY KEY,
    version_id  uuid NOT NULL REFERENCES knowledge_versions (id) ON DELETE CASCADE,
    from_status text,
    to_status   text NOT NULL,
    actor_id    uuid REFERENCES users (id),
    note        text,
    at          timestamptz NOT NULL DEFAULT now()
);

-- §13.3 / §14 chunks with metadata, embeddings and keyword index --------------------------
CREATE TABLE chunks (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        text NOT NULL DEFAULT 'quixotic',
    version_id       uuid NOT NULL REFERENCES knowledge_versions (id) ON DELETE CASCADE,
    chunk_index      integer NOT NULL,
    section          text,                               -- §30 "Section"
    text             text NOT NULL,
    metadata         jsonb NOT NULL,                     -- §14 snapshot
    embedding        vector(1024) NOT NULL,
    embedding_model  text NOT NULL,                      -- §24.2 re-index when the model changes
    -- §25 keyword search: BM25 "or equivalent sparse retrieval" (see docs/PRD_GAPS.md)
    tsv              tsvector GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED,
    UNIQUE (version_id, chunk_index)
);
CREATE INDEX chunks_tsv ON chunks USING gin (tsv);
CREATE INDEX chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops);

-- §16.2 sales memory (field names follow the PRD example exactly) --------------------------
CREATE TABLE sales_memories (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        text NOT NULL DEFAULT 'quixotic',
    department_id    uuid NOT NULL REFERENCES departments (id),
    conversation_id  text,
    channel          text,
    scenario         text,
    customer_intent  text,
    customer_message text,
    agent_response   text,
    sales_stage      text,
    product          text,
    outcome          text,
    sale_value       numeric,
    discount_given   numeric,
    currency         text,
    language         text,
    quality_score    real,
    embedding        vector(1024) NOT NULL,
    embedding_model  text NOT NULL,
    import_job_id    uuid,
    created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX sales_memories_embedding ON sales_memories USING hnsw (embedding vector_cosine_ops);

-- §47 background jobs with progress (processed / total) ---------------------
CREATE TABLE jobs (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     text NOT NULL DEFAULT 'quixotic',
    type          text NOT NULL,
    status        text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
    progress_done integer NOT NULL DEFAULT 0,
    progress_total integer,
    payload       jsonb NOT NULL DEFAULT '{}',
    error         text,
    created_by    uuid REFERENCES users (id),
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE sales_memories ADD FOREIGN KEY (import_job_id) REFERENCES jobs (id);

-- §21 / §35 questions, answers, feedback, outcomes -----------------------------------------
CREATE TABLE query_log (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        text NOT NULL DEFAULT 'quixotic',
    user_id          uuid REFERENCES users (id),
    api_key_id       uuid,
    department_id    uuid REFERENCES departments (id),
    mode             text NOT NULL,
    original_query   text NOT NULL,                      -- §23 preserve the original for audit
    normalized_query text NOT NULL,
    language         text NOT NULL,
    confidence       text CHECK (confidence IN ('high', 'medium', 'low')),
    confidence_score real,
    knowledge_found  boolean NOT NULL,                   -- §35 "Knowledge: Not Found"
    retrieved        jsonb NOT NULL DEFAULT '[]',
    answer           text,
    latency_ms       integer,
    created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX query_log_created ON query_log (created_at);

CREATE TABLE feedback (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    text NOT NULL DEFAULT 'quixotic',
    query_id     uuid NOT NULL REFERENCES query_log (id),
    user_id      uuid REFERENCES users (id),
    helpful      boolean,                                -- §21 👍 / 👎
    outcome      text CHECK (outcome IN ('sale_closed', 'sale_lost', 'customer_still_deciding', 'follow_up_required')),
    agent_action text,
    note         text,
    validated    boolean NOT NULL DEFAULT false,         -- §21 "searchable memory after validation"
    validated_by uuid REFERENCES users (id),
    created_at   timestamptz NOT NULL DEFAULT now()
);

-- §40 API keys -------------------------------------------------------------------------------
CREATE TABLE api_keys (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id              text NOT NULL DEFAULT 'quixotic',
    app_name               text NOT NULL,
    key_prefix             text NOT NULL,                -- e.g. qx_live_callcenter_
    key_hash               text NOT NULL UNIQUE,
    permissions            text[] NOT NULL,
    allowed_department_ids uuid[] NOT NULL,
    rate_limit_per_minute  integer NOT NULL CHECK (rate_limit_per_minute > 0),
    status                 text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    created_by             uuid REFERENCES users (id),
    created_at             timestamptz NOT NULL DEFAULT now(),
    last_used_at           timestamptz,
    revoked_at             timestamptz
);

-- §53 audit logs -------------------------------------------------------------------------------
CREATE TABLE audit_logs (
    id          bigserial PRIMARY KEY,
    tenant_id   text NOT NULL DEFAULT 'quixotic',
    at          timestamptz NOT NULL DEFAULT now(),
    actor_id    uuid,
    actor_label text,
    event       text NOT NULL,
    detail      jsonb NOT NULL DEFAULT '{}'
);
CREATE INDEX audit_logs_at ON audit_logs (at DESC);

-- §10 initial departments
INSERT INTO departments (name) VALUES
 ('Company Wide'), ('Administration'), ('HR'), ('Sales'), ('Marketing'),
 ('AI'), ('Development'), ('Finance'), ('Customer Support'), ('Operations');
