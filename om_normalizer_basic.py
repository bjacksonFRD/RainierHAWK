import os, re, json, argparse, pandas as pd, pdfplumber, fitz

def find_first_page(pdf, keyword):
    for i, p in enumerate(pdf.pages):
        t = (p.extract_text() or "").lower()
        if keyword.lower() in t: return i
    return None

def grab_tables(pdf, max_pages=None):
    rows = []
    for p in pdf.pages[:max_pages or len(pdf.pages)]:
        for tbl in (p.extract_tables() or []):
            if not tbl or len(tbl) < 2: continue
            header = [(h or "").strip().lower() for h in tbl[0]]
            if any(k in " ".join(header) for k in ["tenant", "suite", "sf", "rent", "expiration", "led"]):
                for r in tbl[1:]:
                    rows.append([(c or "").strip() for c in r])
    return rows[:200]

def parse_prop_metrics(doc):
    labels = ["total property gla", "total property occupancy", "shop sales psf", "occupancy cost",
              "year built", "acreage", "parking", "placer.ai"]
    out = []
    text = " ".join(page.get_text() for page in doc).lower()
    for lab in labels:
        m = re.search(rf"{re.escape(lab)}\s*[:=]?\s*([^\n;]+)", text, re.I)
        if m: out.append(m.group(0))
    return out

def extract_mtm(doc):
    text = " ".join(page.get_text() for page in doc).replace("\n", " ")
    m = re.search(r"\$?(\d+\.?\d*)\s*psf.*?\$?(\d+\.?\d*)\s*psf.*?(\d+\.?\d*)\s*%", text, re.I)
    if m:
        return {"InPlace_Avg_PSF": m.group(1), "Market_Avg_PSF": m.group(2), "Avg_MTM_Pct": m.group(3)}
    return {}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--bucket", default="OM_INTAKE")
    ap.add_argument("--outroot", default=r"Outputs\Normalized")
    args = ap.parse_args()

    outdir = os.path.join(args.outroot, args.bucket)
    os.makedirs(outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(args.pdf))[0].replace(" ", "_")

    with pdfplumber.open(args.pdf) as pdf, fitz.open(args.pdf) as doc:
        rr_rows = grab_tables(pdf)
        mtm_head = extract_mtm(doc)
        prop_hint = parse_prop_metrics(doc)

    rr_csv = None
    if rr_rows:
        rr_csv = f"{base}_rentroll_raw.csv"
        pd.DataFrame(rr_rows).to_csv(os.path.join(outdir, rr_csv), index=False, header=False)

    payload = {
        "source_pdf": os.path.abspath(args.pdf),
        "bucket": args.bucket,
        "rentroll_csv": rr_csv,
        "mtm_headline": mtm_head,
        "property_metrics_hints": prop_hint[:20]
    }
    with open(os.path.join(outdir, f"{base}.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Normalized -> {os.path.join(outdir, f'{base}.json')}")

if __name__ == "__main__":
    main()