import ast
import operator
import re
import time
from src.scripting.builtins import BUILTIN_FUNCTIONS
from src.device.device_manager import DeviceManager
from src.device.device_definition import get_device_type, DeviceType

ALLOWED_NODES = {
    ast.Expression, ast.Expr,
    ast.Constant, ast.Name, ast.Load,
    ast.UnaryOp, ast.UAdd, ast.USub, ast.Not,
    ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.BoolOp, ast.And, ast.Or,
    ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.Call,
    ast.List, ast.Tuple,
    ast.keyword,
    ast.IfExp,
}
def safe_pow(a, b):
    if isinstance(b, (int, float)) and (b > 1000 or b < -1000):
        raise TimeoutError("Exponent too large for safe evaluation")
    return a ** b


BINOP_MAP = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: safe_pow,
}
UNARYOP_MAP = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}

CMPOP_MAP = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}

DEVICE_PATTERN = re.compile(r"^([A-Za-z]+)(\d+)$")


class SafeEvaluator:
    def __init__(self, device_manager: DeviceManager | None = None, timeout: float = 0.05) -> None:
        self.device_manager = device_manager or DeviceManager()
        self.timeout = timeout
        self.elapsed: float = 0.0
        self.delta: float = 0.0
        self.tick: int = 0
        self._eval_start: float = 0.0
        self._step_count: int = 0

    def evaluate(self, expr: str) -> object:
        self._eval_start = time.monotonic()
        self._step_count = 0
        tree = ast.parse(expr, mode="eval")
        self._check(tree)
        return self._eval(tree.body)

    def _check(self, node: ast.AST) -> None:
        count = 0
        for child in ast.walk(node):
            count += 1
            if count > 500:
                raise TimeoutError("Expression AST too complex")
            if type(child) not in ALLOWED_NODES:
                raise ValueError(f"Node type not allowed: {type(child).__name__}")
            if isinstance(child, ast.Call):
                func_name = child.func.id if isinstance(child.func, ast.Name) else None
                if func_name not in BUILTIN_FUNCTIONS:
                    raise ValueError(f"Function not allowed: {func_name}")
    def _eval(self, node: ast.AST) -> object:
        self._step_count += 1
        if self._step_count % 8 == 0 or time.monotonic() - self._eval_start > self.timeout:
            if time.monotonic() - self._eval_start > self.timeout:
                raise TimeoutError(f"Expression evaluation timed out ({self.timeout}s exceeded)")
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Name):
            return self._resolve_name(node.id)
        elif isinstance(node, ast.UnaryOp):
            op = UNARYOP_MAP[type(node.op)]
            return op(self._eval(node.operand))
        elif isinstance(node, ast.BinOp):
            op = BINOP_MAP[type(node.op)]
            return op(self._eval(node.left), self._eval(node.right))
        elif isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                result = self._eval(node.values[0])
                for v in node.values[1:]:
                    result = result and self._eval(v)
                return result
            else:
                result = self._eval(node.values[0])
                for v in node.values[1:]:
                    result = result or self._eval(v)
                return result
        elif isinstance(node, ast.Compare):
            left = self._eval(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = self._eval(comparator)
                cmp_op = CMPOP_MAP[type(op)]
                if not cmp_op(left, right):
                    return False
                left = right
            return True
        elif isinstance(node, ast.Call):
            func_name = node.func.id if isinstance(node.func, ast.Name) else None
            if func_name not in BUILTIN_FUNCTIONS:
                raise ValueError(f"Function not allowed: {func_name}")
            args = [self._eval(a) for a in node.args]
            kwargs = {kw.arg: self._eval(kw.value) for kw in node.keywords}
            return BUILTIN_FUNCTIONS[func_name](*args, **kwargs)
        elif isinstance(node, ast.IfExp):
            test = self._eval(node.test)
            return self._eval(node.body) if test else self._eval(node.orelse)
        elif isinstance(node, (ast.List, ast.Tuple)):
            els = [self._eval(e) for e in node.elts]
            return els if isinstance(node, ast.List) else tuple(els)
        else:
            raise ValueError(f"Cannot evaluate node: {type(node).__name__}")

    def _resolve_name(self, name: str) -> object:
        if name == "t":
            return self.elapsed
        elif name == "dt":
            return self.delta
        elif name == "tick":
            return self.tick
        m = DEVICE_PATTERN.match(name)
        if m:
            dev_type = m.group(1).upper()
            addr = int(m.group(2))
            dtype = get_device_type(dev_type)
            if dtype == DeviceType.BIT:
                return 1 if self.device_manager.read_bit(dev_type, addr) else 0
            else:
                return self.device_manager.read_word(dev_type, addr)
        raise ValueError(f"Unknown variable: {name}")
