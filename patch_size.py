with open('src/services/dynamic_evaluator.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('batch_size = 3', 'batch_size = 1')

with open('src/services/dynamic_evaluator.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Batch size updated to 1")
