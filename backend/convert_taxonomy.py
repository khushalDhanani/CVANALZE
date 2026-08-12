import json

def get_match_type(term):
    if " " in term:
        return "CASE_INSENSITIVE_PHRASE"
    else:
        return "CASE_INSENSITIVE_TOKEN"

with open("app/data/department_domains_seed.json", "r") as f:
    data = json.load(f)

for domain in data["domains"]:
    new_keywords = []
    for kw in domain["keywords"]:
        if isinstance(kw, str):
            match_type = get_match_type(kw)
            new_kw = {
                "term": kw,
                "match_type": match_type,
                "weight": 1.0
            }
            new_keywords.append(new_kw)
        elif isinstance(kw, dict):
            if "weight" not in kw:
                kw["weight"] = 1.0
            new_keywords.append(kw)
    domain["keywords"] = new_keywords

with open("app/data/department_domains_seed.json", "w") as f:
    json.dump(data, f, indent=2)

