import asyncio
from app.services.recommendation_service import RecommendationService

async def main():
    res = await RecommendationService.get_candidate_recommendations("cv_gptsuifgr321345678o9p")
    print("Recommendations:")
    for m in res["recommendations"]:
        print(f"Role: {m['job_title']} | Score: {m['overall_confidence']}% | Reason: {m['reason']}")
    print("\nCareer Transitions:")
    for ct in res["career_transitions"]:
        print(f"Role: {ct['target_role']} | Bridge: {ct['skill_bridge']}")

if __name__ == "__main__":
    asyncio.run(main())
