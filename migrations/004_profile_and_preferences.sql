-- Owner request (2026-10-05): every user has a profile picture and personal answer preferences (Personalization).
-- avatar: a small image as a data URL (the app resizes it to 256 px before upload); NULL = initials are shown.
-- preferences: {answer_style, tone, language, about_me, instructions} - style only, never changes what the AI may answer from.
ALTER TABLE users ADD COLUMN avatar text;
ALTER TABLE users ADD COLUMN preferences jsonb NOT NULL DEFAULT '{}'::jsonb;
