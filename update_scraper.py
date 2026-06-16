import re

path = 'c:/laragon/www/imtihan-backend/core/management/commands/scrape_testpoint.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

print(f"File length: {len(content)} chars")
print(f"First 100 chars: {repr(content[:100])}")

# Check what's around line 28-52
print("\n--- Lines 28-52 ---")
lines = content.split('\n')
for i in range(27, min(52, len(lines))):
    print(f"{i+1}: {repr(lines[i])}")
