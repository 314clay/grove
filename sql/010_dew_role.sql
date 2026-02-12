-- Create a restricted postgres role for personal data access (dew sources).
-- Dew source commands (gv dew obsidian, gv dew l2) connect as grove_dew,
-- which has read-only access to personal schemas (obsidian, apple_notes).
-- Automated agents don't have GV_DEW_PASSWORD, so they can't query personal data.

BEGIN;

-- Create restricted role for personal data access
CREATE ROLE grove_dew WITH LOGIN PASSWORD 'iZvCUdDWu3xwFs0NQAQAWnErvhTRaTZ8';

-- Grant connect
GRANT CONNECT ON DATABASE connectingservices TO grove_dew;

-- Grant usage + SELECT on personal schemas
GRANT USAGE ON SCHEMA obsidian TO grove_dew;
GRANT SELECT ON ALL TABLES IN SCHEMA obsidian TO grove_dew;

GRANT USAGE ON SCHEMA apple_notes TO grove_dew;
GRANT SELECT ON ALL TABLES IN SCHEMA apple_notes TO grove_dew;

-- Default privileges for future tables in these schemas
ALTER DEFAULT PRIVILEGES IN SCHEMA obsidian GRANT SELECT ON TABLES TO grove_dew;
ALTER DEFAULT PRIVILEGES IN SCHEMA apple_notes GRANT SELECT ON TABLES TO grove_dew;

-- Revoke personal schema access from PUBLIC
-- (clayarnold is superuser so REVOKE won't block them;
--  the app-level gate in get_dew_session() is the real enforcement)
REVOKE ALL ON ALL TABLES IN SCHEMA obsidian FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA apple_notes FROM PUBLIC;

COMMIT;
