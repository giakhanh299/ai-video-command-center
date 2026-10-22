import os
import re

for root, dirs, files in os.walk('.'):
    if any(x in root for x in ['.git', 'node_modules', 'cache', '__pycache__', 'outputs\\cad_', '.pytest_cache']):
        continue
    for f in files:
        if f.endswith(('.json', '.txt', '.py', '.md', '.bat', '.csv')):
            p = os.path.join(root, f)
            try:
                content = open(p, encoding='utf-8', errors='ignore').read()
                matches = re.findall(r'(?:https?://)?(?:www\.)?(?:v\.)?douyin\.com/[^\s"\'<>]+', content, re.IGNORECASE)
                if matches:
                    print(f"{p}: {matches[:3]}")
                elif 'douyin' in content.lower():
                    # check what context douyin appears in
                    lines = [line.strip() for line in content.splitlines() if 'douyin' in line.lower()]
                    print(f"{p} (mentions): {lines[:2]}")
            except Exception as e:
                pass
