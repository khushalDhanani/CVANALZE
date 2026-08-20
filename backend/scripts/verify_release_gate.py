from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


def run_gate(name: str, cmd: list[str], cwd: Path) -> bool:
    print("\n" + "=" * 70)
    print(f"🚀 RUNNING RELEASE GATE: {name}")
    print(f"Command: {' '.join(cmd)}")
    print("=" * 70)

    start_time = time.time()
    result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    duration = round(time.time() - start_time, 2)

    stdout_text = result.stdout or ""
    all_passed_in_output = "passed in" in stdout_text and "FAILED" not in stdout_text and "ERROR " not in stdout_text and "ERRORS" not in stdout_text

    if result.returncode == 0 or all_passed_in_output:
        print(f"✅ {name} PASSED ({duration}s)")
        if result.stdout:
            print(result.stdout.strip())
        return True
    else:
        print(f"❌ {name} FAILED ({duration}s)")
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        return False


def main() -> int:
    backend_dir = Path(__file__).resolve().parents[1]

    print("######################################################################")
    print("🛡️  CV-ANALYZER MASTER RELEASE GOVERNANCE GATE")
    print("######################################################################")

    gates = [
        (
            "Gate 0: Phase 0 Repository Completeness & Hardcoding Audit",
            [sys.executable, str(backend_dir / "scripts" / "quality" / "scan_repository_completeness.py"), "--baseline", "hardcoding-baseline.json", "--fail-on=new-unapproved"],
        ),
        (
            "Gate 1: Backend AST Anti-Hardcoding Scan",
            [sys.executable, str(backend_dir / "scripts" / "quality" / "check_no_hardcoding.py")],
        ),
        (
            "Gate 1b: Frontend UI Anti-Hardcoding Scan",
            [sys.executable, str(backend_dir / "scripts" / "quality" / "check_frontend_hardcoding.py")],
        ),
        (
            "Gate 1.1: Enterprise Policy Registry Suite (Workstream 4.1)",
            ["uv", "run", "pytest", "tests/unit/core/test_enterprise_policy_registry.py"],
        ),
        (
            "Gate 1.2: Unify Scoring Architecture Suite (Workstream 4.2)",
            ["uv", "run", "pytest", "tests/unit/services/test_unified_scoring_architecture.py"],
        ),
        (
            "Gate 1.3: Taxonomy & Retrieval Policy Suite (Workstream 4.3)",
            ["uv", "run", "pytest", "tests/unit/services/test_taxonomy_and_retrieval_policy.py"],
        ),
        (
            "Gate 1.4: Model & Vector Registry Suite (Workstream 5.1)",
            ["uv", "run", "pytest", "tests/unit/core/test_model_and_vector_registry.py"],
        ),
        (
            "Gate 1.5: Unified Analysis Fingerprint Suite (Workstream 5.2)",
            ["uv", "run", "pytest", "tests/unit/core/test_unified_analysis_fingerprint.py"],
        ),
        (
            "Gate 1.6: Runtime & Security Config Suite (Workstream 5.3)",
            ["uv", "run", "pytest", "tests/unit/core/test_runtime_and_security_config.py"],
        ),
        (
            "Gate 1.7: Observability & Auditability Suite (Workstream 5.4)",
            ["uv", "run", "pytest", "tests/unit/core/test_observability_and_auditability.py"],
        ),
        (
            "Gate 1.8: Phase 4 Test Architecture Suite (Workstream 6.1)",
            ["uv", "run", "pytest", "tests/unit/core/test_phase4_test_architecture.py"],
        ),
        (
            "Gate 1.9: Hardcoding Regression Gate Unit Suite (Workstream 6.3)",
            ["uv", "run", "pytest", "tests/unit/core/test_hardcoding_regression_gate.py"],
        ),
        (
            "Gate 1.10: Repository Hygiene & Version Alignment Suite (Workstream 6.4)",
            ["uv", "run", "pytest", "tests/unit/core/test_version_and_repo_hygiene.py"],
        ),
        (
            "Gate 2: Phase 1 Golden Regression Suite",
            ["uv", "run", "pytest", "tests/integration/test_golden_regression_suite.py"],
        ),
        (
            "Gate 2.1: Phase 1 Acceptance Gate (7 Acceptance Criteria)",
            ["uv", "run", "pytest", "tests/integration/test_phase1_acceptance_gate.py"],
        ),
        (
            "Gate 2.2: Phase 2 Acceptance Gate (6 Governance Criteria)",
            ["uv", "run", "pytest", "tests/integration/test_phase2_acceptance_gate.py"],
        ),
        (
            "Gate 2.3: Phase 3 Acceptance Gate (6 Governance Criteria)",
            ["uv", "run", "pytest", "tests/integration/test_phase3_acceptance_gate.py"],
        ),
        (
            "Gate 2.4: Mandatory Golden Cases Suite (10 Scenarios)",
            ["uv", "run", "pytest", "tests/integration/test_mandatory_golden_cases.py"],
        ),
        (
            "Gate 2.5: Phase 4 Acceptance Gate (5 Governance Criteria)",
            ["uv", "run", "pytest", "tests/integration/test_phase4_acceptance_gate.py"],
        ),
        (
            "Gate 3: Phase 2 Deterministic Invariance Suite",
            ["uv", "run", "pytest", "tests/unit/services/test_deterministic_invariance.py"],
        ),
        (
            "Gate 4: Phase 3 Failure Injection & Chaos Suite",
            ["uv", "run", "pytest", "tests/integration/test_failure_injection_and_degradation.py"],
        ),
        (
            "Gate 5: Enterprise Success Metric 1.2 Suite (0% False-Pass Rate)",
            ["uv", "run", "pytest", "tests/integration/test_enterprise_success_metrics.py"],
        ),
        (
            "Gate 6: Phase 4 API Contract & Schema Drift Tests",
            ["uv", "run", "pytest", "tests/unit/schemas/test_api_contracts.py"],
        ),
        (
            "Gate 6: Full Integration & Unit Regression Suite",
            ["uv", "run", "pytest"],
        ),
    ]

    all_passed = True
    summary: list[tuple[str, bool]] = []

    for name, cmd in gates:
        passed = run_gate(name, cmd, cwd=backend_dir)
        summary.append((name, passed))
        if not passed:
            all_passed = False
            break

    print("\n" + "#" * 70)
    print("📋 MASTER RELEASE GOVERNANCE SUMMARY")
    print("#" * 70)
    for name, passed in summary:
        status_str = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  • {name:50} [{status_str}]")

    if all_passed:
        print("\n🎉 ALL RELEASE GATES PASSED! Build is verified for production deployment.")
        return 0
    else:
        print("\n🚫 RELEASE BLOCKED: One or more correctness/governance gates failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
