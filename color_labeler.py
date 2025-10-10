import os, json, argparse, shutil, yaml, pandas as pd

def to_pct(x):
    try:
        return float(str(x).replace("%","").replace(",","").strip())
    except:
        return None

def parse_occ_from_pm(norm_dir, pm_csv):
    try:
        pm = pd.read_csv(os.path.join(norm_dir, pm_csv))
        occ = pm.loc[pm["Metric"].str.contains("Total Property Occupancy", na=False)]
        if occ.empty:
            return None
        # Prefer collection-wide column if present; else first numeric among the next 4 columns
        for col in occ.columns[1:5]:
            v = str(occ.iloc[0][col]).replace("%","").strip()
            try:
                return float(v)
            except:
                pass
    except:
        pass
    return None

def cleanup_previous(reviewroot, filename, keep_folder, missing_folder):
    for folder in ["Green", "Yellow", "Red", missing_folder]:
        if folder == keep_folder:
            continue
        path = os.path.join(reviewroot, folder, filename)
        try:
            if os.path.exists(path):
                os.remove(path)
        except:
            pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--norm", required=True)                  # path to normalized JSON
    ap.add_argument("--config", default=r"Config\guardrails.yaml")
    ap.add_argument("--reviewroot", default=r"Outputs\Review")
    ap.add_argument("--labels_csv", default=r"Outputs\labels_log.csv")
    args = ap.parse_args()

    with open(args.norm, "r", encoding="utf-8") as f:
        meta = json.load(f)
    with open(args.config, "r", encoding="utf-8") as f:
        G = yaml.safe_load(f) or {}

    thr = G.get("simple_thresholds", {})
    mtm_g = float(thr.get("mtm_pct_green_min", 20))
    mtm_y = float(thr.get("mtm_pct_yellow_min", 10))
    occ_g = float(thr.get("occupancy_green_min", 92))
    occ_y = float(thr.get("occupancy_yellow_min", 88))

    missing_policy = (G.get("missing_policy") or "both").lower()           # "both" or "any"
    missing_folder  = G.get("missing_folder_name") or "Missing Data"

    # Extract metrics
    mtm = meta.get("mtm_headline") or meta.get("mtm_head")
    mtm_pct = to_pct(mtm.get("Avg_MTM_Pct")) if mtm else None

    occ = None
    if meta.get("property_metrics_csv"):
        occ = parse_occ_from_pm(os.path.dirname(args.norm), meta["property_metrics_csv"])

    has_mtm = mtm_pct is not None
    has_occ = occ is not None

    # Decide if this should be sent to Missing Data
    if missing_policy == "any":
        is_missing = (not has_mtm) or (not has_occ)
    else:  # "both"
        is_missing = (not has_mtm) and (not has_occ)

    reasons = []
    if is_missing:
        color = "Missing Data"
        if not has_mtm: reasons.append("missing MTM%")
        if not has_occ: reasons.append("missing Occupancy%")
    else:
        green  = (has_mtm and mtm_pct >= mtm_g) or (has_occ and occ >= occ_g)
        yellow = (not green) and ((has_mtm and mtm_pct >= mtm_y) or (has_occ and occ >= occ_y))
        color  = "Green" if green else ("Yellow" if yellow else "Red")
        if has_mtm: reasons.append(f"MTM%={mtm_pct}")
        if has_occ: reasons.append(f"Occ%={occ}")

    # Ensure review folder exists and move/copy file
    src_pdf = meta.get("source_pdf")
    filename = os.path.basename(src_pdf) if src_pdf else ""
    os.makedirs(os.path.join(args.reviewroot, color), exist_ok=True)
    if src_pdf and os.path.exists(src_pdf):
        cleanup_previous(args.reviewroot, filename, color, missing_folder)
        shutil.copy2(src_pdf, os.path.join(args.reviewroot, color, filename))

    # Log the label
    row = {
        "file": filename,
        "norm_json": os.path.basename(args.norm),
        "label": color,
        "mtm_pct": mtm_pct,
        "occupancy_pct": occ,
        "reasons": "; ".join(reasons)
    }
    os.makedirs(os.path.dirname(args.labels_csv), exist_ok=True)
    if os.path.exists(args.labels_csv):
        df = pd.read_csv(args.labels_csv)
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        df.to_csv(args.labels_csv, index=False)
    else:
        pd.DataFrame([row]).to_csv(args.labels_csv, index=False)

    print(f"Labeled {color} -> {args.labels_csv}")

if __name__ == "__main__":
    main()
