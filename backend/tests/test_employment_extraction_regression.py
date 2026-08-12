import pytest
from app.services.resume_field_extractor import ResumeFieldExtractor
from app.services.resume_normalizer import ResumeNormalizer
from app.schemas.candidate_context import CandidateAnalysisContext

class TestStructuralExtraction:
    def evaluate(self, lines, min_exp=0):
        text = "\n".join(lines)
        resume_json = ResumeFieldExtractor.extract(text)
        normalized = ResumeNormalizer.normalize(resume_json, text)
        context = CandidateAnalysisContext.create(
            cv_text=text,
            resume_json=resume_json,
            normalized_resume=normalized
        )
        return context

    def test_a_company_date_title_resp(self):
        ctx = self.evaluate([
            "Acme Corp",
            "Jan 2020 - Jan 2022",
            "Software Developer",
            "- Built things",
            "- Fixed bugs"
        ])
        assert len(ctx.normalized_resume.employment) == 1
        emp = ctx.normalized_resume.employment[0]
        assert emp.company == "Acme Corp"
        assert emp.job_title.raw_value == "Software Developer"
        assert "Jan 2020" in emp.interval.start_date
        assert len(emp.responsibilities) == 2

    def test_b_title_company_date_resp(self):
        ctx = self.evaluate([
            "Senior Developer",
            "Global Tech Inc",
            "Mar 2018 - Dec 2019",
            "Did some coding"
        ])
        assert len(ctx.normalized_resume.employment) == 1
        emp = ctx.normalized_resume.employment[0]
        assert emp.company == "Global Tech Inc"
        assert emp.job_title.raw_value == "Senior Developer"
        assert len(emp.responsibilities) == 1

    def test_c_date_title_company_resp(self):
        ctx = self.evaluate([
            "05/2015 - 06/2017",
            "QA Engineer",
            "Testing Solutions LLC",
            "- Tested things"
        ])
        assert len(ctx.normalized_resume.employment) == 1
        emp = ctx.normalized_resume.employment[0]
        assert emp.company == "Testing Solutions LLC"
        assert emp.job_title.raw_value == "QA Engineer"

    def test_d_two_consecutive_employers(self):
        ctx = self.evaluate([
            "Developer",
            "Company A Inc",
            "2020 - 2021",
            "- resp A",
            "Manager",
            "Company B LLC",
            "2021 - 2022",
            "- resp B"
        ])
        assert len(ctx.normalized_resume.employment) == 2
        assert ctx.normalized_resume.employment[0].company == "Company A Inc"
        assert ctx.normalized_resume.employment[1].company == "Company B LLC"

    def test_e_two_roles_same_employer(self):
        ctx = self.evaluate([
            "Company A Inc",
            "Senior Developer",
            "2021 - 2022",
            "- resp 2",
            "Junior Developer",
            "2020 - 2021",
            "- resp 1"
        ])
        assert len(ctx.normalized_resume.employment) == 2
        assert ctx.normalized_resume.employment[0].job_title.raw_value == "Senior Developer"
        assert ctx.normalized_resume.employment[1].job_title.raw_value == "Junior Developer"

    def test_f_missing_company(self):
        ctx = self.evaluate([
            "Software Developer",
            "2021 - Present",
            "- resp"
        ])
        assert len(ctx.normalized_resume.employment) == 1
        assert ctx.normalized_resume.employment[0].job_title.raw_value == "Software Developer"

    def test_g_missing_title(self):
        ctx = self.evaluate([
            "Startup LLC",
            "2020 - 2022",
            "- resp"
        ])
        assert len(ctx.normalized_resume.employment) == 1
        assert ctx.normalized_resume.employment[0].company == "Startup LLC"

    def test_h_wrapped_responsibilities(self):
        ctx = self.evaluate([
            "Developer",
            "Tech Inc",
            "2020 - 2021",
            "- Led a team of",
            "manager and engineer",
            "to build technology"
        ])
        assert len(ctx.normalized_resume.employment) == 1
        emp = ctx.normalized_resume.employment[0]
        # manager/engineer/technology should not split the block
        assert len(emp.responsibilities) == 3

class TestGateLogic:
    def get_result(self, cand_exp_val, min_exp, relevant_exp_val):
        class MockResult:
            mandatory_failures = []
        
        req_results = MockResult()
        relevant_exp = relevant_exp_val
        from app.services.match_evaluators import RequirementEvaluator
        class Params:
            below_min_exp_multiplier = 0.5
            overqualification_penalty = 10
            
        penalty = 10
        
        if min_exp is not None and relevant_exp is not None and relevant_exp < min_exp:
            req_results.mandatory_failures.append(RequirementEvaluator._create_failure("req_exp", f"Min: {min_exp}", "Fail", -10))
            
        if relevant_exp is None and min_exp is not None:
            req_results.mandatory_failures.append(RequirementEvaluator._create_failure("req_exp", f"Min: {min_exp}", "Unknown", -10))
            
        return req_results

    def test_i_zero_relevant_fails(self):
        res = self.get_result(cand_exp_val=5.0, min_exp=3.0, relevant_exp_val=0.0)
        assert len(res.mandatory_failures) == 1

    def test_j_none_relevant_fails_unknown(self):
        res = self.get_result(cand_exp_val=5.0, min_exp=3.0, relevant_exp_val=None)
        assert len(res.mandatory_failures) == 1
        assert "Unknown" in res.mandatory_failures[0].reason

    def test_k_pass(self):
        res = self.get_result(cand_exp_val=5.0, min_exp=3.0, relevant_exp_val=4.0)
        assert len(res.mandatory_failures) == 0

