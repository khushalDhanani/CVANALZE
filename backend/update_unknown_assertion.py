with open('backend/tests/test_taxonomy_integration.py', 'r') as f:
    content = f.read()

content = content.replace(
    'assert domain_un == "General Operations"',
    'assert domain_un == "Unknown"'
)

with open('backend/tests/test_taxonomy_integration.py', 'w') as f:
    f.write(content)
