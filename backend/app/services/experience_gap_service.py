from __future__ import annotations
import datetime
import re
from typing import Any, Optional
from dateutil.relativedelta import relativedelta

from app.core.logging import logger
from app.schemas.experience_gap import (
    CanonicalJob,
    ChildAssignment,
    ConcurrentRoleCluster,
    EmploymentEntityResolution,
    ExperienceGap,
    ExperienceGapAnalysis,
    ExperienceTimelineNode,
    ExperienceTimelineSummary,
    TimelineEvent,
)
from app.services.date_interval_parser import DateIntervalParser


class ExperienceGapService:
    """
    Data-driven, domain-agnostic Experience Gap Analysis service for HR.
    
    Implements explicit 7-Type Employment Entity Resolution:
    - PARENT_EMPLOYMENT
    - INTERNAL_ROLE
    - DEPUTATION
    - PROMOTION_TRANSFER
    - INDEPENDENT_CONCURRENT_ROLE
    - DUPLICATE
    - INVALID_HEADING
    
    Guarantees:
    1. Structural/bullet evidence date association (no broad 3500-char window sweeps).
    2. Safe Present Defaulting (never assume Present without current employment evidence).
    3. Single Canonical Timeline Source for Experience, Concurrency, Gaps, and Frontend Timeline.
    4. Genuine Independent Concurrency (excludes internal sub-roles, deputations, and promotions).
    """

    DEFAULT_GAP_THRESHOLD_DAYS = 60
    PLACEHOLDER_COMPANIES = {"organization", "company", "n/a", "none", "null", "position", "job title", ""}
    PLACEHOLDER_TITLES = {"position", "job title", "n/a", "none", "null", "organization", "company", ""}
    SUB_ROLE_KEYWORDS = {
        "deputation",
        "deputed",
        "secondment",
        "internal assignment",
        "sub-role",
        "project assignment",
        "project posting",
        "assignment",
        "promoted",
        "promotion",
        "transferred",
        "internal transfer",
        "rotation",
        "role change",
    }

    JOB_TITLE_KEYWORDS = {
        "sr. executive",
        "senior executive",
        "junior executive",
        "jr. executive",
        "executive",
        "manager",
        "developer",
        "engineer",
        "analyst",
        "consultant",
        "inspector",
        "director",
        "lead",
        "officer",
        "specialist",
        "qa operations",
        "field operations",
        "position",
    }

    @classmethod
    def _is_job_title_string(cls, text: str) -> bool:
        clean = text.lower().strip()
        return any(kw in clean for kw in cls.JOB_TITLE_KEYWORDS)

    @classmethod
    def _sanitize_company_and_title(cls, company: str, title: str) -> tuple[str, str]:
        c_clean = cls._clean_text(company)
        t_clean = cls._clean_text(title)

        if c_clean and cls._is_job_title_string(c_clean) and not t_clean:
            t_clean = c_clean
            c_clean = ""
        elif c_clean and cls._is_job_title_string(c_clean) and t_clean and t_clean.lower() in ("position", "job title", "n/a", "none"):
            t_clean = c_clean
            c_clean = ""

        return c_clean, t_clean

    @classmethod
    def _stitch_adjacent_work_exp(cls, work_exp: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not work_exp:
            return []

        stitched: list[dict[str, Any]] = []
        i = 0
        n = len(work_exp)

        while i < n:
            curr = work_exp[i]
            if not isinstance(curr, dict):
                i += 1
                continue

            c_curr = cls._clean_text(curr.get("company") or "")
            d_curr = str(curr.get("dates") or "").strip()
            r_curr = curr.get("responsibilities") or []

            if i + 1 < n and isinstance(work_exp[i + 1], dict):
                nxt = work_exp[i + 1]
                c_nxt = cls._clean_text(nxt.get("company") or "")
                t_nxt = cls._clean_text(nxt.get("job_title") or "")
                d_nxt = str(nxt.get("dates") or "").strip()
                r_nxt = nxt.get("responsibilities") or []

                if c_curr and not cls._is_job_title_string(c_curr) and not d_curr and not r_curr:
                    if not c_nxt or cls._is_job_title_string(c_nxt):
                        stitched_item = dict(nxt)
                        stitched_item["company"] = c_curr
                        if cls._is_job_title_string(c_nxt) and not t_nxt:
                            stitched_item["job_title"] = c_nxt
                        stitched.append(stitched_item)
                        i += 2
                        continue

            stitched.append(curr)
            i += 1

        return stitched

    @classmethod
    def analyze_timeline(
        cls,
        resume_json: dict[str, Any],
        cv_text: str = "",
        reference_date: Optional[datetime.date] = None,
        authoritative_years: Optional[float] = None,
        gap_threshold_days: Optional[int] = None,
    ) -> ExperienceGapAnalysis:
        ref_date = reference_date or datetime.date.today()
        threshold_days = gap_threshold_days or cls.DEFAULT_GAP_THRESHOLD_DAYS

        raw_work_exp = (
            resume_json.get("work_experience")
            or resume_json.get("experience")
            or (resume_json.get("normalized") or {}).get("employment")
            or []
        )
        work_exp = cls._stitch_adjacent_work_exp(raw_work_exp)

        edu_list = (
            resume_json.get("education")
            or (resume_json.get("normalized") or {}).get("education")
            or []
        )

        # ----------------------------------------------------------------------
        # STAGE 1: Explicit 7-Type Employment Entity Resolution
        # ----------------------------------------------------------------------
        resolved_entries: list[dict[str, Any]] = []
        undated_entries: list[dict[str, Any]] = []
        undated_nodes: list[ExperienceTimelineNode] = []
        all_nodes: list[ExperienceTimelineNode] = []

        existing_parent_keys: list[str] = []

        for idx, job in enumerate(work_exp, start=1):
            if not isinstance(job, dict):
                continue
            raw_dates = str(
                job.get("dates")
                or (job.get("interval") or {}).get("raw_value")
                or ""
            ).strip()
            raw_title = cls._clean_text(
                job.get("job_title")
                or (job.get("job_title") or {}).get("normalized_value")
                or ""
            )
            raw_company = cls._clean_text(
                job.get("company")
                or (job.get("company") or {}).get("normalized_value")
                or job.get("company_name")
                or ""
            )
            emp_type = str(job.get("employment_type") or "full_time").lower()
            resps = job.get("responsibilities") or []
            if isinstance(resps, str):
                resps = [resps]
            desc = job.get("description") or job.get("summary")
            if desc and isinstance(desc, str):
                resps.insert(0, desc)
            evidence = job.get("evidence") or []

            company, title = cls._sanitize_company_and_title(raw_company, raw_title)

            resolution = cls._classify_entry_resolution(company, title, raw_dates, resps, existing_parent_keys)

            # Purge INVALID_HEADING placeholder entries
            if resolution == "INVALID_HEADING":
                continue

            fallback_company = company or "Organization"
            parent_key = cls._get_parent_company_key(fallback_company)
            
            if title:
                fallback_title = title
            elif resolution == "DEPUTATION":
                clean_comp = re.sub(r"\s*\(?Deputation\)?\s*", "", company, flags=re.I).strip(" -–▸")
                fallback_title = clean_comp or "Deputation"
            elif resolution in ("INTERNAL_ROLE", "PROMOTION_TRANSFER"):
                clean_comp = re.sub(r"^\W*"+re.escape(parent_key)+r"\W*", "", company, flags=re.I).strip(" -–▸")
                if not clean_comp and company != parent_key:
                    clean_comp = company.replace(parent_key, "").strip(" -–▸")
                fallback_title = clean_comp or ("Promotion" if resolution == "PROMOTION_TRANSFER" else "Internal Assignment")
            else:
                if not company:
                    fallback_title = "Internal Assignment"
                else:
                    fallback_title = "Position"
                    
            if parent_key not in existing_parent_keys:
                existing_parent_keys.append(parent_key)

            # Strict Structural Date Normalization
            start_dt, end_dt, is_current, precision, date_conf = cls._parse_job_dates_strict(
                raw_dates, job, cv_text, fallback_company, fallback_title, resps, evidence, ref_date
            )

            start_iso = start_dt.isoformat() if start_dt else None
            end_iso = end_dt.isoformat() if end_dt and not is_current else None

            duration_months = 0
            if start_dt and end_dt:
                delta = relativedelta(end_dt + datetime.timedelta(days=1), start_dt)
                duration_months = max(1, (delta.years * 12) + delta.months)

            record_id = f"emp_{idx}"
            node = ExperienceTimelineNode(
                record_id=record_id,
                company=fallback_company,
                job_title=fallback_title,
                employment_type=emp_type,
                start_date=start_iso,
                end_date=end_iso if not is_current else "Present",
                is_current=is_current,
                duration_months=duration_months,
                precision=precision,
                date_confidence=date_conf,
                responsibilities=resps[:3] if isinstance(resps, list) else [],
            )
            all_nodes.append(node)

            entry = {
                "node": node,
                "record_id": record_id,
                "title": fallback_title,
                "company": fallback_company,
                "parent_key": parent_key,
                "resolution": resolution,
                "start_dt": start_dt,
                "end_dt": end_dt or (ref_date if is_current else start_dt),
                "is_current": is_current,
                "emp_type": emp_type,
                "precision": precision,
                "date_confidence": date_conf,
                "raw_dates": raw_dates,
                "resps": resps,
            }

            if start_dt:
                resolved_entries.append(entry)
            else:
                undated_entries.append(entry)

        # ----------------------------------------------------------------------
        # STAGE 2: Deduplication & Canonical Jobs Construction
        # ----------------------------------------------------------------------
        canonical_jobs = cls._build_canonical_jobs(resolved_entries, ref_date, undated_entries, undated_nodes)

        # ----------------------------------------------------------------------
        # STAGE 3: Single Source Mathematical Interval Union Experience
        # ----------------------------------------------------------------------
        canonical_intervals = [(cj.start_date, cj.end_date, cj) for cj in canonical_jobs if cj.start_date]
        parsed_canon_ranges: list[tuple[datetime.date, datetime.date]] = []
        for s_iso, e_iso, cj in canonical_intervals:
            s_d = datetime.date.fromisoformat(s_iso)
            e_d = ref_date if cj.is_current else (datetime.date.fromisoformat(e_iso) if e_iso and e_iso != "Present" else s_d)
            parsed_canon_ranges.append((s_d, e_d))

        parsed_canon_ranges.sort(key=lambda x: x[0])

        unique_days = 0
        if parsed_canon_ranges:
            cur_s, cur_e = parsed_canon_ranges[0][0], parsed_canon_ranges[0][1]
            for s, e in parsed_canon_ranges[1:]:
                if s <= cur_e:
                    cur_e = max(cur_e, e)
                else:
                    unique_days += (cur_e - cur_s).days + 1
                    cur_s, cur_e = s, e
            unique_days += (cur_e - cur_s).days + 1

        total_verified_years = round(unique_days / 365.25, 1)

        # ----------------------------------------------------------------------
        # STAGE 4: Genuine Independent Concurrency Resolution
        # ----------------------------------------------------------------------
        genuine_concurrency_count = cls._calculate_genuine_concurrency(canonical_jobs, ref_date)

        # ----------------------------------------------------------------------
        # STAGE 5: Employment Gap Sweeping (Canonical Jobs Only)
        # ----------------------------------------------------------------------
        edu_intervals: list[tuple[datetime.date, datetime.date, str]] = []
        for edu in edu_list:
            if not isinstance(edu, dict):
                continue
            edu_dates = edu.get("dates") or (edu.get("interval") or {}).get("raw_value")
            degree = edu.get("degree") or "Degree"
            if edu_dates and isinstance(edu_dates, str):
                interval = DateIntervalParser.parse_interval(edu_dates)
                if interval.start_date:
                    s_d = datetime.date.fromisoformat(interval.start_date)
                    e_d = (
                        datetime.date.fromisoformat(interval.end_date)
                        if interval.end_date
                        else (ref_date if interval.is_current else s_d)
                    )
                    edu_intervals.append((s_d, e_d, str(degree)))

        consolidated_blocks = cls._consolidate_canonical_blocks(canonical_jobs, ref_date)

        detected_gaps: list[ExperienceGap] = []
        hr_indicators: list[str] = []
        gap_counter = 1
        unexplained_gap_months_total = 0.0

        for idx in range(len(consolidated_blocks) - 1):
            curr_block = consolidated_blocks[idx]
            next_block = consolidated_blocks[idx + 1]

            gap_start = curr_block["end_dt"] + datetime.timedelta(days=1)
            gap_end = next_block["start_dt"] - datetime.timedelta(days=1)
            gap_days = (gap_end - gap_start).days + 1

            if gap_days >= threshold_days:
                gap_months = round(gap_days / 30.4375, 1)
                coverage_status, hr_reason, reliability = cls._evaluate_gap_coverage(
                    gap_start, gap_end, edu_intervals, resolved_entries
                )

                prec_str = curr_block["job"].parent_company
                foll_str = next_block["job"].parent_company

                status_display = coverage_status.replace("_", " ").title()
                desc = (
                    f"{gap_months} month employment gap ({status_display}) between "
                    f"{prec_str} and {foll_str}."
                )

                hr_flag = coverage_status in ("UNEXPLAINED", "TIMELINE_UNCERTAINTY") and gap_months >= 3.0

                gap_obj = ExperienceGap(
                    gap_id=f"gap_{gap_counter}",
                    category="EMPLOYMENT_GAP",
                    coverage_status=coverage_status,
                    boundary_reliability=reliability,
                    start_date=gap_start.isoformat(),
                    end_date=gap_end.isoformat(),
                    duration_days=gap_days,
                    duration_months=gap_months,
                    preceding_role=prec_str,
                    following_role=foll_str,
                    description=desc,
                    hr_review_indicator=hr_flag,
                    hr_review_reason=hr_reason,
                )
                detected_gaps.append(gap_obj)
                gap_counter += 1

                if coverage_status == "UNEXPLAINED":
                    unexplained_gap_months_total += gap_months
                    if gap_months >= 6.0:
                        hr_indicators.append(
                            f"Unexplained {gap_months} month employment gap between {gap_start.strftime('%b %Y')} and {gap_end.strftime('%b %Y')}."
                        )

        # ----------------------------------------------------------------------
        # STAGE 6: Payload Output & Timeline Event Generation
        # ----------------------------------------------------------------------
        timeline_events = cls._build_timeline_events(canonical_jobs, detected_gaps, ref_date)

        if resolved_entries:
            reliable_count = sum(1 for p in resolved_entries if p["date_confidence"] in ("EXACT", "MONTH_ONLY"))
            analysis_confidence = round(reliable_count / len(resolved_entries), 2)
            uncertainty_flags = sum(1 for p in resolved_entries if p["date_confidence"] in ("YEAR_ONLY", "UNKNOWN"))
            uncertainty_score = round(uncertainty_flags / len(resolved_entries), 2)
        else:
            analysis_confidence = 0.5
            uncertainty_score = 0.5

        total_months = int(round(total_verified_years * 12))
        years_part = total_months // 12
        months_part = total_months % 12
        gross_display = f"{years_part} years {months_part} months"

        has_current = any(cj.is_current for cj in canonical_jobs)
        unexplained_gaps = [g for g in detected_gaps if g.coverage_status == "UNEXPLAINED"]
        sig_gaps = [g for g in detected_gaps if g.duration_months >= 3.0]

        hr_obs: list[str] = []
        hr_obs.append(f"Total Employment Duration: {total_verified_years:.1f} years ({gross_display}).")
        if has_current:
            hr_obs.append("Candidate is currently employed in an active role.")
        if genuine_concurrency_count > 0:
            hr_obs.append(f"Documented {genuine_concurrency_count} genuine independent concurrent employment period(s).")
        if unexplained_gaps:
            hr_obs.append(f"Identified {len(unexplained_gaps)} unexplained employment gap(s).")
        elif detected_gaps:
            hr_obs.append(f"Identified {len(detected_gaps)} employment gap(s) (covered by education/freelance).")
        else:
            hr_obs.append("Continuous employment history with zero detected gaps.")

        summary = ExperienceTimelineSummary(
            total_verified_years=total_verified_years,
            gross_display=gross_display,
            timeline_start_date=parsed_canon_ranges[0][0].isoformat() if parsed_canon_ranges else None,
            timeline_end_date=(ref_date if has_current else parsed_canon_ranges[-1][1]).isoformat() if parsed_canon_ranges else None,
            has_current_employment=has_current,
            concurrent_roles_count=genuine_concurrency_count,
            total_employment_gaps_count=len(detected_gaps),
            unexplained_gaps_count=len(unexplained_gaps),
            significant_gaps_count=len(sig_gaps),
            total_gap_duration_months=round(unexplained_gap_months_total, 1),
            analysis_confidence=analysis_confidence,
            timeline_uncertainty_score=uncertainty_score,
            hr_review_required=bool(hr_indicators) or analysis_confidence < 0.5,
            hr_observations=hr_obs,
        )

        return ExperienceGapAnalysis(
            summary=summary,
            detected_gaps=detected_gaps,
            canonical_jobs=canonical_jobs,
            timeline_nodes=all_nodes,
            undated_nodes=undated_nodes,
            timeline_events=timeline_events,
            hr_review_indicators=hr_indicators,
        )

    # ==========================================================================
    # HELPER METHODS FOR ENTITY RESOLUTION & PIPELINE
    # ==========================================================================

    @classmethod
    def _classify_entry_resolution(
        cls,
        company: str,
        title: str,
        raw_dates: str,
        resps: list[Any],
        existing_parents: list[str],
    ) -> EmploymentEntityResolution:
        c_clean = company.lower().strip()
        t_clean = title.lower().strip()
        has_dates = bool(raw_dates and raw_dates != "N/A")
        has_resps = bool(resps)

        if not has_dates and not has_resps:
            if c_clean in cls.PLACEHOLDER_COMPANIES or t_clean in cls.PLACEHOLDER_TITLES:
                return "INVALID_HEADING"

        combined_text = f"{company} {title} {' '.join(str(r) for r in resps)}".lower()

        if any(kw in combined_text for kw in ("deputation", "deputed", "secondment")):
            return "DEPUTATION"

        if any(kw in combined_text for kw in ("promotion", "promoted", "transfer", "transferred", "rotation")):
            return "PROMOTION_TRANSFER"

        parent_key = cls._get_parent_company_key(company)
        for existing in existing_parents:
            if cls._are_same_employer(parent_key, existing):
                return "INTERNAL_ROLE"

        if any(kw in combined_text for kw in ("sub-role", "internal assignment", "project posting", "project assignment")):
            return "INTERNAL_ROLE"

        return "PARENT_EMPLOYMENT"

    @classmethod
    def _are_same_employer(cls, parent_a: str, parent_b: str) -> bool:
        a_clean = parent_a.lower().strip()
        b_clean = parent_b.lower().strip()
        if not a_clean or not b_clean:
            return False
        if a_clean in b_clean or b_clean in a_clean:
            return True
        tok_a = a_clean.split()[:2]
        tok_b = b_clean.split()[:2]
        if len(tok_a) >= 2 and tok_a == tok_b:
            return True
        return False

    @classmethod
    def _clean_text(cls, text: str) -> str:
        if not text:
            return ""
        return str(text).replace("#", "").strip(" -•\t\n")

    @classmethod
    def _get_parent_company_key(cls, company: str) -> str:
        clean = cls._clean_text(company)
        clean = re.sub(r"\s*[\-–—]\s*(Quality Assurance|Operations|Engineering|Singapore|Deputation).*$", "", clean, flags=re.I)
        return clean.strip()

    @classmethod
    def _parse_job_dates_strict(
        cls,
        raw_dates: str,
        job: dict[str, Any],
        cv_text: str,
        company: str,
        title: str,
        resps: list[Any],
        evidence: list[Any],
        ref_date: datetime.date,
    ) -> tuple[Optional[datetime.date], Optional[datetime.date], bool, str, str]:
        start_dt, end_dt = None, None
        is_current = False
        precision = "day"
        date_conf = "MONTH_ONLY"

        if raw_dates and isinstance(raw_dates, str) and raw_dates != "N/A":
            interval = DateIntervalParser.parse_interval(raw_dates)
            is_current = interval.is_current
            if interval.start_date:
                try:
                    start_dt = datetime.date.fromisoformat(interval.start_date)
                except ValueError:
                    pass
            if interval.end_date and not is_current:
                try:
                    end_dt = datetime.date.fromisoformat(interval.end_date)
                except ValueError:
                    pass

            raw_str = raw_dates.strip()
            if re.search(r"^\d{2}/\d{2}/\d{4}", raw_str) or re.search(r"^\d{4}-\d{2}-\d{2}", raw_str):
                precision = "day"
                date_conf = "EXACT"
            elif re.search(r"^\d{4}\s*[\-–—]\s*\d{4}$", raw_str) or re.search(r"^\d{4}$", raw_str):
                precision = "year"
                date_conf = "YEAR_ONLY"
            else:
                precision = "month"
                date_conf = "MONTH_ONLY"

        # Localized bullet evidence date parsing (max 300 chars)
        if not start_dt:
            combined_bullets = " ".join([str(r) for r in resps[:3]] + [str(e) for e in evidence[:2]])
            if len(combined_bullets) <= 400:
                inv = DateIntervalParser.parse_interval(combined_bullets)
                if inv.start_date:
                    try:
                        start_dt = datetime.date.fromisoformat(inv.start_date)
                        end_dt = datetime.date.fromisoformat(inv.end_date) if inv.end_date else (ref_date if inv.is_current else start_dt)
                        is_current = inv.is_current
                        precision = "month"
                        date_conf = "MONTH_ONLY"
                    except ValueError:
                        pass

        # Fallback to unassigned date intervals in cv_text starting from company match position
        if not start_dt and cv_text and company and not cls._is_job_title_string(company):
            comp_first = company.split()[0]
            if len(comp_first) >= 3:
                pos = cv_text.lower().find(comp_first.lower())
                search_text = cv_text[pos:] if pos != -1 else cv_text
                pattern = r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\s*[\-–—]\s*(?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}|Present|Current)\b"
                matches = list(re.finditer(pattern, search_text, flags=re.IGNORECASE))
                for m in matches:
                    inv = DateIntervalParser.parse_interval(m.group(0))
                    if inv.start_date:
                        try:
                            s_candidate = datetime.date.fromisoformat(inv.start_date)
                            start_dt = s_candidate
                            end_dt = datetime.date.fromisoformat(inv.end_date) if inv.end_date else (ref_date if inv.is_current else start_dt)
                            is_current = inv.is_current
                            precision = "month"
                            date_conf = "MONTH_ONLY"
                            break
                        except ValueError:
                            pass

        if not start_dt:
            date_conf = "UNKNOWN"

        # SAFE PRESENT RULE: Only set Present if explicitly specified in text or interval
        if start_dt and not end_dt:
            text_check = f"{raw_dates} {' '.join(str(r) for r in resps[:2])}".lower()
            if is_current or any(kw in text_check for kw in ("present", "current", "till date", "ongoing")):
                is_current = True
                end_dt = ref_date
            else:
                is_current = False
                end_dt = start_dt

        return start_dt, end_dt, is_current, precision, date_conf

    @classmethod
    def _build_canonical_jobs(
        cls,
        resolved_entries: list[dict[str, Any]],
        ref_date: datetime.date,
        undated_entries: list[dict[str, Any]] = None,
        undated_nodes: list[ExperienceTimelineNode] = None,
    ) -> list[CanonicalJob]:
        if not resolved_entries:
            return []

        resolved_entries.sort(key=lambda x: x["start_dt"])

        canonical_dict: dict[str, CanonicalJob] = {}
        assignment_counter = 1
        job_counter = 1

        for item in resolved_entries:
            parent_key = item["parent_key"]
            s_dt, e_dt = item["start_dt"], item["end_dt"]
            is_curr = item["is_current"]
            title = item["title"]
            resps = item["resps"]
            resolution = item["resolution"]

            matched_parent_key: Optional[str] = None
            for p_key, p_job in canonical_dict.items():
                if cls._are_same_employer(p_key, parent_key):
                    matched_parent_key = p_key
                    break
                if resolution in ("DEPUTATION", "INTERNAL_ROLE", "PROMOTION_TRANSFER"):
                    combined = f"{parent_key} {' '.join(str(r) for r in resps)}".lower()
                    if p_key.lower() in combined:
                        matched_parent_key = p_key
                        break
                if parent_key.lower() in ("organization", "position", "company", "n/a", ""):
                    c_s = datetime.date.fromisoformat(p_job.start_date)
                    c_e = ref_date if p_job.is_current else (datetime.date.fromisoformat(p_job.end_date) if p_job.end_date and p_job.end_date != "Present" else c_s)
                    if not (c_e < s_dt or c_s > e_dt):
                        matched_parent_key = p_key
                        break

            if matched_parent_key:
                c_job = canonical_dict[matched_parent_key]
                c_s = datetime.date.fromisoformat(c_job.start_date)
                c_e = ref_date if c_job.is_current else (datetime.date.fromisoformat(c_job.end_date) if c_job.end_date and c_job.end_date != "Present" else c_s)

                new_s = min(c_s, s_dt)
                new_e = max(c_e, e_dt)
                new_curr = c_job.is_current or is_curr

                c_job.start_date = new_s.isoformat()
                c_job.end_date = new_e.isoformat() if not new_curr else "Present"
                c_job.is_current = new_curr

                delta = relativedelta(new_e + datetime.timedelta(days=1), new_s)
                c_job.duration_months = max(1, (delta.years * 12) + delta.months)

                asg_type = "DEPUTATION" if resolution == "DEPUTATION" else "PROMOTION" if resolution == "PROMOTION_TRANSFER" else "SUB_ROLE"
                asg = ChildAssignment(
                    assignment_id=f"asg_{assignment_counter}",
                    title_or_subrole=title,
                    assignment_type=asg_type,
                    entity_resolution=resolution,
                    start_date=s_dt.isoformat(),
                    end_date=e_dt.isoformat() if not is_curr else "Present",
                    is_current=is_curr,
                    details=resps[:2] if isinstance(resps, list) else [],
                )
                assignment_counter += 1
                c_job.child_assignments.append(asg)
            else:
                asg_list: list[ChildAssignment] = []
                if resolution in ("DEPUTATION", "PROMOTION_TRANSFER", "INTERNAL_ROLE"):
                    asg_type = "DEPUTATION" if resolution == "DEPUTATION" else "PROMOTION" if resolution == "PROMOTION_TRANSFER" else "SUB_ROLE"
                    asg = ChildAssignment(
                        assignment_id=f"asg_{assignment_counter}",
                        title_or_subrole=title,
                        assignment_type=asg_type,
                        entity_resolution=resolution,
                        start_date=s_dt.isoformat(),
                        end_date=e_dt.isoformat() if not is_curr else "Present",
                        is_current=is_curr,
                        details=resps[:2] if isinstance(resps, list) else [],
                    )
                    assignment_counter += 1
                    asg_list.append(asg)

                delta = relativedelta(e_dt + datetime.timedelta(days=1), s_dt)
                dur = max(1, (delta.years * 12) + delta.months)

                c_job = CanonicalJob(
                    job_id=f"canon_job_{job_counter}",
                    parent_company=parent_key,
                    primary_title=title,
                    employment_type=item["emp_type"],
                    entity_resolution="PARENT_EMPLOYMENT",
                    start_date=s_dt.isoformat(),
                    end_date=e_dt.isoformat() if not is_curr else "Present",
                    is_current=is_curr,
                    duration_months=dur,
                    date_confidence=item["date_confidence"],
                    responsibilities=resps[:3] if isinstance(resps, list) else [],
                    child_assignments=asg_list,
                )
                job_counter += 1
                canonical_dict[parent_key] = c_job

        if undated_entries:
            for u in undated_entries:
                u_parent = u["parent_key"]
                u_title = u["title"]
                u_resps = u["resps"]
                u_resolution = u["resolution"]
                u_node = u["node"]
                
                matched_p_key = None
                for p_key, c_job in canonical_dict.items():
                    if cls._are_same_employer(p_key, u_parent):
                        matched_p_key = p_key
                        break
                    if u_resolution in ("DEPUTATION", "INTERNAL_ROLE", "PROMOTION_TRANSFER"):
                        combined = f"{u_parent} {' '.join(str(r) for r in u_resps)}".lower()
                        if p_key.lower() in combined:
                            matched_p_key = p_key
                            break
                            
                if matched_p_key:
                    c_job = canonical_dict[matched_p_key]
                    asg_type = "DEPUTATION" if u_resolution == "DEPUTATION" else "PROMOTION" if u_resolution == "PROMOTION_TRANSFER" else "SUB_ROLE"
                    asg = ChildAssignment(
                        assignment_id=f"asg_{assignment_counter}",
                        title_or_subrole=u_title,
                        assignment_type=asg_type,
                        entity_resolution=u_resolution,
                        start_date=c_job.start_date,
                        end_date=c_job.end_date,
                        is_current=c_job.is_current,
                        details=u_resps[:2] if isinstance(u_resps, list) else [],
                    )
                    assignment_counter += 1
                    c_job.child_assignments.append(asg)
                    if undated_nodes and u_node in undated_nodes:
                        undated_nodes.remove(u_node)
                        
        jobs = list(canonical_dict.values())
        jobs.sort(key=lambda x: x.start_date or "")
        return jobs

    @classmethod
    def _calculate_genuine_concurrency(
        cls,
        canonical_jobs: list[CanonicalJob],
        ref_date: datetime.date,
    ) -> int:
        if len(canonical_jobs) <= 1:
            return 0

        concurrency_pairs = 0
        for i in range(len(canonical_jobs)):
            for j in range(i + 1, len(canonical_jobs)):
                job_a = canonical_jobs[i]
                job_b = canonical_jobs[j]

                if cls._are_same_employer(job_a.parent_company, job_b.parent_company):
                    continue

                s_a = datetime.date.fromisoformat(job_a.start_date)
                e_a = ref_date if job_a.is_current else (datetime.date.fromisoformat(job_a.end_date) if job_a.end_date and job_a.end_date != "Present" else s_a)

                s_b = datetime.date.fromisoformat(job_b.start_date)
                e_b = ref_date if job_b.is_current else (datetime.date.fromisoformat(job_b.end_date) if job_b.end_date and job_b.end_date != "Present" else s_b)

                if not (e_a < s_b or s_a > e_b):
                    concurrency_pairs += 1

        return concurrency_pairs

    @classmethod
    def _consolidate_canonical_blocks(
        cls,
        canonical_jobs: list[CanonicalJob],
        ref_date: datetime.date,
    ) -> list[dict[str, Any]]:
        if not canonical_jobs:
            return []

        blocks: list[dict[str, Any]] = []

        def is_continuous(end_dt: datetime.date, start_dt: datetime.date) -> bool:
            if start_dt <= end_dt:
                return True
            days_hiatus = (start_dt - end_dt).days - 1
            if days_hiatus <= 7:
                return True
            if start_dt.year == end_dt.year and start_dt.month == end_dt.month + 1:
                return True
            if start_dt.year == end_dt.year + 1 and end_dt.month == 12 and start_dt.month == 1:
                return True
            return False

        for cj in canonical_jobs:
            s_d = datetime.date.fromisoformat(cj.start_date)
            e_d = ref_date if cj.is_current else (datetime.date.fromisoformat(cj.end_date) if cj.end_date and cj.end_date != "Present" else s_d)

            if not blocks:
                blocks.append(
                    {
                        "start_dt": s_d,
                        "end_dt": e_d,
                        "job": cj,
                    }
                )
            else:
                last = blocks[-1]
                if is_continuous(last["end_dt"], s_d):
                    last["end_dt"] = max(last["end_dt"], e_d)
                else:
                    blocks.append(
                        {
                            "start_dt": s_d,
                            "end_dt": e_d,
                            "job": cj,
                        }
                    )

        blocks.sort(key=lambda x: x["start_dt"])
        return blocks

    @classmethod
    def _evaluate_gap_coverage(
        cls,
        gap_start: datetime.date,
        gap_end: datetime.date,
        edu_intervals: list[tuple[datetime.date, datetime.date, str]],
        resolved_entries: list[dict[str, Any]],
    ) -> tuple[str, Optional[str], str]:
        for e_s, e_e, degree in edu_intervals:
            if (e_s <= gap_start <= e_e) or (e_s <= gap_end <= e_e) or (gap_start <= e_s and e_e <= gap_end):
                return (
                    "EDUCATION_COVERED",
                    f"Hiatus covered by education ({degree}).",
                    "HIGH",
                )

        for item in resolved_entries:
            if item["emp_type"] in ("freelance", "contract", "consulting", "self_employed"):
                s_d, e_d = item["start_dt"], item["end_dt"]
                if (s_d <= gap_start <= e_d) or (s_d <= gap_end <= e_d):
                    cov_type = (
                        "FREELANCE_COVERED"
                        if item["emp_type"] == "freelance"
                        else "CONTRACT_COVERED"
                    )
                    return (
                        cov_type,
                        f"Hiatus covered by {item['emp_type'].replace('_', ' ').title()} role ({item['title']}).",
                        "HIGH",
                    )

        return "UNEXPLAINED", None, "HIGH"

    @classmethod
    def _build_timeline_events(
        cls,
        canonical_jobs: list[CanonicalJob],
        detected_gaps: list[ExperienceGap],
        ref_date: datetime.date,
    ) -> list[TimelineEvent]:
        events: list[TimelineEvent] = []
        event_counter = 1

        for cj in canonical_jobs:
            s_d = datetime.date.fromisoformat(cj.start_date)
            matching_gap = next(
                (g for g in detected_gaps if g.end_date and (datetime.date.fromisoformat(g.end_date) + datetime.timedelta(days=1)) == s_d),
                None,
            )
            if matching_gap:
                gap_event_type = (
                    "EMPLOYMENT_GAP"
                    if matching_gap.coverage_status == "UNEXPLAINED"
                    else "TIMELINE_UNCERTAINTY"
                    if matching_gap.coverage_status == "TIMELINE_UNCERTAINTY"
                    else "COVERED_GAP"
                )
                events.append(
                    TimelineEvent(
                        event_id=f"event_gap_{matching_gap.gap_id}",
                        event_type=gap_event_type,
                        start_date=matching_gap.start_date,
                        end_date=matching_gap.end_date,
                        is_current=False,
                        duration_months=matching_gap.duration_months,
                        gap=matching_gap,
                    )
                )

            node = ExperienceTimelineNode(
                record_id=cj.job_id,
                company=cj.parent_company,
                job_title=cj.primary_title,
                employment_type=cj.employment_type,
                start_date=cj.start_date,
                end_date=cj.end_date,
                is_current=cj.is_current,
                duration_months=cj.duration_months,
                precision="month",
                date_confidence=cj.date_confidence,
                responsibilities=cj.responsibilities,
            )

            if len(cj.child_assignments) > 0:
                child_nodes: list[ExperienceTimelineNode] = []
                for asg in cj.child_assignments:
                    child_nodes.append(
                        ExperienceTimelineNode(
                            record_id=asg.assignment_id,
                            company=cj.parent_company,
                            job_title=asg.title_or_subrole,
                            employment_type=cj.employment_type,
                            start_date=asg.start_date,
                            end_date=asg.end_date,
                            is_current=asg.is_current,
                            duration_months=cj.duration_months,
                            precision="month",
                            date_confidence=cj.date_confidence,
                            responsibilities=asg.details,
                        )
                    )
                cluster = ConcurrentRoleCluster(
                    cluster_id=f"cluster_{cj.job_id}",
                    start_date=cj.start_date,
                    end_date=cj.end_date,
                    is_current=cj.is_current,
                    duration_months=cj.duration_months,
                    roles_count=len(child_nodes),
                    child_nodes=child_nodes,
                )
                events.append(
                    TimelineEvent(
                        event_id=f"event_{event_counter}",
                        event_type="CONCURRENT_CLUSTER",
                        start_date=cj.start_date,
                        end_date=cj.end_date,
                        is_current=cj.is_current,
                        duration_months=cj.duration_months,
                        cluster=cluster,
                    )
                )
            else:
                events.append(
                    TimelineEvent(
                        event_id=f"event_{event_counter}",
                        event_type="EMPLOYMENT_PERIOD",
                        start_date=cj.start_date,
                        end_date=cj.end_date,
                        is_current=cj.is_current,
                        duration_months=cj.duration_months,
                        node=node,
                    )
                )
            event_counter += 1

        return events
