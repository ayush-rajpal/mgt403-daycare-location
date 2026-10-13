"""
Reproduce every result, document and slide in this repository with one command:

    python run_all.py              # uses the committed data extracts (no downloads, no API key needed)
    python run_all.py --download   # first re-download the large public raw files (see src/download_raw_data.py)

Steps (all scripts live in src/; paths are defined once in src/common.py):
  1 step1_ps4_prices.py         PS4: childcare price distribution and trends           -> outputs/ps4
  2 step2_ps4_report.py         PS4 report PDF                                         -> deliverables/
  3 step3_ps5_cost_panel.py     PS5: year x county panel (OEWS wages + ACS + crosswalk) -> outputs/ps5
  4 step4_ps5_report.py         PS5 report PDF                                         -> deliverables/
  5 step5_final_analysis.py     Pre-analysis + final project analysis                  -> outputs/final
  6 step6_final_documents.py    Pre-analysis/final-analysis PDF and appendix PDF       -> deliverables/
  7 step7_final_deck.js         Six-slide presentation (Node.js + pptxgenjs)           -> deliverables/
  check checks/verify_results.py  independent recomputation of every key number
"""
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = [sys.executable]
STEPS = [
    ("PS4 analysis", PY + ["src/step1_ps4_prices.py"]),
    ("PS4 report", PY + ["src/step2_ps4_report.py"]),
    ("PS5 panel and analysis", PY + ["src/step3_ps5_cost_panel.py"]),
    ("PS5 report", PY + ["src/step4_ps5_report.py"]),
    ("Final analysis", PY + ["src/step5_final_analysis.py"]),
    ("Final documents", PY + ["src/step6_final_documents.py"]),
    ("Slide deck", ["node", "src/step7_final_deck.js"]),
    ("Independent checks", PY + ["checks/verify_results.py"]),
]


def run(label, cmd):
    t = time.time()
    print(f"\n=== {label}: {' '.join(cmd[1:] if cmd[0] == sys.executable else cmd)}", flush=True)
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:], sep="\n")
        sys.exit(f"FAILED at step '{label}' (exit {r.returncode})")
    print(f"    ok ({time.time() - t:.0f}s)  {tail[:150]}")


if __name__ == "__main__":
    if "--download" in sys.argv:
        run("Download raw data", PY + ["src/download_raw_data.py"])
    if shutil.which("node") is None:
        sys.exit("Node.js is required for the slide deck (step 7): https://nodejs.org")
    if not (ROOT / "node_modules" / "pptxgenjs").exists():
        print("Installing pptxgenjs (npm install) ...")
        subprocess.run("npm install --no-audit --no-fund", cwd=ROOT, shell=True, check=True)
    for label, cmd in STEPS:
        run(label, cmd)
    if (ROOT / "private" / "presenter_script.py").exists():  # optional personal step, git-ignored
        run("Presenter script (private)", PY + ["private/presenter_script.py"])
    print("\nAll steps finished. Results: outputs/   Documents and slides: deliverables/")
