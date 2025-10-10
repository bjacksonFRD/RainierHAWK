# universal_ocr_automation.py
# Universal OCR-driven GUI automation for all broker platforms.

import sys
import time
import pyautogui
from chrome_launcher_gui import launch_chrome, ocr_find_and_click, clear_download_tray

# ---------- Argument Parsing ----------
if len(sys.argv) < 2:
    print("Usage: python universal_ocr_automation.py <target_url>")
    sys.exit(1)

TARGET_URL = sys.argv[1]

# Define general-purpose OCR target words common across platforms
PLATFORM_WORDS = [
    # Login / Access
    "Sign Up or Log In", "Log In", "Login", "Sign In",
    # Common NDAs / confirmations
    "I Agree", "Accept", "Continue", "Proceed",
    # Common download buttons
    "Download", "View OM", "View Offering", "Open Package", "Access Files"
]

# ---------- Workflow ----------
print(f"Starting OCR automation for {TARGET_URL} ...")
launch_chrome(TARGET_URL)
time.sleep(5)

# Step 1: Trigger any login / access modal
ocr_find_and_click(["Sign Up or Log In", "Log In", "Login", "Sign In"], max_wait=40)

# Step 2: Handle NDA / confirmation
ocr_find_and_click(["I Agree", "Accept", "Continue", "Proceed"], max_wait=20)

# Step 3: Handle main download / view action
ocr_find_and_click(["Download", "View OM", "View Offering", "Access Files"], max_wait=30)

# Step 4: Clear tray and finalize
clear_download_tray()
print("Universal OCR automation complete.")
