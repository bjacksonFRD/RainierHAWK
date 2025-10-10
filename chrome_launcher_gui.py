# chrome_launcher_gui.py
# Stable Chrome launcher + OCR clicker using system profile
# (ported directly from the working FileCloud version)

import os
import time
import pyautogui
import pytesseract
from PIL import ImageGrab
from dotenv import load_dotenv
import subprocess

# ---------- Environment ----------
load_dotenv()
pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_PATH")

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE_PATH = r"--profile-directory=Default"
# Use the actual logged-in Chrome profile, not a temp one

# ---------- Launch Chrome ----------
def launch_chrome(target_url):
    """
    Launch Chrome using the system's default user profile (visible and authenticated)
    """
    if not os.path.exists(CHROME_PATH):
        raise FileNotFoundError(f"Chrome not found at {CHROME_PATH}")

    subprocess.Popen([
        CHROME_PATH,
        "--new-window",
        "--start-maximized",
        PROFILE_PATH,
        "--disable-download-notification",
        target_url
    ])
    print(f"Chrome launched -> {target_url}")
    time.sleep(10)  # wait for visible rendering

# ---------- OCR Click Engine ----------
def ocr_find_and_click(target_words, max_wait=30, interval=2):
    """
    Scan visible screen for target words and click them.
    """
    waited = 0
    clicked = False
    while waited < max_wait and not clicked:
        screenshot = ImageGrab.grab()
        gray = screenshot.convert("L")
        gray.save("ocr_debug.png")
        print("Saved ocr_debug.png for review")

        data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
        for i, word in enumerate(data["text"]):
            if any(tw.lower() in word.strip().lower() for tw in target_words):
                x, y = data["left"][i], data["top"][i]
                w, h = data["width"][i], data["height"][i]
                pyautogui.moveTo(x + w // 2, y + h // 2, duration=0.2)
                pyautogui.click()
                print(f"OCR clicked '{word.strip()}' at ({x},{y})")
                clicked = True
                break

        if not clicked:
            time.sleep(interval)
            waited += interval

    if not clicked:
        print(f"Target {target_words} not found after {max_wait}s.")
    return clicked

# ---------- Post-click Cleanup ----------
def clear_download_tray():
    """
    Dismiss Chrome's download bar and reposition cursor.
    """
    time.sleep(2)
    pyautogui.press('esc')
    time.sleep(1)
    pyautogui.moveRel(0, 750, duration=0.2)
    print("Mouse moved 750px down to clear download tray.")

# ---------- Example Test ----------
if __name__ == "__main__":
    test_url = "https://www.crexi.com"
    launch_chrome(test_url)
    ocr_find_and_click(["Sign Up or Log In", "Login"])
    clear_download_tray()
    print("Chrome OCR launcher test complete.")
