import os, json, argparse, pandas as pd

def percentify(x):
    try:
        s=str(x).replace("%","").strip()
        return float(s) if s else None
    except: return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--bucket", default="OM_INTAKE")
    ap.add_argument("--norm", required=True)
    ap.add_argument("--outdir", default=r"Outputs\Scorecards")
    args=ap.parse_args()

    with open(args.norm,"r",encoding="utf-8") as f: meta=json.load(f)
    outdir=os.path.join(args.outdir, args.bucket); os.makedirs(outdir, exist_ok=True)

    rows=[["Source PDF", meta.get("source_pdf","")]]
    mtm=meta.get("mtm_headline") or meta.get("mtm_headline".replace("headline","headline"))  # tolerant
    if not mtm: mtm=meta.get("mtm_head")
    if mtm:
        rows+=[
            ["Avg In-Place Rent PSF", mtm.get("InPlace_Avg_PSF")],
            ["Avg Market Rent PSF",  mtm.get("Market_Avg_PSF")],
            ["Avg Mark-to-Market %", mtm.get("Avg_MTM_Pct")]
        ]

    # If a property metrics CSV exists (from OKC plugin), include GLA/Occ
    pm_csv=meta.get("property_metrics_csv")
    if pm_csv:
        pm_path=os.path.join(os.path.dirname(args.norm), pm_csv)
        if os.path.exists(pm_path):
            pm=pd.read_csv(pm_path)
            gla=pm.loc[pm["Metric"].str.contains("Total Property GLA", na=False)]
            occ=pm.loc[pm["Metric"].str.contains("Total Property Occupancy", na=False)]
            if not gla.empty: rows.append(["GLA (Collection/CC/Triangle/NHP)", " / ".join(str(x) for x in gla.iloc[0,1:5])])
            if not occ.empty: rows.append(["Occupancy (Collection/CC/Triangle/NHP)", " / ".join(str(x) for x in occ.iloc[0,1:5])])

    out_csv=os.path.join(outdir, os.path.splitext(os.path.basename(args.norm))[0] + "_summary.csv")
    pd.DataFrame(rows, columns=["Metric","Value"]).to_csv(out_csv, index=False)
    print(f"Summary -> {out_csv}")
if __name__=="__main__":
    main()
