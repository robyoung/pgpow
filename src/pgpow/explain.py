import re
from dataclasses import dataclass, field
from enum import Enum, auto
from functools import cached_property
from typing import Callable, Self, assert_never

from rich.color import Color


@dataclass
class Costs:
    startup: float
    total: float
    rows: int
    width: int


@dataclass
class Actuals:
    startup_time: float | None
    total_time: float | None
    rows: int
    loops: int


@dataclass
class PlanNode:
    node_type: str
    indent: int
    target: str | None
    costs: Costs | None
    actuals: Actuals | None
    metadata: list[str] = field(default_factory=list)
    children: list[Self] = field(default_factory=list)

    cost_score: float | None = field(default=None, compare=False, hash=False)
    time_score: float | None = field(default=None, compare=False, hash=False)

    @cached_property
    def self_cost(self) -> float | None:
        def _stats(node: PlanNode) -> tuple[float, int] | None:
            if node.costs is None or node.costs.total is None:
                return None
            return node.costs.total, node.costs.rows

        return self._self_cost(_stats)

    @cached_property
    def self_time(self) -> float | None:
        def _stats(node: PlanNode) -> tuple[float, int] | None:
            if node.actuals is None or node.actuals.total_time is None:
                return None
            return node.actuals.total_time, node.actuals.loops

        return self._self_cost(_stats)

    @property
    def all_children(self) -> list[Self]:
        return [self, *[c2 for c1 in self.children for c2 in c1.all_children]]

    def _self_cost(
        self,
        stats_func: Callable[[Self], tuple[float, int] | None],
    ) -> float | None:
        if (self_stats := stats_func(self)) is None:
            return None
        self_total, self_rows = self_stats

        child_stats = list(filter(None, [stats_func(child) for child in self.children]))

        if not child_stats:
            return self_total

        child_totals, child_rows = zip(*child_stats)

        node_type = self.node_type

        if "Nested Loop" in node_type:
            child_total = sum(ct * cr for ct, cr in zip(child_totals, child_rows))
        elif node_type.endswith("Join"):
            if "Merge" in node_type:
                child_total = max(child_totals)
            elif "Hash" in node_type:
                child_total = sum(child_totals)
            else:
                raise ValueError(f"Unknown join type for self cost calculation: {node_type}")
        else:
            child_total = sum(child_totals)

        return self_total - child_total


@dataclass
class Plan:
    root: PlanNode
    tail: list[str]

    @cached_property
    def min_cost(self) -> float:
        return min(cost for node in self.root.all_children if (cost := node.self_cost) is not None)

    @cached_property
    def max_cost(self) -> float:
        return max(cost for node in self.root.all_children if (cost := node.self_cost) is not None)

    def cost_score(self, cost: float) -> float:
        if self.max_cost == self.min_cost:
            return 1.0

        return (cost - self.min_cost) / (self.max_cost - self.min_cost)

    @cached_property
    def min_time(self) -> float | None:
        return min((time for node in self.root.all_children if (time := node.self_time) is not None), default=None)

    @cached_property
    def max_time(self) -> float | None:
        if self.root.actuals is None:
            return None
        return max((time for node in self.root.all_children if (time := node.self_time) is not None), default=None)

    def time_score(self, time: float) -> float:
        assert self.min_time is not None and self.max_time is not None
        if self.max_time == self.min_time:
            return 1.0
        return (time - self.min_time) / (self.max_time - self.min_time)

    def add_scores(self) -> None:
        for node in self.root.all_children:
            if (cost := node.self_cost) is not None:
                node.cost_score = self.cost_score(cost)
            if (time := node.self_time) is not None:
                node.time_score = self.time_score(time)


def calculate_colour(score: float) -> tuple[int, int, int]:
    parts: tuple[float | int, float | int, float | int]
    if score < 0.5:
        score = score / 0.5
        parts = (255 * score, 255, 0)
        return _tweak_brightness(parts, 0.9)
    else:
        score = (score - 0.5) / 0.5
        parts = (255, 255 * (1 - score), 0)
        return _tweak_brightness(parts, 1)


def _tweak_brightness(colour: tuple[float | int, float | int, float | int], brightness: float) -> tuple[int, int, int]:
    return (
        int(colour[0] * brightness),
        int(colour[1] * brightness),
        int(colour[2] * brightness),
    )


def parse_text_plan(data: str) -> Plan:
    lines = data.splitlines()
    lines = [line for line in lines if line.strip() != ""]
    try:
        root_node = parse_plan_line(lines[0])
    except ValueError:
        lines = clean_headers_and_borders(lines)
        root_node = parse_plan_line(lines[0])
    path_to_root = [root_node]
    tail: list[str] = []

    for line in lines[1:]:
        if not line.startswith(" ") or len(tail) > 0:
            if line.endswith(" rows)"):
                continue
            tail.append(line)
        elif IS_PLAN_LINE_PAT.match(line):
            # new plan node
            new_node = parse_plan_line(line)
            if new_node.indent > path_to_root[-1].indent:
                # child node
                path_to_root[-1].children.append(new_node)
                path_to_root.append(new_node)
            else:
                # sibling or ancestor's sibling
                while new_node.indent <= path_to_root[-1].indent:
                    path_to_root.pop()
                path_to_root[-1].children.append(new_node)
                path_to_root.append(new_node)
        else:
            # metadata line
            path_to_root[-1].metadata.append(line.strip())

    plan = Plan(root=root_node, tail=tail)
    plan.add_scores()
    return plan


def clean_headers_and_borders(lines: list[str]) -> list[str]:
    found_separator = False
    for i, line in enumerate(lines):
        if line.strip() == "":
            continue
        if found_separator:
            new_lines = lines[i:]
            indented = len(line) - len(line.lstrip())
            if indented > 0:
                return [line[indented:] for line in new_lines]
            else:
                return new_lines
        elif all(c == "-" for c in line.strip()):
            found_separator = True
            continue
    return lines


IS_PLAN_LINE_PAT = re.compile(r"^(\s+->\s+)?[A-Z]")
COSTS_PAT = re.compile(
    r"""
    \(cost=(?P<startup>[\d.]+)\.\.(?P<total>[\d.]+)
    \srows=(?P<rows>\d+)
    \swidth=(?P<width>\d+)\)
    """,
    re.VERBOSE,
)
ACTUALS_PAT = re.compile(
    r"""
    \(actual(?:\stime=(?P<startup>[\d.]+)\.\.(?P<total>[\d.]+))?
    \srows=(?P<rows>\d+)
    \sloops=(?P<loops>\d+)\)
    """,
    re.VERBOSE,
)


def parse_plan_line(line: str) -> PlanNode:
    if not (match := IS_PLAN_LINE_PAT.match(line)):
        raise ValueError(f"Not a plan line: {line}")

    indent_text = match.group(1)
    if indent_text is None:
        indent = 0
    else:
        line = line.removeprefix(indent_text)

        if len(indent_text) % 6 != 0:
            raise ValueError(f"Invalid indentation: {indent_text!r}")

        indent = len(indent_text) // 6

    if match := COSTS_PAT.search(line):
        costs = Costs(
            startup=float(match.group("startup")),
            total=float(match.group("total")),
            rows=int(match.group("rows")),
            width=int(match.group("width")),
        )
        line = line[: match.start()] + line[match.end() :]
    else:
        costs = None

    if match := ACTUALS_PAT.search(line):
        actuals = Actuals(
            startup_time=float(match.group("startup")) if match.group("startup") else None,
            total_time=float(match.group("total")) if match.group("total") else None,
            rows=int(match.group("rows")),
            loops=int(match.group("loops")),
        )
        line = line[: match.start()] + line[match.end() :]
    else:
        actuals = None

    node_type = line.split(" using ")[0].split(" on ")[0].strip()
    if not node_type:
        raise ValueError(f"Could not parse node type from line: {line}")

    target = line[len(node_type) :].strip() or None

    return PlanNode(
        node_type=node_type,
        indent=indent,
        target=target,
        costs=costs,
        actuals=actuals,
        metadata=[],
        children=[],
    )


def format_plan(plan: Plan) -> str:
    lines = [
        *format_plan_node(plan.root),
        *plan.tail,
    ]
    return "\n".join(lines)


def format_plan_node(node: PlanNode) -> list[str]:
    lines = [
        format_plan_line(node),
        *format_metadata(node),
        *format_children(node),
    ]

    return lines


def format_plan_line(node: PlanNode) -> str:
    if node.indent > 0:
        indent = "      " * (node.indent - 1) + "  ->  "
    else:
        indent = ""

    parts = [f"{indent}{format_node_type(node)}"]

    if node.target:
        parts.append(f" {node.target}")

    if node.costs:
        cost_range = f"{node.costs.startup:.2f}..{node.costs.total:.2f}"

        if (cost_score := node.cost_score) is not None:
            cost_colour = Color.from_rgb(*calculate_colour(cost_score))
            cost_range = f"[bold {cost_colour.name}]{cost_range}[/]"

        parts.append(f"  (cost={cost_range} rows={node.costs.rows} width={node.costs.width})")

    if node.actuals:
        actuals_parts = []
        if node.actuals.startup_time is not None and node.actuals.total_time is not None:
            time_range = f"{node.actuals.startup_time:.3f}..{node.actuals.total_time:.3f}"
            if (time_score := node.time_score) is not None:
                time_colour = Color.from_rgb(*calculate_colour(time_score))
                time_range = f"[bold {time_colour.name}]{time_range}[/]"

            actuals_parts.append(f"time={time_range}")
        actuals_parts.append(f"rows={node.actuals.rows}")
        actuals_parts.append(f"loops={node.actuals.loops}")
        parts.append(f" (actual {' '.join(actuals_parts)})")

    return "".join(parts)


def format_metadata(node: PlanNode) -> list[str]:
    indent = ("      " * node.indent) + "  "
    return [f"{indent}{line}" for line in node.metadata]


def format_children(node: PlanNode) -> list[str]:
    lines = []
    for child in node.children:
        lines.extend(format_plan_node(child))
    return lines


def format_node_type(node: PlanNode) -> str:
    icon = get_node_type_icon(node)
    colour = get_node_type_colour(node)

    return f"{icon} [{colour}]{node.node_type}[/{colour}]"  # Reset colour at end


class NodeTypeGroup(Enum):
    data_retrieval = auto()
    join = auto()
    aggregation = auto()
    modification = auto()
    utility = auto()


def get_node_type_group(node: PlanNode) -> NodeTypeGroup:
    if "Scan" in node.node_type:
        return NodeTypeGroup.data_retrieval
    if "Join" in node.node_type or "Nested Loop" in node.node_type:
        return NodeTypeGroup.join
    if any(sub in node.node_type for sub in ("Aggregate", "Group", "SetOp", "WindowAgg", "Unique")):
        return NodeTypeGroup.aggregation
    if any(sub in node.node_type for sub in ("Insert", "Update", "Delete")) or node.node_type == "Merge":
        return NodeTypeGroup.modification
    return NodeTypeGroup.utility


def get_node_type_icon(node: PlanNode) -> str:
    match node.node_type.lstrip("Parallel "):
        case "Seq Scan":
            return "🔍"
        case "Index Scan" | "Index Only Scan":
            return "📖"
        case "Bitmap Heap Scan":
            return "🧺"
        case "Merge Join":
            return "🔀"
        case "Sort":
            return "↕️"
        case "Limit":
            return "🛑"
        case "Materialize":
            return "📦"
        case "Gather":
            return "🌐"
        case "Hash":
            return "🏗️"

    if node.node_type.startswith("Nested Loop"):
        return "🔁"

    if node.node_type.startswith("Hash ") and node.node_type.endswith(" Join"):
        return "🔢"

    match group := get_node_type_group(node):
        case NodeTypeGroup.data_retrieval:
            return "📂"
        case NodeTypeGroup.join:
            return "🔗"
        case NodeTypeGroup.aggregation:
            return "📊"
        case NodeTypeGroup.modification:
            return "✏️"
        case NodeTypeGroup.utility:
            return "⚙️"
        case _:
            assert_never(group)


def get_node_type_colour(node: PlanNode) -> str:
    match group := get_node_type_group(node):
        case NodeTypeGroup.data_retrieval:
            return "blue"
        case NodeTypeGroup.join:
            return "purple"
        case NodeTypeGroup.aggregation:
            return "green"
        case NodeTypeGroup.modification:
            return "red"
        case NodeTypeGroup.utility:
            return "bright_black"
        case _:
            assert_never(group)
