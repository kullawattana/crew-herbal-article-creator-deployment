import io, os, re, json, base64
from pathlib import Path
from typing import List, Dict, Any, Tuple
from typing import Optional

from crewai.tools import tool
from google.oauth2.service_account import Credentials as SA_Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# ====== CONFIG ======
DOWNLOAD_DIR = os.getenv("RAG_PDF_DIR", "data/pdf")  # mount volume/ persistent path
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

def _get_sa_credentials():
    """
    Expect one of:
    - GOOGLE_SERVICE_ACCOUNT_JSON_B64 (base64 of SA json)
    - GOOGLE_SERVICE_ACCOUNT_JSON_PATH (path inside container)
    "data/gdrive/autorize_google_drive_service_account_json_b64.txt"
    """
    b64 = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_B64")
    if b64:
        info = json.loads(base64.b64decode(b64).decode("utf-8"))
        return SA_Credentials.from_service_account_info(info, scopes=SCOPES)

    path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_PATH")
    if path and Path(path).exists():
        return SA_Credentials.from_service_account_file(path, scopes=SCOPES)

    raise RuntimeError("Missing SA credentials: set GOOGLE_SERVICE_ACCOUNT_JSON_B64 or GOOGLE_SERVICE_ACCOUNT_JSON_PATH")

def _drive():
    creds = _get_sa_credentials()
    return build("drive", "v3", credentials=creds, cache_discovery=False)

def _extract_file_id(link_or_id: str) -> str:
    if re.fullmatch(r"[\w-]{20,}", link_or_id):
        return link_or_id
    pats = [
        r"/file/d/([\w-]+)/",
        r"id=([\w-]+)",
        r"/document/d/([\w-]+)/",
        r"/presentation/d/([\w-]+)/",
        r"/spreadsheets/d/([\w-]+)/",
    ]
    for p in pats:
        m = re.search(p, link_or_id)
        if m: return m.group(1)
    return link_or_id

def _download_pdf_bytes(svc, file_id: str) -> Tuple[bytes, Dict[str, Any]]:
    meta = svc.files().get(
        fileId=file_id,
        fields="id,name,mimeType,modifiedTime,driveId"
    ).execute()
    mime = meta["mimeType"]

    if mime == "application/pdf":
        req = svc.files().get_media(fileId=file_id)
    elif mime.startswith("application/vnd.google-apps"):
        # Export Google Docs/Slides/Sheets -> PDF
        req = svc.files().export_media(fileId=file_id, mimeType="application/pdf")
    else:
        raise ValueError(f"Unsupported mimeType for RAG source: {mime}")

    fh = io.BytesIO()
    dl = MediaIoBaseDownload(fh, req)
    done = False
    while not done:
        _, done = dl.next_chunk()
    fh.seek(0)
    return fh.read(), meta

def _safe_name(name: str) -> str:
    name = re.sub(r"[^\w\-.ก-๙\s]", "_", name)
    name = re.sub(r"\s+", "_", name).strip("_")
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name

@tool("gdrive_list_pdfs_for_rag")
def gdrive_list_pdfs_for_rag(query: str, max_files: int = 10) -> List[Dict[str, Any]]:
    """
    Search PDF/Google Docs files exported as PDF in Drive (including Shared Drives)
    Returns file list metadata
    """
    svc = _drive()
    q = (
        f"(name contains '{query}' and trashed = false) and ("
        "mimeType='application/pdf' or "
        "mimeType='application/vnd.google-apps.document' or "
        "mimeType='application/vnd.google-apps.presentation' or "
        "mimeType='application/vnd.google-apps.spreadsheet')"
    )

    resp = svc.files().list(
        q=q,
        pageSize=max_files,
        fields="files(id,name,mimeType,modifiedTime,owners/displayName,driveId)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="allDrives"
    ).execute()
    return resp.get("files", [])

@tool("gdrive_fetch_pdfs_for_rag")
def gdrive_fetch_pdfs_for_rag(file_ids_or_links: List[str]) -> Dict[str, Any]:
    """
    Download files based on specified IDs/links -> Save as .pdf in DOWNLOAD_DIR
    Return {"count": N, "paths": [...], "items": [...]}
    """
    svc = _drive()
    out_dir = Path(DOWNLOAD_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    paths, items = [], []
    for raw in file_ids_or_links:
        fid = _extract_file_id(raw)
        pdf_bytes, meta = _download_pdf_bytes(svc, fid)
        fname = _safe_name(meta["name"])
        fpath = out_dir / fname
        fpath.write_bytes(pdf_bytes)

        paths.append(str(fpath))
        items.append({
            "id": meta["id"],
            "name": meta["name"],
            "mimeType": meta["mimeType"],
            "modifiedTime": meta.get("modifiedTime"),
            "driveId": meta.get("driveId"),
            "local_path": str(fpath),
        })

    return {"count": len(paths), "paths": paths, "items": items}

@tool("gdrive_list_pdfs_in_folder_for_rag")
def gdrive_list_pdfs_in_folder_for_rag(folder_id: str, query: Optional[str] = None, max_files: int = 50):
    """
    Find PDF/Google Docs files that can be exported as PDF 'only in this folder'
    """
    svc = _drive()
    # Conditions are in the folder
    parent_q = f"'{folder_id}' in parents and trashed = false"
    # Supported file types
    mime_q = "(" + " or ".join([
        "mimeType='application/pdf'",
        "mimeType='application/vnd.google-apps.document'",
        "mimeType='application/vnd.google-apps.presentation'",
        "mimeType='application/vnd.google-apps.spreadsheet'",
    ]) + ")"
    # Continue query (optional)
    name_q = f" and name contains '{query}'" if query else ""
    q = f"{parent_q} and {mime_q}{name_q}"

    resp = svc.files().list(
        q=q,
        pageSize=max_files,
        fields="files(id,name,mimeType,modifiedTime,owners/displayName,driveId)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="allDrives"
    ).execute()
    return resp.get("files", [])

@tool("gdrive_fetch_pdfs_in_folder_for_rag")
def gdrive_fetch_pdfs_in_folder_for_rag(folder_id: str, max_files: int = 50):
    """
    Download all supported files as PDF in this folder -> save to DOWNLOAD_DIR and return paths.
    """
    files = gdrive_list_pdfs_in_folder_for_rag.run(folder_id=folder_id, query=None, max_files=max_files)
    return gdrive_fetch_pdfs_for_rag.run([f["id"] for f in files])
