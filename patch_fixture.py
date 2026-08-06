import json

with open("backend/tests/rule_config_test_fixture.json", "r") as f:
    data = json.load(f)

# Patch scoring_parameters
if "scoring_parameters" not in data["scoring"]["match"]:
    data["scoring"]["match"]["scoring_parameters"] = {}

data["scoring"]["match"]["scoring_parameters"].update({
    "match_high_threshold": 80.0,
    "match_medium_threshold": 50.0,
    "mandatory_failure_penalty": 20.0,
    "max_score_on_failure": 80.0,
    "llm_semantic_weight": 0.1,
    "max_llm_boost": 10.0,
    "component_weights": {
        "role": 0.15,
        "skills": 0.25,
        "experience": 0.15,
        "education": 0.10,
        "domain": 0.15,
        "technology": 0.10,
        "certification": 0.05,
        "responsibilities": 0.05
    }
})

data["scoring"]["resume_quality"]["default_density_score"] = 0.05
data["scoring"]["resume_quality"]["contact_weights"] = {"email": 1.0, "phone": 1.0, "linkedin": 0.5, "github": 0.5, "portfolio": 0.5}

with open("backend/tests/rule_config_test_fixture.json", "w") as f:
    json.dump(data, f, indent=2)
print("Patched!")
