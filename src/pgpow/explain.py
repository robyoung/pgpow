import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Self, assert_never


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


@dataclass
class Plan:
    root: PlanNode
    tail: list[str]


def parse_text_plan(data: str) -> Plan:
    lines = data.splitlines()
    lines = [line for line in lines if line.strip() != ""]
    try:
        root_node = parse_plan_line(lines[0])
    except ValueError:
        lines = clean_headers_and_borders(lines)
        root_node = parse_plan_line(lines[0])
    path_to_root = [root_node]
    tail = []

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

    return Plan(root=root_node, tail=tail)


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
        parts.append(
            f"  (cost={node.costs.startup:.2f}..{node.costs.total:.2f} rows={node.costs.rows} width={node.costs.width})"
        )

    if node.actuals:
        actuals_parts = []
        if node.actuals.startup_time is not None and node.actuals.total_time is not None:
            actuals_parts.append(f"time={node.actuals.startup_time:.3f}..{node.actuals.total_time:.3f}")
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
    match node.node_type:
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
