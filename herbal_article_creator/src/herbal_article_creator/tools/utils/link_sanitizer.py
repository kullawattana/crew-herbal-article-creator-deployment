# utils/link_sanitizer.py
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode
import re

DROP_PARAMS = {
    "utm_source","utm_medium","utm_campaign","utm_term","utm_content",
    "ved","sa","usg","oq","source","aqs","ei","sca_esv","sxsrf","client","gws_rd"
}

def _strip_tracking(url: str) -> str:
    p = urlparse(url)
    q = parse_qs(p.query, keep_blank_values=False)
    q2 = {k: v for k, v in q.items() if k not in DROP_PARAMS}
    return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(q2, doseq=True), p.fragment))

def canonicalize_url(url: str, max_hops: int = 5) -> str:
    # แกะ redirect ของ Google: https://www.google.com/url?q=<dest>
    u = url
    for _ in range(max_hops):
        p = urlparse(u)
        if p.netloc.endswith("google.com") and p.path == "/url":
            q = parse_qs(p.query)
            if "q" in q and q["q"]:
                u = q["q"][0]
                continue
        break
    return _strip_tracking(u)

def sanitize_markdown_urls(text: str) -> str:
    # แก้ URL ใน markdown/plaintext ทั้งแบบเปลือยและแบบ [label](url)
    def repl_raw(m): return canonicalize_url(m.group(0))
    text = re.sub(r'https?://[^\s)>\]]+', repl_raw, text)

    def repl_md(m):
        label, url = m.group(1), m.group(2)
        return f'[{label}]({canonicalize_url(url)})'
    text = re.sub(r'\[([^\]]+)\]\((https?://[^\s)]+)\)', repl_md, text)
    return text

def strip_rag_file_links(text: str) -> str:
    # เปลี่ยน [File, p.X](http...) -> [File, p.X]
    return re.sub(
        r'\[([^\]]+\.(?:pdf|json),\s*p\.\d+)\]\((?:https?://[^\s)]+)\)',
        r'[\1]', text, flags=re.I
    )
