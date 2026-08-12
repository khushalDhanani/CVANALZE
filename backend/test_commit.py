current = {"company": "Bitfront Infotech", "dates": "Apr 2024"}
is_title = True
is_greedy_company = True

needs_commit = True
if is_title and not current.get("job_title"):
    needs_commit = False
elif is_greedy_company and not current.get("company"):
    needs_commit = False

print(needs_commit)
