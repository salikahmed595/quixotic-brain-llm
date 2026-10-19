-- M7 (docs/P0_PLAN.md): tamper-resistant audit log. PRD §10: "Record account approvals, document changes, access-scope changes,
-- publishing, administrative exports, and privileged bot actions in tamper-resistant audit logs."
-- Implementation choice (docs/PRD_GAPS.md §4): append-only table (UPDATE/DELETE refused by a trigger) + a SHA-256 hash chain:
-- every row stores the previous row's hash and its own hash over its content, so any edit, removal or reordering is detectable
-- (GET /v1/admin/system/audit-verify). The newest hash is also written into every backup manifest as an external anchor.

ALTER TABLE audit_logs ADD COLUMN prev_hash text;
ALTER TABLE audit_logs ADD COLUMN hash text;

CREATE FUNCTION audit_row_hash(prev text, t text, at timestamptz, actor uuid, label text, ev text, detail jsonb) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT encode(sha256(convert_to(concat_ws('|', prev, t, to_char(at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US'),
                                              COALESCE(actor::text, ''), COALESCE(label, ''), ev, detail::text), 'UTF8')), 'hex')
$$;

-- Backfill the rows written before this migration, in id order.
DO $$
DECLARE r record; last text := 'genesis';
BEGIN
    FOR r IN SELECT * FROM audit_logs ORDER BY id LOOP
        UPDATE audit_logs SET prev_hash = last,
               hash = audit_row_hash(last, r.tenant_id, r.at, r.actor_id, r.actor_label, r.event, r.detail)
         WHERE id = r.id RETURNING hash INTO last;
    END LOOP;
END $$;

CREATE FUNCTION audit_chain() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE last text;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext('audit_logs_chain'));          -- one writer at a time: the chain never forks
    -- A row with a lower id can commit after one with a higher id; then it links to that one. The verifier follows the links.
    SELECT a.hash INTO last FROM audit_logs a WHERE a.hash IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM audit_logs b WHERE b.prev_hash = a.hash) ORDER BY a.id DESC LIMIT 1;
    NEW.prev_hash := COALESCE(last, 'genesis');
    NEW.hash := audit_row_hash(NEW.prev_hash, NEW.tenant_id, NEW.at, NEW.actor_id, NEW.actor_label, NEW.event, NEW.detail);
    RETURN NEW;
END $$;
CREATE TRIGGER audit_chain BEFORE INSERT ON audit_logs FOR EACH ROW EXECUTE FUNCTION audit_chain();

CREATE FUNCTION audit_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs is append-only (PRD §10)';
END $$;
CREATE TRIGGER audit_append_only BEFORE UPDATE OR DELETE ON audit_logs FOR EACH ROW EXECUTE FUNCTION audit_append_only();
CREATE INDEX audit_logs_prev_hash ON audit_logs (prev_hash);
