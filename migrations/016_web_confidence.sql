-- Owner 2026-10-24: answers with Web Search on are logged with confidence 'web'.
ALTER TABLE query_log DROP CONSTRAINT IF EXISTS query_log_confidence_check;
ALTER TABLE query_log ADD CONSTRAINT query_log_confidence_check CHECK (confidence IN ('high', 'medium', 'low', 'general', 'web'));
