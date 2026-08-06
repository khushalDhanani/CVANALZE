# PR4 AIRIS MSSQL Metadata Handoff

Use the accompanying JSON as the authoritative source for PR4 model and repository implementation.

## Rules

- MSSQL `AIRIS_TEST` is read-only.
- Preserve exact table and column names, including `RecruitVacancyRequriedQualificationDet`.
- Do not invent substitute tables or columns.
- PostgreSQL owns CV Analyzer application data.

## Included table groups

### Candidate
- `dbo.RecruitCandidateMst`
- `dbo.RecruitCandidateExperienceDet`
- `dbo.RecruitCandidateQualificationDet`
- `dbo.RecruitCandidateSkillDet`
- `dbo.RecruitCandidateLanguageDet`
- `dbo.RecruitCandidateLocationMst`
- `dbo.RecruitCandidateNoticePeriodMst`

### Vacancy and workflow
- `dbo.RecruitVacancyRequest`
- `dbo.RecruitVacancyRequriedQualificationDet`
- `dbo.RecruitVacancyCandidateList`
- `dbo.RecruitVacancyRequestTrack`
- `dbo.RecruitVacancyCandidiateHistoryDet`

### Organization
- `dbo.OrgCompanyMst`
- `dbo.OrgLocationMst`
- `dbo.OrgMainDepartmentMst`
- `dbo.OrgDepartmentMst`
- `dbo.OrgDesignationMst`
- `dbo.OrgDesignationMappingDet`

### Job profile
- `dbo.OrgJobProfileMst`
- `dbo.JobProfileDepartmentDet`
- `dbo.JobProfileDomainKnowledgeDet`
- `dbo.OrgJobProfileQualificationDet`

### Taxonomy and lookups
- `dbo.RecruitDomainKnowledgeMst`
- `dbo.RecruitDomainKnowledgeDeptDet`
- `dbo.RecruitDomainKnowledgeSkillDet`
- `dbo.RecruitSkillMst`
- `dbo.RecruitSkillTypeMst`
- `dbo.QualificationMst`
- `dbo.TransactionStatusMst`
- `dbo.LanguageMst`
- `dbo.CityMst`
- `dbo.StateMst`
- `dbo.CountryMst`
- `dbo.OrgBusinessGroupMst`
- `dbo.OrgDesignationMstAether`
- `dbo.EmployeeGradeMst`
- `dbo.RecruitChannelMst`
- `dbo.RecruitChannelCategoryMst`

## Required implementation

Create read-only SQLAlchemy models and dedicated repositories:

- `CandidateSourceRepository`
- `VacancySourceRepository`
- `OrganizationSourceRepository`
- `JobProfileSourceRepository`
- `TaxonomySourceRepository`
- `QualificationSourceRepository`

Required aggregate methods:

- `get_candidate_aggregate(candidate_id)`
- `get_vacancy_aggregate(vacancy_id)`
- `get_job_profile_aggregate(job_profile_id)`

All queries must use explicit columns, bound parameters, timeouts, and the MSSQL read-only session.