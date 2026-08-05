import sys

with open('backend/app/services/match_service.py', 'r') as f:
    content = f.read()

# Conditionally set classification and top_level_match_status
old_block = """        if not has_genuine_match and suitable_roles:
            ai_career_suggestions = [
                AISuggestion(
                    suggested_role=role,
                    suggested_domain=professional_domain,
                    confidence=0.5,
                    evidence=[
                        ClassificationEvidence(
                            source="candidate_domain_profile",
                            matched_term=professional_domain,
                            matched_against=role,
                            confidence=0.5,
                        )
                    ],
                    missing_requirements=["No active vacancy matches this domain profile"],
                )
                for role in suitable_roles[:3]
            ]

        result = EnrichedCandidateAnalysis("""

new_block = """        if not has_genuine_match and suitable_roles:
            ai_career_suggestions = [
                AISuggestion(
                    suggested_role=role,
                    suggested_domain=professional_domain,
                    confidence=0.5,
                    evidence=[
                        ClassificationEvidence(
                            source="candidate_domain_profile",
                            matched_term=professional_domain,
                            matched_against=role,
                            confidence=0.5,
                        )
                    ],
                    missing_requirements=["No active vacancy matches this domain profile"],
                )
                for role in suitable_roles[:3]
            ]
            
        top_level_match_status = "DB_MATCH" if has_genuine_match or (cand_classification and cand_classification.match_status == "DB_MATCH") else "NO_MATCH"
        
        if cand_classification and cand_classification.match_status == "NO_SUITABLE_MATCH":
            cand_classification = None

        result = EnrichedCandidateAnalysis(
            match_status=top_level_match_status,"""

content = content.replace(old_block, new_block)

with open('backend/app/services/match_service.py', 'w') as f:
    f.write(content)
