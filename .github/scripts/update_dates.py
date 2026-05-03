import os
import re
from datetime import datetime, timezone

def update_file_dates(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return False

    if not content.startswith('---'):
        return False

    parts = content.split('---', 2)
    if len(parts) < 3:
        return False

    frontmatter = parts[1]
    body = parts[2]

    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    modified = False
    
    if re.search(r'^updated:', frontmatter, re.MULTILINE):
        frontmatter = re.sub(r'(^updated:\s*).*', f'\\g<1>{now}', frontmatter, flags=re.MULTILINE)
        modified = True
    else:
        frontmatter = frontmatter.strip() + f"\nupdated: {now}\n"
        modified = True

    date_match = re.search(r'^date:\s*(.*)', frontmatter, re.MULTILINE)
    if date_match:
        current_val = date_match.group(1).strip().lower()
        if not current_val or current_val == "none":
            frontmatter = re.sub(r'(^date:\s*).*', f'\\g<1>{now}', frontmatter, flags=re.MULTILINE)
            modified = True
    else:
        frontmatter = frontmatter.strip() + f"\ndate: {now}\n"
        modified = True

    if modified:
        try:
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                f.write(f"---{frontmatter}---{body}")
            return True
        except Exception as e:
            print(f"Error writing to {file_path}: {e}")
    
    return False

def main():
    docs_dir = 'docs'
    if not os.path.exists(docs_dir):
        print(f"Directory '{docs_dir}' not found.")
        return

    count = 0
    for root, dirs, files in os.walk(docs_dir):
        if 'projects' in dirs:
            dirs.remove('projects')
            
        for file in files:
            if file.endswith('.md'):
                path = os.path.join(root, file)
                if update_file_dates(path):
                    print(f"  [Updated] {path}")
                    count += 1
    
    if count > 0:
        print(f"Successfully updated {count} files.")
    else:
        print("No files required updates.")

if __name__ == "__main__":
    main()
