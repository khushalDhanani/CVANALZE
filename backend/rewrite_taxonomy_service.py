import sys

with open('backend/app/services/taxonomy_service.py', 'r') as f:
    content = f.read()

content = content.replace(
    '    "General Operations"',
    ''
)
content = content.replace(
    '    ("General Professional", "General Operations")',
    ''
)
# Clean up trailing commas in the lists
content = content.replace(
    '    "Finance & Administration",\n\n',
    '    "Finance & Administration"\n'
)
content = content.replace(
    '    ("Finance & Administration", "Finance & Administration"),\n\n',
    '    ("Finance & Administration", "Finance & Administration")\n'
)


with open('backend/app/services/taxonomy_service.py', 'w') as f:
    f.write(content)

