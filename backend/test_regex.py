import re
clean_bullet = "Architected admin panels with role-based access control systems using Redux"
desig_match = re.search(r"(?:designation|job\s+title|role|position)\s*[:\-]+\s*(.+)$", clean_bullet, re.IGNORECASE)
if desig_match:
    print(f"Matched! Title becomes: {desig_match.group(1).strip()}")
else:
    print("No match")
