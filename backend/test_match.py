from app.services.cv_service import process_cv_task_sync
import asyncio

def main():
    file_path = "uploads/cv_gptsuifgr321345678o9p_c369770edae6dbd27123d2ea68cc20cf6329535022a48c74850c0e20df910fd6.pdf"
    
    # Run the worker task synchronously
    res = process_cv_task_sync(file_path)
    
    # Now that it's processed, let's print the recommendations
    from app.services.recommendation_service import RecommendationService
    rec = asyncio.run(RecommendationService.get_candidate_recommendations(res["cv_key"]))
    
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
