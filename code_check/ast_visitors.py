"""
ast_visitors.py
───────────────
Core AST visitor hierarchy for the static analysis engine.

All visitors extend ast.NodeVisitor and are designed to be composed
by the MetricsOrchestrator.  None of them modify the tree.

Visitors implemented:
  • ScopeVisitor          – builds a scope table (functions / classes / modules)
  • CyclomaticVisitor     – V(G) = E - N + 2P  (decision-point counting variant)
  • HalsteadVisitor       – operator / operand frequency tables
  • LOCVisitor            – logical + physical lines, comment ratio
  • DependencyVisitor     – import graph + coupling metrics
  • NestingVisitor        – max / average nesting depth per scope
  • CohesionVisitor       – LCOM4 approximation via shared-attribute graph
"""

from __future__ import annotations

import ast
import math
import textwrap
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


# ──────────────────────────────────────────────────────────────────────────────
# Data containers
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ScopeInfo:
    name: str
    kind: str                        # 'function' | 'class' | 'module'
    lineno: int
    end_lineno: int
    parent: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    args: List[str] = field(default_factory=list)


@dataclass
class CyclomaticResult:
    scope: str
    complexity: int                  # V(G)
    decision_points: List[Tuple[str, int]] = field(default_factory=list)
    # (node_type, lineno)


@dataclass
class HalsteadRaw:
    scope: str
    operators: Dict[str, int] = field(default_factory=dict)
    operands: Dict[str, int] = field(default_factory=dict)

    # ── derived properties ────────────────────────────────────────────────────
    @property
    def n1(self) -> int:   return len(self.operators)        # distinct operators
    @property
    def n2(self) -> int:   return len(self.operands)         # distinct operands
    @property
    def N1(self) -> int:   return sum(self.operators.values())
    @property
    def N2(self) -> int:   return sum(self.operands.values())
    @property
    def vocabulary(self) -> int: return self.n1 + self.n2
    @property
    def length(self) -> int:     return self.N1 + self.N2
    @property
    def estimated_length(self) -> float:
        n1, n2 = self.n1, self.n2
        return (n1 * math.log2(n1) if n1 > 0 else 0) + \
               (n2 * math.log2(n2) if n2 > 0 else 0)
    @property
    def volume(self) -> float:
        v = self.vocabulary
        return self.length * math.log2(v) if v > 1 else 0.0
    @property
    def difficulty(self) -> float:
        return (self.n1 / 2) * (self.N2 / self.n2) if self.n2 > 0 else 0.0
    @property
    def effort(self) -> float:
        return self.difficulty * self.volume
    @property
    def time_to_program(self) -> float:   # seconds
        return self.effort / 18.0
    @property
    def delivered_bugs(self) -> float:
        return self.volume / 3000.0


@dataclass
class LOCResult:
    scope: str
    physical_lines: int = 0
    logical_lines: int = 0
    blank_lines: int = 0
    comment_lines: int = 0
    docstring_lines: int = 0

    @property
    def comment_ratio(self) -> float:
        return self.comment_lines / self.physical_lines \
               if self.physical_lines > 0 else 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Operator / operand classification tables
# ──────────────────────────────────────────────────────────────────────────────

_OPERATOR_NODES = {
    # Binary operators
    ast.Add: '+',  ast.Sub: '-',  ast.Mult: '*',  ast.Div: '/',
    ast.FloorDiv: '//',  ast.Mod: '%',  ast.Pow: '**',
    ast.BitAnd: '&',  ast.BitOr: '|',  ast.BitXor: '^',
    ast.LShift: '<<',  ast.RShift: '>>',
    ast.MatMult: '@',
    # Unary operators
    ast.UAdd: 'u+',  ast.USub: 'u-',  ast.Invert: '~',  ast.Not: 'not',
    # Boolean operators
    ast.And: 'and',  ast.Or: 'or',
    # Comparison operators
    ast.Eq: '==',  ast.NotEq: '!=',  ast.Lt: '<',  ast.LtE: '<=',
    ast.Gt: '>',   ast.GtE: '>=',   ast.Is: 'is', ast.IsNot: 'is not',
    ast.In: 'in',  ast.NotIn: 'not in',
}

# Decision-point node types for cyclomatic complexity
_DECISION_NODES = (
    ast.If, ast.While, ast.For, ast.AsyncFor,
    ast.ExceptHandler, ast.With, ast.AsyncWith,
    ast.Assert, ast.comprehension,
)


# ──────────────────────────────────────────────────────────────────────────────
# 1. ScopeVisitor
# ──────────────────────────────────────────────────────────────────────────────

class ScopeVisitor(ast.NodeVisitor):
    """
    First-pass visitor: builds an ordered list of ScopeInfo records.
    The scope name uses dot-notation (ClassName.method_name).
    """

    def __init__(self) -> None:
        self.scopes: List[ScopeInfo] = []
        self._stack: List[str] = []

    def _current_scope(self) -> str:
        return '.'.join(self._stack) if self._stack else '<module>'

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._enter_scope(node, 'function')

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._enter_scope(node, 'class')

    def _enter_scope(self, node: ast.AST, kind: str) -> None:
        parent = self._current_scope()
        decorators = [ast.unparse(d) for d in getattr(node, 'decorator_list', [])]
        args = []
        if hasattr(node, 'args'):
            a = node.args
            args = [arg.arg for arg in a.args + a.posonlyargs + a.kwonlyargs]

        self._stack.append(node.name)
        scope_name = self._current_scope()

        self.scopes.append(ScopeInfo(
            name=scope_name,
            kind=kind,
            lineno=node.lineno,
            end_lineno=getattr(node, 'end_lineno', node.lineno),
            parent=parent,
            decorators=decorators,
            args=args,
        ))
        self.generic_visit(node)
        self._stack.pop()


# ──────────────────────────────────────────────────────────────────────────────
# 2. CyclomaticVisitor  –  V(G) = Σ decision-points + 1
# ──────────────────────────────────────────────────────────────────────────────

class CyclomaticVisitor(ast.NodeVisitor):
    """
    Computes Cyclomatic Complexity (McCabe, 1976) per function/method.

    Formula (decision-point variant):
        V(G) = number of binary decision points + 1

    Boolean short-circuit operators (and / or) each add one branch,
    matching the industry convention used by tools like McCabe's complexity.
    """

    def __init__(self) -> None:
        self.results: List[CyclomaticResult] = []
        self._stack: List[CyclomaticResult] = []

    def _push(self, name: str) -> None:
        self._stack.append(CyclomaticResult(scope=name, complexity=1))

    def _pop(self) -> CyclomaticResult:
        result = self._stack.pop()
        self.results.append(result)
        return result

    def _increment(self, node_type: str, lineno: int) -> None:
        if self._stack:
            top = self._stack[-1]
            top.complexity += 1
            top.decision_points.append((node_type, lineno))

    # ── Scope entry/exit ─────────────────────────────────────────────────────

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        qual = f"{self._stack[-1].scope}.{node.name}" if self._stack else node.name
        self._push(qual)
        self.generic_visit(node)
        self._pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    # ── Decision nodes ───────────────────────────────────────────────────────

    def visit_If(self, node: ast.If) -> None:
        self._increment('if', node.lineno)
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self._increment('while', node.lineno)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self._increment('for', node.lineno)
        self.generic_visit(node)

    visit_AsyncFor = visit_For

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self._increment('except', node.lineno)
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        self._increment('assert', node.lineno)
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self._increment('comprehension', 0)
        # visit ifs within comprehension
        for cond in node.ifs:
            self._increment('comp_if', getattr(cond, 'lineno', 0))
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        # Each extra operand in and/or is a decision branch
        branches = len(node.values) - 1
        op_name = 'and' if isinstance(node.op, ast.And) else 'or'
        for _ in range(branches):
            self._increment(op_name, node.lineno)
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self._increment('ternary', node.lineno)
        self.generic_visit(node)


# ──────────────────────────────────────────────────────────────────────────────
# 3. HalsteadVisitor
# ──────────────────────────────────────────────────────────────────────────────

class HalsteadVisitor(ast.NodeVisitor):
    """
    Collects Halstead operator and operand counts per function scope.

    Operators  : arithmetic, bitwise, boolean, comparison, augmented assignment,
                 built-in keywords (return, yield, del, raise, pass …), call '()'
    Operands   : Name nodes, Constant literals, attribute accesses
    """

    def __init__(self) -> None:
        self.results: List[HalsteadRaw] = []
        self._stack: List[HalsteadRaw] = []

    def _current(self) -> Optional[HalsteadRaw]:
        return self._stack[-1] if self._stack else None

    def _add_op(self, symbol: str) -> None:
        r = self._current()
        if r:
            r.operators[symbol] = r.operators.get(symbol, 0) + 1

    def _add_operand(self, symbol: str) -> None:
        r = self._current()
        if r:
            r.operands[symbol] = r.operands.get(symbol, 0) + 1

    # ── Scope management ─────────────────────────────────────────────────────

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        qual = f"{self._stack[-1].scope}.{node.name}" if self._stack else node.name
        raw = HalsteadRaw(scope=qual)
        self._stack.append(raw)
        self.generic_visit(node)
        self.results.append(self._stack.pop())

    visit_AsyncFunctionDef = visit_FunctionDef

    # ── Operator nodes ───────────────────────────────────────────────────────

    def visit_BinOp(self, node: ast.BinOp) -> None:
        sym = _OPERATOR_NODES.get(type(node.op), '?')
        self._add_op(sym)
        self.generic_visit(node)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
        sym = _OPERATOR_NODES.get(type(node.op), '?')
        self._add_op(sym)
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        sym = _OPERATOR_NODES.get(type(node.op), '?')
        for _ in range(len(node.values) - 1):
            self._add_op(sym)
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        for op in node.ops:
            sym = _OPERATOR_NODES.get(type(op), '?')
            self._add_op(sym)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        sym = _OPERATOR_NODES.get(type(node.op), '?') + '='
        self._add_op(sym)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        self._add_op('=')
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._add_op(':=')
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        self._add_op('()')
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        self._add_op('[]')
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        self._add_op('return')
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise) -> None:
        self._add_op('raise')
        self.generic_visit(node)

    def visit_Yield(self, node: ast.Yield) -> None:
        self._add_op('yield')
        self.generic_visit(node)

    def visit_YieldFrom(self, node: ast.YieldFrom) -> None:
        self._add_op('yield from')
        self.generic_visit(node)

    def visit_Delete(self, node: ast.Delete) -> None:
        self._add_op('del')
        self.generic_visit(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._add_op('lambda')
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self._add_op('if_expr')
        self.generic_visit(node)

    # ── Operand nodes ────────────────────────────────────────────────────────

    def visit_Name(self, node: ast.Name) -> None:
        self._add_operand(node.id)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        self._add_operand(repr(node.value))
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self._add_operand(node.attr)
        # do NOT call generic_visit – we don't want to double-count the Name
        # that holds the object; we handle it above.
        # We still need to visit nested attributes though:
        if isinstance(node.value, ast.Attribute):
            self.visit(node.value)


# ──────────────────────────────────────────────────────────────────────────────
# 4. LOCVisitor
# ──────────────────────────────────────────────────────────────────────────────

class LOCVisitor(ast.NodeVisitor):
    """
    Counts lines of code metrics per function/class scope using source lines.
    Physical LOC counting is done directly on source text slices;
    this visitor only resolves scope boundaries from the AST.
    """

    def __init__(self, source_lines: List[str]) -> None:
        self._lines = source_lines
        self.results: List[LOCResult] = []
        self._stack: List[LOCResult] = []

    def _push(self, name: str) -> None:
        self._stack.append(LOCResult(scope=name))

    def _pop(self) -> LOCResult:
        r = self._stack.pop()
        self.results.append(r)
        return r

    def _analyse_lines(self, start: int, end: int, result: LOCResult) -> None:
        """Populate result from a slice of source_lines (1-based inclusive)."""
        in_docstring = False
        for raw in self._lines[start - 1: end]:
            stripped = raw.strip()
            result.physical_lines += 1
            if not stripped:
                result.blank_lines += 1
                continue
            if stripped.startswith(('"""', "'''", 'r"""', "r'''")):
                in_docstring = not in_docstring
                result.docstring_lines += 1
                continue
            if in_docstring:
                result.docstring_lines += 1
                continue
            if stripped.startswith('#'):
                result.comment_lines += 1
                continue
            result.logical_lines += 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        qual = '.'.join([r.scope for r in self._stack] + [node.name])
        self._push(qual)
        end = getattr(node, 'end_lineno', node.lineno)
        self._analyse_lines(node.lineno, end, self._stack[-1])
        self.generic_visit(node)
        self._pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qual = '.'.join([r.scope for r in self._stack] + [node.name])
        self._push(qual)
        end = getattr(node, 'end_lineno', node.lineno)
        self._analyse_lines(node.lineno, end, self._stack[-1])
        self.generic_visit(node)
        self._pop()


# ──────────────────────────────────────────────────────────────────────────────
# 5. NestingVisitor
# ──────────────────────────────────────────────────────────────────────────────

_NESTING_NODES = (
    ast.If, ast.For, ast.While, ast.AsyncFor,
    ast.With, ast.AsyncWith, ast.Try, ast.ExceptHandler,
)


class NestingVisitor(ast.NodeVisitor):
    """
    Tracks nesting depth per function scope.
    Reports max_depth and average_depth.
    """

    def __init__(self) -> None:
        self.results: Dict[str, Dict] = {}
        self._func_stack: List[str] = []
        self._depth_counter: int = 0
        self._depth_samples: List[int] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        qual = '.'.join(self._func_stack + [node.name])
        self._func_stack.append(node.name)
        prev_samples = self._depth_samples
        prev_depth = self._depth_counter
        self._depth_samples = []
        self._depth_counter = 0

        self.generic_visit(node)

        max_d = max(self._depth_samples) if self._depth_samples else 0
        avg_d = (sum(self._depth_samples) / len(self._depth_samples)
                 if self._depth_samples else 0.0)
        self.results[qual] = {'max_depth': max_d, 'avg_depth': round(avg_d, 2)}

        self._depth_samples = prev_samples
        self._depth_counter = prev_depth
        self._func_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def _visit_block(self, node: ast.AST) -> None:
        self._depth_counter += 1
        self._depth_samples.append(self._depth_counter)
        self.generic_visit(node)
        self._depth_counter -= 1

    def visit_If(self, node):      self._visit_block(node)
    def visit_For(self, node):     self._visit_block(node)
    def visit_While(self, node):   self._visit_block(node)
    def visit_AsyncFor(self, node): self._visit_block(node)
    def visit_With(self, node):    self._visit_block(node)
    def visit_AsyncWith(self, node): self._visit_block(node)
    def visit_Try(self, node):     self._visit_block(node)
    def visit_ExceptHandler(self, node): self._visit_block(node)


# ──────────────────────────────────────────────────────────────────────────────
# 6. DependencyVisitor
# ──────────────────────────────────────────────────────────────────────────────

class DependencyVisitor(ast.NodeVisitor):
    """
    Collects:
      • imports (module-level & local)
      • afferent/efferent coupling per class
      • fan-in / fan-out call graph approximation
    """

    def __init__(self) -> None:
        self.imports: List[Dict] = []
        self.calls: Dict[str, List[str]] = defaultdict(list)   # scope → [callee]
        self._scope_stack: List[str] = []

    def _scope(self) -> str:
        return '.'.join(self._scope_stack) or '<module>'

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append({
                'module': alias.name,
                'alias': alias.asname,
                'kind': 'import',
                'lineno': node.lineno,
            })
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ''
        for alias in node.names:
            self.imports.append({
                'module': f"{module}.{alias.name}",
                'alias': alias.asname,
                'kind': 'from_import',
                'lineno': node.lineno,
            })
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        callee = self._resolve_callee(node.func)
        if callee:
            self.calls[self._scope()].append(callee)
        self.generic_visit(node)

    @staticmethod
    def _resolve_callee(func_node: ast.AST) -> Optional[str]:
        if isinstance(func_node, ast.Name):
            return func_node.id
        if isinstance(func_node, ast.Attribute):
            return func_node.attr
        return None


# ──────────────────────────────────────────────────────────────────────────────
# 7. CohesionVisitor  (LCOM4 approximation)
# ──────────────────────────────────────────────────────────────────────────────

class CohesionVisitor(ast.NodeVisitor):
    """
    Approximates LCOM4 (Lack of Cohesion of Methods, variant 4) per class.

    LCOM4 = number of connected components in the graph where:
      - Nodes  = methods
      - Edges  = two methods share a direct attribute access (self.x)

    A value of 1 indicates perfect cohesion.
    Higher values indicate the class should potentially be split.
    """

    def __init__(self) -> None:
        self.results: Dict[str, Dict] = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        methods: List[str] = []
        method_attrs: Dict[str, Set[str]] = {}

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(item.name)
                method_attrs[item.name] = self._collect_self_attrs(item)

        lcom4 = self._compute_lcom4(methods, method_attrs)
        self.results[node.name] = {
            'lcom4': lcom4,
            'method_count': len(methods),
            'shared_attr_pairs': self._shared_pairs(methods, method_attrs),
        }
        self.generic_visit(node)

    @staticmethod
    def _collect_self_attrs(func_node: ast.FunctionDef) -> Set[str]:
        attrs: Set[str] = set()
        first_arg = None
        if func_node.args.args:
            first_arg = func_node.args.args[0].arg
        for n in ast.walk(func_node):
            if isinstance(n, ast.Attribute):
                if isinstance(n.value, ast.Name) and n.value.id == first_arg:
                    attrs.add(n.attr)
        return attrs

    @staticmethod
    def _shared_pairs(
        methods: List[str],
        attrs: Dict[str, Set[str]],
    ) -> List[Tuple[str, str]]:
        pairs = []
        for i, m1 in enumerate(methods):
            for m2 in methods[i + 1:]:
                if attrs.get(m1, set()) & attrs.get(m2, set()):
                    pairs.append((m1, m2))
        return pairs

    def _compute_lcom4(
        self,
        methods: List[str],
        attrs: Dict[str, Set[str]],
    ) -> int:
        """Union-Find to count connected components."""
        parent = {m: m for m in methods}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            pa, pb = find(a), find(b)
            if pa != pb:
                parent[pa] = pb

        for i, m1 in enumerate(methods):
            for m2 in methods[i + 1:]:
                if attrs.get(m1, set()) & attrs.get(m2, set()):
                    union(m1, m2)

        if not methods:
            return 0
        return len({find(m) for m in methods})