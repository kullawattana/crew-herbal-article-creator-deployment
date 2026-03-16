# crew.py (วางไว้ด้านบนไฟล์)
import json, re

def parse_json_output(text: str):
    # 1) พยายามดึง JSON บล็อก ===DATA_JSON===
    m = re.search(r"===DATA_JSON===\s*(\[.*?\])\s*===END_DATA_JSON===", text, re.S)
    if m:
        try:
            return json.loads(m.group(1))  # list[dict]
        except Exception:
            pass
    # 2) พาร์ส Markdown table -> list[dict]
    lines = [l for l in text.splitlines() if l.strip()]
    for i in range(len(lines)-1):
        if "|" in lines[i] and set(lines[i+1].replace("|","").strip()).issubset(set("-: ")):
            headers = [h.strip() for h in lines[i].strip("| ").split("|")]
            rows = []
            for row in lines[i+2:]:
                if "|" not in row: break
                cells = [c.strip() for c in row.strip("| ").split("|")]
                rows.append(dict(zip(headers, cells)))
            return rows
    return []
