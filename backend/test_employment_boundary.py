from app.services.resume_field_extractor import ResumeFieldExtractor

def test_boundaries():
    print("Test 1: Company -> Date -> Title -> Responsibilities")
    lines1 = [
        "Dignizant Technologies",
        "Jun 2025 - Feb 2026",
        "Front-end Developer",
        "• Developed dynamic dashboard",
        "Bitfront Infotech",
        "Apr 2024 - May 2025",
        "React.js Developer",
        "• Implemented real-time chat"
    ]
    res1 = ResumeFieldExtractor._extract_employment(lines1)
    for j in res1:
        print(f"  {j.get('job_title')} | {j.get('company')} | {j.get('dates')}")
        print(f"  Resps: {len(j.get('responsibilities', []))}")

    print("\nTest 2: Title -> Company -> Date")
    lines2 = [
        "Software Engineer",
        "Tech Corp",
        "2020 - 2022",
        "• Did things"
    ]
    res2 = ResumeFieldExtractor._extract_employment(lines2)
    for j in res2:
        print(f"  {j.get('job_title')} | {j.get('company')} | {j.get('dates')}")

    print("\nTest 3: Two consecutive jobs (Title -> Company -> Date)")
    lines3 = [
        "Backend Dev",
        "ABC Corp",
        "2022 - 2023",
        "• Stuff",
        "Frontend Dev",
        "XYZ Inc",
        "2023 - 2024",
        "• More stuff"
    ]
    res3 = ResumeFieldExtractor._extract_employment(lines3)
    for j in res3:
        print(f"  {j.get('job_title')} | {j.get('company')} | {j.get('dates')}")
        
    print("\nTest 4: Two roles at same company")
    lines4 = [
        "Acme Corp",
        "Senior Dev",
        "2023 - 2024",
        "Junior Dev",
        "2021 - 2022"
    ]
    res4 = ResumeFieldExtractor._extract_employment(lines4)
    for j in res4:
        print(f"  {j.get('job_title')} | {j.get('company')} | {j.get('dates')}")
        
    print("\nTest 5: Missing title")
    lines5 = [
        "Some Startup",
        "2021 - 2022",
        "• Bullet",
        "Other Startup",
        "2022 - 2023",
        "• Bullet 2"
    ]
    res5 = ResumeFieldExtractor._extract_employment(lines5)
    for j in res5:
        print(f"  {j.get('job_title')} | {j.get('company')} | {j.get('dates')}")

    print("\nTest 6: Missing company")
    lines6 = [
        "Data Scientist",
        "2021 - 2022",
        "• Bullet",
        "Lead Data Scientist",
        "2022 - 2023",
        "• Bullet 2"
    ]
    res6 = ResumeFieldExtractor._extract_employment(lines6)
    for j in res6:
        print(f"  {j.get('job_title')} | {j.get('company')} | {j.get('dates')}")
        
test_boundaries()
