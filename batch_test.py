import os
import json
import time
import requests
from datetime import datetime

API_EVALUATE_URL = "http://localhost:8000/api/evaluate"
API_STATUS_URL = "http://localhost:8000/api/status/"

INPUT_DIR = "inputs"
OUTPUT_DIR = "inputs/Test (results)"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def main():
    json_files = ["real_15min_mid_v2.json"]
    
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
                
            response = requests.post(API_EVALUATE_URL, json=payload)
            response.raise_for_status()
            
            job_data = response.json()
            job_id = job_data.get('job_id')
            
            if not job_id:
                print(f"  -> ERROR: No job_id returned. Response: {job_data}")
                continue
                
            print(f"  -> Job ID: {job_id}")
            print(f"  -> Waiting for completion ", end="", flush=True)
            
            status = "processing"
            result_data = None
            
            while status == "processing" or status == "pending":
                time.sleep(2)
                print(".", end="", flush=True)
                
                status_response = requests.get(f"{API_STATUS_URL}{job_id}")
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    status = status_data.get('status', 'unknown')
                    if status == "completed":
                        result_data = status_data
                else:
                    print(f" [API ERROR {status_response.status_code}]")
                    break
                    
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
