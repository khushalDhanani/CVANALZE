from __future__ import annotations
# backend/app/services/dynamic_geo_heading_service.py
import logging
import re
from typing import Any

from app.core.database import PostgresAppSession
from app.core.rule_config_manager import RuleConfigManager
from app.models.geo_headings import GeoLocation, NameDenylist, SectionHeading

logger = logging.getLogger("cv_analyzer")


class DynamicGeoAndHeadingService:
    """
    Dynamic Location Gazetteer, Section Heading, Vocabulary, and Denylist Service.
    Queries MSSQL/PostgreSQL with in-memory caching and fallback to RuleConfigManager.
    Serves as the single deduplicated source of truth for extraction vocabularies and rules.
    """

    _gazetteer_cache: set[str] | None = None
    _country_names_cache: set[str] | None = None
    _name_denylist_cache: set[str] | None = None
    _tech_and_role_denylist_cache: set[str] | None = None
    _section_heading_cache: set[str] | None = None
    _label_prefix_denylist_cache: set[str] | None = None
    _non_name_field_labels_cache: set[str] | None = None
    _verb_starters_cache: set[str] | None = None
    _preposition_starters_cache: set[str] | None = None
    _allowed_compound_titles_cache: set[str] | None = None
    _common_roles_cache: set[str] | None = None
    _common_company_words_cache: set[str] | None = None
    _company_suffixes_cache: set[str] | None = None
    _degree_keywords_cache: set[str] | None = None
    _degree_pattern_cache: re.Pattern | None = None

    # Canonical Baseline Defaults (Single Source of Truth)
    _DEFAULT_COUNTRIES: frozenset[str] = frozenset({
        "AFGHANISTAN", "ALBANIA", "ALGERIA", "ANDORRA", "ANGOLA", "ARGENTINA", "ARMENIA", "AUSTRALIA", "AUS",
        "AUSTRIA", "AZERBAIJAN", "BAHAMAS", "BAHRAIN", "BANGLADESH", "BARBADOS", "BELARUS", "BELGIUM", "BELIZE",
        "BENIN", "BHUTAN", "BOLIVIA", "BOSNIA", "BOTSWANA", "BRAZIL", "BRUNEI", "BULGARIA", "BURKINA FASO",
        "BURUNDI", "CAMBODIA", "CAMEROON", "CANADA", "CAN", "CHILE", "CHINA", "COLOMBIA", "COSTA RICA", "CROATIA",
        "CUBA", "CYPRUS", "CZECH REPUBLIC", "CZECHIA", "DENMARK", "DJIBOUTI", "DOMINICA", "DOMINICAN REPUBLIC",
        "ECUADOR", "EGYPT", "EL SALVADOR", "ESTONIA", "ETHIOPIA", "FIJI", "FINLAND", "FRANCE", "GABON", "GAMBIA",
        "GEORGIA", "GERMANY", "GHANA", "GREECE", "GRENADA", "GUATEMALA", "GUINEA", "GUYANA", "HAITI", "HONDURAS",
        "HONG KONG", "HUNGARY", "ICELAND", "INDIA", "IND", "INDONESIA", "IRAN", "IRAQ", "IRELAND", "ISRAEL",
        "ITALY", "JAMAICA", "JAPAN", "JORDAN", "KAZAKHSTAN", "KENYA", "KOREA", "SOUTH KOREA", "NORTH KOREA",
        "KUWAIT", "KYRGYZSTAN", "LAOS", "LATVIA", "LEBANON", "LESOTHO", "LIBERIA", "LIBYA", "LIECHTENSTEIN",
        "LITHUANIA", "LUXEMBOURG", "MADAGASCAR", "MALAWI", "MALAYSIA", "MALDIVES", "MALI", "MALTA", "MAURITANIA",
        "MAURITIUS", "MEXICO", "MOLDOVA", "MONACO", "MONGOLIA", "MONTENEGRO", "MOROCCO", "MOZAMBIQUE", "MYANMAR",
        "NAMIBIA", "NEPAL", "NETHERLANDS", "NEW ZEALAND", "NICARAGUA", "NIGER", "NIGERIA", "NORWAY", "OMAN",
        "PAKISTAN", "PALESTINE", "PANAMA", "PAPUA NEW GUINEA", "PARAGUAY", "PERU", "PHILIPPINES", "POLAND",
        "PORTUGAL", "QATAR", "ROMANIA", "RUSSIA", "RWANDA", "SAUDI ARABIA", "KSA", "SENEGAL", "SERBIA",
        "SEYCHELLES", "SIERRA LEONE", "SINGAPORE", "SLOVAKIA", "SLOVENIA", "SOMALIA", "SOUTH AFRICA", "SPAIN",
        "SRI LANKA", "SUDAN", "SURINAME", "SWEDEN", "SWITZERLAND", "SYRIA", "TAIWAN", "TAJIKISTAN", "TANZANIA",
        "THAILAND", "TIMOR-LESTE", "TOGO", "TRINIDAD AND TOBAGO", "TUNISIA", "TURKEY", "TURKMENISTAN", "UGANDA",
        "UKRAINE", "UNITED ARAB EMIRATES", "UAE", "DUBAI", "ABU DHABI", "UNITED KINGDOM", "UK", "GREAT BRITAIN",
        "ENGLAND", "SCOTLAND", "WALES", "UNITED STATES", "USA", "US", "URUGUAY", "UZBEKISTAN", "VANUATU",
        "VENEZUELA", "VIETNAM", "YEMEN", "ZAMBIA", "ZIMBABWE",
    })

    _DEFAULT_TECH_AND_ROLE_DENYLIST: frozenset[str] = frozenset({
        "AI", "IT", "ML", "UI", "UX", "QA", "HR", "PR", "DBA", "SEO", "PMP", "API", "ETL", "ELT", "SRE",
        "REACT", "NATIVE", "ANDROID", "FLUTTER", "IONIC", "NODE", "NODEJS", "PYTHON", "ANGULAR", "VUE",
        "TYPESCRIPT", "JAVASCRIPT", "JAVA", "SPRING", "DOCKER", "AWS", "AZURE", "KUBERNETES",
        "DEVELOPER", "ENGINEER", "LEADER", "LEAD", "ARCHITECT", "INTEGRATION", "SERVICES",
        "FRONTEND", "BACKEND", "FULLSTACK", "STACK", "MOBILE", "SOFTWARE", "SENIOR", "JUNIOR",
    })

    _DEFAULT_SECTION_HEADINGS: frozenset[str] = frozenset({
        "experience", "work experience", "work history", "employment", "employment history",
        "professional experience", "education", "academic background", "qualifications",
        "skills", "technical skills", "core competencies", "key skills", "summary",
        "professional summary", "career summary", "profile", "projects", "certifications",
        "awards", "honors", "publications", "languages", "hobbies", "interests", "references",
        "declaration", "personal details", "personal information", "contact", "contact information",
    })

    _DEFAULT_LABEL_PREFIX_DENYLIST: frozenset[str] = frozenset({
        "duration", "period", "tenure", "date", "from", "to",
        "organization", "company", "employer", "institution",
        "designation", "position", "role", "department",
        "location", "address", "place", "city",
        "qualification", "education", "degree", "board", "institute",
        "sex", "gender", "marital", "marital status", "nationality",
        "dob", "date of birth", "birth", "father", "father's name", "mother's name",
        "languages", "languages known", "hobbies", "declaration", "permanent address",
        "current address", "residential address", "contact no", "email", "phone",
        "roll no", "roll no.", "roll number", "roll", "enrollment no", "enrollment no.", "enrollment number", "enrollment",
        "registration no", "registration no.", "registration number", "reg no", "reg no.", "reg. no.", "reg. no", "reg",
        "prn", "prn no", "prn no.", "seat no", "seat no.", "hall ticket no", "hall ticket",
        "student id", "candidate id", "id no", "id no.", "index no", "index no.",
        "uid", "aadhar", "aadhaar", "pan", "passport", "cpi", "cgpa", "sgpa", "percentage", "marks", "grade", "rank", "air", "gate score", "gate rank",
        "specialization", "branch", "stream", "batch", "semester",
    })

    _DEFAULT_NON_NAME_FIELD_LABELS: frozenset[str] = frozenset({
        "subject", "contact", "phone", "mobile", "email", "language", "address",
        "gender", "sex", "state", "nationality", "marital status", "marital", "date of birth", "dob",
        "pin", "pin code", "pincode", "personal data", "personal details", "resume", "cv",
        "father's name", "father name", "mother's name", "declaration", "hobbies",
        "roll no", "roll no.", "roll number", "roll", "enrollment no", "enrollment no.", "enrollment number", "enrollment",
        "registration no", "registration no.", "registration number", "reg no", "reg no.", "reg. no.", "reg. no", "reg",
        "prn", "prn no", "prn no.", "seat no", "seat no.", "hall ticket no", "hall ticket",
        "student id", "candidate id", "id no", "id no.", "index no", "index no.",
        "uid", "aadhar", "aadhaar", "pan", "passport", "cpi", "cgpa", "sgpa", "percentage", "marks", "grade", "rank", "air", "gate score", "gate rank",
        "specialization", "branch", "stream", "batch", "semester",
    })

    _DEFAULT_VERB_STARTERS: frozenset[str] = frozenset({
        "did", "done", "do", "was", "were", "is", "are", "have", "had", "has",
        "built", "made", "helped", "tested", "coded", "wrote", "learned",
        "responsible", "responsibilities", "handled", "handling", "managed", "managing",
        "worked", "working", "developed", "developing", "spearheaded", "oversaw",
        "involved", "participated", "created", "creating", "implemented", "implementing",
        "aiming", "seeking", "looking", "dedicated", "passionate", "proficient",
        "experienced", "experienced in", "skilled in", "knowledge of", "duties",
        "achieved", "maintained", "maintaining", "executed", "executing", "assisted",
        "assisting", "monitored", "monitoring", "conducted", "conducting", "ensured",
        "ensuring", "designed", "designing", "coordinated", "coordinating", "reporting",
        "building", "troubleshooting", "supervising", "leading a team", "managed a team",
        "graduated", "completed", "attended", "born", "started", "joined", "finished", "served", "led"
    })

    _DEFAULT_PREPOSITION_AND_CONJUNCTION_STARTERS: frozenset[str] = frozenset({
        "to", "for", "with", "by", "from", "in", "on", "at", "about", "into",
        "through", "during", "and", "or", "but", "the", "a", "an",
    })

    _DEFAULT_ALLOWED_COMPOUND_TITLES: frozenset[str] = frozenset({
        "sales and marketing", "research and development", "learning and development",
        "compensation and benefits", "strategy and operations", "qa and qc", "quality and compliance",
    })

    _DEFAULT_COMMON_ROLES: frozenset[str] = frozenset({
        "product manager", "project manager", "program manager", "general manager",
        "senior officer", "police officer", "chief officer", "executive officer",
        "marketing executive", "sales executive", "billing executive", "operations manager",
        "plant operator", "site engineer", "civil engineer", "mechanical engineer",
        "electrical engineer", "software engineer", "full stack developer", "frontend developer",
        "backend developer", "data analyst", "data scientist", "store incharge", "qc chemist",
        "lab technician", "machine operator", "accounts executive", "support specialist",
    })

    _DEFAULT_COMMON_COMPANY_WORDS: frozenset[str] = frozenset({
        "solutions", "services", "technologies", "technology", "industries",
        "consultancy", "consulting", "enterprises", "corporation", "corp",
        "pvt", "ltd", "limited", "llc", "inc", "systems", "labs", "group",
        "bank", "hospital", "motors", "power", "infotech", "pharma",
        "chemicals", "holdings", "ventures", "agency", "firm", "studio",
        "associates", "logistics",
    })

    _DEFAULT_COMPANY_SUFFIXES: frozenset[str] = frozenset({
        "ltd", "limited", "pvt", "private", "inc", "incorporated", "llc", "llp", "corp",
        "corporation", "industries", "solutions", "enterprises", "infosys", "infotech",
        "technologies", "technology", "pharma", "chemicals", "remedies", "generics",
        "organics", "techno lab", "techno labs",
    })

    _DEFAULT_DEGREES: frozenset[str] = frozenset({
        "B.Tech", "BTech", "Bachelor of Technology",
        "B.E.", "B.E", "BE", "Bachelor of Engineering",
        "B.Sc.", "B.Sc", "BSc", "Bachelor of Science",
        "BCA", "Bachelor of Computer Applications", "Bachelor of Computer Application",
        "BBA", "Bachelor of Business Administration",
        "B.Com.", "B.Com", "BCom", "Bachelor of Commerce",
        "B.A.", "B.A", "BA", "Bachelor of Arts",
        "B.Pharm.", "B.Pharm", "BPharm", "Bachelor of Pharmacy",
        "B.Arch.", "B.Arch", "BArch", "Bachelor of Architecture",
        "B.Des.", "B.Des", "BDes", "Bachelor of Design",
        "B.Ed.", "B.Ed", "BEd", "Bachelor of Education",
        "LLB", "L.L.B", "Bachelor of Laws",
        "M.Tech", "MTech", "Master of Technology",
        "M.E.", "M.E", "ME", "Master of Engineering",
        "M.Sc.", "M.Sc", "MSc", "Master of Science",
        "MCA", "Master of Computer Applications", "Master of Computer Application",
        "MBA", "Master of Business Administration",
        "M.Com.", "M.Com", "MCom", "Master of Commerce",
        "M.A.", "M.A", "MA", "Master of Arts",
        "M.Pharm.", "M.Pharm", "MPharm", "Master of Pharmacy",
        "M.Arch.", "M.Arch", "MArch", "Master of Architecture",
        "M.Des.", "M.Des", "MDes", "Master of Design",
        "M.Ed.", "M.Ed", "MEd", "Master of Education",
        "LLM", "L.L.M", "Master of Laws",
        "Ph.D.", "PhD", "Doctor of Philosophy", "Doctorate",
        "Diploma", "PGDM", "PGDCA", "ITI", "Industrial Training Institute",
        "CA", "CS", "ICWA", "CMA", "Degree", "Bachelor", "Master",
    })

    @classmethod
    def get_gazetteer_cities(cls) -> set[str]:
        if cls._gazetteer_cache is None:
            cls.refresh_cache()
        return cls._gazetteer_cache or set()

    @classmethod
    def get_countries(cls) -> set[str]:
        if cls._country_names_cache is None:
            cls.refresh_cache()
        return cls._country_names_cache or set()

    @classmethod
    def get_name_denylist(cls) -> set[str]:
        if cls._name_denylist_cache is None:
            cls.refresh_cache()
        return cls._name_denylist_cache or set()

    @classmethod
    def get_tech_and_role_denylist(cls) -> set[str]:
        if cls._tech_and_role_denylist_cache is None:
            cls.refresh_cache()
        return cls._tech_and_role_denylist_cache or set()

    @classmethod
    def get_section_headings(cls) -> set[str]:
        if cls._section_heading_cache is None:
            cls.refresh_cache()
        return cls._section_heading_cache or set()

    @classmethod
    def get_label_prefix_denylist(cls) -> set[str]:
        if cls._label_prefix_denylist_cache is None:
            cls.refresh_cache()
        return cls._label_prefix_denylist_cache or set()

    @classmethod
    def get_non_name_field_labels(cls) -> set[str]:
        if cls._non_name_field_labels_cache is None:
            cls.refresh_cache()
        return cls._non_name_field_labels_cache or set()

    @classmethod
    def get_verb_starters(cls) -> set[str]:
        if cls._verb_starters_cache is None:
            cls.refresh_cache()
        return cls._verb_starters_cache or set()

    @classmethod
    def get_preposition_and_conjunction_starters(cls) -> set[str]:
        if cls._preposition_starters_cache is None:
            cls.refresh_cache()
        return cls._preposition_starters_cache or set()

    @classmethod
    def get_allowed_compound_titles(cls) -> set[str]:
        if cls._allowed_compound_titles_cache is None:
            cls.refresh_cache()
        return cls._allowed_compound_titles_cache or set()

    @classmethod
    def get_common_roles(cls) -> set[str]:
        if cls._common_roles_cache is None:
            cls.refresh_cache()
        return cls._common_roles_cache or set()

    @classmethod
    def get_common_company_words(cls) -> set[str]:
        if cls._common_company_words_cache is None:
            cls.refresh_cache()
        return cls._common_company_words_cache or set()

    @classmethod
    def get_company_suffixes(cls) -> set[str]:
        if cls._company_suffixes_cache is None:
            cls.refresh_cache()
        return cls._company_suffixes_cache or set()

    @classmethod
    def get_degree_keywords(cls) -> set[str]:
        if cls._degree_keywords_cache is None:
            cls.refresh_cache()
        return cls._degree_keywords_cache or set()

    @classmethod
    def get_degree_pattern(cls) -> re.Pattern:
        if cls._degree_pattern_cache is None:
            cls.refresh_cache()
        if cls._degree_pattern_cache is None:
            cls._degree_pattern_cache = re.compile(
                r"\b(B\.?\s*Tech|B\.?E\.?|B\.?Sc\.?|BCA|BBA|B\.?\s*Com\.?|B\.?A\.?|B\.?\s*Pharm|B\.?\s*Arch|B\.?\s*Des|B\.?\s*Ed|L\.?L\.?B|Bachelor|M\.?\s*Tech|M\.?E\.?|M\.?Sc\.?|MCA|MBA|M\.?\s*Com\.?|M\.?\s*A\.?|M\.?\s*Pharm|M\.?\s*Arch|M\.?\s*Des|M\.?\s*Ed|L\.?L\.?M|Master|Ph\.?D|Doctorate|Diploma|PGDM|PGDCA|ITI|CA|CS|ICWA|CMA|Degree)\b",
                re.IGNORECASE,
            )
        return cls._degree_pattern_cache

    @classmethod
    def refresh_cache(cls) -> None:
        cities: set[str] = set()
        countries: set[str] = set(cls._DEFAULT_COUNTRIES)
        denylists: set[str] = set()
        tech_roles: set[str] = set(cls._DEFAULT_TECH_AND_ROLE_DENYLIST)
        headings: set[str] = set(cls._DEFAULT_SECTION_HEADINGS)
        label_prefixes: set[str] = set(cls._DEFAULT_LABEL_PREFIX_DENYLIST)
        non_name_labels: set[str] = set(cls._DEFAULT_NON_NAME_FIELD_LABELS)
        verb_starters: set[str] = set(cls._DEFAULT_VERB_STARTERS)
        prep_starters: set[str] = set(cls._DEFAULT_PREPOSITION_AND_CONJUNCTION_STARTERS)
        allowed_compounds: set[str] = set(cls._DEFAULT_ALLOWED_COMPOUND_TITLES)
        common_roles: set[str] = set(cls._DEFAULT_COMMON_ROLES)
        common_company_words: set[str] = set(cls._DEFAULT_COMMON_COMPANY_WORDS)
        company_suffixes: set[str] = set(cls._DEFAULT_COMPANY_SUFFIXES)
        degrees: set[str] = set(cls._DEFAULT_DEGREES)

        # 1. Load from DB if available
        if PostgresAppSession is not None:
            try:
                with PostgresAppSession() as session:
                    db_cities = session.query(GeoLocation.city_name).filter(GeoLocation.is_active == True).all()
                    cities.update(c[0].strip().lower() for c in db_cities if c[0])

                    db_denylists = session.query(NameDenylist.word).filter(NameDenylist.is_active == True).all()
                    denylists.update(d[0].strip().upper() for d in db_denylists if d[0])

                    db_headings = session.query(SectionHeading.heading_text).filter(SectionHeading.is_active == True).all()
                    headings.update(h[0].strip().lower() for h in db_headings if h[0])
            except Exception as exc:
                logger.warning(f"[DYNAMIC_GEO_HEADING] Database query failed: {exc}")

        # 2. Fallback / merge from RuleConfigManager
        try:
            config = RuleConfigManager.load_config()
            loc_field = config.fields.get("location")
            if loc_field:
                cities.update(loc_field.get_keyword_set("gazetteer"))
                countries.update(loc_field.get_upper_keyword_set("country_names"))

            name_field = config.fields.get("name")
            if name_field:
                denylists.update(name_field.get_upper_keyword_set("job_title_denylist"))
                denylists.update(name_field.get_upper_keyword_set("header_denylist"))
                tech_roles.update(name_field.get_upper_keyword_set("tech_and_role_denylist"))
                non_name_labels.update(name_field.get_keyword_set("non_name_field_labels"))

            comp_field = config.fields.get("company_name")
            if comp_field:
                headings.update(comp_field.get_keyword_set("generic_section_headers"))
                company_suffixes.update(comp_field.get_keyword_set("suffixes"))
                common_company_words.update(comp_field.get_keyword_set("common_company_words"))
                verb_starters.update(comp_field.get_keyword_set("verb_starters"))

            job_field = config.fields.get("job_title")
            if job_field:
                verb_starters.update(job_field.get_keyword_set("verb_starters"))
                verb_starters.update(job_field.get_keyword_set("narrative_starters"))
                prep_starters.update(job_field.get_keyword_set("preposition_starters"))
                allowed_compounds.update(job_field.get_keyword_set("allowed_compound"))
                common_roles.update(job_field.get_keyword_set("common_roles"))
                label_prefixes.update(job_field.get_keyword_set("label_prefixes"))

            edu_field = config.fields.get("education")
            if edu_field:
                degrees.update(edu_field.get_keyword_set("degrees"))
        except Exception as exc:
            logger.warning(f"[DYNAMIC_GEO_HEADING] Config fallback failed: {exc}")

        cls._gazetteer_cache = cities
        cls._country_names_cache = countries
        cls._name_denylist_cache = denylists
        cls._tech_and_role_denylist_cache = tech_roles
        cls._section_heading_cache = headings
        cls._label_prefix_denylist_cache = label_prefixes
        cls._non_name_field_labels_cache = non_name_labels
        cls._verb_starters_cache = verb_starters
        cls._preposition_starters_cache = prep_starters
        cls._allowed_compound_titles_cache = allowed_compounds
        cls._common_roles_cache = common_roles
        cls._common_company_words_cache = common_company_words
        cls._company_suffixes_cache = company_suffixes
        cls._degree_keywords_cache = degrees

        # Build dynamic degree pattern
        cls._degree_pattern_cache = re.compile(
            r"\b(B\.?\s*Tech|B\.?E\.?|B\.?Sc\.?|BCA|BBA|B\.?\s*Com\.?|B\.?A\.?|B\.?\s*Pharm|B\.?\s*Arch|B\.?\s*Des|B\.?\s*Ed|L\.?L\.?B|Bachelor|M\.?\s*Tech|M\.?E\.?|M\.?Sc\.?|MCA|MBA|M\.?\s*Com\.?|M\.?\s*A\.?|M\.?\s*Pharm|M\.?\s*Arch|M\.?\s*Des|M\.?\s*Ed|L\.?L\.?M|Master|Ph\.?D|Doctorate|Diploma|PGDM|PGDCA|ITI|CA|CS|ICWA|CMA|Degree)\b",
            re.IGNORECASE,
        )

        logger.info(
            f"[DYNAMIC_GEO_HEADING] Cache refreshed: {len(cities)} gazetteer cities, {len(countries)} countries, "
            f"{len(denylists)} name denylists, {len(tech_roles)} tech/role keywords, {len(headings)} section headings, "
            f"{len(verb_starters)} verb starters, {len(degrees)} degrees."
        )

    @classmethod
    def is_city_in_gazetteer(cls, city_or_location: str) -> bool:
        clean = city_or_location.strip().lower()
        if not clean:
            return False
        gazetteer = cls.get_gazetteer_cities()
        return clean in gazetteer or any(city in clean for city in gazetteer if len(city) > 3)

    @classmethod
    def is_country(cls, candidate: str) -> bool:
        clean = candidate.strip().upper()
        if not clean:
            return False
        return clean in cls.get_countries()

    @classmethod
    def is_word_in_name_denylist(cls, word: str) -> bool:
        clean = word.strip().upper()
        if not clean:
            return False
        return clean in cls.get_name_denylist()
