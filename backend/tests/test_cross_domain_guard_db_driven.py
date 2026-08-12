"""Tests for DB-driven CrossDomainGuard — no hardcoded keyword reliance."""


class TestCrossDomainGuardDbDriven:
    """Verify CrossDomainGuardEvaluator uses DynamicTaxonomyService, not keyword patterns."""

    def test_cross_domain_guard_uses_family_compatibility(self):
        """Guard should call DynamicTaxonomyService.check_family_compatibility for domain checks."""
        import inspect
        from app.services.match_evaluators import CrossDomainGuardEvaluator
        source = inspect.getsource(CrossDomainGuardEvaluator.evaluate)
        assert "check_family_compatibility" in source, (
            "CrossDomainGuardEvaluator.evaluate must call DynamicTaxonomyService.check_family_compatibility"
        )

    def test_candidate_context_no_hardcoded_sw_patterns(self):
        """CandidateAnalysisContext.create should use DB family compatibility for is_software_cand."""
        import inspect
        from app.schemas.candidate_context import CandidateAnalysisContext
        source = inspect.getsource(CandidateAnalysisContext.create)
        # Should use DynamicTaxonomyService, not hardcoded patterns
        assert "check_family_compatibility" in source, (
            "CandidateAnalysisContext.create must use DynamicTaxonomyService for is_software_cand"
        )
        # The old patterns-only path should be replaced
        assert "sw_patterns = compiled_guard" not in source, (
            "CandidateAnalysisContext.create must not use hardcoded sw_patterns for is_software_cand"
        )

    def test_apply_optimized_profile_no_hardcoded_sw_patterns(self):
        """apply_optimized_profile should use DB family compatibility for is_software_cand."""
        import inspect
        from app.schemas.candidate_context import CandidateAnalysisContext
        source = inspect.getsource(CandidateAnalysisContext.apply_optimized_profile)
        assert "check_family_compatibility" in source, (
            "apply_optimized_profile must use DynamicTaxonomyService for is_software_cand"
        )

    def test_same_family_is_compatible(self):
        """Same family should always be compatible with score 1.0."""
        from app.services.dynamic_taxonomy_service import DynamicTaxonomyService
        is_compat, score = DynamicTaxonomyService.check_family_compatibility(
            "Software Engineering & Development",
            "Software Engineering & Development",
        )
        assert is_compat is True
        assert score == 1.0

    def test_it_software_family_name_constant(self):
        """The IT software family constant used in both create() and apply_optimized_profile() must be consistent."""
        import inspect
        from app.schemas.candidate_context import CandidateAnalysisContext
        source = inspect.getsource(CandidateAnalysisContext)
        it_family = "Software Engineering & Development"
        assert source.count(it_family) >= 2, (
            f"'{it_family}' must appear in both create() and apply_optimized_profile()"
        )
