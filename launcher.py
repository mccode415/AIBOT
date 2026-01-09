# AIBOT Launcher with Dark Mode Support
# GUI interface for controlling the AI Game Bot

import os
import json
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading

CONFIG_FILE = "config.json"

# Theme definitions
THEMES = {
    "light": {
        "bg": "#f0f0f0",
        "fg": "#000000",
        "button_bg": "#e0e0e0",
        "button_fg": "#000000",
        "accent": "#0078d4",
        "frame_bg": "#ffffff",
        "status_bg": "#e8e8e8"
    },
    "dark": {
        "bg": "#1e1e1e",
        "fg": "#ffffff",
        "button_bg": "#3c3c3c",
        "button_fg": "#ffffff",
        "accent": "#0078d4",
        "frame_bg": "#2d2d2d",
        "status_bg": "#252525"
    }
}


class AIBotLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AIBOT - Game AI Launcher")
        self.root.geometry("500x400")
        self.root.resizable(False, False)

        # Load saved configuration
        self.config = self.load_config()
        self.dark_mode = tk.BooleanVar(value=self.config.get("dark_mode", False))

        self.setup_ui()
        self.apply_theme()

    def load_config(self):
        """Load configuration from file."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"dark_mode": False}

    def save_config(self):
        """Save configuration to file."""
        self.config["dark_mode"] = self.dark_mode.get()
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
        except IOError as e:
            print(f"Error saving config: {e}")

    def setup_ui(self):
        """Set up the user interface."""
        # Main container
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title
        self.title_label = tk.Label(
            self.main_frame,
            text="AIBOT Game AI",
            font=("Helvetica", 24, "bold")
        )
        self.title_label.pack(pady=(0, 10))

        # Subtitle
        self.subtitle_label = tk.Label(
            self.main_frame,
            text="Machine Learning Game Automation",
            font=("Helvetica", 10)
        )
        self.subtitle_label.pack(pady=(0, 20))

        # Dark mode toggle frame
        self.toggle_frame = tk.Frame(self.main_frame)
        self.toggle_frame.pack(fill=tk.X, pady=10)

        self.theme_label = tk.Label(
            self.toggle_frame,
            text="Dark Mode:",
            font=("Helvetica", 11)
        )
        self.theme_label.pack(side=tk.LEFT)

        self.dark_mode_toggle = tk.Checkbutton(
            self.toggle_frame,
            variable=self.dark_mode,
            command=self.toggle_dark_mode,
            text="",
            font=("Helvetica", 11)
        )
        self.dark_mode_toggle.pack(side=tk.LEFT, padx=5)

        self.theme_status = tk.Label(
            self.toggle_frame,
            text="ON" if self.dark_mode.get() else "OFF",
            font=("Helvetica", 11, "bold")
        )
        self.theme_status.pack(side=tk.LEFT)

        # Separator
        self.separator = tk.Frame(self.main_frame, height=2)
        self.separator.pack(fill=tk.X, pady=15)

        # Buttons frame
        self.buttons_frame = tk.Frame(self.main_frame)
        self.buttons_frame.pack(fill=tk.X, pady=10)

        # Action buttons
        self.collect_btn = tk.Button(
            self.buttons_frame,
            text="Collect Training Data",
            font=("Helvetica", 12),
            command=self.run_collect_data,
            height=2,
            cursor="hand2"
        )
        self.collect_btn.pack(fill=tk.X, pady=5)

        self.train_btn = tk.Button(
            self.buttons_frame,
            text="Train Model",
            font=("Helvetica", 12),
            command=self.run_training,
            height=2,
            cursor="hand2"
        )
        self.train_btn.pack(fill=tk.X, pady=5)

        self.run_btn = tk.Button(
            self.buttons_frame,
            text="Run AI",
            font=("Helvetica", 12),
            command=self.run_ai,
            height=2,
            cursor="hand2"
        )
        self.run_btn.pack(fill=tk.X, pady=5)

        # Status bar
        self.status_frame = tk.Frame(self.main_frame)
        self.status_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(20, 0))

        self.status_label = tk.Label(
            self.status_frame,
            text="Ready",
            font=("Helvetica", 10),
            anchor=tk.W
        )
        self.status_label.pack(fill=tk.X, padx=10, pady=5)

    def toggle_dark_mode(self):
        """Toggle between light and dark mode."""
        self.theme_status.config(text="ON" if self.dark_mode.get() else "OFF")
        self.apply_theme()
        self.save_config()

    def apply_theme(self):
        """Apply the current theme to all widgets."""
        theme_name = "dark" if self.dark_mode.get() else "light"
        theme = THEMES[theme_name]

        # Apply to root
        self.root.configure(bg=theme["bg"])

        # Apply to main frame
        self.main_frame.configure(bg=theme["bg"])

        # Apply to labels
        for widget in [self.title_label, self.subtitle_label, self.theme_label, self.theme_status]:
            widget.configure(bg=theme["bg"], fg=theme["fg"])

        # Apply to toggle frame
        self.toggle_frame.configure(bg=theme["bg"])

        # Apply to dark mode checkbox
        self.dark_mode_toggle.configure(
            bg=theme["bg"],
            fg=theme["fg"],
            activebackground=theme["bg"],
            activeforeground=theme["fg"],
            selectcolor=theme["button_bg"]
        )

        # Apply to separator
        self.separator.configure(bg=theme["accent"])

        # Apply to buttons frame
        self.buttons_frame.configure(bg=theme["bg"])

        # Apply to buttons
        for btn in [self.collect_btn, self.train_btn, self.run_btn]:
            btn.configure(
                bg=theme["button_bg"],
                fg=theme["button_fg"],
                activebackground=theme["accent"],
                activeforeground="#ffffff"
            )

        # Apply to status bar
        self.status_frame.configure(bg=theme["status_bg"])
        self.status_label.configure(bg=theme["status_bg"], fg=theme["fg"])

    def update_status(self, message):
        """Update the status bar message."""
        self.status_label.config(text=message)
        self.root.update()

    def run_script(self, script_name, description):
        """Run a Python script in a separate thread."""
        def execute():
            self.update_status(f"Running {description}...")
            try:
                result = subprocess.run(
                    ["python", script_name],
                    capture_output=True,
                    text=True,
                    cwd=os.path.dirname(os.path.abspath(__file__))
                )
                if result.returncode == 0:
                    self.update_status(f"{description} completed successfully")
                else:
                    self.update_status(f"Error: {result.stderr[:50]}...")
                    messagebox.showerror("Error", f"{description} failed:\n{result.stderr}")
            except Exception as e:
                self.update_status(f"Error: {str(e)[:50]}...")
                messagebox.showerror("Error", f"Failed to run {script_name}:\n{str(e)}")

        thread = threading.Thread(target=execute)
        thread.daemon = True
        thread.start()

    def run_collect_data(self):
        """Start data collection."""
        self.run_script("create_dataset.py", "Data Collection")

    def run_training(self):
        """Start model training."""
        self.run_script("train.py", "Model Training")

    def run_ai(self):
        """Start the AI."""
        self.run_script("ai.py", "AI Bot")

    def run(self):
        """Start the application."""
        self.root.mainloop()


def main():
    app = AIBotLauncher()
    app.run()


if __name__ == "__main__":
    main()
