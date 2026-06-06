import json
import os

log_file_path = "/home/Ryder/.gemini/antigravity/brain/5e811bfc-549c-4f33-8288-1adedca2c67b/.system_generated/logs/overview.txt"
output_file_path = "/run/media/Ryder/Coding/AndroidIQOO/scratch/user_request_1165.txt"

def main():
    if not os.path.exists(log_file_path):
        print(f"Log file not found at {log_file_path}")
        return
        
    with open(log_file_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line.strip())
                if data.get("step_index") == 1165:
                    content = data.get("content", "")
                    with open(output_file_path, "w", encoding="utf-8") as out:
                        out.write(content)
                    print(f"Successfully extracted step 1165 to {output_file_path}")
                    return
            except Exception as e:
                continue
    print("Could not find step 1165 in logs.")

if __name__ == "__main__":
    main()
