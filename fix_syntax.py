with open('src/services/dynamic_evaluator.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the broken newline
bad_string = "failed_str = \"\n\".join"
good_string = "failed_str = \"\\n\".join"

content = content.replace(bad_string, good_string)

with open('src/services/dynamic_evaluator.py', 'w', encoding='utf-8') as f:
    f.write(content)
