"""Tests for LLM domain validation gate in CandidateAnalysisContext."""
import inspect


class TestLLMDomainValidation:
    """Verify that LLM-returned domains are validated against DB canonicals before use."""

    def test_create_validates_llm_domain(self):
        """CandidateAnalysisContext.create() must validate LLM domain against canonical_domains."""
        from app.schemas.candidate_context import CandidateAnalysisContext
        source = inspect.getsource(CandidateAnalysisContext.create)
        assert "canonical_domains" in source, (
            "create() must check LLM domain against canonical_domains"
        )
        assert "if llm_domain in canonical_domains" in source, (
            "create() must gate LLM domain override on DB canonical membership"
        )

    def test_apply_optimized_profile_validates_llm_domain(self):
        """apply_optimized_profile() must also validate LLM domain before applying."""
        from app.schemas.candidate_context import CandidateAnalysisContext
        source = inspect.getsource(CandidateAnalysisContext.apply_optimized_profile)
        assert "canonical_domains" in source, (
            "apply_optimized_profile() must check LLM domain against canonical_domains"
        )

    def test_create_no_blind_llm_override(self):
        """The old blind override pattern must not exist in create()."""
        from app.schemas.candidate_context import CandidateAnalysisContext
        source = inspect.getsource(CandidateAnalysisContext.create)
        assert "cand_tax_domain = optimized_profile.professional_domains[0]" not in source, (
            "create() must NOT blindly set cand_tax_domain from LLM without validation"
        )

    def test_apply_optimized_profile_no_blind_llm_override(self):
        """The old blind override pattern must not exist in apply_optimized_profile()."""
        from app.schemas.candidate_context import CandidateAnalysisContext
        source = inspect.getsource(CandidateAnalysisContext.apply_optimized_profile)
        assert "self.cand_tax_domain = optimized_profile.professional_domains[0]" not in source, (
            "apply_optimized_profile() must NOT blindly set cand_tax_domain without validation"
        )

    def test_warning_logged_for_invalid_domain(self):
        """When LLM returns an invalid domain, a warning must be logged and deterministic domain kept."""
        from app.schemas.candidate_context import CandidateAnalysisContext
        source_create = inspect.getsource(CandidateAnalysisContext.create)
        source_apply = inspect.getsource(CandidateAnalysisContext.apply_optimized_profile)
        # Both methods must log a warning
        assert "not in DB canonicals" in source_create, (
            "create() must log warning when LLM domain is not in DB canonicals"
        )
        assert "not in DB canonicals" in source_apply, (
            "apply_optimized_profile() must log warning when LLM domain is not in DB canonicals"
        )

    def test_optimized_match_prompt_has_no_suitable_match_instruction(self):
        """The LLM prompt must include a NO_SUITABLE_MATCH fallback instruction."""
        from app.prompts.optimized_match import build_optimized_match_prompt
        prompt, _, _ = build_optimized_match_prompt("Test CV text.", [])
        assert "NO_SUITABLE_MATCH" in prompt, (
            "LLM prompt must instruct model to return NO_SUITABLE_MATCH when no domain fits"
        )

    def test_optimized_match_prompt_injects_dept_list(self):
        """The LLM prompt must include valid department names."""
        from app.prompts.optimized_match import build_optimized_match_prompt
        prompt, _, _ = build_optimized_match_prompt("Test CV text.", [])
        # Should mention department selection constraint
        assert "recommended_department" in prompt and ("MUST be selected from" in prompt or "DEPARTMENT" in prompt), (
            "LLM prompt must include department selection constraint"
        )

    def test_optimized_match_prompt_requires_evidence_citation(self):
        """The LLM prompt must require per-field CV evidence citations."""
        from app.prompts.optimized_match import build_optimized_match_prompt
        prompt, _, _ = build_optimized_match_prompt("Test CV text.", [])
        assert "EVIDENCE CITATION" in prompt or "evidenced" in prompt.lower(), (
            "LLM prompt must require per-field CV evidence citations"
        )
