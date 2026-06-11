import re
from datetime import datetime, timedelta

def resolve_date_string(date_str: str | None) -> str:
    today_str = "2025-06-01" # Mock today
    if not date_str:
        return today_str
        
    date_str_clean = date_str.lower().strip()
    if date_str_clean in ("none", "null", "undefined", ""):
        return today_str
        
    base_dt = datetime.strptime(today_str, "%Y-%m-%d")
    
    # Check for relative keywords (more specific keywords checked first)
    if "day after" in date_str_clean:
        return (base_dt + timedelta(days=2)).strftime("%Y-%m-%d")
    elif re.search(r"\b(t[om]{2,4}o?r{1,2}[ow]*|tmw)\b", date_str_clean) or "tomorrow" in date_str_clean or "tomoorow" in date_str_clean:
        return (base_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    elif re.search(r"\b(tod[aeiouy]{1,3}|tonig[ht]*|tonite)\b", date_str_clean) or "today" in date_str_clean or "tonight" in date_str_clean:
        return today_str
    elif re.search(r"\b(3|three)\s+day", date_str_clean) or "in 3" in date_str_clean:
        return (base_dt + timedelta(days=3)).strftime("%Y-%m-%d")
    elif re.search(r"\b(4|four)\s+day", date_str_clean) or "in 4" in date_str_clean:
        return (base_dt + timedelta(days=4)).strftime("%Y-%m-%d")
        
    # Match YYYY-MM-DD
    match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", date_str_clean)
    if match:
        return match.group(0)
        
    return date_str

test_cases = [
    (None, "2025-06-01"),
    ("none", "2025-06-01"),
    ("null", "2025-06-01"),
    ("todays", "2025-06-01"),
    ("today", "2025-06-01"),
    ("tonight", "2025-06-01"),
    ("tomoorow", "2025-06-02"),
    ("tomorrow", "2025-06-02"),
    ("day after tomorrow", "2025-06-03"),
]

for inp, expected in test_cases:
    actual = resolve_date_string(inp)
    print(f"Input: {str(inp):25} -> Actual: {actual:10} | Expected: {expected:10} | {'PASS' if actual == expected else 'FAIL'}")
