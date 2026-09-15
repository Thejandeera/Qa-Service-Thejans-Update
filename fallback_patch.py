with open('src/services/dynamic_evaluator.py', 'r', encoding='utf-8') as f:
    content = f.read()

bad = '''        except Exception as e:
            print("Coaching generation failed:", e)'''

good = '''        except Exception as e:
            print("Coaching generation failed:", e)
            for r in ratings:
                if r["rating"] in ["FAIL", "NO"] and r["reason"] == "Standard compliant response":
                    r["reason"] = "Evaluated as FAIL"
                    r["coaching"] = "Review transcript."'''

content = content.replace(bad, good)

with open('src/services/dynamic_evaluator.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Fallback patched")
