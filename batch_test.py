import os
import json
import time
import requests
from datetime import datetime

API_EVALUATE_URL = "http://localhost:8005/api/evaluate"

INPUT_DIR = "inputs"
OUTPUT_DIR = "inputs/Test (results)"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def main():
    json_files = [f for f in sorted(os.listdir(INPUT_DIR)) if f.endswith('.json')]
    
    if not json_files:
        print(f"No JSON files found in '{INPUT_DIR}' directory.")
        return

    print(f"Found {len(json_files)} files. Starting batch run...\n")

    for idx, filename in enumerate(json_files, 1):
        filepath = os.path.join(INPUT_DIR, filename)
        
        print(f"[{idx}/{len(json_files)}] Processing: {filename}")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                payload = json.load(f)
                
            response = requests.post(API_EVALUATE_URL, json=payload, timeout=600)
            response.raise_for_status()
            
            result_data = response.json()
            status = result_data.get('status', 'completed')
            print(f" [{status.upper()}]")
            
            if status == "completed" and result_data:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"result_{timestamp}_{filename}"
                output_path = os.path.join(OUTPUT_DIR, output_filename)
                
                with open(output_path, 'w', encoding='utf-8') as out_f:
                    json.dump(result_data, out_f, indent=2)
                    
                print(f"  -> Saved result to: {output_path}\n")
                
            elif status == "failed":
                print(f"  -> Job failed.\n")
                
        except Exception as e:
            print(f"  -> EXCEPTION: {str(e)}\n")

if __name__ == "__main__":
    main()
