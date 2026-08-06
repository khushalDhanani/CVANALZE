from app.services.recommendation_service import RecommendationService

def main():
    cv_key = "cv_gptsuifgr321345678o9p"
    rec = RecommendationService.get_candidate_recommendations(cv_key)
    
    print("\n\nMATCH RESULTS:")
    for m in rec.get("recommendations", [])[:3]:
        print(f"Role: {m.get('job_title')} | Score: {m.get('overall_confidence')}% | Reason: {m.get('reason')}")
    print("\nCAREER TRANSITIONS:")
    for ct in rec.get("career_transitions", []):
        print(f"Role: {ct['target_role']} | Bridge: {ct['skill_bridge']}")
    print("\nSKILLS:")
    print(rec.get("profile_summary", {}).get("related_skills", []))

if __name__ == "__main__":
    main()
