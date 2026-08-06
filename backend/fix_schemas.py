import re

for filepath in ["app/models/org.py", "app/models/recruit.py"]:
    with open(filepath, "r") as f:
        content = f.read()

    new_content = content.replace('__table_args__ = {"schema": "AIRIS"}    ', '__table_args__ = {"schema": "AIRIS"}\n\n    ')
    
    with open(filepath, "w") as f:
        f.write(new_content)
