from __future__ import annotations
import os
import time
import mimetypes
from typing import Optional, Dict, Any

from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from googleapiclient.errors import HttpError

from crewai.tools import tool
from dotenv import load_dotenv

load_dotenv() 

# -------------------------------------------------
# 1) Auth Google Drive
# -------------------------------------------------
def gdrive_client(client_secret_path: Optional[str] = None) -> GoogleDrive:
    client_secret_path = client_secret_path or os.getenv(
        "GDRIVE_CLIENT_SECRET",
        "data/credentials/client_secrete_gdrive_desktop.json",
    )
    gauth = GoogleAuth()
    gauth.LoadClientConfigFile(client_secret_path)
    gauth.LocalWebserverAuth()
    return GoogleDrive(gauth)

# -------------------------------------------------
# 2) Helper upload file to Drive
# -------------------------------------------------
def upload_file_to_drive(
    drive: GoogleDrive,
    local_path: str,
    drive_filename: str,
    folder_id: Optional[str] = None,
    max_retries: int = 5,
) -> Dict[str, Any]:
    metadata = {"title": drive_filename}
    if folder_id:
        metadata["parents"] = [{"id": folder_id}]
    f = drive.CreateFile(metadata)
    f.SetContentFile(local_path)

    guess, _ = mimetypes.guess_type(drive_filename)
    if guess:
        f["mimeType"] = guess

    for attempt in range(max_retries):
        try:
            f.Upload()
            link = f.get("webViewLink") or f.get("alternateLink")
            return {"id": f["id"], "link": link, "title": f["title"]}
        except HttpError as e:
            status = getattr(e.resp, "status", None)
            if status in (403, 429, 500, 503) and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise

# -------------------------------------------------
# 3) CrewAI Tool [decorator (@tool)]
# -------------------------------------------------
@tool("gdrive_upload_file")
def gdrive_upload_file(
    local_path: str,
    drive_filename: str,
    folder_id: str | None = None, 
) -> Dict[str, Any]:
    """
    CrewAI upload file to Drive Google Drive
    """
    client_secret_path = os.getenv(
        "GDRIVE_CLIENT_SECRET_PATH",
        "data/credentials/client_secrete_gdrive_desktop.json",
    )
    default_folder_id = os.getenv("GDRIVE_UPLOAD_FOLDER_ID")

    drive = gdrive_client(client_secret_path)

    result = upload_file_to_drive(
        drive=drive,
        local_path=local_path,
        drive_filename=drive_filename,
        folder_id=default_folder_id,
    )

    return {
        "file_id": result["id"],
        "view_link": result["link"],
        "title": result["title"],
        "folder_id": default_folder_id,
    }