import pytest
from app.services.resume_field_extractor import ResumeFieldExtractor
from app.services.candidate_domain_service import CandidateDomainService
from app.schemas.candidate_context import CandidateAnalysisContext
from app.services.resume_normalizer import ResumeNormalizer


class TestStructuralJobTitleSanity:
    """Validate structural noun phrase checks to ensure true roles pass and junk/narrative text fails."""

    @pytest.mark.parametrize(
        "valid_title",
        [
            "Site Engineer",
            "Store Incharge",
            "Billing Executive",
            "Plant Operator",
            "QC Chemist",
            "Accounts Executive",
            "Sales Representative",
            "CNC Machine Operator",
            "Lab Technician",
            "Sr. Frontend Developer",
            "UI/UX Designer",
            "VP - Operations",
            "Sales & Marketing Executive",
            "Research Associate - II",
            "Assistant Manager - QA/QC",
            "Lead Software Engineer",
            "Full Stack Developer",
            "Junior Data Analyst",
            "Project Manager",
            "Chief Technology Officer",
            "DevOps Engineer",
            "Field Support Specialist",
        ],
    )
    def test_valid_structural_noun_phrases_accepted(self, valid_title):
        assert ResumeFieldExtractor.is_structural_job_title_noun_phrase(valid_title) is True
        assert ResumeFieldExtractor.is_valid_job_title(valid_title) is True

    @pytest.mark.parametrize(
        "junk_text",
        [
            "Responsible for managing the team and delivering code on time.",
            "Handled customer queries and escalated issues.",
            "Worked on python django postgresql redis and docker.",
            "Seeking a challenging position in a reputed organization.",
            "Experienced in software engineering and cloud infrastructure.",
            "john.doe@example.com",
            "+91 9876543210",
            "https://linkedin.com/in/johndoe",
            "2019 - 2022",
            "12/2020 to Present",
            "WORK EXPERIENCE",
            "EDUCATION QUALIFICATION",
            "PERSONAL DETAILS",
            "DECLARATION",
            "the and or to for",
            "12345678",
            "A very long sentence that describes many different responsibilities and tasks carried out during employment exceeding normal limits.",
        ],
    )
    def test_junk_and_narrative_text_rejected(self, junk_text):
        assert ResumeFieldExtractor.is_structural_job_title_noun_phrase(junk_text) is False


class TestLatestRoleMultiLayoutExtraction:
    """Validate Latest Role extraction across diverse CV layouts (single-column, tables, key-value, modern headers)."""

    def test_layout_1_key_value_unbulleted(self):
        cv_text = """
        John Doe
        Email: john.doe@example.com
        Phone: +91 9876543210

        WORK HISTORY
        Company: Apex Industrial Solutions
        Designation: Plant Operator
        Duration: March 2021 - Present
        Location: Vadodara, Gujarat
        Responsibilities: Managed chemical plant operations and safety.

        Company: Baroda Chemicals Ltd
        Designation: Junior Technician
        Duration: Jan 2019 - Feb 2021
        Responsibilities: Supported plant maintenance.
        """
        resume_json = ResumeFieldExtractor.extract(cv_text)
        assert resume_json["contact_info"]["name"] == "John Doe"
        assert resume_json["contact_info"]["job_title"] == "Plant Operator"
        assert resume_json["contact_info"]["company_name"] == "Apex Industrial Solutions"

        work_exp = resume_json["work_experience"]
        assert len(work_exp) == 2
        assert work_exp[0]["job_title"] == "Plant Operator"
        assert work_exp[0]["company"] == "Apex Industrial Solutions"

    def test_layout_2_markdown_table_3_columns(self):
        cv_text = """
        Priya Sharma
        Email: priya.sharma@example.com

        ## EMPLOYMENT RECORD
        | Company | Designation | Duration |
        |---|---|---|
        | Tata Consultancy Services | Site Engineer | 06/2021 - Present |
        | L&T Construction | Graduate Engineer Trainee | 06/2019 - 05/2021 |

        ## EDUCATION
        B.Tech Civil Engineering
        """
        resume_json = ResumeFieldExtractor.extract(cv_text)
        assert resume_json["contact_info"]["name"] == "Priya Sharma"
        assert resume_json["contact_info"]["job_title"] == "Site Engineer"
        assert resume_json["contact_info"]["company_name"] == "Tata Consultancy Services"

    def test_layout_3_markdown_table_4_columns(self):
        cv_text = """
        Rahul Verma
        Email: rahul.verma@example.com

        ## CAREER GRAPH
        | S.No | Organization | Position | Period |
        |---|---|---|---|
        | 1 | Reliance Industries | QC Chemist | 2020 - Present |
        | 2 | Sun Pharma | Lab Assistant | 2018 - 2020 |
        """
        resume_json = ResumeFieldExtractor.extract(cv_text)
        assert resume_json["contact_info"]["name"] == "Rahul Verma"
        assert resume_json["contact_info"]["job_title"] == "QC Chemist"
        assert resume_json["contact_info"]["company_name"] == "Reliance Industries"

    def test_layout_4_header_designation_under_name(self):
        cv_text = """
        Jane Smith
        Store Incharge
        Email: jane.smith@example.com
        Phone: 9988776655

        SUMMARY
        Experienced professional managing warehousing and inventory control.

        EXPERIENCE
        ABC Logistics (2019 - 2023)
        - Managed all retail stores and stock movement.
        """
        resume_json = ResumeFieldExtractor.extract(cv_text)
        assert resume_json["contact_info"]["name"] == "Jane Smith"
        assert resume_json["contact_info"]["job_title"] == "Store Incharge"

    def test_layout_5_modern_banner_format(self):
        cv_text = """
        # ANKIT MEHTA
        Billing Executive | Vadodara
        ankit.mehta@example.com | +91 9123456789

        PROFESSIONAL BACKGROUND
        Modern Retail Solutions Pvt Ltd
        Billing Executive
        2021 - Present
        - Handled GST billing, invoices, and ledger accounts.
        """
        resume_json = ResumeFieldExtractor.extract(cv_text)
        assert resume_json["contact_info"]["name"].upper() == "ANKIT MEHTA"
        assert resume_json["contact_info"]["job_title"] == "Billing Executive"
        assert resume_json["contact_info"]["company_name"] == "Modern Retail Solutions Pvt Ltd"


class TestCandidateDomainValidationAndContext:
    """Validate CandidateDomainService.validate_job_roles and CandidateAnalysisContext current_role."""

    def test_validate_job_roles_accepts_verbatim_cv_titles(self):
        cv_text = """
        Experience:
        Worked as Store Incharge at Apex Logistics from 2020 to Present.
        """
        roles = ["Store Incharge"]
        accepted = CandidateDomainService.validate_job_roles(roles, cv_text=cv_text)
        assert "Store Incharge" in accepted

    def test_validate_job_roles_rejects_narrative_sentences(self):
        cv_text = """
        Experience:
        Responsible for managing the team at Apex Logistics from 2020 to Present.
        """
        roles = ["Responsible for managing the team"]
        accepted = CandidateDomainService.validate_job_roles(roles, cv_text=cv_text)
        assert len(accepted) == 0

    def test_candidate_context_resolves_current_role(self):
        cv_text = """
        Amit Kumar
        Email: amit.kumar@example.com
        WORK EXPERIENCE
        Company: Torrent Power
        Role: Site Engineer
        Duration: 2020 - Present
        - Supervised field sub-stations.
        """
        resume_json = ResumeFieldExtractor.extract(cv_text)
        normalized = ResumeNormalizer.normalize(resume_json, cv_text)
        context = CandidateAnalysisContext.create(
            cv_text=cv_text,
            resume_json=resume_json,
            normalized_resume=normalized,
        )
        assert context.current_role == "Site Engineer"
