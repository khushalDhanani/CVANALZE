import argparse
import re
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import engine

LEADING_PHRASES = (
    "ability to",
    "excellent",
    "experience in",
    "experience with",
    "familiar with",
    "familiarity with",
    "good knowledge of",
    "hands-on experience in",
    "knowledge of",
    "proficiency in",
    "proficient in",
    "should have a knowledge of using",
    "solid understanding of",
    "strong communication and",
    "strong understanding of",
)

NOISE_TERMS = {
    "ability",
    "ability to work effectively in a team environment",
    "excellent problem-solving and debugging skills",
    "interpersonal skills",
    "skills",
    "strong communication",
}


def _clean_phrase(value: str) -> str:
    phrase = re.sub(r"\s+", " ", value.strip(" >•*.#;:-\t\r\n"))
    phrase = re.sub(r"^(?:and|or|with|using|particularly)\s+", "", phrase, flags=re.IGNORECASE)

    lowered = phrase.lower()
    for leading in LEADING_PHRASES:
        if lowered.startswith(leading):
            phrase = phrase[len(leading) :].strip(" .;:-")
            break

    phrase = re.sub(r"\b(?:e\.g\.|i\.e\.)\b", "", phrase, flags=re.IGNORECASE)
    phrase = re.sub(r"\s+", " ", phrase.strip(" .;:-\t\r\n"))
    return phrase


def extract_required_skill_terms(description: str) -> str:
    terms: list[str] = []

    for raw_line in description.splitlines():
        line = raw_line.strip(" -\t\r\n")
        if not line:
            continue

        parenthetical_parts = re.findall(r"\(([^)]*)\)", line)
        line = re.sub(r"\(([^)]*)\)", r", \1, ", line)
        line = re.sub(r"\bincluding\b", ",", line, flags=re.IGNORECASE)

        fragments = re.split(r",|;|\band\b", line)
        for parenthetical in parenthetical_parts:
            fragments.extend(re.split(r",|;|\band\b", parenthetical))

        for fragment in fragments:
            term = _clean_phrase(fragment)
            lowered = term.lower()
            if not term or lowered in NOISE_TERMS or len(term) < 3:
                continue
            if len(term.split()) > 8:
                continue
            if term not in terms:
                terms.append(term)

    return ", ".join(terms)


def fit_to_column(value: str, max_length: int | None) -> str:
    if not max_length or max_length < 0 or len(value) <= max_length:
        return value

    terms = [term.strip() for term in value.split(",") if term.strip()]
    fitted_terms: list[str] = []
    for term in terms:
        candidate = ", ".join([*fitted_terms, term])
        if len(candidate) > max_length:
            break
        fitted_terms.append(term)

    if fitted_terms:
        return ", ".join(fitted_terms)
    return value[:max_length].rstrip(" ,")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill RecruitVacancyRequest.RequestedAdditionalKnowledge from "
            "OrgJobProfileMst.JobProfileDesc for rows where the skills field is NULL or blank."
        )
    )
    parser.add_argument("--apply", action="store_true", help="Apply the update. Defaults to dry-run.")
    args = parser.parse_args()

    if engine is None:
        raise RuntimeError("Database connection is not configured.")

    select_sql = text(
        """
        SELECT
            v.VacancyRequestID,
            jp.JobProfileName,
            jp.JobProfileDesc
        FROM RecruitVacancyRequest v
        JOIN OrgJobProfileMst jp ON v.JobProfileID = jp.JobProfileID
        WHERE (
            v.RequestedAdditionalKnowledge IS NULL
            OR LTRIM(RTRIM(CAST(v.RequestedAdditionalKnowledge AS NVARCHAR(MAX)))) = ''
          )
          AND jp.JobProfileDesc IS NOT NULL
          AND LTRIM(RTRIM(CAST(jp.JobProfileDesc AS NVARCHAR(MAX)))) <> ''
        ORDER BY v.VacancyRequestID
        """
    )
    update_sql = text(
        """
        UPDATE RecruitVacancyRequest
        SET RequestedAdditionalKnowledge = :required_skills
        WHERE VacancyRequestID = :vacancy_id
          AND (
              RequestedAdditionalKnowledge IS NULL
              OR LTRIM(RTRIM(CAST(RequestedAdditionalKnowledge AS NVARCHAR(MAX)))) = ''
          )
        """
    )

    with engine.begin() as conn:
        max_length = conn.execute(
            text(
                """
                SELECT CHARACTER_MAXIMUM_LENGTH
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'RecruitVacancyRequest'
                  AND COLUMN_NAME = 'RequestedAdditionalKnowledge'
                """
            )
        ).scalar()
        rows = conn.execute(select_sql).mappings().all()
        updates = [
            {
                "vacancy_id": row["VacancyRequestID"],
                "job_title": row["JobProfileName"],
                "required_skills": fit_to_column(
                    extract_required_skill_terms(row["JobProfileDesc"] or ""),
                    max_length,
                ),
            }
            for row in rows
        ]
        updates = [u for u in updates if u["required_skills"]]

        print(f"candidate_rows={len(rows)}")
        print(f"rows_with_extracted_required_skills={len(updates)}")
        for sample in updates[:10]:
            print(
                f"sample vacancy_id={sample['vacancy_id']} title={sample['job_title']!r} "
                f"required_skills={sample['required_skills']!r}"
            )

        if not args.apply:
            print("dry_run=true")
            return

        result = conn.execute(update_sql, updates)
        print(f"updated_rows={result.rowcount}")


if __name__ == "__main__":
    main()
