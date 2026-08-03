import json
from pathlib import Path

from app.services.experience_calculator import ExperienceCalculator

path = Path("uploads/results/cv_Utkarsh_Patil_07012026.json")
if path.exists():
    data = json.loads(path.read_text())
    resume_json = data.get("resume_json", {})
    cv_text = data.get("text", "")

    print("Work Experience:")
    print(json.dumps(resume_json.get("work_experience"), indent=2))

    exp = ExperienceCalculator.calculate_total_experience(resume_json, cv_text)
    print(f"\nCalculated Experience: {exp}")
else:
    print("File not found")
