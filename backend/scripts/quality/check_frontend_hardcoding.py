from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Forbidden candidate fixtures and production placeholders in frontend code
FORBIDDEN_FRONTEND_LITERALS = {
    "alex.mercer@example.com",
    "tarun.gupta@example.com",
    "jaymin.patel@example.com",
    "sarah.connor@example.com",
    "johnathan.vance@example.com",
    "mock_market_demand",
    "generic_candidate_role",
    "default_business_classification",
    "dummy_score",
    "fake_candidate_data",
}

# Decision threshold variables in frontend code requiring explicit policy annotation or API source
DECISION_VAR_PATTERNS = [
    r".*_threshold\s*=\s*\d+",
    r".*_confidence\s*=\s*\d+",
    r"top_k\s*=\s*\d+",
]

APPROVED_ANNOTATIONS = {
    "// policy-approved-constant",
    "/* policy-approved-constant */",
    "// constant-approved",
    "// policy-governed",
}


def scan_frontend_directory(target_dir: Path) -> list[str]:
    violations: list[str] = []
    if not target_dir.exists():
        return violations

    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.endswith((".ts", ".tsx", ".js", ".jsx")) and not file.endswith((".test.ts", ".test.tsx", ".spec.ts")):
                file_path = Path(root) / file
                try:
                    lines = file_path.read_text(encoding="utf-8").splitlines()
                    for idx, line in enumerate(lines, 1):
                        line_lower = line.lower()
                        # 1. Check forbidden literals
                        for forbidden in FORBIDDEN_FRONTEND_LITERALS:
                            if forbidden in line_lower:
                                violations.append(
                                    f"{file_path}:{idx} - Found forbidden fixture/placeholder '{forbidden}' in UI code"
                                )

                        # 2. Check un-annotated decision variable assignments
                        for pattern in DECISION_VAR_PATTERNS:
                            if re.search(pattern, line, re.IGNORECASE):
                                if not any(ann in line for ann in APPROVED_ANNOTATIONS):
                                    # Check preceding line
                                    prev_has_ann = idx > 1 and any(ann in lines[idx - 2] for ann in APPROVED_ANNOTATIONS)
                                    if not prev_has_ann:
                                        violations.append(
                                            f"{file_path}:{idx} - Found un-annotated decision constant assignment. "
                                            f"Use backend policy endpoint or add '// policy-approved-constant'."
                                        )
                except Exception as exc:
                    violations.append(f"{file_path}:0 - Failed to read file: {exc}")
    return violations


def main() -> int:
    backend_root = Path(__file__).resolve().parents[2]
    frontend_src = backend_root.parent / "frontend" / "src"

    print("================================================================")
    print("🔍 FRONTEND UI ANTI-HARDCODING QUALITY GATE")
    print("================================================================")
    print(f"Scanning: {frontend_src}")

    violations = scan_frontend_directory(frontend_src)

    if violations:
        print(f"\n❌ FAILED: Found {len(violations)} frontend anti-hardcoding violation(s):")
        for v in violations:
            print(f"  • {v}")
        return 1

    print("\n✅ PASSED: No hardcoded candidate fixtures or forbidden placeholders found in frontend UI code.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
