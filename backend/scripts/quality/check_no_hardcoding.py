from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

# 1. Disallowed candidate fixture strings and test literals in production code
FORBIDDEN_CANDIDATE_LITERALS = {
    "alex mercer",
    "tarun gupta",
    "jaymin patel",
    "sarah jane connor",
    "johnathan vance",
    "emily watson",
    "markus thorne",
    "robert sterling",
    "liam chen",
}

FORBIDDEN_EMAIL_FIXTURES = {
    "alex.mercer@example.com",
    "tarun.gupta@example.com",
    "jaymin.patel@example.com",
    "sarah.connor@example.com",
    "johnathan.vance@example.com",
}

# 2. Production Placeholders & Mock Data forbidden in service/app code
FORBIDDEN_PRODUCTION_PLACEHOLDERS = {
    "mock_market_demand",
    "generic_candidate_role",
    "default_business_classification",
    "dummy_score",
    "placeholder_company",
    "fake_candidate_data",
}

# 3. Decision variable patterns that require policy lookup or explicit annotation
DECISION_VAR_PATTERNS = [
    r"^threshold$",
    r".*_threshold$",
    r".*_confidence$",
    r"^top_k$",
    r"^limit$",
    r".*_limit$",
    r".*_timeout$",
    r".*_ttl$",
    r".*_batch_size$",
    r".*_interval$",
    r".*_penalty$",
    r".*_weight$",
    r".*_score_cap$",
]

OPERATIONAL_CALL_ARGUMENTS = {
    "batch_size",
    "blocking_timeout",
    "failure_ttl",
    "interval",
    "job_timeout",
    "limit",
    "result_ttl",
    "socket_connect_timeout",
    "socket_timeout",
    "temperature",
    "threshold",
    "timeout",
    "top_k",
    "top_p",
}

# 4. Approved annotation comments that allow intentional constants
APPROVED_ANNOTATIONS = {
    "# policy-approved-constant",
    "# constant-approved",
    "# policy-governed",
    "# fallback-approved",
}

# 5. Allowed numeric literals (standard math, bounds, HTTP status codes, defaults)
ALLOWED_NUMERICS = {
    0, 0.0, 1, 1.0, 2, 5, 10, 100, 100.0, 0.5, 0.1, 0.01, 1e-5, 1e-6,
    200, 201, 202, 204, 400, 401, 403, 404, 409, 422, 429, 500, 502, 503,
    60, 3600, 86400, 768, 1536,
}


class AntiHardcodingVisitor(ast.NodeVisitor):
    def __init__(self, filepath: Path, source_lines: list[str]) -> None:
        self.filepath = filepath
        self.source_lines = source_lines
        self.violations: list[str] = []

    def _line_has_annotation(self, lineno: int) -> bool:
        if 1 <= lineno <= len(self.source_lines):
            line_str = self.source_lines[lineno - 1]
            if any(ann in line_str for ann in APPROVED_ANNOTATIONS):
                return True
            # Check previous line for annotation comment
            if lineno > 1:
                prev_line = self.source_lines[lineno - 2].strip()
                if any(ann in prev_line for ann in APPROVED_ANNOTATIONS):
                    return True
        return False

    @staticmethod
    def _call_name(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return ""

    @staticmethod
    def _is_literal(node: ast.expr | None) -> bool:
        return isinstance(node, ast.Constant) and isinstance(
            node.value, (str, int, float)
        )

    def _report_decision_literal(
        self, *, lineno: int, name: str, value: object, context: str
    ) -> None:
        if self._line_has_annotation(lineno):
            return
        self.violations.append(
            f"{self.filepath}:{lineno} - Hardcoded {context} '{name}' ({value}). "
            "Use Settings/PolicyRegistry or add '# policy-approved-constant' annotation."
        )

    def _check_function_defaults(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        positional_args = [*node.args.posonlyargs, *node.args.args]
        positional_defaults = zip(
            positional_args[-len(node.args.defaults) :], node.args.defaults, strict=False
        )
        keyword_defaults = zip(
            node.args.kwonlyargs, node.args.kw_defaults, strict=False
        )
        for argument, default in [*positional_defaults, *keyword_defaults]:
            if default is None or not self._is_literal(default):
                continue
            if any(
                re.match(pattern, argument.arg, re.IGNORECASE)
                for pattern in DECISION_VAR_PATTERNS
            ):
                self._report_decision_literal(
                    lineno=default.lineno,
                    name=argument.arg,
                    value=default.value,
                    context="policy-bearing function default",
                )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_function_defaults(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_function_defaults(node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        call_name = self._call_name(node.func)
        if call_name == "Queue" and node.args and self._is_literal(node.args[0]):
            self._report_decision_literal(
                lineno=node.args[0].lineno,
                name="queue name",
                value=node.args[0].value,
                context="operational",
            )

        for keyword in node.keywords:
            if keyword.arg is None or not self._is_literal(keyword.value):
                continue
            is_retry_max = call_name == "Retry" and keyword.arg == "max"
            if keyword.arg in OPERATIONAL_CALL_ARGUMENTS or is_retry_max:
                self._report_decision_literal(
                    lineno=keyword.value.lineno,
                    name=keyword.arg,
                    value=keyword.value.value,
                    context="operational call argument",
                )

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        # Check target variable names against decision patterns
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                if any(re.match(pattern, var_name, re.IGNORECASE) for pattern in DECISION_VAR_PATTERNS):
                    # Value must be a policy lookup or annotated constant
                    if isinstance(node.value, ast.Constant) and isinstance(
                        node.value.value, (int, float)
                    ):
                        val = node.value.value
                        if val not in ALLOWED_NUMERICS and not self._line_has_annotation(node.lineno):
                            self.violations.append(
                                f"{self.filepath}:{node.lineno} - Un-annotated business decision constant assigned to '{var_name}' ({val}). "
                                f"Use PolicyRegistry or add '# policy-approved-constant' annotation."
                            )

        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            val_lower = node.value.strip().lower()

            # Check literal candidate names
            for forbidden in FORBIDDEN_CANDIDATE_LITERALS:
                if forbidden in val_lower:
                    self.violations.append(
                        f"{self.filepath}:{node.lineno} - Found hardcoded candidate fixture '{forbidden}'"
                    )

            # Check test fixture emails
            for forbidden in FORBIDDEN_EMAIL_FIXTURES:
                if forbidden in val_lower:
                    self.violations.append(
                        f"{self.filepath}:{node.lineno} - Found hardcoded test email fixture '{forbidden}'"
                    )

            # Check production placeholders
            for forbidden in FORBIDDEN_PRODUCTION_PLACEHOLDERS:
                if forbidden in val_lower:
                    self.violations.append(
                        f"{self.filepath}:{node.lineno} - Found forbidden production placeholder '{forbidden}'"
                    )

        self.generic_visit(node)


def scan_directory(target_dir: Path) -> list[str]:
    violations: list[str] = []
    if not target_dir.exists():
        return violations

    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.endswith(".py") and not file.startswith("test_"):
                file_path = Path(root) / file
                try:
                    source = file_path.read_text(encoding="utf-8")
                    source_lines = source.splitlines()
                    tree = ast.parse(source, filename=str(file_path))
                    visitor = AntiHardcodingVisitor(file_path, source_lines)
                    visitor.visit(tree)
                    violations.extend(visitor.violations)
                except Exception as exc:
                    violations.append(f"{file_path}:0 - Failed to parse AST: {exc}")
    return violations


def main() -> int:
    backend_root = Path(__file__).resolve().parents[2]
    services_dir = backend_root / "app" / "services"

    print("================================================================")
    print("🔍 AST ANTI-HARDCODING & REGRESSION QUALITY GATE")
    print("================================================================")
    print(f"Scanning: {services_dir}")

    violations = scan_directory(services_dir)

    if violations:
        print(f"\n❌ FAILED: Found {len(violations)} anti-hardcoding violation(s):")
        for v in violations:
            print(f"  • {v}")
        return 1

    print("\n✅ PASSED: No hardcoded candidate fixtures, production placeholders, or un-annotated decision constants found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
