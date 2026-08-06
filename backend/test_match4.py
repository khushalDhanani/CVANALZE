from app.services.recommendation_service import RecommendationService
import json

def main():
    cv_key = "cv_gptsuifgr321345678o9p_c369770edae6dbd27123d2ea68cc20cf6329535022a48c74850c0e20df910fd6"
    rec = RecommendationService.get_candidate_recommendations(cv_key)
    print(json.dumps(rec, indent=2))

if __name__ == "__main__":
    main()
