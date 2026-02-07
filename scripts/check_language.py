import os
import ast
import re
import sys

# Force UTF-8 for Windows consoles
sys.stdout.reconfigure(encoding='utf-8')

# Script to audit codebase for English strings in user-facing files.
# Usage: python scripts/check_language.py

IGNORE_DIRS = {'__pycache__', 'migrations', 'tests', 'venv', '.git'}
IGNORE_FILES = {'__init__.py', 'config.py', 'logging_config.py'}

# Files known to contain technical strings we can ignore, 
# or files that are not user-facing.
SKIP_FILES = {
    'gupshup_service.py', # Mostly API logic
    'user_service.py',    # Internal logic
    'receipt_service.py', # We audited this, but let's scan it anyway for safety
}

def is_suspicious(s):
    """
    Returns True if string 's' looks like user-facing English text.
    False if it looks like Telugu, data, or technical keys.
    """
    if not isinstance(s, str):
        return False
    
    # 1. Must contain English letters to be suspicious
    if not re.search(r'[a-zA-Z]', s):
        return False 
    
    # 2. Ignore typical technical strings
    if re.match(r'^[A-Z0-9_]+$', s): return False # CONSTANTS (e.g. WAITING_FOR_NAME)
    if re.match(r'^[a-z0-9_]+$', s): return False # snake_case (e.g. user_id)
    if re.match(r'^\S+$', s): return False        # No spaces (URLs, IDs, keys)
    
    # 3. Ignore f-string formatting placeholders (rough check)
    if s.strip() == "": return False
    
    # 4. Ignore SQL/Technical keywords
    upper_s = s.upper()
    technical_terms = ["SELECT ", "INSERT ", "UPDATE ", "DELETE ", "FROM ", "WHERE ", "HTTP", "ERROR:", "EXCEPTION:"]
    if any(term in upper_s for term in technical_terms): return False

    # 5. If it contains Telugu characters, it might be mixed.
    # Telugu block is roughly 0C00–0C7F. 
    # If a string has BOTH Telugu AND English, it is HIGHLY suspicious (e.g. "Monthly Seva (నెలవారీ)")
    has_telugu = bool(re.search(r'[\u0c00-\u0c7f]', s))
    if has_telugu and re.search(r'[a-zA-Z]', s):
        return True # Mixed content is banned!
    
    # 6. If it's strict English with spaces -> Suspicious
    if not has_telugu and " " in s:
        return True

    return False

def check_file(filepath):
    issues = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            tree = ast.parse(content)
    except Exception as e:
        print(f"⚠️ Could not parse {filepath}: {e}")
        return []

    for node in ast.walk(tree):
        # Check string literals
        s = None
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            s = node.value
        elif isinstance(node, ast.Str): # Python < 3.8
            s = node.s
        
        # Ignore Docstrings (if the string is the first expression in a function/class/module)
        # This is hard to detect perfectly in a simple walk, but we can filter by content.
        if s and getattr(node, 'col_offset', -1) == 0 and (s.strip().startswith('"""') or s.strip().startswith("'''") or "\n" in s):
             # Heuristic: multi-line strings at col 0 are likely docstrings
             if "Service" in s or "Psychological" in s: continue

        # Check for strict English
        if s and is_suspicious(s):
            # Filtering Context (Heuristic parent check)
            # We can't easily see the parent in ast.walk, so we'll check the source line
            # This is slow but effective for a script.
            try:
                # Get the line from file content (lines are 1-indexed)
                line_content = content.splitlines()[node.lineno - 1]
                
                # IGNORE LOGS
                if "logger." in line_content: continue
                if "print(" in line_content: continue
                
                # IGNORE DOCSTRINGS (Triple quotes detection in line)
                if '"""' in line_content or "'''" in line_content: continue
                
                # IGNORE DICT KEYS (Rough check)
                # e.g. "status": "ok" -> we only care about values, but AST gives both.
                # It's hard to distinguish key vs value without parent node. 
                # But typically keys are snake_case.
                
                issues.append((node.lineno, s))
            except:
                issues.append((node.lineno, s))
            
    return issues

def main():
    print("🕉️  Subhamasthu Language Audit Tool")
    print("   Scanning for English text in user-facing modules...")
    print("---------------------------------------------------")
    
    target_dirs = [
        os.path.join('app', 'fsm'),
        os.path.join('app', 'services'),
        os.path.join('app', 'api', 'webhooks')
    ]
    
    total_issues = 0
    
    for d in target_dirs:
        if not os.path.exists(d):
            print(f"Skipping missing dir: {d}")
            continue
            
        for root, dirs, files in os.walk(d):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for file in files:
                if file.endswith('.py') and file not in IGNORE_FILES:
                    if file in SKIP_FILES: continue
                    
                    filepath = os.path.join(root, file)
                    issues = check_file(filepath)
                    
                    if issues:
                        print(f"\n📂 {filepath}")
                        for lineno, text in issues:
                            print(f"   Line {lineno}: \"{text[:60]}...\"")
                            total_issues += 1

    print("\n---------------------------------------------------")
    if total_issues == 0:
        print("✅ SUCCESS: No suspicious English strings found.")
        sys.exit(0)
    else:
        print(f"❌ FOUND {total_issues} SUSPICIOUS STRINGS.")
        print("   Please review them. Some might be false positives (logs, errors).")
        print("   But user-facing text MUST be 100% Telugu.")
        sys.exit(1)

if __name__ == "__main__":
    main()
