-- Owner request (2026-10-05): teach the system company-specific Urdu / Roman Urdu words and phrases.
-- A phrase (as staff write it) maps to its English meaning; the meaning is added to the SEARCH text (PRD §23).
CREATE TABLE vocabulary (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id  text NOT NULL DEFAULT 'quixotic',
    phrase     text NOT NULL,
    meaning    text NOT NULL,
    created_by uuid REFERENCES users (id),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX vocabulary_phrase ON vocabulary (tenant_id, lower(phrase));
