import os
import sys
import json
import urllib.request
import subprocess
import threading
from tkinter import messagebox

# Configuration
CURRENT_VERSION = "v1.0.0"
GITHUB_REPO = "sav1on/checkin-terminal"  # Your repository


def check_for_updates():
    """
    Queries the GitHub API for the latest release.
    Returns: (latest_version_tag, download_url) or (None, None)
    """
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    headers = {"User-Agent": "CheckInTerminal-App"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                latest_version = data.get("tag_name", "")

                if latest_version and latest_version != CURRENT_VERSION:
                    for asset in data.get("assets", []):
                        if asset["name"].endswith(".exe"):
                            return latest_version, asset["browser_download_url"]

    except Exception as e:
        print(f"[Updater] Error checking for updates: {e}")

    return None, None


def download_and_install_update(download_url, parent_window=None, on_finish_callback=None):
    """
    Downloads the new .exe release in a background thread and executes 
    updater.bat to swap executables upon app exit.
    """
    def _download_thread():
        try:
            new_exe_path = "CheckInTerminal_new.exe"
            current_exe_path = sys.executable

            # Download executable asset
            print(f"[Updater] Downloading release from: {download_url}")
            urllib.request.urlretrieve(download_url, new_exe_path)

            # Generate batch file to swap .exe files after process exit
            bat_script = f"""@echo off
timeout /t 3 /nobreak > nul
move /y "{new_exe_path}" "{current_exe_path}"
start "" "{current_exe_path}"
del "%~f0"
"""
            with open("updater.bat", "w") as f:
                f.write(bat_script)

            print("[Updater] Download complete. Restarting application...")

            # Destroy parent Tkinter window if passed
            if parent_window:
                parent_window.after(0, parent_window.destroy)

            # Launch batch script and exit current process
            subprocess.Popen(["updater.bat"], shell=True)
            sys.exit(0)

        except Exception as e:
            print(f"[Updater] Download/Install failed: {e}")
            if parent_window:
                parent_window.after(
                    0, lambda: messagebox.showerror("Update Error", f"Failed to download update: {e}")
                )
            if on_finish_callback:
                parent_window.after(0, on_finish_callback)

    # Run download in non-blocking background thread
    threading.Thread(target=_download_thread, daemon=True).start()


def trigger_github_update_flow(parent_window=None, on_finish_callback=None):
    """
    Main function to connect to your UI's 'Check for Updates' button.
    Runs check asynchronously and prompts the user.
    """
    def _check_thread():
        latest_version, download_url = check_for_updates()

        if download_url:
            def _prompt_user():
                answer = messagebox.askyesno(
                    "Update Available",
                    f"A new version ({latest_version}) is available!\n"
                    f"Current version: {CURRENT_VERSION}\n\n"
                    f"Would you like to download and install the update now?"
                )
                if answer:
                    download_and_install_update(download_url, parent_window, on_finish_callback)
                elif on_finish_callback:
                    on_finish_callback()

            if parent_window:
                parent_window.after(0, _prompt_user)
        else:
            def _no_update_notice():
                messagebox.showinfo("Up to Date", f"You are using the latest version ({CURRENT_VERSION}).")
                if on_finish_callback:
                    on_finish_callback()

            if parent_window:
                parent_window.after(0, _no_update_notice)

    threading.Thread(target=_check_thread, daemon=True).start()