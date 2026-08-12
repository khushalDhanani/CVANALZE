import json

with open('app/data/department_domains_seed.json', 'r') as f:
    data = json.load(f)

short_keywords = set()
for item in data.get("domains", []):
    for kw in item.get('keywords', []):
        if len(kw) <= 3 and kw.isalpha():
            short_keywords.add(kw)

print(f"Found {len(short_keywords)} short alphabetic keywords.")
for kw in sorted(short_keywords):
    print(kw)
