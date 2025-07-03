import click


from typing import Literal


# Shared options
def limit(default:int):
    return click.option("--limit", default=default, help="Number of queries to show")

def _add_limit(query: str, limit: str | int) -> str:
    if limit != "":
        query += f"\nLIMIT {limit}"
    return query


@click.group()
@click.version_option()
def cli():
    """PostgreSQL tools that go POW!"""
    # """PostgreSQL Power Tools - A collection of useful tools for PostgreSQL administration."""
    pass


@cli.group()
def query():
    """Useful queries for PostgreSQL administration."""
    pass


@query.group()
def activity():
    """Queries related to database activity."""
    pass


@activity.command()
@click.option("--min-query-duration", help="Minimum query time")
@click.option("--min-transaction-duration", help="Minimum transaction time")
@click.option(
    "--order-by",
    type=click.Choice(["transaction", "query"]),
    default="transaction",
    help="Order by transaction or query duration",
)
@click.option("--compact", is_flag=True, help="Show compact view without query text")
def long_running(
    compact: bool,
    min_query_duration: str | None,
    min_transaction_duration: str | None,
    order_by: Literal["transaction", "query"],
):
    """Show long-running transactions and queries.

    See:
    - `pg_stat_activity` https://www.postgresql.org/docs/current/monitoring-stats.html#MONITORING-PG-STAT-ACTIVITY-VIEW
    """
    # TODO: consider using https://github.com/shssoichiro/sqlformat-rs to format queries for printing
    columns = """
        pid,
        now() - xact_start as txn_duration,
        now() - query_start as query_duration,
        usename,
        application_name,
        client_addr,
        state"""

    if not compact:
        columns += """,
        query_start,
        wait_event_type,
        wait_event,
        query"""

    where = ""
    if min_query_duration and min_transaction_duration:
        raise click.UsageError(
            "Cannot specify both --min-query-duration and --min-transaction-duration"
        )
    elif min_query_duration:
        where = f"AND now() - query_start > interval '{min_query_duration}'"
    elif min_transaction_duration:
        where = f"AND now() - xact_start > interval '{min_transaction_duration}'"

    _order_by = "txn_duration" if order_by == "transaction" else "query_duration"

    query = f"""
    SELECT
        {columns}
    FROM pg_stat_activity
    WHERE xact_start IS NOT NULL
        AND state <> 'idle'
        AND pid <> pg_backend_pid()
        {where}
    ORDER BY {_order_by} DESC
    """
    print(query)


@activity.command()
@click.option("--min-duration", default=None, help="Minimum blocking duration")
@click.option("--compact", is_flag=True, help="Show compact view without query text")
def blocked(min_duration: str, compact: bool):
    """Show queries that are currently blocked.

    See:
    - `pg_stat_activity` https://www.postgresql.org/docs/current/monitoring-stats.html#MONITORING-PG-STAT-ACTIVITY-VIEW
    - `pg_blocking_pids` https://www.postgresql.org/docs/17/functions-info.html#FUNCTIONS-INFO-SESSION
    """

    activity_columns = """
        blocked.pid,
        blocked.usename,
        blocked.application_name,
        now() - blocked.query_start as query_duration
    """
    blocking_columns = """,
        blocking.pid as blocking_pid,
        blocking.application_name as blocking_app_name,
        now() - blocking.query_start as blocking_duration
    """
    if not compact:
        activity_columns += """,
        blocked.query
        """
        blocking_columns += """,
        blocking.query as blocking_query
        """

    columns = activity_columns + blocking_columns

    if min_duration:
        where = f"WHERE now() - blocked.query_start > interval '{min_duration}'"
    else:
        where = ""

    query = f"""
    SELECT
        {columns}
    FROM pg_stat_activity blocked
    JOIN pg_stat_activity blocking ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
    {where}
    ORDER BY query_duration DESC;
    """
    print(query)


@activity.command()
@click.option("--pid", type=int, help="Filter by specific process ID")
@click.option(
    "--granted/--not-granted",
    is_flag=True,
    default=None,
    help="Filter by granted or waiting locks",
)
@click.option("--compact", is_flag=True, help="Show compact view without query text")
def locks(pid: int | None, granted: bool | None, compact: bool):
    """Show detailed lock information for sessions.

    See:
    - https://www.postgresql.org/docs/current/view-pg-locks.html
    """
    where_clauses = []
    if granted is not None:
        where_clauses.append("granted" if granted else "not granted")
    if pid:
        where_clauses.append(f"pid = {pid}")

    if where_clauses:
        where = "WHERE " + " AND ".join(where_clauses)
    else:
        where = ""

    query = f"""
    SELECT
        pg_locks.*
    FROM pg_locks
    {where}
    """
    print(query)


@query.group()
def maintenance():
    """Database maintenance commands."""
    pass


@maintenance.command("bloat-check")
@click.option("--min-size", default="100MB", help="Minimum table size to check")
def bloat_check(schema: str, min_size: str):
    """Check for table bloat."""
    pass

@maintenance.command("dead-tuples")
@limit(30)
def dead_tuples(limit: int | str):
    """Show the tables with the highest proportion of dead tuples"""
    query = """
    SELECT
      schemaname,
      relname,
      n_dead_tup,
      n_live_tup,
      ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) AS dead_tuple_pct
    FROM pg_stat_user_tables
    WHERE schemaname = 'public'
    ORDER BY dead_tuple_pct DESC NULLS LAST
    """
    query = _add_limit(query, limit)
    print(query)

@maintenance.command("table-size")
@limit(10)
def table_size(limit: int | str):
    """Show the largest tables by size"""
    query = """
    SELECT
      table_schema || '.' || table_name AS table_full_name,
      pg_size_pretty(pg_total_relation_size(quote_ident(table_schema) || '.' || quote_ident(table_name))) AS total_size
    FROM information_schema.tables
    WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('pg_catalog', 'information_schema')
    ORDER BY pg_total_relation_size(quote_ident(table_schema) || '.' || quote_ident(table_name)) DESC
    """
    query = _add_limit(query, limit)
    print(query)


@query.group()
def performance():
    """Database performance commands."""
    pass


@performance.command("frequent-patterns")
@limit(10)
@click.option("--min-calls", default=1000, help="Minimum number of calls")
def frequent_patterns(limit: int, min_calls: int):
    """Show frequent query patterns."""
    pass


@performance.command("indexes-used")
@limit(10)
@click.option("--no-pkey", is_flag=True, default=False, help="Exclude primary key indexes")
def indexes_used(limit: int | str, no_pkey: bool):
    """Most used indexes"""
    _no_pkey = "AND indexrelname NOT ILIKE '%_pkey'" if no_pkey else ""
    query = f"""
    SELECT
        relname,
        indexrelname,
        idx_scan
    FROM
        pg_stat_all_indexes
    WHERE
        schemaname = 'public' AND idx_scan > 0 {_no_pkey}
    ORDER BY
        idx_scan DESC
    """
    query = _add_limit(query, limit)

    print(query)


@performance.command("indexes-unused")
@limit(10)
def indexes_unused(limit: int):
    """Unused indexes that may be candidates for removal"""
    query = """
    SELECT
        schemaname,
        relname,
        indexrelname,
        idx_scan,
        pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
    FROM
        pg_stat_all_indexes
    WHERE
        schemaname = 'public' AND idx_scan = 0
    ORDER BY
        pg_relation_size(indexrelid) DESC
    """
    query = _add_limit(query, limit)
    print(query)
