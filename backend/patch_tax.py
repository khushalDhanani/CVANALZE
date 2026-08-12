with open('app/services/job_taxonomy.py', 'r') as f:
    content = f.read()

# Update CandidateResumeDTO class
old_dto = """    skills: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    normalized_full_text: str = ""

    @classmethod
    def from_resume(cls, cv_text: str, resume_json: dict[str, Any] | None = None) -> "CandidateResumeDTO":
        text_lower = cv_text.lower()
        summary = ""
        exp_titles: list[str] = []
        skills_str: list[str] = []
        edu_str: list[str] = []
        responsibilities: list[str] = []"""

new_dto = """    skills: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    normalized_full_text: str = ""
    
    # Original-casing strings kept local for case-sensitive acronym matching
    raw_summary: str = ""
    raw_experience_titles: list[str] = Field(default_factory=list)
    raw_responsibilities: list[str] = Field(default_factory=list)
    raw_skills: list[str] = Field(default_factory=list)
    raw_education: list[str] = Field(default_factory=list)

    @classmethod
    def from_resume(cls, cv_text: str, resume_json: dict[str, Any] | None = None) -> "CandidateResumeDTO":
        text_lower = cv_text.lower()
        raw_summary = ""
        raw_exp_titles: list[str] = []
        raw_skills_str: list[str] = []
        raw_edu_str: list[str] = []
        raw_responsibilities: list[str] = []
        
        summary = ""
        exp_titles: list[str] = []
        skills_str: list[str] = []
        edu_str: list[str] = []
        responsibilities: list[str] = []"""

content = content.replace(old_dto, new_dto)

# Update from_resume extraction
old_extract = """        if resume_json and isinstance(resume_json, dict):
            summary = str(resume_json.get("summary") or "").lower()
            exp_list = resume_json.get("work_experience", []) or resume_json.get("experience", [])
            if isinstance(exp_list, list):
                exp_titles = [str(e.get("job_title") or e.get("title") or "").lower() for e in exp_list if isinstance(e, dict)]
                for experience in exp_list:
                    if not isinstance(experience, dict):
                        continue
                    responsibilities.extend(
                        str(item).lower()
                        for item in experience.get("responsibilities") or []
                        if isinstance(item, str) and item.strip()
                    )
            
            skills_data = resume_json.get("skills")
            if isinstance(skills_data, dict):
                if "all_skills" in skills_data:
                    skills_str = [str(s).lower() for s in skills_data["all_skills"]]
                elif "categorized" in skills_data:
                    for cat, s_list in skills_data["categorized"].items():
                        if isinstance(s_list, list):
                            skills_str.extend([str(s).lower() for s in s_list])
            elif isinstance(skills_data, list):
                skills_str = [str(s).lower() for s in skills_data]
            
            edu_list = resume_json.get("education", [])
            if isinstance(edu_list, list):
                edu_str = [str(e.get("degree", "")) + " " + str(e.get("field", "")) + " " + str(e.get("institution", "")) if isinstance(e, dict) else str(e).lower() for e in edu_list]

        combined = f"{text_lower} {summary} {' '.join(exp_titles)} {' '.join(responsibilities)} {' '.join(skills_str)} {' '.join(edu_str)}"
        norm_full_text = re.sub(r"\s+", " ", combined).strip()

        return cls(
            experience_titles=exp_titles,
            responsibilities=responsibilities,
            summary=summary,
            skills=skills_str,
            education=edu_str,
            normalized_full_text=norm_full_text,
        )"""

new_extract = """        if resume_json and isinstance(resume_json, dict):
            raw_summary = str(resume_json.get("summary") or "")
            summary = raw_summary.lower()
            
            exp_list = resume_json.get("work_experience", []) or resume_json.get("experience", [])
            if isinstance(exp_list, list):
                raw_exp_titles = [str(e.get("job_title") or e.get("title") or "") for e in exp_list if isinstance(e, dict)]
                exp_titles = [t.lower() for t in raw_exp_titles]
                for experience in exp_list:
                    if not isinstance(experience, dict):
                        continue
                    for item in experience.get("responsibilities") or []:
                        if isinstance(item, str) and item.strip():
                            raw_responsibilities.append(str(item))
                            responsibilities.append(str(item).lower())
            
            skills_data = resume_json.get("skills")
            if isinstance(skills_data, dict):
                if "all_skills" in skills_data:
                    raw_skills_str = [str(s) for s in skills_data["all_skills"]]
                elif "categorized" in skills_data:
                    for cat, s_list in skills_data["categorized"].items():
                        if isinstance(s_list, list):
                            raw_skills_str.extend([str(s) for s in s_list])
            elif isinstance(skills_data, list):
                raw_skills_str = [str(s) for s in skills_data]
            skills_str = [s.lower() for s in raw_skills_str]
            
            edu_list = resume_json.get("education", [])
            if isinstance(edu_list, list):
                raw_edu_str = [str(e.get("degree", "")) + " " + str(e.get("field", "")) + " " + str(e.get("institution", "")) if isinstance(e, dict) else str(e) for e in edu_list]
                edu_str = [e.lower() for e in raw_edu_str]

        if not summary and not exp_titles and not skills_str:
            raw_summary = cv_text
            summary = text_lower

        combined = f"{text_lower} {summary} {' '.join(exp_titles)} {' '.join(responsibilities)} {' '.join(skills_str)} {' '.join(edu_str)}"
        norm_full_text = re.sub(r"\\s+", " ", combined).strip()

        return cls(
            experience_titles=exp_titles,
            responsibilities=responsibilities,
            summary=summary,
            skills=skills_str,
            education=edu_str,
            normalized_full_text=norm_full_text,
            raw_summary=raw_summary,
            raw_experience_titles=raw_exp_titles,
            raw_responsibilities=raw_responsibilities,
            raw_skills=raw_skills_str,
            raw_education=raw_edu_str,
        )"""

content = content.replace(old_extract, new_extract)

# Update classify_candidate_dto
old_classify = """        w_summary = tax_rules.evidence_weight_summary
        w_edu = tax_rules.evidence_weight_education
        
        exp_text = " ".join(dto.experience_titles).lower()
        skills_text = " ".join(dto.skills).lower()
        summary_text = dto.summary.lower() if dto.summary else ""
        edu_text = " ".join(dto.education).lower()
        responsibilities_text = " ".join(dto.responsibilities).lower()"""

new_classify = """        w_summary = tax_rules.evidence_weight_summary
        w_edu = tax_rules.evidence_weight_education
        
        exp_text = " ".join(dto.raw_experience_titles)
        skills_text = " ".join(dto.raw_skills)
        summary_text = dto.raw_summary if dto.raw_summary else ""
        edu_text = " ".join(dto.raw_education)
        responsibilities_text = " ".join(dto.raw_responsibilities)"""

content = content.replace(old_classify, new_classify)

with open('app/services/job_taxonomy.py', 'w') as f:
    f.write(content)
