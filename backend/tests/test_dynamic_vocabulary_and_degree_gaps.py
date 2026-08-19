
import pytest

from app.services.dynamic_geo_heading_service import DynamicGeoAndHeadingService
from app.services.resume_field_extractor import ResumeFieldExtractor
from app.services.resume_normalizer import ResumeNormalizer


class TestDynamicVocabularyAndDegreeGaps:
    """Validate dynamic vocabulary deduplication, global countries, and degree extraction enhancements."""

    def test_dynamic_geo_and_heading_service_sets_populated(self):
        """Ensure all dynamic sets are non-empty single sources of truth."""
        DynamicGeoAndHeadingService.refresh_cache()
        assert len(DynamicGeoAndHeadingService.get_countries()) >= 100
        assert len(DynamicGeoAndHeadingService.get_tech_and_role_denylist()) >= 30
        assert len(DynamicGeoAndHeadingService.get_label_prefix_denylist()) >= 20
        assert len(DynamicGeoAndHeadingService.get_non_name_field_labels()) >= 15
        assert len(DynamicGeoAndHeadingService.get_verb_starters()) >= 30
        assert len(DynamicGeoAndHeadingService.get_preposition_and_conjunction_starters()) >= 10
        assert len(DynamicGeoAndHeadingService.get_allowed_compound_titles()) >= 5
        assert len(DynamicGeoAndHeadingService.get_common_roles()) >= 20
        assert len(DynamicGeoAndHeadingService.get_common_company_words()) >= 20
        assert len(DynamicGeoAndHeadingService.get_company_suffixes()) >= 15
        assert len(DynamicGeoAndHeadingService.get_degree_keywords()) >= 20

    @pytest.mark.parametrize(
        "country",
        [
            "INDIA", "UNITED STATES", "USA", "UK", "UNITED KINGDOM", "CANADA", "GERMANY",
            "FRANCE", "AUSTRALIA", "SINGAPORE", "UAE", "DUBAI", "JAPAN", "CHINA", "ITALY",
            "SPAIN", "BRAZIL", "MEXICO", "NETHERLANDS", "SWITZERLAND", "SWEDEN",
            "ARGENTINA", "AUSTRIA", "BELGIUM", "CHILE", "COLOMBIA", "DENMARK", "EGYPT",
            "FINLAND", "GREECE", "HONG KONG", "INDONESIA", "IRELAND", "ISRAEL", "KENYA",
            "MALAYSIA", "NEW ZEALAND", "NIGERIA", "NORWAY", "PAKISTAN", "PHILIPPINES",
            "POLAND", "PORTUGAL", "QATAR", "SAUDI ARABIA", "SOUTH AFRICA", "THAILAND",
            "TURKEY", "VIETNAM",
        ]
    )
    def test_global_countries_recognized(self, country: str):
        """Ensure country names from all over the world are recognized and rejected as candidate names."""
        assert DynamicGeoAndHeadingService.is_country(country) is True
        assert ResumeFieldExtractor._is_valid_name(country, None, None, None) is False

    @pytest.mark.parametrize(
        "degree_text,expected_canonical",
        [
            ("Bachelor of Computer Applications (BCA)", "BCA"),
            ("BCA from Gujarat University", "BCA"),
            ("Master of Computer Applications (MCA)", "MCA"),
            ("MCA, 2024", "MCA"),
            ("Bachelor of Business Administration (BBA)", "BBA"),
            ("BBA in Marketing", "BBA"),
            ("Bachelor of Commerce (B.Com)", "B.Com"),
            ("B.Com from Mumbai University", "B.Com"),
            ("BCom Accounting & Finance", "B.Com"),
            ("Master of Commerce (M.Com)", "M.Com"),
            ("Bachelor of Arts (B.A.)", "B.A."),
            ("Master of Arts (M.A.)", "M.A."),
            ("Bachelor of Pharmacy (B.Pharm)", "B.Pharm"),
            ("Master of Pharmacy (M.Pharm)", "M.Pharm"),
            ("Bachelor of Laws (LLB)", "LLB"),
            ("Master of Laws (LLM)", "LLM"),
            ("Bachelor of Technology in CSE", "B.Tech"),
            ("B.Tech Mechanical", "B.Tech"),
            ("Bachelor of Engineering (B.E.)", "B.E."),
            ("B.Sc. Chemistry", "B.Sc."),
            ("Master of Technology (M.Tech)", "M.Tech"),
            ("Master of Science (M.Sc.)", "M.Sc."),
            ("MBA in Human Resources", "MBA"),
            ("Ph.D. in Chemical Engineering", "Ph.D."),
            ("Diploma in Electrical Engineering", "Diploma"),
            ("PGDM Finance", "PGDM"),
            ("PGDCA", "PGDCA"),
            ("ITI Fitter Trade", "ITI"),
            ("Chartered Accountant (CA)", "CA"),
            ("Company Secretary (CS)", "CS"),
        ]
    )
    def test_degree_pattern_and_canonical_normalization(self, degree_text: str, expected_canonical: str):
        """Ensure degree_pattern matches and ResumeNormalizer canonicalizes all common degrees."""
        pattern = ResumeFieldExtractor.DEGREE_PATTERN
        assert bool(pattern.search(degree_text)) is True
        canonical = ResumeNormalizer._canonical_degree(degree_text)
        assert canonical == expected_canonical

    def test_education_extraction_detects_all_common_degrees(self):
        """Verify _extract_education successfully extracts entries for BCA, MCA, BBA, B.Com, ITI, etc."""
        lines = [
            "# Jain University",
            "Master of Computer Applications (MCA)",
            "2024 - 2026",
            "# Gujarat University",
            "Bachelor of Computer Applications (BCA)",
            "2020 - 2023",
            "# Commerce College",
            "Bachelor of Commerce (B.Com)",
            "2017 - 2020",
            "# Technical Training Institute",
            "ITI Fitter",
            "2015 - 2017",
        ]
        extracted = ResumeFieldExtractor._extract_education(lines)
        degrees = [e.get("degree") for e in extracted]
        assert any("MCA" in d for d in degrees)
        assert any("BCA" in d for d in degrees)
        assert any("B.Com" in d for d in degrees)
        assert any("ITI" in d for d in degrees)

    def test_verb_starters_and_prepositions_rejected_across_all_methods(self):
        """Ensure verb and preposition starters are consistently rejected across all extraction methods."""
        junk_verbs = [
            "Responsible for client communications",
            "Managed a team of 10 developers",
            "Working on python django microservices",
            "Developed responsive web applications",
            "Handled customer support tickets",
            "Seeking a challenging position in IT",
            "Dedicated and enthusiastic software developer",
        ]
        junk_prepositions = [
            "to develop web applications",
            "for building cloud infrastructure",
            "with python and react",
            "in mumbai office",
            "at client site",
        ]

        for text in junk_verbs:
            assert ResumeFieldExtractor.is_valid_job_title(text) is False
            assert ResumeFieldExtractor.is_structural_job_title_noun_phrase(text) is False

        for text in junk_prepositions:
            assert ResumeFieldExtractor.is_valid_job_title(text) is False
            assert ResumeFieldExtractor.is_structural_job_title_noun_phrase(text) is False
            assert ResumeFieldExtractor.is_valid_company_name(text) is False
            assert ResumeFieldExtractor._looks_like_company(text) is False

    @pytest.mark.parametrize(
        "degree_text,expected_domain",
        [
            ("B.Tech in Computer Science and Engineering", "Computer Science & IT"),
            ("Bachelor of Science in Information Technology", "Computer Science & IT"),
            ("B.E. Mechanical Engineering", "Mechanical Engineering"),
            ("B.Tech Electrical & Electronics", "Electrical & Electronics Engineering"),
            ("Diploma in Civil Engineering", "Civil Engineering"),
            ("B.Tech in Chemical Engineering", "Chemical Engineering"),
            ("M.Tech in Polymer Technology", "Chemical Engineering"),
            ("B.Tech in Biomedical Engineering", "Biomedical & Biotechnology"),
            ("M.Sc. in Biotechnology", "Biomedical & Biotechnology"),
            ("B.E. in Aerospace Engineering", "Aerospace Engineering"),
            ("Bachelor of Aeronautical Engineering", "Aerospace Engineering"),
            ("Bachelor of Pharmacy (B.Pharm)", "Pharmacy & Pharmaceutical Sciences"),
            ("M.Pharm in Pharmacology", "Pharmacy & Pharmaceutical Sciences"),
            ("MBA in Finance & Marketing", "Business & Finance"),
            ("Bachelor of Business Administration", "Business & Finance"),
            ("M.Sc. in Analytical Chemistry", "Chemical Sciences"),
            ("B.Sc. in Physics", "Physical Sciences"),
            ("Master of Science in Statistics & Data Science", "Mathematics & Data Science"),
            ("Bachelor of Architecture (B.Arch)", "Architecture & Design"),
            ("Bachelor of Laws (LLB)", "Law & Legal Studies"),
        ]
    )
    def test_education_domain_canonicalization_expanded(self, degree_text: str, expected_domain: str):
        """Ensure degrees from chemical to aerospace to biomedical are accurately canonicalized."""
        domain = ResumeNormalizer._education_domain(degree_text)
        assert domain == expected_domain

    def test_noise_words_strictly_configuration_driven(self):
        """Ensure ScoringEngine does not hardcode unremovable noise words and respects RuleConfigManager."""
        from unittest.mock import patch

        from app.services.scoring_engine import ScoringEngine

        custom_assets = {
            "noise_words": ["programming", "language", "framework"],
            "aliases": {},
            "stop_phrases": [],
        }
        with patch("app.core.rule_config_manager.RuleConfigManager.get_term_matching_assets", return_value=custom_assets):
            # Term "leadership skills" has sub-token "skills". Since "skills" is not in custom noise_words, it should be kept as a sub-token.
            matched, missing = ScoringEngine._extract_term_matches(
                normalized_text="has great leadership skills and team management",
                terms=["leadership skills"],
            )
            assert "leadership skills" in matched
