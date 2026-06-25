"""Desktop GUI for MLS Photo Processor."""
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from pathlib import Path
import logging
import threading


class MLSPhotoProcessorGUI:
    """Desktop GUI application for processing MLS photos."""

    def __init__(
        self,
        title_admin_processor,
        appraiser_processor,
        parcel_matcher,
        classifier,
        appraiser_classifier,
        gps_resolver,
    ):
        self.title_admin_processor = title_admin_processor
        self.appraiser_processor = appraiser_processor
        self.parcel_matcher = parcel_matcher
        self.classifier = classifier
        self.appraiser_classifier = appraiser_classifier
        self.gps_resolver = gps_resolver

        self.root = tk.Tk()
        self.root.title("MLS Photo Processor")
        self.root.geometry("620x580")
        self.root.resizable(True, True)

        self.selected_folder = None
        self.selected_role = tk.StringVar(value="")

        self._create_widgets()
        self._setup_logging()
        self._update_process_button()

    def _create_widgets(self):
        main_frame = tk.Frame(self.root, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        tk.Label(
            main_frame,
            text="MLS Photo Processor",
            font=("Arial", 16, "bold")
        ).pack(pady=(0, 16))

        # --- Role selector ---
        role_frame = tk.LabelFrame(main_frame, text="Select Your Role", padx=10, pady=10)
        role_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Radiobutton(
            role_frame,
            text="Title Administrator",
            variable=self.selected_role,
            value="title_admin",
            command=self._update_process_button,
            font=("Arial", 11),
        ).pack(anchor=tk.W, pady=2)

        tk.Radiobutton(
            role_frame,
            text="Appraiser",
            variable=self.selected_role,
            value="appraiser",
            command=self._update_process_button,
            font=("Arial", 11),
        ).pack(anchor=tk.W, pady=2)

        # --- Folder selection ---
        folder_frame = tk.LabelFrame(main_frame, text="Select Folder", padx=10, pady=10)
        folder_frame.pack(fill=tk.X, pady=(0, 10))

        self.folder_label = tk.Label(
            folder_frame,
            text="No folder selected",
            wraplength=540,
            anchor="w"
        )
        self.folder_label.pack(fill=tk.X, pady=(0, 5))

        tk.Button(
            folder_frame,
            text="Select Folder",
            command=self._select_folder,
            width=20
        ).pack()

        # --- Process button ---
        self.process_btn = tk.Button(
            main_frame,
            text="Process Images",
            command=self._process_images,
            state=tk.DISABLED,
            font=("Arial", 14, "bold"),
            bg="white",
            fg="black",
            width=20,
            height=2,
            relief=tk.RAISED,
            borderwidth=3,
            highlightthickness=2,
            highlightbackground="black"
        )
        self.process_btn.pack(pady=10)

        # --- Status log ---
        log_frame = tk.LabelFrame(main_frame, text="Status", padx=10, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=10,
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _setup_logging(self):
        class GUILogHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.text_widget = text_widget

            def emit(self, record):
                msg = self.format(record)
                self.text_widget.config(state=tk.NORMAL)
                self.text_widget.insert(tk.END, msg + "\n")
                self.text_widget.see(tk.END)
                self.text_widget.config(state=tk.DISABLED)

        handler = GUILogHandler(self.log_text)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(handler)

    def _log(self, message: str):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def _select_folder(self):
        folder = filedialog.askdirectory(title="Select folder containing photos")
        if folder:
            self.selected_folder = folder
            self.folder_label.config(text=f"Selected: {folder}")
            self._log(f"Selected folder: {folder}")
            self._update_process_button()

    def _update_process_button(self):
        role = self.selected_role.get()
        if self.selected_folder and role:
            self.process_btn.config(
                state=tk.NORMAL,
                bg="white",
                fg="black",
                font=("Arial", 14, "bold"),
                activebackground="#E0E0E0",
                activeforeground="black"
            )
        else:
            self.process_btn.config(
                state=tk.DISABLED,
                bg="white",
                fg="#808080",
                font=("Arial", 14, "bold")
            )

    def _process_images(self):
        if not self.selected_folder:
            messagebox.showerror("Error", "Please select a folder first")
            return

        role = self.selected_role.get()
        if not role:
            messagebox.showerror("Error", "Please select your role first")
            return

        self.process_btn.config(
            state=tk.DISABLED,
            text="Processing...",
            bg="white",
            fg="black",
            font=("Arial", 14, "bold")
        )
        self._log("=" * 60)
        self._log(f"Starting processing (mode: {role.replace('_', ' ').title()})...")

        output_dir = str(Path(self.selected_folder) / "processed")

        def process_thread():
            try:
                if role == "title_admin":
                    result = self.title_admin_processor(
                        self.selected_folder,
                        output_dir,
                        self.parcel_matcher,
                        self.classifier,
                    )
                else:
                    result = self.appraiser_processor(
                        self.selected_folder,
                        output_dir,
                        self.gps_resolver,
                        self.appraiser_classifier,
                    )
                self.root.after(0, self._processing_complete, result, role)
            except Exception as e:
                self.root.after(0, self._processing_error, str(e))

        threading.Thread(target=process_thread, daemon=True).start()

    def _processing_complete(self, result: dict, role: str):
        self.process_btn.config(
            state=tk.NORMAL,
            text="Process Images",
            bg="white",
            fg="black",
            font=("Arial", 14, "bold"),
            activebackground="#E0E0E0",
            activeforeground="black"
        )

        self._log("=" * 60)
        self._log("Processing complete!")

        if role == "title_admin":
            self._log(f"Account Number: {result.get('account_no', 'UNKNOWN')}")
            if result.get('parcel_no'):
                self._log(f"Parcel Number: {result['parcel_no']}")
            self._log(f"Processed: {result.get('processed_count', 0)} images")
        else:
            self._log(f"Processed: {result.get('processed_count', 0)} images")
            unresolved = result.get('unresolved_count', 0)
            if unresolved:
                self._log(f"Unresolved: {unresolved} images — see processed/unresolved/ folder")

        if result.get('skipped_files'):
            self._log(f"Skipped {len(result['skipped_files'])} invalid files")
        if result.get('errors'):
            self._log(f"Errors: {len(result['errors'])}")
            for error in result['errors']:
                self._log(f"  - {error}")

        # Summary popup
        msg = f"Processing complete!\n\nProcessed: {result.get('processed_count', 0)} images\n"
        if role == "title_admin":
            msg += f"Account: {result.get('account_no', 'UNKNOWN')}\n"
        else:
            unresolved = result.get('unresolved_count', 0)
            if unresolved:
                msg += f"\n{unresolved} image(s) could not be resolved — see processed/unresolved/ folder"
        if result.get('errors'):
            msg += f"\n{len(result['errors'])} error(s) — check log for details."

        messagebox.showinfo("Processing Complete", msg)

    def _processing_error(self, error_msg: str):
        self.process_btn.config(
            state=tk.NORMAL,
            text="Process Images",
            bg="white",
            fg="black",
            font=("Arial", 14, "bold"),
            activebackground="#E0E0E0",
            activeforeground="black"
        )
        self._log(f"ERROR: {error_msg}")
        messagebox.showerror("Processing Error", f"An error occurred:\n\n{error_msg}")

    def run(self):
        self.root.mainloop()
