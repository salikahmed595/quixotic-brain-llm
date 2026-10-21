-- Owner 2026-10-21: general assistant answers (QB_GENERAL_ASSISTANT) are logged with confidence 'general'.
ALTER TABLE query_log DROP CONSTRAINT IF EXISTS query_log_confidence_check;
ALTER TABLE query_log ADD CONSTRAINT query_log_confidence_check CHECK (confidence IN ('high', 'medium', 'low', 'general'));
