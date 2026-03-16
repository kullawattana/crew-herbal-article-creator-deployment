import requests
import xml.etree.ElementTree as ET
import time
import re
import html
import json
import os

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Type

from .utils.link_sanitizer import sanitize_markdown_urls

DOI_PREFIX      = "https://doi.org/"
PMID_URL        = "https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
PMCID_URL       = "https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/"
E_SEARCH_URL    = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
E_FETCH_URL     = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
E_SUMMARY_URL   = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

class PubMedSearchInput(BaseModel):
    query: str = Field(...)
    retmax: int = Field(3, description="Maximum number of results to return")

class PubMedFetchInput(BaseModel):
    pmid: str = Field(...)
    retmode: str = Field("xml", description="Return mode (xml or text)")

class PubMedParseInput(BaseModel):
    xml: str = Field(...)
    style: str = Field("vancouver", description="Citation style (vancouver or apa)")

class PubMedSummaryInput(BaseModel):
    pmid: str = Field(..., description="PubMed ID for summary")

#-----------------Start Helper--------------------    
def log_err(data: Dict[str, Any]):
    try:
        with open("pubmed_errors.ndjson", "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\\n")
    except Exception:
        pass

def xml_sanitize(s: str) -> str:
    """Sanitize XML string"""
    s = re.sub(r"<!DOCTYPE[^>]*>", "", s, flags=re.IGNORECASE)
    s = re.sub(r"<!ENTITY[^>]*>", "", s, flags=re.IGNORECASE)
    s = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", s)
    s = html.unescape(s)
    return s

def looks_like_html(s: str) -> bool:
    """Check if string looks like HTML"""
    head = s.strip()[:200].lower()
    return head.startswith("<!doctype html") or head.startswith("<html")

def looks_like_pubmed_xml(s: str) -> bool:
    """Check if string looks like PubMed XML"""
    return ("<PubmedArticle" in s) or ("<PubmedBookArticle" in s)

def retry(n=4, base_delay=0.8):
    """Retry decorator"""
    def wrapper(fn):
        def inner(*args, **kwargs):
            last_err = None
            for i in range(n):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    time.sleep(base_delay * (2**i))
            raise last_err
        return inner
    return wrapper

def safe_text(el: Optional[ET.Element]) -> str:
    """Safely extract text from XML element"""
    return (el.text or "").strip() if el is not None else ""
#-----------------End Helper-------------------- 

def extract_year(root: ET.Element) -> str:
    """Extract publication year from XML"""
    year = safe_text(root.find(".//Journal/JournalIssue/PubDate/Year"))
    if year:
        return year
    medline = safe_text(root.find(".//Journal/JournalIssue/PubDate/MedlineDate"))
    m = re.search(r"\\d{4}", medline)
    return m.group(0) if m else ""

def extract_authors(root: ET.Element) -> List[Dict[str, str]]:
    """Extract authors from XML"""
    authors = []
    for a in root.findall(".//AuthorList/Author"):
        last = safe_text(a.find("LastName"))
        initials = safe_text(a.find("Initials"))
        fore = safe_text(a.find("ForeName"))
        collective = safe_text(a.find("CollectiveName"))
        if collective:
            authors.append({"last": collective, "initials": "", "fore": collective})
        elif last or fore or initials:
            authors.append({"last": last, "initials": initials, "fore": fore})
    return authors

def authors_vancouver(authors: List[Dict[str, str]]) -> str:
    """Format authors in Vancouver style"""
    names = []
    for a in authors:
        if a["initials"]:
            names.append(f"{a['last']} {a['initials']}")
        else:
            names.append(a["last"])
    return ", ".join([n for n in names if n]).strip()

def authors_apa(authors: List[Dict[str, str]]) -> str:
    """Format authors in APA style"""
    parts = []
    for a in authors:
        last = a["last"]
        fore = a["fore"]
        if last and fore:
            parts.append(f"{last}, {fore[0]}.")
        elif last:
            parts.append(last)
    return ", ".join(parts)

def _collect_abstract_texts(root: ET.Element) -> str:
    """
    Collect full abstract text from PubMed XML.
    - รองรับหลาย <AbstractText> (Section) และดึงข้อความจาก child nodes ด้วย .itertext()
    - ถ้ามี Label/NlmCategory จะพรีฟิกซ์ "Label: "
    - ถ้าไม่มี <Abstract> ลองดู <OtherAbstract>
    """
    def section_text(el: ET.Element) -> str:
        # รวมทุก text/child text ให้ครบ ไม่ตกหล่น <i>, <sup>, ฯลฯ
        return "".join(el.itertext()).strip()

    sections = []
    # main abstract
    for ab in root.findall(".//Abstract/AbstractText"):
        txt = section_text(ab)
        if not txt:
            continue
        label = ab.get("Label") or ab.get("NlmCategory") or ""
        sections.append(f"{label}: {txt}" if label else txt)

    # fallback: OtherAbstract
    if not sections:
        for ab in root.findall(".//OtherAbstract/AbstractText"):
            txt = section_text(ab)
            if not txt:
                continue
            label = ab.get("Label") or ab.get("NlmCategory") or ""
            sections.append(f"{label}: {txt}" if label else txt)

    return "\n".join(sections).strip()

def format_vancouver(meta: Dict[str, Any]) -> str:
    """Format citation in Vancouver style"""
    pieces = []
    if meta["authors_str"]:
        pieces.append(meta["authors_str"])
    if meta["title"]:
        pieces.append(f"{meta['title']}.")
    j = meta["journal"]; y = meta["year"]; vol = meta["volume"]; issue = meta["issue"]; pages = meta["pages"]
    tail = ""
    if j: tail += j
    if y: tail += f". {y}"
    if vol:
        tail += f";{vol}"
        if issue:
            tail += f"({issue})"
    if pages:
        tail += f":{pages}"
    if tail:
        tail += "."
        pieces.append(tail)
    if meta["doi"]:
        pieces.append(f"doi:{meta['doi']}.")
    return " ".join(pieces).strip()

def format_apa(meta: Dict[str, Any]) -> str:
    """Format citation in APA style"""
    parts = []
    
    if meta["authors_apa"]:
        parts.append(f"{meta['authors_apa']} ")
    
    year = meta["year"] or "n.d."
    parts.append(f"({year}). ")
    
    if meta["title"]:
        parts.append(f"{meta['title']}. ")
    
    journal_line = ""
    if meta["journal"]:
        journal_line += meta["journal"]
    
    if meta["volume"]:
        journal_line += f", {meta['volume']}"
        if meta["issue"]:
            journal_line += f"({meta['issue']})"
    
    if meta["pages"]:
        journal_line += f", {meta['pages']}"
    
    if journal_line:
        journal_line += ". "
        parts.append(journal_line)
    
    doi_url = meta.get("doi_url")
    if doi_url:
        parts.append(doi_url)
    elif meta["doi"]:
        parts.append(f"{DOI_PREFIX}{meta['doi']}")
    
    out = "".join(parts).strip()  
    return sanitize_markdown_urls(out)
    
def build_canonical_links(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Add canonical links to the meta based on the information provided."""
    pmid = (meta.get("pmid") or "").strip()
    doi  = (meta.get("doi")  or "").strip()
    pmcid = (meta.get("pmcid") or meta.get("PMCID") or "").strip()

    if doi:
        # meta['doi'] may be an empty name, such as '10.1038/xxx'.'
        meta["doi_url"] = doi if doi.startswith("http") else (DOI_PREFIX + doi)
    if pmid:
        meta["pubmed_url"] = PMID_URL.format(pmid=pmid)
    if pmcid:
        # It should be in the format 'PMC1234567' or just numbers.
        meta["pmc_url"] = PMCID_URL.format(pmcid=pmcid if pmcid.startswith("PMC") else f"PMC{pmcid}")
    return meta

class PubMedSearchTool(BaseTool):
    name: str = "pubmed_search"
    description: str = (
        "Search PubMed and return a list of PMIDs for a query. "
        "Use this to find relevant research papers. "
        "Input should be a search query string."
    )
    args_schema: Type[BaseModel] = PubMedSearchInput

    def _run(self, query: str, retmax: int = 3) -> List[str]:
        """Search PubMed"""
        
        # Guard: Must be a single JSON, not a list/array JSON string.
        # ====================Start Guard====================
        if isinstance(query, list):
            raise ValueError("Invalid Action: expected single JSON object, not a list.")
        try:
            parsed = json.loads(query)
            if isinstance(parsed, list):
                raise ValueError("Invalid Action: JSON string contains an array.")
        except json.JSONDecodeError:
            pass
        # ======================End Guard====================
        # Prepare parameters
        params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": retmax,
            "tool": "crew-pubmed-agent",
            "email": os.getenv("PUBMED_CONTACT_EMAIL", "you@example.com"),
        }
        ncbi_key = os.getenv("NCBI_API_KEY")
        if ncbi_key:
            params["api_key"] = ncbi_key
        
        headers = {
            "User-Agent": "CrewAI-PubMed-Tool/1.0",
            "Accept": "application/json",
        }
        
        r = requests.get(E_SEARCH_URL, params=params, timeout=30, headers=headers)
        if r.status_code in (429, 502, 503, 504):
            raise RuntimeError(f"Transient HTTP {r.status_code} on esearch")
        r.raise_for_status()
        
        return r.json()["esearchresult"]["idlist"]

class PubMedFetchTool(BaseTool):
    name: str = "pubmed_fetch"
    description: str = (
        "Fetch PubMed content by PMID (XML by default). "
        "Use this after searching to get full paper details. "
        "Input should be a PMID string."
    )
    args_schema: Type[BaseModel] = PubMedFetchInput

    @staticmethod
    @retry(n=4, base_delay=0.8)
    def _do_fetch(pmid: str, retmode: str = "xml") -> requests.Response:
        params = {
            "db": "pubmed",
            "id": pmid,
            "retmode": retmode,
            #"rettype": "abstract" if retmode == "text" else None,
            "rettype": "medline" if retmode == "text" else None,
            "tool": "crew-pubmed-agent",
            "email": os.getenv("PUBMED_CONTACT_EMAIL", "you@example.com"),
        }
        ncbi_key = os.getenv("NCBI_API_KEY")
        
        if ncbi_key:
            params["api_key"] = ncbi_key
        params = {k: v for k, v in params.items() if v is not None}
        
        headers = {
            "User-Agent": "CrewAI-PubMed-Tool/1.0",
            "Accept": "application/xml" if retmode == "xml" else "text/plain",
        }
        
        r = requests.get(E_FETCH_URL, params=params, timeout=30, headers=headers)
        time.sleep(float(os.getenv("PUBMED_POLITE_DELAY", "0.2")))
        
        if r.status_code in (429, 502, 503, 504):
            raise RuntimeError(f"Transient HTTP {r.status_code} on efetch")
        r.raise_for_status()
        
        return r

    def _run(self, pmid: str, retmode: str = "xml") -> str:
        r = self._do_fetch(pmid=pmid, retmode=retmode)
        text = r.text
        
        if "<eFetchResult" in text and "<ERROR>" in text:
            log_err({"pmid": pmid, "stage": "efetch", "error": "EFETCH_ERROR", "preview": text[:400]})
            return text
        
        if retmode == "xml" and (looks_like_html(text) or not looks_like_pubmed_xml(text)):
            try:
                r2 = self._do_fetch(pmid=pmid, retmode="text")
                return r2.text
            except Exception:
                return text
        return text

class PubMedParseTool(BaseTool):
    name: str = "pubmed_parse"
    description: str = (
        "Parse PubMed efetch XML to structured metadata. "
        "Use this to extract citation information from fetched XML. "
        "Input should be XML content from pubmed_fetch."
    )
    args_schema: Type[BaseModel] = PubMedParseInput
    
    def _run(self, xml: str, style: str = "vancouver") -> Dict[str, Any]:
        if looks_like_html(xml):
            log_err({"stage": "parse", "error": "HTML_RESPONSE", "preview": xml[:400]})
            return {"error": "HTML_RESPONSE", "message": "E-utilities returned HTML", "preview": xml[:400]}
        if "<eFetchResult" in xml and "<ERROR>" in xml:
            log_err({"stage": "parse", "error": "EFETCH_ERROR", "preview": xml[:400]})
            return {"error": "EFETCH_ERROR", "message": "E-utilities returned <ERROR>", "preview": xml[:400]}
        if "<" not in xml and len(xml.strip()) > 0:
            return {
                "pmid": "", "title": "", "journal": "", "year": "", "volume": "", "issue": "", "pages": "",
                "doi": "", "authors": [], "authors_str": "", "authors_apa": "",
                "abstract": xml.strip(), "reference": "", "parse_status": "fallback-text"
            }
        
        try_text = xml
        try:
            root = ET.fromstring(try_text)
        except Exception as e1:
            sani = xml_sanitize(try_text)
            try:
                root = ET.fromstring(sani)
            except Exception as e2:
                log_err({"stage": "parse", "error": "PARSE_ERROR", "message": str(e2), "preview": sani[:500]})
                return {"error": "PARSE_ERROR", "message": f"XML parsing failed: {e2}", "preview": sani[:500]}
        
        pmid = safe_text(root.find(".//MedlineCitation/PMID"))
        title = safe_text(root.find(".//Article/ArticleTitle"))
        journal = safe_text(root.find(".//Journal/Title"))
        volume = safe_text(root.find(".//JournalIssue/Volume"))
        issue = safe_text(root.find(".//JournalIssue/Issue"))
        year = extract_year(root)
        pages = safe_text(root.find(".//Pagination/MedlinePgn")) or safe_text(root.find(".//Article/ELocationID[@EIdType='pii']"))
        doi = ""
        
        for idel in root.findall(".//ArticleIdList/ArticleId"):
            if idel.get("IdType", "").lower() == "doi":
                doi = safe_text(idel)
                break
        
        if not doi: # still not finding doi
            for eloc in root.findall(".//Article/ELocationID"):
                if eloc.get("EIdType", "").lower() == "doi":
                    doi = safe_text(eloc)
                    break
        
        authors = extract_authors(root)
        authors_v = authors_vancouver(authors)
        authors_a = authors_apa(authors)
        
        # texts = []
        # for ab in root.findall(".//Abstract/AbstractText"):
        #     label = ab.get("Label")
        #     t = (ab.text or "").strip()
        #     if not t:
        #         continue
        #     texts.append(f"{label}: {t}" if label else t)
        # abstract = "\n".join(texts).strip()
        
        abstract = _collect_abstract_texts(root)
        
        meta = {
            "pmid": pmid, "title": title, "journal": journal, "year": year, "volume": volume, "issue": issue,
            "pages": pages, "doi": doi, "authors": authors, "authors_str": authors_v, "authors_apa": authors_a,
            "abstract": abstract, "abstract_length": len(abstract),
        }
        
        # Add canonical URLs to meta
        meta = build_canonical_links(meta)
        
        # References are in the same format (using APA/Vancouver as before).
        meta["reference"] = format_apa(meta) if style.lower() == "apa" else format_vancouver(meta)

        # Sanitize reference text to prevent strange links/parameters.
        meta["reference"] = sanitize_markdown_urls(meta["reference"])
        
        return meta

class PubMedSummaryTool(BaseTool):
    name: str = "pubmed_summary"
    description: str = "Fallback via esummary"
    args_schema: Type[BaseModel] = PubMedSummaryInput
    
    def _run(self, pmid: str) -> Dict[str, Any]:
        params = {
            "db": "pubmed", "id": pmid, "retmode": "json",
            "tool": "crew-pubmed-agent",
            "email": os.getenv("PUBMED_CONTACT_EMAIL", "you@example.com"),
        }
        
        ncbi_key = os.getenv("NCBI_API_KEY")
        if ncbi_key:
            params["api_key"] = ncbi_key
        
        headers = {
            "User-Agent": "CrewAI-PubMed-Tool/1.0", 
            "Accept": "application/json"
        }
        r = requests.get(E_SUMMARY_URL, params=params, timeout=30, headers=headers)
        
        if r.status_code in (429, 502, 503, 504):
            log_err({"pmid": pmid, "stage": "esummary", "error": f"HTTP {r.status_code}"})
            raise RuntimeError(f"Transient HTTP {r.status_code} on esummary")
        
        r.raise_for_status()
        
        j = r.json().get("result", {}).get(pmid, {})
        
        meta = {
            "pmid": pmid,
            "title": j.get("title", ""),
            "journal": (j.get("fulljournalname") or j.get("source") or ""),
            "year": str(j.get("pubdate", "")).split(" ")[0][:4],
            "volume": j.get("volume", ""), "issue": j.get("issue", ""), "pages": j.get("pages", ""),
            "doi": "", "authors": [], "authors_str": "", "authors_apa": "", "abstract": "",
            "reference": "", "parse_status": "esummary-fallback"
        }
        
        eloc = j.get("elocationid", "")
        
        if isinstance(eloc, str) and "doi:" in eloc.lower():
            meta["doi"] = eloc.lower().replace("doi:", "").strip()
            
        meta = build_canonical_links(meta)
        
        return meta