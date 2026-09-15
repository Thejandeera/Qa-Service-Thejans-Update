import os
import ast
import json

c_reply = '''
[
  {
    "name": "Paraphrasing",
    "reason": "Agent did not paraphrase the problem.",
    "coaching": "Always paraphrase."
  }
]
'''
s_idx = c_reply.find('[')
e_idx = c_reply.rfind(']')
coaching_json = []
if s_idx != -1 and e_idx != -1:
    try:
        coaching_json = json.loads(c_reply[s_idx:e_idx+1])
    except json.JSONDecodeError:
        try:
            py_str = c_reply[s_idx:e_idx+1].replace('true', 'True').replace('false', 'False').replace('null', 'None')
            coaching_json = ast.literal_eval(py_str)
        except:
            pass

print(coaching_json)
