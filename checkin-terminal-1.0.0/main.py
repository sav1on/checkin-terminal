import customtkinter as ctk
from tkinter import messagebox, ttk
from datetime import datetime
import cv2
from PIL import Image
import os
import sys
import subprocess
import tempfile
import urllib.request
import json
import webbrowser
from database import (
    init_db, register_student_profile, register_employee_profile, 
    delete_student_profile, delete_employee_profile,
    log_student_checkin, log_employee_clock, get_students_with_todays_activity, 
    search_students_with_activity, get_all_employees, get_employee_hours_report, 
    get_student_full_profile, get_employee_full_profile,
    export_to_excel, export_employee_hours_to_excel, has_todays_activity
)

# Silence OpenCV console warning spam for missing camera indices
cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_FATAL)

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

CURRENT_VERSION = "1.0.0"

class CheckInApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Check in Terminal")
        self.root.geometry("1300x780")
        
        init_db()
        os.makedirs("student_photos", exist_ok=True)
        os.makedirs("employee_photos", exist_ok=True)
        self.temp_photo_path = None
        self.sidebar_expanded = True
        
        self.camera_sources = self.detect_camera_sources()
        self.selected_camera_name = list(self.camera_sources.keys())[0] if self.camera_sources else "Built-in FaceTime HD Camera"
        self.saved_camera_name = self.selected_camera_name
        self.saved_theme = ctk.get_appearance_mode()
        
        self.last_date = datetime.now().strftime("%Y-%m-%d")
        self.students_open = True
        self.employees_open = True

        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=1)

        # TOP BAR
        top_bar = ctk.CTkFrame(root, height=60, corner_radius=0, fg_color=("gray80", "gray20"))
        top_bar.grid(row=0, column=0, columnspan=2, sticky="nsew")
        top_bar.grid_columnconfigure(1, weight=1)

        self.hamburger_btn = ctk.CTkButton(top_bar, text="☰", width=45, height=35, font=ctk.CTkFont(size=18, weight="bold"), command=self.toggle_sidebar)
        self.hamburger_btn.grid(row=0, column=0, padx=15, pady=12)

        app_title = ctk.CTkLabel(top_bar, text="Check in Terminal", font=ctk.CTkFont(size=20, weight="bold"))
        app_title.grid(row=0, column=1, sticky="w", padx=5)

        settings_btn = ctk.CTkButton(top_bar, text="⚙", width=45, height=35, font=ctk.CTkFont(size=18, weight="bold"), fg_color="transparent", hover_color=("gray70", "gray30"), command=self.open_settings_modal)
        settings_btn.grid(row=0, column=2, padx=15, pady=12)

        # ACCORDION SIDEBAR MENU
        self.sidebar = ctk.CTkScrollableFrame(root, width=240, corner_radius=0, fg_color=("gray85", "gray15"))
        self.sidebar.grid(row=1, column=0, sticky="nsew")

        ctk.CTkButton(self.sidebar, text="➕ Create Profile (NFC)", fg_color="#27AE60", hover_color="#1E8449", command=lambda: self.switch_frame("creator")).pack(fill="x", padx=10, pady=(15, 10))

        # STUDENTS CATEGORY
        self.btn_students_cat = ctk.CTkButton(self.sidebar, text="▼ 🎓 Students Section", font=ctk.CTkFont(size=14, weight="bold"), fg_color=("gray75", "gray25"), text_color=("black", "white"), command=self.toggle_students_category)
        self.btn_students_cat.pack(fill="x", padx=5, pady=(5, 2))

        self.students_sub_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.students_sub_frame.pack(fill="x", padx=10, pady=2)

        ctk.CTkButton(self.students_sub_frame, text="Student Check-In", command=lambda: self.switch_frame("student_checkin")).pack(fill="x", pady=3)
        ctk.CTkButton(self.students_sub_frame, text="Student Directory", command=lambda: self.switch_frame("lookup")).pack(fill="x", pady=3)

        # EMPLOYEES CATEGORY
        self.btn_emp_cat = ctk.CTkButton(self.sidebar, text="▼ 👥 Employees Section", font=ctk.CTkFont(size=14, weight="bold"), fg_color=("gray75", "gray25"), text_color=("black", "white"), command=self.toggle_employees_category)
        self.btn_emp_cat.pack(fill="x", padx=5, pady=(15, 2))

        self.emp_sub_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.emp_sub_frame.pack(fill="x", padx=10, pady=2)

        ctk.CTkButton(self.emp_sub_frame, text="Employee Time Clock", command=lambda: self.switch_frame("emp_checkin")).pack(fill="x", pady=3)
        ctk.CTkButton(self.emp_sub_frame, text="Show All Employees", fg_color="#2980B9", hover_color="#1F618D", command=lambda: self.switch_frame("emp_directory")).pack(fill="x", pady=3)
        ctk.CTkButton(self.emp_sub_frame, text="Employee Hours & Pay", fg_color="#C0392B", hover_color="#962D22", command=lambda: self.switch_frame("emp_hours")).pack(fill="x", pady=3)

        # MAIN CONTENT AREA
        self.content_area = ctk.CTkFrame(root, fg_color="transparent")
        self.content_area.grid(row=1, column=1, sticky="nsew", padx=20, pady=20)
        self.content_area.grid_rowconfigure(0, weight=1)
        self.content_area.grid_columnconfigure(0, weight=1)

        self.frames = {}
        self.setup_student_checkin_frame()
        self.setup_emp_checkin_frame()
        self.setup_emp_directory_frame()
        self.setup_creator_frame()
        self.setup_lookup_frame()
        self.setup_emp_hours_frame()

        self.switch_frame("student_checkin")
        self.run_background_timer()

    def toggle_sidebar(self):
        if self.sidebar_expanded:
            self.sidebar.grid_remove()
            self.sidebar_expanded = False
        else:
            self.sidebar.grid()
            self.sidebar_expanded = True

    def toggle_students_category(self):
        if self.students_open:
            self.students_sub_frame.pack_forget()
            self.btn_students_cat.configure(text="▶ 🎓 Students Section")
            self.students_open = False
        else:
            self.students_sub_frame.pack(in_=self.sidebar, fill="x", padx=10, pady=2, after=self.btn_students_cat)
            self.btn_students_cat.configure(text="▼ 🎓 Students Section")
            self.students_open = True

    def toggle_employees_category(self):
        if self.employees_open:
            self.emp_sub_frame.pack_forget()
            self.btn_emp_cat.configure(text="▶ 👥 Employees Section")
            self.employees_open = False
        else:
            self.emp_sub_frame.pack(in_=self.sidebar, fill="x", padx=10, pady=2, after=self.btn_emp_cat)
            self.btn_emp_cat.configure(text="▼ 👥 Employees Section")
            self.employees_open = True

    def switch_frame(self, frame_name):
        frame = self.frames[frame_name]
        frame.tkraise()
        if frame_name == "lookup":
            self.refresh_student_directory()
        elif frame_name == "emp_directory":
            self.refresh_employee_directory()
        elif frame_name == "emp_hours":
            self.refresh_emp_hours_table()

    def run_background_timer(self):
        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M")

        if current_date != self.last_date:
            self.last_date = current_date
            self.refresh_student_directory()
            self.refresh_emp_hours_table()

        if current_time == "23:59" and has_todays_activity():
            try:
                export_to_excel()
            except Exception:
                pass

        self.root.after(60000, self.run_background_timer)

    def detect_camera_sources(self):
        sources = {}
        for i in range(3):
            cap = cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION if os.name != 'nt' else cv2.CAP_ANY)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    if i == 0:
                        name = "Built-in FaceTime HD Camera"
                    elif i == 1:
                        name = "OBS Virtual Webcam"
                    else:
                        name = f"External Camera Device {i}"
                    sources[name] = i
                cap.release()
        
        if not sources:
            sources["Built-in FaceTime HD Camera"] = 0
        return sources

    def test_camera(self, cam_name):
        idx = self.camera_sources.get(cam_name, 0)
        cap = cv2.VideoCapture(idx, cv2.CAP_AVFOUNDATION if os.name != 'nt' else cv2.CAP_ANY)
        if not cap.isOpened():
            messagebox.showerror("Camera Test Failed", f"Could not open camera: {cam_name}")
            return

        messagebox.showinfo("Camera Test", f"Testing '{cam_name}'.\nA live preview window will open. Press [Q] or [ESC] to close.")
        while True:
            ret, frame = cap.read()
            if not ret: break
            cv2.imshow(f"Testing: {cam_name} (Press Q to close)", frame)
            if (cv2.waitKey(1) & 0xFF in [ord('q'), 27]):
                break
        cap.release()
        cv2.destroyAllWindows()

    def check_for_github_updates(self):
        try:
            # Replace with your actual GitHub Username and Repository name
            url = "https://api.github.com/repos/YOUR_GITHUB_USERNAME/YOUR_REPO_NAME/releases/latest"
            
            req = urllib.request.Request(url, headers={'User-Agent': 'CheckInTerminalApp'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                latest_tag = data.get("tag_name", "").strip("v")
                release_notes = data.get("body", "No release notes provided.")
                
                exe_download_url = None
                for asset in data.get("assets", []):
                    if asset.get("name", "").endswith(".exe"):
                        exe_download_url = asset.get("browser_download_url")
                        break
                
                if latest_tag and latest_tag > CURRENT_VERSION:
                    msg = f"A new version ({latest_tag}) is available!\n\nRelease Notes:\n{release_notes}\n\nWould you like to download and update automatically?"
                    if messagebox.askyesno("Update Available", msg):
                        if exe_download_url:
                            self.download_and_apply_update(exe_download_url, latest_tag)
                        else:
                            webbrowser.open(data.get("html_url", ""))
                else:
                    messagebox.showinfo("Up to Date", f"You are running the latest version ({CURRENT_VERSION}).")
        except Exception as e:
            messagebox.showerror("Update Error", f"Could not check for updates.\n\nError: {e}")

    def download_and_apply_update(self, download_url, latest_tag):
        try:
            progress_win = ctk.CTkToplevel(self.root)
            progress_win.title("Downloading Update")
            progress_win.geometry("350x150")
            progress_win.grab_set()
            
            ctk.CTkLabel(progress_win, text=f"Downloading version {latest_tag}...", font=ctk.CTkFont(weight="bold")).pack(pady=20)
            p_bar = ctk.CTkProgressBar(progress_win, width=280)
            p_bar.pack(pady=10)
            p_bar.set(0)
            
            temp_dir = tempfile.gettempdir()
            update_exe_path = os.path.join(temp_dir, "update_temp.exe")
            
            def reporthook(blocknum, blocksize, totalsize):
                if totalsize > 0:
                    readed = blocknum * blocksize
                    percent = min(readed / totalsize, 1.0)
                    p_bar.set(percent)
                    progress_win.update_idletasks()
            
            urllib.request.urlretrieve(download_url, update_exe_path, reporthook)
            progress_win.destroy()
            
            if getattr(sys, 'frozen', False):
                current_exe = sys.executable
            else:
                messagebox.showinfo("Dev Mode", "Auto-update simulation complete! (Cannot replace running python script in development mode).")
                return
                
            batch_path = os.path.join(temp_dir, "updater.bat")
            bat_content = f"""
            @echo off
            timeout /t 2 /nobreak > nul
            del /f /q "{current_exe}"
            move /y "{update_exe_path}" "{current_exe}"
            start "" "{current_exe}"
            del "%~f0"
            """
            with open(batch_path, "w") as f:
                f.write(bat_content)
                
            if messagebox.askyesno("Ready to Restart", "Update downloaded successfully!\nThe application will now restart to apply the update."):
                subprocess.Popen([batch_path], shell=True)
                sys.exit(0)
                
        except Exception as e:
            messagebox.showerror("Update Failed", f"An error occurred during update download:\n{e}")

    def open_settings_modal(self):
        settings_win = ctk.CTkToplevel(self.root)
        settings_win.title("System Settings")
        settings_win.geometry("500x480")
        settings_win.grab_set()

        ctk.CTkLabel(settings_win, text="⚙ System Settings", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=15)

        theme_frame = ctk.CTkFrame(settings_win, fg_color="transparent")
        theme_frame.pack(fill="x", padx=30, pady=8)
        ctk.CTkLabel(theme_frame, text="Appearance Theme:").pack(side="left")
        
        theme_menu = ctk.CTkOptionMenu(theme_frame, values=["System", "Light", "Dark"], width=180)
        theme_menu.set(self.saved_theme)
        theme_menu.pack(side="right")

        cam_frame = ctk.CTkFrame(settings_win, fg_color="transparent")
        cam_frame.pack(fill="x", padx=30, pady=8)
        ctk.CTkLabel(cam_frame, text="Camera Input Source:").pack(side="left")
        
        cam_names = list(self.camera_sources.keys())
        cam_menu = ctk.CTkOptionMenu(cam_frame, values=cam_names, width=180)
        cam_menu.set(self.selected_camera_name)
        cam_menu.pack(side="right")

        test_btn = ctk.CTkButton(settings_win, text="🎥 Test Selected Camera", fg_color="#D35400", hover_color="#BA4A00", command=lambda: self.test_camera(cam_menu.get()))
        test_btn.pack(pady=8)

        update_btn = ctk.CTkButton(settings_win, text="🔄 Check for Software Updates", fg_color="#2980B9", hover_color="#1F618D", command=self.check_for_github_updates)
        update_btn.pack(pady=8)

        def save_settings():
            self.saved_theme = theme_menu.get()
            self.selected_camera_name = cam_menu.get()
            ctk.set_appearance_mode(self.saved_theme)
            messagebox.showinfo("Settings Saved", "System settings successfully updated!")
            settings_win.destroy()

        save_btn = ctk.CTkButton(settings_win, text="💾 Save Settings", fg_color="#27AE60", hover_color="#1E8449", height=38, command=save_settings)
        save_btn.pack(pady=15)

    def setup_student_checkin_frame(self):
        f = ctk.CTkFrame(self.content_area, fg_color="transparent")
        f.grid(row=0, column=0, sticky="nsew")
        self.frames["student_checkin"] = f

        card = ctk.CTkFrame(f, corner_radius=15)
        card.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(card, text="🎓 Student Check-In / Check-Out Portal", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(30, 15))

        self.s_entry = ctk.CTkEntry(card, placeholder_text="Tap student badge here...", font=ctk.CTkFont(size=16), width=320, height=45, justify="center")
        self.s_entry.pack(pady=10)
        self.s_entry.focus_set()
        self.s_entry.bind("<Return>", self.process_student_tap)

        info_card = ctk.CTkFrame(card, fg_color=("gray90", "gray20"), corner_radius=10)
        info_card.pack(fill="both", expand=True, padx=40, pady=20)

        self.s_photo_lbl = ctk.CTkLabel(info_card, text="No Photo", width=160, height=180, fg_color="gray", corner_radius=8)
        self.s_photo_lbl.pack(side="left", padx=25, pady=25)

        self.s_info_lbl = ctk.CTkLabel(info_card, text="Ready for student check-ins / outs...", font=ctk.CTkFont(size=15), justify="left")
        self.s_info_lbl.pack(side="left", fill="both", expand=True, padx=20, pady=25)

        f.bind("<Button-1>", lambda e: self.s_entry.focus_set())

    def process_student_tap(self, event):
        nfc_id = self.s_entry.get().strip()
        self.s_entry.delete(0, ctk.END)
        if not nfc_id: return

        data = log_student_checkin(nfc_id)
        if data:
            action_color = "#2ECC71" if data['action'] == "Check In" else "#E67E22"
            text = f"✔ STUDENT {data['action'].upper()} SUCCESSFUL\n\nName: {data['name']}\nTime: {data['timestamp']}\n\n" \
                   f"🚨 Emergency Contact: {data['em_name']} ({data['em_rel']}) - {data['em_phone']} | {data['em_email']}\n" \
                   f"⚠️ Allergies: {data['allergies']}"
            self.s_info_lbl.configure(text=text, text_color=action_color)
            
            if data['photo'] and os.path.exists(data['photo']):
                img = Image.open(data['photo']).resize((160, 180))
                p_img = ctk.CTkImage(light_image=img, dark_image=img, size=(160, 180))
                self.s_photo_lbl.configure(image=p_img, text="")
                self.s_photo_lbl.image = p_img
            else:
                self.s_photo_lbl.configure(image=None, text="No Photo")
        else:
            self.s_info_lbl.configure(text=f"✖ Unknown NFC ID: '{nfc_id}'\nPlease register this card in 'Create Profile (NFC)'.", text_color="#E74C3C")
            self.s_photo_lbl.configure(image=None, text="No Photo")

        self.s_entry.focus_set()

    def setup_emp_checkin_frame(self):
        f = ctk.CTkFrame(self.content_area, fg_color="transparent")
        f.grid(row=0, column=0, sticky="nsew")
        self.frames["emp_checkin"] = f

        card = ctk.CTkFrame(f, corner_radius=15)
        card.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(card, text="⏰ Employee Time Clock Terminal", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(30, 15))

        self.e_entry = ctk.CTkEntry(card, placeholder_text="Tap employee badge here...", font=ctk.CTkFont(size=16), width=320, height=45, justify="center")
        self.e_entry.pack(pady=10)
        self.e_entry.bind("<Return>", self.process_emp_tap)

        info_card = ctk.CTkFrame(card, fg_color=("gray90", "gray20"), corner_radius=10)
        info_card.pack(fill="both", expand=True, padx=40, pady=20)

        self.e_photo_lbl = ctk.CTkLabel(info_card, text="No Photo", width=160, height=180, fg_color="gray", corner_radius=8)
        self.e_photo_lbl.pack(side="left", padx=25, pady=25)

        self.e_info_lbl = ctk.CTkLabel(info_card, text="Ready for employee clock-ins / outs...", font=ctk.CTkFont(size=16), justify="left")
        self.e_info_lbl.pack(side="left", fill="both", expand=True, padx=20, pady=25)

        f.bind("<Button-1>", lambda e: self.e_entry.focus_set())

    def process_emp_tap(self, event):
        nfc_id = self.e_entry.get().strip()
        self.e_entry.delete(0, ctk.END)
        if not nfc_id: return

        name, action, timestamp, photo_path = log_employee_clock(nfc_id)
        if name:
            color = "#2ECC71" if action == "Clock In" else "#E67E22"
            self.e_info_lbl.configure(text=f"✔ EMPLOYEE {action.upper()}\n\nName: {name}\nTimestamp: {timestamp}", text_color=color)
            
            if photo_path and os.path.exists(photo_path):
                img = Image.open(photo_path).resize((160, 180))
                p_img = ctk.CTkImage(light_image=img, dark_image=img, size=(160, 180))
                self.e_photo_lbl.configure(image=p_img, text="")
                self.e_photo_lbl.image = p_img
            else:
                self.e_photo_lbl.configure(image=None, text="No Photo")
        else:
            self.e_info_lbl.configure(text=f"✖ Unknown Employee NFC ID: '{nfc_id}'", text_color="#E74C3C")
            self.e_photo_lbl.configure(image=None, text="No Photo")

        self.e_entry.focus_set()

    def setup_emp_directory_frame(self):
        f = ctk.CTkFrame(self.content_area, fg_color="transparent")
        f.grid(row=0, column=0, sticky="nsew")
        self.frames["emp_directory"] = f

        card = ctk.CTkFrame(f, corner_radius=15)
        card.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(card, text="👥 All Registered Employees (Double-click row to edit profile)", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=15)

        table_frame = ctk.CTkFrame(card)
        table_frame.pack(fill="both", expand=True, padx=20, pady=15)

        columns = ("NFC UID", "Employee Name", "Photo Status")
        self.emp_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        for col in columns:
            self.emp_tree.heading(col, text=col)
            self.emp_tree.column(col, width=220, anchor="center")
        
        self.emp_tree.pack(side="left", fill="both", expand=True)
        self.emp_tree.bind("<Double-1>", self.open_employee_profile_editor)
        
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.emp_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.emp_tree.configure(yscrollcommand=scrollbar.set)

        btn_refresh = ctk.CTkButton(card, text="Refresh Employee List", command=self.refresh_employee_directory)
        btn_refresh.pack(pady=10)

        self.refresh_employee_directory()

    def refresh_employee_directory(self):
        for row in self.emp_tree.get_children():
            self.emp_tree.delete(row)
        for nfc_id, name, photo_path in get_all_employees():
            clean_nfc = str(nfc_id).strip()
            photo_status = "Has Photo" if photo_path and os.path.exists(photo_path) else "No Photo"
            self.emp_tree.insert("", ctk.END, values=(clean_nfc, name, photo_status), tags=(clean_nfc,))

    def open_employee_profile_editor(self, event):
        item_id = self.emp_tree.identify_row(event.y)
        if not item_id or item_id == "":
            item_id = self.emp_tree.focus()
        if not item_id:
            selected = self.emp_tree.selection()
            if selected:
                item_id = selected[0]
        if not item_id:
            return
            
        item = self.emp_tree.item(item_id)
        tags = item.get('tags', ())
        if tags:
            nfc_id = str(tags[0]).strip()
        else:
            values = item.get('values', [])
            if not values: return
            nfc_id = str(values[0]).strip()

        row = get_employee_full_profile(nfc_id)
        if not row: return

        edit_win = ctk.CTkToplevel(self.root)
        edit_win.title(f"Employee Profile: {row[1]}")
        edit_win.geometry("450x520")
        edit_win.grab_set()

        ctk.CTkLabel(edit_win, text=f"Edit Employee: {row[1]}", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=15)

        photo_lbl = ctk.CTkLabel(edit_win, text="No Photo", width=120, height=140, fg_color="gray", corner_radius=6)
        photo_lbl.pack(pady=5)
        if row[2] and os.path.exists(row[2]):
            img = Image.open(row[2]).resize((120, 140))
            p_img = ctk.CTkImage(light_image=img, dark_image=img, size=(120, 140))
            photo_lbl.configure(image=p_img, text="")
            photo_lbl.image = p_img

        form = ctk.CTkFrame(edit_win, fg_color="transparent")
        form.pack(pady=10)

        ctk.CTkLabel(form, text="Full Name:").grid(row=0, column=0, sticky="w", padx=10, pady=8)
        name_ent = ctk.CTkEntry(form, width=220)
        name_ent.insert(0, row[1])
        name_ent.grid(row=0, column=1, padx=10, pady=8)

        current_photo = [row[2]]

        def change_photo():
            idx = self.camera_sources.get(self.selected_camera_name, 0)
            cap = cv2.VideoCapture(idx, cv2.CAP_AVFOUNDATION if os.name != 'nt' else cv2.CAP_ANY)
            if not cap.isOpened(): return
            while True:
                ret, frame = cap.read()
                if not ret: break
                cv2.imshow("Take New Photo - Press SPACE", frame)
                if (cv2.waitKey(1) & 0xFF) == 32:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    p = f"employee_photos/emp_{ts}.jpg"
                    cv2.imwrite(p, frame)
                    current_photo[0] = p
                    break
            cap.release()
            cv2.destroyAllWindows()
            img = Image.open(current_photo[0]).resize((120, 140))
            p_img = ctk.CTkImage(light_image=img, dark_image=img, size=(120, 140))
            photo_lbl.configure(image=p_img, text="")
            photo_lbl.image = p_img
            messagebox.showinfo("Success", "New photo captured successfully!")

        ctk.CTkButton(edit_win, text="📷 Retake Photo", fg_color="#D35400", command=change_photo).pack(pady=5)

        def save_changes():
            new_name = name_ent.get().strip()
            if new_name:
                register_employee_profile(row[0], new_name, current_photo[0])
                messagebox.showinfo("Success", "Employee profile updated successfully!")
                edit_win.destroy()
                self.refresh_employee_directory()

        def delete_profile():
            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete employee '{row[1]}' from the system?"):
                delete_employee_profile(row[0])
                messagebox.showinfo("Deleted", "Employee profile deleted successfully.")
                edit_win.destroy()
                self.refresh_employee_directory()

        ctk.CTkButton(edit_win, text="Save Changes", fg_color="#27AE60", command=save_changes).pack(pady=8)
        ctk.CTkButton(edit_win, text="🗑 Delete Employee Profile", fg_color="#C0392B", hover_color="#962D22", command=delete_profile).pack(pady=5)

    def setup_creator_frame(self):
        f = ctk.CTkFrame(self.content_area, fg_color="transparent")
        f.grid(row=0, column=0, sticky="nsew")
        self.frames["creator"] = f

        scroll_container = ctk.CTkScrollableFrame(f, corner_radius=15)
        scroll_container.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(scroll_container, text="Create NFC Profile & Badge Assignment", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=20)

        form = ctk.CTkFrame(scroll_container, fg_color="transparent")
        form.pack(pady=10)

        ctk.CTkLabel(form, text="Profile Role Type:", font=ctk.CTkFont(size=14)).grid(row=0, column=0, sticky="w", padx=10, pady=8)
        self.c_role_menu = ctk.CTkOptionMenu(form, values=["Student", "Employee"], command=self.toggle_creator_role, width=280)
        self.c_role_menu.grid(row=0, column=1, padx=10, pady=8)

        ctk.CTkLabel(form, text="NFC Tag UID:", font=ctk.CTkFont(size=14)).grid(row=1, column=0, sticky="w", padx=10, pady=8)
        self.c_nfc_ent = ctk.CTkEntry(form, placeholder_text="Tap card or enter UID...", width=280)
        self.c_nfc_ent.grid(row=1, column=1, padx=10, pady=8)

        ctk.CTkLabel(form, text="Full Name:", font=ctk.CTkFont(size=14)).grid(row=2, column=0, sticky="w", padx=10, pady=8)
        self.c_name_ent = ctk.CTkEntry(form, width=280)
        self.c_name_ent.grid(row=2, column=1, padx=10, pady=8)

        ctk.CTkLabel(form, text="Birthday (MM/DD/YYYY):", font=ctk.CTkFont(size=14)).grid(row=3, column=0, sticky="w", padx=10, pady=8)
        self.c_bday_ent = ctk.CTkEntry(form, width=280)
        self.c_bday_ent.grid(row=3, column=1, padx=10, pady=8)

        self.student_extra_frame = ctk.CTkFrame(form, fg_color="transparent")
        self.student_extra_frame.grid(row=4, column=0, columnspan=2, sticky="ew")

        ctk.CTkLabel(self.student_extra_frame, text="Known Allergies:").grid(row=0, column=0, sticky="w", padx=10, pady=8)
        self.c_allergies_ent = ctk.CTkEntry(self.student_extra_frame, width=280)
        self.c_allergies_ent.grid(row=0, column=1, padx=10, pady=8)

        ctk.CTkLabel(self.student_extra_frame, text="Emergency Contact Name:").grid(row=1, column=0, sticky="w", padx=10, pady=8)
        self.c_em_name_ent = ctk.CTkEntry(self.student_extra_frame, width=280)
        self.c_em_name_ent.grid(row=1, column=1, padx=10, pady=8)

        ctk.CTkLabel(self.student_extra_frame, text="Relationship to Student:").grid(row=2, column=0, sticky="w", padx=10, pady=8)
        self.c_em_rel_ent = ctk.CTkEntry(self.student_extra_frame, width=280)
        self.c_em_rel_ent.grid(row=2, column=1, padx=10, pady=8)

        ctk.CTkLabel(self.student_extra_frame, text="Emergency Phone Number:").grid(row=3, column=0, sticky="w", padx=10, pady=8)
        self.c_em_phone_ent = ctk.CTkEntry(self.student_extra_frame, width=280)
        self.c_em_phone_ent.grid(row=3, column=1, padx=10, pady=8)

        ctk.CTkLabel(self.student_extra_frame, text="Emergency Email Address:").grid(row=4, column=0, sticky="w", padx=10, pady=8)
        self.c_em_email_ent = ctk.CTkEntry(self.student_extra_frame, width=280)
        self.c_em_email_ent.grid(row=4, column=1, padx=10, pady=8)

        ctk.CTkLabel(self.student_extra_frame, text="Emergency Address:").grid(row=5, column=0, sticky="w", padx=10, pady=8)
        self.c_em_addr_ent = ctk.CTkEntry(self.student_extra_frame, width=280)
        self.c_em_addr_ent.grid(row=5, column=1, padx=10, pady=8)

        cam_btn = ctk.CTkButton(scroll_container, text="📷 Take Profile Photo via Webcam", fg_color="#D35400", hover_color="#BA4A00", command=self.capture_profile_photo)
        cam_btn.pack(pady=15)

        self.c_photo_status = ctk.CTkLabel(scroll_container, text="No photo attached yet", text_color="gray")
        self.c_photo_status.pack(pady=5)

        save_btn = ctk.CTkButton(scroll_container, text="Save Profile to Database", font=ctk.CTkFont(size=15, weight="bold"), height=42, width=240, command=self.save_new_profile)
        save_btn.pack(pady=25)

    def toggle_creator_role(self, choice):
        if choice == "Employee":
            self.student_extra_frame.grid_remove()
        else:
            self.student_extra_frame.grid()

    def capture_profile_photo(self):
        idx = self.camera_sources.get(self.selected_camera_name, 0)
        cap = cv2.VideoCapture(idx, cv2.CAP_AVFOUNDATION if os.name != 'nt' else cv2.CAP_ANY)
        if not cap.isOpened():
            messagebox.showerror("Camera Error", f"Could not access camera: {self.selected_camera_name}")
            return

        messagebox.showinfo("Camera Ready", f"Using: {self.selected_camera_name}\nPress [SPACEBAR] to snap photo, or [ESC] to cancel.")
        saved_path = None
        
        while True:
            ret, frame = cap.read()
            if not ret: break
            cv2.imshow(f"Capture Photo ({self.selected_camera_name}) - Press SPACE", frame)
            if (cv2.waitKey(1) & 0xFF) == 32:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                saved_path = f"student_photos/profile_{ts}.jpg"
                cv2.imwrite(saved_path, frame)
                break
            elif (cv2.waitKey(1) & 0xFF) == 27:
                break
        cap.release()
        cv2.destroyAllWindows()

        if saved_path and os.path.exists(saved_path):
            self.temp_photo_path = saved_path
            self.c_photo_status.configure(text=f"✔ Photo attached successfully!", text_color="#2ECC71")

    def save_new_profile(self):
        role = self.c_role_menu.get()
        nfc = self.c_nfc_ent.get().strip()
        name = self.c_name_ent.get().strip()
        birthday = self.c_bday_ent.get().strip()
        photo = self.temp_photo_path or ""

        if not nfc or not name:
            messagebox.showerror("Validation Error", "NFC UID and Full Name are required.")
            return

        if role == "Student":
            em_name = self.c_em_name_ent.get().strip()
            em_rel = self.c_em_rel_ent.get().strip()
            em_phone = self.c_em_phone_ent.get().strip()
            em_email = self.c_em_email_ent.get().strip()
            em_addr = self.c_em_addr_ent.get().strip()
            allergies = self.c_allergies_ent.get().strip()

            register_student_profile(nfc, name, birthday, em_name, em_rel, em_phone, em_email, em_addr, allergies, photo)
            messagebox.showinfo("Success", f"Student profile for '{name}' successfully saved!")
            self.clear_creator_form()
        else:
            register_employee_profile(nfc, name, photo)
            messagebox.showinfo("Success", f"Employee profile for '{name}' successfully saved!")
            self.clear_creator_form()

    def clear_creator_form(self):
        self.c_nfc_ent.delete(0, ctk.END)
        self.c_name_ent.delete(0, ctk.END)
        self.c_bday_ent.delete(0, ctk.END)
        self.c_em_name_ent.delete(0, ctk.END)
        self.c_em_rel_ent.delete(0, ctk.END)
        self.c_em_phone_ent.delete(0, ctk.END)
        self.c_em_email_ent.delete(0, ctk.END)
        self.c_em_addr_ent.delete(0, ctk.END)
        self.c_allergies_ent.delete(0, ctk.END)
        self.temp_photo_path = None
        self.c_photo_status.configure(text="No photo attached yet")

    def setup_lookup_frame(self):
        f = ctk.CTkFrame(self.content_area, fg_color="transparent")
        f.grid(row=0, column=0, sticky="nsew")
        self.frames["lookup"] = f

        card = ctk.CTkFrame(f, corner_radius=15)
        card.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(card, text="Saved Student Directory & Today's Status (Double-click row to edit profile)", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=15)

        search_bar = ctk.CTkFrame(card, fg_color="transparent")
        search_bar.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(search_bar, text="Search Name or UID:").pack(side="left", padx=5)
        self.search_ent = ctk.CTkEntry(search_bar, placeholder_text="Type name or UID...", width=250)
        self.search_ent.pack(side="left", padx=5)
        self.search_ent.bind("<Return>", lambda e: self.perform_search())

        btn_search = ctk.CTkButton(search_bar, text="Search", command=self.perform_search, width=100)
        btn_search.pack(side="left", padx=5)

        btn_show_all = ctk.CTkButton(search_bar, text="Show All", command=self.refresh_student_directory, width=100)
        btn_show_all.pack(side="right", padx=5)

        table_frame = ctk.CTkFrame(card)
        table_frame.pack(fill="both", expand=True, padx=20, pady=15)

        columns = ("NFC ID", "Name", "Birthday", "Check-In", "Check-Out", "Emergency Contact", "Phone", "Allergies")
        self.lookup_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        for col in columns:
            self.lookup_tree.heading(col, text=col)
            self.lookup_tree.column(col, width=120, anchor="center")
        
        self.lookup_tree.pack(side="left", fill="both", expand=True)
        self.lookup_tree.bind("<Double-1>", self.open_student_profile_editor)
        
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.lookup_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.lookup_tree.configure(yscrollcommand=scrollbar.set)

        self.refresh_student_directory()

    def refresh_student_directory(self):
        for row in self.lookup_tree.get_children():
            self.lookup_tree.delete(row)
        for row in get_students_with_todays_activity():
            clean_nfc = str(row[0]).strip()
            formatted_row = (clean_nfc,) + row[1:]
            self.lookup_tree.insert("", ctk.END, values=formatted_row, tags=(clean_nfc,))

    def perform_search(self):
        query = self.search_ent.get().strip()
        for row in self.lookup_tree.get_children():
            self.lookup_tree.delete(row)
            
        rows = search_students_with_activity(query) if query else get_students_with_todays_activity()
        for row in rows:
            clean_nfc = str(row[0]).strip()
            formatted_row = (clean_nfc,) + row[1:]
            self.lookup_tree.insert("", ctk.END, values=formatted_row, tags=(clean_nfc,))

    def open_student_profile_editor(self, event):
        item_id = self.lookup_tree.identify_row(event.y)
        if not item_id or item_id == "":
            item_id = self.lookup_tree.focus()
        if not item_id:
            selected = self.lookup_tree.selection()
            if selected:
                item_id = selected[0]
        if not item_id:
            return

        item = self.lookup_tree.item(item_id)
        tags = item.get('tags', ())
        if tags:
            nfc_id = str(tags[0]).strip()
        else:
            values = item.get('values', [])
            if not values: return
            nfc_id = str(values[0]).strip()

        row = get_student_full_profile(nfc_id)
        if not row: return

        edit_win = ctk.CTkToplevel(self.root)
        edit_win.title(f"Student Profile: {row[1]}")
        edit_win.geometry("500x750")
        edit_win.grab_set()

        scroll_c = ctk.CTkScrollableFrame(edit_win, corner_radius=10)
        scroll_c.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(scroll_c, text=f"Edit Student Profile: {row[1]}", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)

        student_photo_lbl = ctk.CTkLabel(scroll_c, text="No Photo", width=120, height=140, fg_color="gray", corner_radius=6)
        student_photo_lbl.pack(pady=5)
        if row[9] and os.path.exists(row[9]):
            img = Image.open(row[9]).resize((120, 140))
            p_img = ctk.CTkImage(light_image=img, dark_image=img, size=(120, 140))
            student_photo_lbl.configure(image=p_img, text="")
            student_photo_lbl.image = p_img

        form = ctk.CTkFrame(scroll_c, fg_color="transparent")
        form.pack(pady=5)

        ctk.CTkLabel(form, text="NFC UID (Locked):").grid(row=0, column=0, sticky="w", padx=10, pady=6)
        ctk.CTkLabel(form, text=row[0], font=ctk.CTkFont(weight="bold")).grid(row=0, column=1, sticky="w", padx=10, pady=6)

        ctk.CTkLabel(form, text="Full Name:").grid(row=1, column=0, sticky="w", padx=10, pady=6)
        name_ent = ctk.CTkEntry(form, width=240)
        name_ent.insert(0, row[1])
        name_ent.grid(row=1, column=1, padx=10, pady=6)

        ctk.CTkLabel(form, text="Birthday:").grid(row=2, column=0, sticky="w", padx=10, pady=6)
        bday_ent = ctk.CTkEntry(form, width=240)
        bday_ent.insert(0, row[2] or "")
        bday_ent.grid(row=2, column=1, padx=10, pady=6)

        ctk.CTkLabel(form, text="Emergency Contact:").grid(row=3, column=0, sticky="w", padx=10, pady=6)
        em_name_ent = ctk.CTkEntry(form, width=240)
        em_name_ent.insert(0, row[3] or "")
        em_name_ent.grid(row=3, column=1, padx=10, pady=6)

        ctk.CTkLabel(form, text="Relationship:").grid(row=4, column=0, sticky="w", padx=10, pady=6)
        em_rel_ent = ctk.CTkEntry(form, width=240)
        em_rel_ent.insert(0, row[4] or "")
        em_rel_ent.grid(row=4, column=1, padx=10, pady=6)

        ctk.CTkLabel(form, text="Phone:").grid(row=5, column=0, sticky="w", padx=10, pady=6)
        em_phone_ent = ctk.CTkEntry(form, width=240)
        em_phone_ent.insert(0, row[5] or "")
        em_phone_ent.grid(row=5, column=1, padx=10, pady=6)

        ctk.CTkLabel(form, text="Email:").grid(row=6, column=0, sticky="w", padx=10, pady=6)
        em_email_ent = ctk.CTkEntry(form, width=240)
        em_email_ent.insert(0, row[6] or "")
        em_email_ent.grid(row=6, column=1, padx=10, pady=6)

        ctk.CTkLabel(form, text="Address:").grid(row=7, column=0, sticky="w", padx=10, pady=6)
        em_addr_ent = ctk.CTkEntry(form, width=240)
        em_addr_ent.insert(0, row[7] or "")
        em_addr_ent.grid(row=7, column=1, padx=10, pady=6)

        ctk.CTkLabel(form, text="Allergies:").grid(row=8, column=0, sticky="w", padx=10, pady=6)
        allergies_ent = ctk.CTkEntry(form, width=240)
        allergies_ent.insert(0, row[8] or "")
        allergies_ent.grid(row=8, column=1, padx=10, pady=6)

        current_photo = [row[9]]

        def retake_photo():
            idx = self.camera_sources.get(self.selected_camera_name, 0)
            cap = cv2.VideoCapture(idx, cv2.CAP_AVFOUNDATION if os.name != 'nt' else cv2.CAP_ANY)
            if not cap.isOpened(): return
            while True:
                ret, frame = cap.read()
                if not ret: break
                cv2.imshow("Retake Photo - Press SPACE", frame)
                if (cv2.waitKey(1) & 0xFF) == 32:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    p = f"student_photos/profile_{ts}.jpg"
                    cv2.imwrite(p, frame)
                    current_photo[0] = p
                    break
            cap.release()
            cv2.destroyAllWindows()
            img = Image.open(current_photo[0]).resize((120, 140))
            p_img = ctk.CTkImage(light_image=img, dark_image=img, size=(120, 140))
            student_photo_lbl.configure(image=p_img, text="")
            student_photo_lbl.image = p_img
            messagebox.showinfo("Success", "New photo captured successfully!")

        ctk.CTkButton(scroll_c, text="📷 Retake Student Photo", fg_color="#D35400", command=retake_photo).pack(pady=8)

        def save_student_edits():
            register_student_profile(
                row[0], name_ent.get().strip(), bday_ent.get().strip(),
                em_name_ent.get().strip(), em_rel_ent.get().strip(), em_phone_ent.get().strip(),
                em_email_ent.get().strip(), em_addr_ent.get().strip(), allergies_ent.get().strip(), current_photo[0]
            )
            messagebox.showinfo("Success", "Student profile updated successfully!")
            edit_win.destroy()
            self.refresh_student_directory()

        def delete_student():
            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete student '{row[1]}' from the system?"):
                delete_student_profile(row[0])
                messagebox.showinfo("Deleted", "Student profile deleted successfully.")
                edit_win.destroy()
                self.refresh_student_directory()

        ctk.CTkButton(scroll_c, text="Save Profile Changes", fg_color="#27AE60", height=38, width=200, command=save_student_edits).pack(pady=8)
        ctk.CTkButton(scroll_c, text="🗑 Delete Student Profile", fg_color="#C0392B", hover_color="#962D22", height=38, width=200, command=delete_student).pack(pady=5)

    def setup_emp_hours_frame(self):
        f = ctk.CTkFrame(self.content_area, fg_color="transparent")
        f.grid(row=0, column=0, sticky="nsew")
        self.frames["emp_hours"] = f

        card = ctk.CTkFrame(f, corner_radius=15)
        card.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(card, text="Employee Hours & Timesheet Calculator", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=15)

        top_bar = ctk.CTkFrame(card, fg_color="transparent")
        top_bar.pack(fill="x", padx=20, pady=5)

        btn_refresh = ctk.CTkButton(top_bar, text="🔄 Refresh Hours", command=self.refresh_emp_hours_table, width=140)
        btn_refresh.pack(side="left", padx=5)

        btn_excel = ctk.CTkButton(top_bar, text="📊 Export Employee Hours to Excel", fg_color="#2E7D32", hover_color="#1B5E20", command=self.export_emp_excel, width=220)
        btn_excel.pack(side="right", padx=5)

        table_frame = ctk.CTkFrame(card)
        table_frame.pack(fill="both", expand=True, padx=20, pady=15)

        columns = ("Employee Name", "NFC ID", "Hours Today", "Hours This Week")
        self.emp_hours_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        for col in columns:
            self.emp_hours_tree.heading(col, text=col)
            self.emp_hours_tree.column(col, width=180, anchor="center")
        
        self.emp_hours_tree.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.emp_hours_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.emp_hours_tree.configure(yscrollcommand=scrollbar.set)

        self.refresh_emp_hours_table()

    def refresh_emp_hours_table(self):
        for row in self.emp_hours_tree.get_children():
            self.emp_hours_tree.delete(row)
        for row in get_employee_hours_report():
            self.emp_hours_tree.insert("", ctk.END, values=row)

    def export_emp_excel(self):
        try:
            filename = export_employee_hours_to_excel()
            messagebox.showinfo("Export Successful", f"Employee hours report exported to:\n{filename}")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))

if __name__ == "__main__":
    root = ctk.CTk()
    app = CheckInApp(root)
    root.mainloop()