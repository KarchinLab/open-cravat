#!/usr/bin/env python3

import os
import sys
import json
import yaml

REQUIRED_FIELDS = ["name", "version", "description"]

def validate_manifest(path):
    if not os.path.exists(path):
        print(f"Error: File or directory '{path}' does not exist.")
        return False

    files_to_check = []
    if os.path.isfile(path):
        files_to_check.append(path)
    else:
        for root, _, files in os.walk(path):
            for file in files:
                if file.endswith((".yml", ".yaml", ".json")):
                    files_to_check.append(os.path.join(root, file))

    all_valid = True
    for file_path in files_to_check:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                if file_path.endswith(".json"):
                    data = json.load(f)
                else:
                    data = yaml.safe_load(f)

            missing = [field for field in REQUIRED_FIELDS if field not in data]
            if missing:
                print(f"[FAIL] {file_path} is missing fields: {', '.join(missing)}")
                all_valid = False
            else:
                print(f"[PASS] {file_path} contains all required fields.")

        except Exception as e:
            print(f"[ERROR] Failed to parse {file_path}: {e}")
            all_valid = False

    return all_valid

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python validate_manifest.py <file_or_directory_path>")
        sys.exit(1)

    target_path = sys.argv[1]
    success = validate_manifest(target_path)
    sys.exit(0 if success else 2)
