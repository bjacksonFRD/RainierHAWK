# email_intake_graph_router.py (fast, can't-hang)
# - Short timeouts (HEAD 5s / GET 8s)
# - Max 5 links probed per message
# - Skips known tracking/gated hosts early
# - Unwraps SafeLinks
# - Downloads direct PDFs/ZIPs to Inputs\
# - Queues gated links to Logs\gated_queue.json
# - Writes progress to Logs\email_intake.log

import os, re, io, json, zipfile, base64, logging
from urllib.parse import urlparse, parse_qs, unquote
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from msal import ConfidentialClientApplication
from dotenv import load_dotenv

ROOT   = os.getcwd()
INPUTS = os.path.join(ROOT, "Inputs")
LOGS   = os.path.join(ROOT, "Logs")
os.makedirs(INPUTS, exist_ok=True)
os.makedirs(LOGS, exist_ok=True)

LOG_PATH   = os.path.join(LOGS, "email_intake.log")
QUEUE_PATH = os.path.join(LOGS, "gated_queue.json")
logging.basicConfig(filename=LOG_PATH, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ---- Tunables ----
HEAD_TIMEOUT = 5
GET_TIMEOUT  = 8
MAX_LINKS_PER_MESSAGE = 5
UA_HDRS = {"User-Agent": "Rainier-OM-Intake/1.0 (+Windows; Python requests)"}

# Known tracking/gated hosts to short-circuit
GATED_TRACKING_HOSTS = {
    "email.search.crexi.com",
    "url4030.crexi.com",
    "links.crexi.com",
    "lnk.crexi.com",
    "click.em.crexi.com",
    "communications.costar.com",
    "email.10xmarketingcloud.com",
    "nam10.safelinks.protection.outlook.com",  # we still unwrap, but treat as gated
}

load_dotenv()
TENANT  = os.getenv("GRAPH_TENANT_ID", "")
CID     = os.getenv("GRAPH_CLIENT_ID", "")
CSECRET = os.getenv("GRAPH_CLIENT_SECRET", "")
MAILBOX = os.getenv("GRAPH_USER", "")
FOLDER  = os.getenv("GRAPH_FOLDER", "Inbox")
TOP     = int(os.getenv("GRAPH_TOP", "50"))
BROKER_LINK_DOMAINS = {
    d.strip().lower() for d in (os.getenv("BROKER_LINK_DOMAINS", "").split(",")) if d.strip()
}

def token() -> str:
    app = ConfidentialClientApplication(
        CID,
        authority=f"https://login.microsoftonline.com/{TENANT}",
        client_credential=CSECRET,
    )
    scopes = ["https://graph.microsoft.com/.default"]
    res = app.acquire_token_silent(scopes, account=None) or app.acquire_token_for_client(scopes=scopes)
    if "access_token" not in res:
        raise RuntimeError(f"MSAL auth failed: {res}")
    return res["access_token"]

def gget(url, tok, timeout=20):
    try:
        r = requests.get(url, headers={"Authorization": f"Bearer {tok}", **UA_HDRS}, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.Timeout:
        logging.error(f"Timeout fetching {url}")
        raise
    except requests.HTTPError as e:
        logging.error(f"HTTP error fetching {url}: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error fetching {url}: {e}")
        raise

def sanitize_filename(name: str) -> str:
    name = os.path.basename(name or "file.pdf")
    name = re.sub(r"[\\/:*?\"<>|]", "_", name).strip()
    return name or "file.pdf"

def save_pdf_bytes(name_hint: str, data: bytes):
    name = sanitize_filename(name_hint)
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    out = os.path.join(INPUTS, name)
    with open(out, "wb") as f:
        f.write(data)
    logging.info(f"Saved PDF -> {out}")
    print(f"  [+] saved: {out}")

def extract_zip_to_inputs(zip_bytes: bytes):
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for memb in zf.infolist():
                if memb.is_dir():
                    continue
                if memb.filename.lower().endswith(".pdf"):
                    save_pdf_bytes(os.path.basename(memb.filename), zf.read(memb))
    except zipfile.BadZipFile:
        logging.warning("Invalid ZIP file provided")
    except Exception as e:
        logging.warning(f"Failed to extract ZIP: {e}")

def is_safelink(url: str) -> bool:
    try:
        return "safelinks.protection.outlook.com" in urlparse(url).netloc.lower()
    except Exception:
        return False

def unwrap_safelink(url: str) -> str:
    try:
        p = urlparse(url)
        q = parse_qs(p.query)
        target = q.get("url", [None])[0]
        if target:
            return unquote(target)
    except Exception:
        pass
    return url

def host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""

def likely_file_endpoint(url: str) -> str:
    try:
        p = urlparse(url)
        path = p.path.lower()
        if path.endswith(".pdf"):
            return "pdf"
        if path.endswith(".zip"):
            return "zip"
        return ""
    except Exception:
        return ""

def direct_downloadable(url: str) -> bool:
    try:
        h = host(url)
        if h in GATED_TRACKING_HOSTS:
            return False
        if not any(h.endswith(d) for d in BROKER_LINK_DOMAINS):
            return False
        r = requests.head(url, headers=UA_HDRS, timeout=HEAD_TIMEOUT, allow_redirects=True)
        ct = (r.headers.get("content-type", "").lower())
        return (
            r.status_code == 200 and
            (ct.startswith("application/pdf") or ct.startswith("application/zip") or
             url.lower().endswith(".pdf") or url.lower().endswith(".zip"))
        )
    except Exception:
        return False

def write_queue_append(url: str, subject: str):
    try:
        q = {"queue": []}
        if os.path.exists(QUEUE_PATH):
            with open(QUEUE_PATH, "r", encoding="utf-8") as f:
                cur = json.load(f)
                if isinstance(cur, dict) and isinstance(cur.get("queue"), list):
                    q = cur
        q["queue"].append({
            "url": url,
            "subject": subject[:200],
            "queued_at": datetime.utcnow().isoformat() + "Z"
        })
        tmp = QUEUE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(q, f, indent=2)
        os.replace(tmp, QUEUE_PATH)
        print(f"  [>] queued gated: {url}")
    except Exception as e:
        logging.warning(f"Queue write failed: {e}")

def download_link(url: str) -> int:
    kind = likely_file_endpoint(url)
    if not kind and not direct_downloadable(url):
        return 0
    try:
        r = requests.get(url, allow_redirects=True, timeout=GET_TIMEOUT, headers=UA_HDRS)
        r.raise_for_status()
        ct = (r.headers.get("content-type", "").lower())
        if kind == "pdf" or ct.startswith("application/pdf") or r.content[:5] == b"%PDF-":
            fname = os.path.basename(urlparse(url).path) or "download.pdf"
            save_pdf_bytes(fname, r.content)
            return 1
        if kind == "zip" or "zip" in ct:
            extract_zip_to_inputs(r.content)
            return 1
    except requests.Timeout:
        logging.warning(f"Timeout downloading {url}")
    except requests.HTTPError as e:
        logging.warning(f"HTTP error downloading {url}: {e}")
    except zipfile.BadZipFile:
        logging.warning(f"Invalid ZIP file at {url}")
    except Exception as e:
        logging.warning(f"Unexpected error downloading {url}: {e}")
    return 0

def handle_attachments(mid: str, tok: str) -> int:
    saved = 0
    try:
        base = f"https://graph.microsoft.com/v1.0/users/{MAILBOX}/messages/{mid}/attachments"
        atts = gget(base, tok)
        for att in atts.get("value", []):
            ct = (att.get("contentType") or "").lower()
            name = att.get("name", "").lower()
            if not (ct.startswith("application/pdf") or name.endswith(".pdf") or
                    ct.startswith("application/zip") or name.endswith(".zip")):
                continue
            data = base64.b64decode(att.get("contentBytes", ""))
            if name.endswith(".pdf"):
                save_pdf_bytes(name, data)
                saved += 1
            elif name.endswith(".zip"):
                extract_zip_to_inputs(data)
                saved += 1
    except Exception as e:
        logging.warning(f"Attachment processing failed for message {mid}: {e}")
    return saved

def handle_links(subject: str, body_html: str) -> int:
    if not body_html:
        return 0
    soup = BeautifulSoup(body_html, "lxml")
    saved = 0
    probed = 0
    for a in soup.find_all("a", href=True):
        if probed >= MAX_LINKS_PER_MESSAGE:
            print("  [!] link cap reached; skipping rest")
            break
        raw = a["href"]
        url = unwrap_safelink(raw) if is_safelink(raw) else raw
        h = host(url)

        if h in GATED_TRACKING_HOSTS:
            logging.info(f"GATED host (skip): {raw}")
            write_queue_append(url, subject)
            probed += 1
            continue

        path = urlparse(url).path.lower()
        if not (any(h.endswith(d) for d in BROKER_LINK_DOMAINS) or path.endswith(".pdf") or path.endswith(".zip")):
            logging.info(f"Non-allowlisted link (queue): {url}")
            write_queue_append(url, subject)
            probed += 1
            continue

        got = download_link(url)
        if got > 0:
            saved += got
        else:
            logging.info(f"GUI/NDA (queue): {url}")
            write_queue_append(url, subject)
        probed += 1
    return saved

def main():
    missing = [k for k, v in {
        "GRAPH_TENANT_ID": TENANT,
        "GRAPH_CLIENT_ID": CID,
        "GRAPH_CLIENT_SECRET": CSECRET,
        "GRAPH_USER": MAILBOX
    }.items() if not v]
    if missing:
        print("Missing required .env values: " + ", ".join(missing))
        return

    print("[intake] starting...")
    try:
        tok = token()
    except RuntimeError as e:
        print(f"[intake] auth failed: {e}")
        return

    base = f"https://graph.microsoft.com/v1.0/users/{MAILBOX}/mailFolders/{FOLDER}/messages"
    params = f"?$top={TOP}&$orderby=receivedDateTime desc&$select=id,subject,from,hasAttachments,body"
    try:
        data = gget(base + params, tok)
    except Exception as e:
        print(f"[intake] fetch failed: {e}")
        return

    pulled = 0
    for i, m in enumerate(data.get("value", []), 1):
        subject = (m.get("subject") or "").strip()
        print(f"[intake] message {i}: {subject[:72]}")
        mid = m["id"]
        body = (m.get("body", {}) or {}).get("content", "")

        a_saved = handle_attachments(mid, tok) if m.get("hasAttachments") else 0
        l_saved = handle_links(subject, body)
        if (a_saved + l_saved) > 0:
            pulled += 1
            logging.info(f"Message pulled: attachments={a_saved} links={l_saved} subj='{subject[:120]}'")

    print(f"[intake] done. messages with captured files: {pulled}. log: {LOG_PATH}")
    logging.info(f"Intake complete. Messages with captured files: {pulled}")

if __name__ == "__main__":
    main()