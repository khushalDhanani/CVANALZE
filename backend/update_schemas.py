import re

for filepath in ["app/models/org.py", "app/models/recruit.py"]:
    with open(filepath, "r") as f:
        content = f.read()

    # Find all __tablename__ = "..." and add __table_args__ = {"schema": "AIRIS"} on the next line
    # if it doesn't already have __table_args__
    
    def replacement(m):
        tablename_line = m.group(0)
        return tablename_line + '\n    __table_args__ = {"schema": "AIRIS"}'

    # Use negative lookahead to avoid double-adding if run twice
    new_content = re.sub(r'^[ \t]*__tablename__[ \t]*=[ \t]*"[^"]+"\n(?![ \t]*__table_args__)', replacement, content, flags=re.MULTILINE)

    with open(filepath, "w") as f:
        f.write(new_content)
