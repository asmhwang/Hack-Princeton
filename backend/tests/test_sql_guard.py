import pytest

from backend.api.validators.sql_guard import SqlSafetyError, validate_select_only


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "SELECT id, name FROM suppliers WHERE region = 'EU'",
        "SELECT count(*) FROM shipments s JOIN ports p ON s.origin_port_id = p.id",
        "  select * from signals where first_seen_at > now() - interval '72 hours'  ",
        "/* ; DROP TABLE x; -- */ SELECT 1",  # block comment stripped → safe SELECT
        "SELECT * FROM signals WHERE notes = 'pg_sleep_active monitor'",  # literal, not function
        "SELECT * FROM signals WHERE summary = 'uses -- as separator'",  # literal, not comment
        "SELECT * FROM signals WHERE keyword = 'pg_sleep'",  # literal keyword-in-string
        "SELECT pg_sleep_active FROM foo",  # identifier containing forbidden substring
    ],
)
def test_accepts_plain_selects(sql):
    validate_select_only(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE signals",
        "DELETE FROM shipments",
        "UPDATE suppliers SET reliability_score = 0",
        "INSERT INTO signals VALUES (1)",
        "SELECT 1; DROP TABLE x",
        "SELECT 1 -- ; DROP TABLE x",
        "WITH q AS (SELECT 1) DELETE FROM shipments",
        "GRANT ALL ON signals TO public",
        "TRUNCATE shipments",
        "ALTER TABLE signals ADD COLUMN x INT",
        "",
        "SELECT",
        "SELECT 1; SELECT 2",
        "SELECT pg_sleep(60)",
        "COPY signals TO '/tmp/stolen.csv'",
        "SET ROLE postgres; SELECT 1",
        "EXPLAIN ANALYZE DELETE FROM shipments",
        "SELECT pg_advisory_lock(1)",
        "SELECT pg_terminate_backend(12345)",
        "SELECT dblink('host=evil', 'SELECT * FROM suppliers')",
        "SELECT lo_import('/etc/passwd')",
        "DISCARD ALL",
    ],
)
def test_rejects_mutations_and_multi_statement(sql):
    with pytest.raises(SqlSafetyError):
        validate_select_only(sql)
