import click


from typing import Literal, Optional


def connection_options(func):
    func = click.option(
        "-x", "--execute", is_flag=True, help="Execute query instead of printing"
    )(func)
    func = click.option("-c", "--connection", help="PostgreSQL connection string")(func)
    func = click.option("--host", help="Database server host")(func)
    func = click.option("--port", type=int, help="Database server port")(func)
    func = click.option("--user", help="Database user")(func)
    func = click.option("--dbname", help="Database name")(func)
    return func


@click.group()
@click.version_option()
def cli():
    """PostgreSQL tools that go POW!"""
    # """PostgreSQL Power Tools - A collection of useful tools for PostgreSQL administration."""
    pass


@cli.group()
@connection_options
@click.pass_context
def query(
    ctx,
    execute: bool,
    connection: Optional[str],
    host: Optional[str],
    port: Optional[int],
    user: Optional[str],
    dbname: Optional[str],
):
    """Query commands for PostgreSQL administration."""
    # Store connection options in the context for sub-commands
    ctx.obj = {
        "execute": execute,
        "connection": connection,
        "host": host,
        "port": port,
        "user": user,
        "dbname": dbname,
    }


@query.group()
@click.pass_context
def activity(ctx):
    """Commands related to database activity."""
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
@click.pass_context
def long_running(
    ctx,
    compact: bool,
    min_query_duration: str | None,
    min_transaction_duration: str | None,
    order_by: Literal["transaction", "query"],
):
    """Show long-running transactions and queries."""
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
        raise click.UsageError("Cannot specify both --min-query-duration and --min-transaction-duration")
    elif min_query_duration:
        where = f"AND now() - query_start > interval '{min_query_duration}'"
    elif min_transaction_duration:
        where = f"AND now() - xact_start > interval '{min_transaction_duration}'"

    _order_by = "txn_duration" if order_by == "transaction" else "query_duration"


    _query_tpl = f"""
    SELECT
        {columns}
    FROM pg_stat_activity
    WHERE xact_start IS NOT NULL
        AND state != 'idle'
        {where}
    ORDER BY {_order_by} DESC;
    """
    if not ctx.obj["execute"]:
        print(_query_tpl)


@activity.command()
@click.option("--min-duration", default="5m", help="Minimum blocking duration")
@click.pass_context
def blocking(ctx, min_duration: str):
    """Show blocking queries."""
    pass


@query.group()
@click.pass_context
def maintenance(ctx):
    """Database maintenance commands."""
    pass


@maintenance.command("bloat-check")
@click.option("--schema", default="public", help="Schema to check")
@click.option("--min-size", default="100MB", help="Minimum table size to check")
@click.pass_context
def bloat_check(ctx, schema: str, min_size: str):
    """Check for table bloat."""
    pass


@query.group()
@click.pass_context
def performance(ctx):
    """Database performance commands."""
    pass


@performance.command("frequent-patterns")
@click.option("--limit", default=10, help="Number of queries to show")
@click.option("--min-calls", default=1000, help="Minimum number of calls")
@click.pass_context
def frequent_patterns(ctx, limit: int, min_calls: int):
    """Show frequent query patterns."""
    pass
