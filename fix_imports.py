import os

files_to_fix = [
    'src/services/qa_summary.py',
    'src/services/qa_suggestions.py',
    'src/services/dynamic_evaluator.py'
]

for f in files_to_fix:
    with open(f, 'r') as file:
        content = file.read()
    content = content.replace('src.core.llm_client', 'src.services.llm_adapter')
    with open(f, 'w') as file:
        file.write(content)

