# om_agent.py (single-parser version)
import os, json, hashlib, subprocess

ROOT = os.getcwd()
INPUT_DIR  = os.path.join(ROOT, "Inputs")
NORM_DIR   = os.path.join(ROOT, r"Outputs\Normalized\OM_INTAKE")
SCORE_DIR  = os.path.join(ROOT, r"Outputs\Scorecards\OM_INTAKE")
REVIEWROOT = os.path.join(ROOT, r"Outputs\Review")
CONFIG_YAML= os.path.join(ROOT, r"Config\guardrails.yaml")
LOGS_DIR   = os.path.join(ROOT, "Logs")
STATE_PATH = os.path.join(LOGS_DIR, "processed_files.json")

os.makedirs(NORM_DIR, exist_ok=True)
os.makedirs(SCORE_DIR, exist_ok=True)
os.makedirs(REVIEWROOT, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def load_state():
    if not os.path.exists(STATE_PATH):
        return {"processed": []}
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def process_pdf(pdf_path):
    base = os.path.splitext(os.path.basename(pdf_path))[0].replace(" ", "_")
    # 1) normalize (generic only)
    subprocess.run(["python", "om_normalizer_basic.py",
                    "--pdf", pdf_path,
                    "--bucket", "OM_INTAKE",
                    "--outroot", r"Outputs\Normalized"],
                   check=False)
    norm_json = os.path.join(NORM_DIR, f"{base}.json")
    if not os.path.exists(norm_json):
        print(f"Skip (no normalized JSON): {os.path.basename(pdf_path)}")
        return False

    # 2) summary
    subprocess.run(["python", "om_summary.py",
                    "--bucket", "OM_INTAKE",
                    "--norm", norm_json,
                    "--outdir", r"Outputs\Scorecards"],
                   check=False)

    # 3) color label (copies PDF into Outputs\Review\{color})
    subprocess.run(["python", "color_labeler.py",
                    "--norm", norm_json,
                    "--config", CONFIG_YAML,
                    "--reviewroot", r"Outputs\Review",
                    "--labels_csv", r"Outputs\labels_log.csv"],
                   check=False)
    print(f"Processed: {os.path.basename(pdf_path)}")
    return True

def main():
    state = load_state()
    seen = set(state.get("processed", []))

    for name in os.listdir(INPUT_DIR):
        if not name.lower().endswith(".pdf"):
            continue
        pdf = os.path.join(INPUT_DIR, name)
        h = file_hash(pdf)
        if h in seen:
            continue
        if process_pdf(pdf):
            seen.add(h)
            save_state({"processed": list(seen)})

if __name__ == "__main__":
    main()
