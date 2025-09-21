# ruff: noqa: E501
import pytest

from pgpow.explain import (
    Actuals,
    Costs,
    Plan,
    PlanNode,
    format_node_type,
    format_plan,
    parse_plan_line,
    parse_text_plan,
)


def test_parse_text_plan_simple() -> None:
    # Given
    plan_text = """
Index Only Scan using building_pkey on building b  (cost=0.15..0.45 rows=1 width=4) (actual time=0.003..0.003 rows=1 loops=11)
  Index Cond: (id = rb.building_id)
  Heap Fetches: 10
  Buffers: shared hit=20
Planning Time: 3.278 ms
Execution Time: 129.345 ms
""".strip()
    expected = Plan(
        PlanNode(
            node_type="Index Only Scan",
            indent=0,
            target="using building_pkey on building b",
            costs=Costs(startup=0.15, total=0.45, rows=1, width=4),
            actuals=Actuals(startup_time=0.003, total_time=0.003, rows=1, loops=11),
            metadata=[
                "Index Cond: (id = rb.building_id)",
                "Heap Fetches: 10",
                "Buffers: shared hit=20",
            ],
            children=[],
        ),
        tail=["Planning Time: 3.278 ms", "Execution Time: 129.345 ms"],
    )

    # When
    plan = parse_text_plan(plan_text)

    # Then
    assert plan == expected


def test_parse_text_plan_with_one_child() -> None:
    plan_text = """
GroupAggregate  (cost=23558.04..26145.55 rows=100 width=43) (actual time=93.905..126.623 rows=100 loops=1)
  Group Key: s.name
  Buffers: shared hit=500, temp read=899 written=904
  ->  Sort  (cost=23558.04..23989.13 rows=172434 width=27) (actual time=93.537..102.804 rows=195804 loops=1)
        Sort Key: s.name
        Sort Method: external merge  Disk: 7192kB
        Buffers: shared hit=497, temp read=899 written=904
        ->  Hash Right Join  (cost=1577.66..4433.51 rows=172434 width=27) (actual time=30.465..53.756 rows=195804 loops=1)
              Hash Cond: (w.plant_id = p.id)
              Buffers: shared hit=494
              ->  Seq Scan on watering w  (cost=0.00..819.00 rows=50000 width=8) (actual time=0.004..1.955 rows=50000 loops=1)
                    Buffers: shared hit=319
              ->  Hash  (cost=1146.57..1146.57 rows=34487 width=23) (actual time=30.373..30.375 rows=38909 loops=1)
                    Buckets: 65536  Batches: 1  Memory Usage: 2617kB
                    Buffers: shared hit=175
Planning:
  Buffers: shared hit=303
Planning Time: 3.278 ms
Execution Time: 129.345 ms
""".strip()
    expected = Plan(
        PlanNode(
            node_type="GroupAggregate",
            indent=0,
            target=None,
            costs=Costs(startup=23558.04, total=26145.55, rows=100, width=43),
            actuals=Actuals(startup_time=93.905, total_time=126.623, rows=100, loops=1),
            metadata=[
                "Group Key: s.name",
                "Buffers: shared hit=500, temp read=899 written=904",
            ],
            children=[
                PlanNode(
                    node_type="Sort",
                    indent=1,
                    target=None,
                    costs=Costs(startup=23558.04, total=23989.13, rows=172434, width=27),
                    actuals=Actuals(startup_time=93.537, total_time=102.804, rows=195804, loops=1),
                    metadata=[
                        "Sort Key: s.name",
                        "Sort Method: external merge  Disk: 7192kB",
                        "Buffers: shared hit=497, temp read=899 written=904",
                    ],
                    children=[
                        PlanNode(
                            node_type="Hash Right Join",
                            indent=2,
                            target=None,
                            costs=Costs(startup=1577.66, total=4433.51, rows=172434, width=27),
                            actuals=Actuals(startup_time=30.465, total_time=53.756, rows=195804, loops=1),
                            metadata=[
                                "Hash Cond: (w.plant_id = p.id)",
                                "Buffers: shared hit=494",
                            ],
                            children=[
                                PlanNode(
                                    node_type="Seq Scan",
                                    indent=3,
                                    target="on watering w",
                                    costs=Costs(startup=0.00, total=819.00, rows=50000, width=8),
                                    actuals=Actuals(startup_time=0.004, total_time=1.955, rows=50000, loops=1),
                                    metadata=["Buffers: shared hit=319"],
                                    children=[],
                                ),
                                PlanNode(
                                    node_type="Hash",
                                    indent=3,
                                    target=None,
                                    costs=Costs(startup=1146.57, total=1146.57, rows=34487, width=23),
                                    actuals=Actuals(startup_time=30.373, total_time=30.375, rows=38909, loops=1),
                                    metadata=[
                                        "Buckets: 65536  Batches: 1  Memory Usage: 2617kB",
                                        "Buffers: shared hit=175",
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
        tail=[
            "Planning:",
            "  Buffers: shared hit=303",
            "Planning Time: 3.278 ms",
            "Execution Time: 129.345 ms",
        ],
    )

    plan = parse_text_plan(plan_text)

    assert plan == expected


def test_parse_plan_line() -> None:
    plan_line_text = (
        "Index Only Scan using building_pkey on building b  "
        "(cost=0.15..0.45 rows=1 width=4) "
        "(actual time=0.003..0.003 rows=1 loops=11)"
    )
    expected = PlanNode(
        node_type="Index Only Scan",
        indent=0,
        target="using building_pkey on building b",
        costs=Costs(startup=0.15, total=0.45, rows=1, width=4),
        actuals=Actuals(startup_time=0.003, total_time=0.003, rows=1, loops=11),
    )
    assert parse_plan_line(plan_line_text) == expected


def test_parse_plan_line_no_actuals() -> None:
    plan_line_text = "Seq Scan on users u  (cost=0.00..431.00 rows=21000 width=244)"
    expected = PlanNode(
        node_type="Seq Scan",
        indent=0,
        target="on users u",
        costs=Costs(startup=0.00, total=431.00, rows=21000, width=244),
        actuals=None,
    )
    assert parse_plan_line(plan_line_text) == expected


def test_parse_plan_line_no_target_or_costs() -> None:
    plan_line_text = "        ->  Aggregate"
    expected = PlanNode(
        node_type="Aggregate",
        indent=2,
        target=None,
        costs=None,
        actuals=None,
    )

    assert parse_plan_line(plan_line_text) == expected


@pytest.mark.parametrize(
    "node_type,expected",
    [
        pytest.param("Parallel Seq Scan", "🔍 [blue]Parallel Seq Scan[/blue]", id="para_seq_scan"),
        pytest.param("Seq Scan", "🔍 [blue]Seq Scan[/blue]", id="seq_scan"),
        pytest.param("Invalid Seq Scan", "📂 [blue]Invalid Seq Scan[/blue]", id="inv_seq_scan"),
        pytest.param("Index Scan", "📖 [blue]Index Scan[/blue]", id="index_scan"),
        pytest.param("Sort", "↕️ [bright_black]Sort[/bright_black]", id="sort"),
        pytest.param("Insert", "✏️ [red]Insert[/red]", id="insert"),
    ],
)
def test_format_node_type(node_type: str, expected: str) -> None:
    # Given
    node = PlanNode(
        node_type=node_type,
        indent=0,
        target=None,
        costs=None,
        actuals=None,
    )

    # When
    result = format_node_type(node)

    # Then
    assert result == expected


def test_parse_and_format_plan() -> None:
    # Given
    plan_text = """
Index Only Scan using building_pkey on building b  (cost=0.15..0.45 rows=1 width=4) (actual time=0.003..0.003 rows=1 loops=11)
  Index Cond: (id = rb.building_id)
  Heap Fetches: 10
  Buffers: shared hit=20
Planning Time: 3.278 ms
Execution Time: 129.345 ms
"""
    expected = """
📖 [blue]Index Only Scan[/blue] using building_pkey on building b  (cost=0.15..0.45 rows=1 width=4) (actual time=0.003..0.003 rows=1 loops=11)
  Index Cond: (id = rb.building_id)
  Heap Fetches: 10
  Buffers: shared hit=20
Planning Time: 3.278 ms
Execution Time: 129.345 ms
"""

    # When
    plan = parse_text_plan(plan_text)
    result = format_plan(plan)

    # Then
    assert result.strip() == expected.strip()
