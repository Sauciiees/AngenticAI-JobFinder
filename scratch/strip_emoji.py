import os
import re

for filepath in ['agent/nodes.py', 'main.py']:
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # We can just replace specific emojis or just remove them manually.
        content = content.replace("🚀", "")
        content = content.replace("🎯", "")
        content = content.replace("✅", "")
        content = content.replace("⏳", "")
        content = content.replace("📂", "")
        content = content.replace("✨", "")
        content = content.replace("📋", "")
        content = content.replace("⚠️", "")
        content = content.replace("🔍", "")
        content = content.replace("❌", "")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
print("Done")
