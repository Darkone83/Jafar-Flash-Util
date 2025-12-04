import os
import sys
import shutil
import subprocess
import threading
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import webbrowser


class UrJTAGGui(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Jafar Lattice LC4032V Flasher - By: Darkone83")
        self.geometry("820x540")

        # --- Top frame: paths & settings ---
        top = tk.Frame(self)
        top.pack(fill=tk.X, padx=10, pady=10)

        # UrJTAG executable path
        tk.Label(top, text="UrJTAG executable:").grid(row=0, column=0, sticky="w")
        # On Linux/macOS this can just be "jtag", or a full path to the binary
        self.urjtag_path_var = tk.StringVar(value="jtag")
        self.urjtag_entry = tk.Entry(top, textvariable=self.urjtag_path_var, width=50)
        self.urjtag_entry.grid(row=0, column=1, sticky="we", padx=5)
        tk.Button(top, text="Browse...", command=self.browse_urjtag).grid(row=0, column=2, padx=5)

        # SVF file path
        tk.Label(top, text="SVF file:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.svf_path_var = tk.StringVar()
        self.svf_entry = tk.Entry(top, textvariable=self.svf_path_var, width=50)
        self.svf_entry.grid(row=1, column=1, sticky="we", padx=5, pady=(8, 0))
        tk.Button(top, text="Browse...", command=self.browse_svf).grid(row=1, column=2, padx=5, pady=(8, 0))

        # Cable config
        tk.Label(top, text="Cable config (UrJTAG):").grid(row=2, column=0, sticky="w", pady=(8, 0))
        # Default to your FT232H Amazon board VID/PID
        self.cable_var = tk.StringVar(
            value="cable ft232h vid 0x0403 pid 0x6014"
        )
        self.cable_entry = tk.Entry(top, textvariable=self.cable_var, width=50)
        self.cable_entry.grid(row=2, column=1, sticky="we", padx=5, pady=(8, 0))
        # User can edit if needed

        top.columnconfigure(1, weight=1)

        # --- Buttons frame ---
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=(0, 5))

        self.deps_button = tk.Button(
            btn_frame, text="Check Dependencies", command=self.on_check_deps_clicked
        )
        self.deps_button.grid(row=0, column=0, padx=5)

        self.auto_button = tk.Button(
            btn_frame, text="Auto-detect Cable", command=self.on_auto_cable_clicked
        )
        self.auto_button.grid(row=0, column=1, padx=5)

        self.detect_button = tk.Button(
            btn_frame, text="Detect Lattice Chip", command=self.on_detect_clicked
        )
        self.detect_button.grid(row=0, column=2, padx=5)

        self.program_button = tk.Button(
            btn_frame, text="Program LC4032V", command=self.on_program_clicked
        )
        self.program_button.grid(row=0, column=3, padx=5)

        # --- Log window ---
        self.log = scrolledtext.ScrolledText(self, wrap=tk.WORD, height=20)
        self.log.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.append_log(
            "Quick start:\n"
            "  • Step 0: Install UrJTAG.\n"
            "      - Either make sure 'jtag' is in your PATH\n"
            "        (Linux/macOS/WSL: usually just 'jtag')\n"
            "        (Windows: jtag.exe in a directory on PATH),\n"
            "      - OR use the 'Browse...' button to select the UrJTAG binary manually.\n"
            "  • Step 1: Wire FT232H to LC4032V JTAG:\n"
            "        D0 -> TCK, D1 -> TDI, D2 <- TDO, D3 -> TMS, plus 3V3 + GND.\n"
            "  • Step 2: Click 'Check Dependencies' to confirm UrJTAG is reachable.\n"
            "  • Step 3: (Optional) Click 'Auto-detect Cable' to find the right FTDI config.\n"
            "  • Step 4: Click 'Detect Lattice Chip' to confirm the LC4032V is seen.\n"
            "  • Step 5: Export an SVF file from Lattice Diamond.\n"
            "  • Step 6: Select the SVF file and click 'Program LC4032V'.\n\n"
        )

    # --- Browsers ---

    def browse_urjtag(self):
        # On Linux/macOS, this will show all files; just pick the 'jtag' binary.
        # On Windows, filter to .exe by default but allow all files as well.
        if os.name == "nt":
            ftypes = [("Executable", "*.exe"), ("All files", "*.*")]
        else:
            ftypes = [("All files", "*.*")]

        path = filedialog.askopenfilename(
            title="Select UrJTAG executable",
            filetypes=ftypes,
        )
        if path:
            self.urjtag_path_var.set(path)

    def browse_svf(self):
        path = filedialog.askopenfilename(
            title="Select SVF file",
            filetypes=[("SVF files", "*.svf"), ("All files", "*.*")],
        )
        if path:
            self.svf_path_var.set(path)

    # --- Dependency check ---

    def on_check_deps_clicked(self):
        self.append_log("=== Checking Dependencies ===\n")

        # Python version
        py_ver = sys.version.split()[0]
        self.append_log(f"Python version: {py_ver}\n")

        # pip availability
        pip_ok = False
        try:
            self.append_log("Checking pip...\n")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                pip_ok = True
                self.append_log("pip is available:\n")
                self.append_log("  " + result.stdout.strip() + "\n")
            else:
                self.append_log("pip check returned non-zero exit code.\n")
        except Exception as e:
            self.append_log(f"pip check failed: {e}\n")

        if not pip_ok:
            self.append_log("Note: pip is not strictly required; this GUI only uses stdlib.\n")

        # UrJTAG availability
        urjtag_path = self.urjtag_path_var.get().strip() or "jtag"
        self.append_log(f"\nChecking UrJTAG at: {urjtag_path}\n")

        resolved = urjtag_path
        if urjtag_path == "jtag":
            # Try to locate in PATH
            which_name = "jtag.exe" if os.name == "nt" else "jtag"
            which = shutil.which(which_name)
            if which:
                resolved = which
                self.append_log(f"Resolved 'jtag' to: {which}\n")
            else:
                self.append_log(f"Could not find '{which_name}' in PATH.\n")

        try:
            result = subprocess.run(
                [resolved, "-v"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                self.append_log("UrJTAG responds:\n")
                self.append_log(result.stdout + "\n")
            else:
                self.append_log("UrJTAG returned non-zero exit code on '-v'. Output:\n")
                self.append_log(result.stdout + "\n")
        except FileNotFoundError:
            self.append_log("ERROR: UrJTAG executable not found.\n")
            if messagebox.askyesno(
                "UrJTAG not found",
                "UrJTAG executable was not found.\n\n"
                "Do you want to open the UrJTAG download page in your browser?",
            ):
                webbrowser.open("https://sourceforge.net/projects/urjtag/files/urjtag/")
        except Exception as e:
            self.append_log(f"Error when checking UrJTAG: {e}\n")

        self.append_log("=== Dependency check complete ===\n\n")

    # --- Auto-detect cable ---

    def on_auto_cable_clicked(self):
        urjtag_path = self.urjtag_path_var.get().strip()
        if not urjtag_path:
            messagebox.showerror("Error", "Please specify the UrJTAG executable (or leave as 'jtag' if it's on PATH).")
            return

        self.append_log("=== Auto-detecting FTDI cable configuration ===\n")
        self.deps_button.config(state=tk.DISABLED)
        self.auto_button.config(state=tk.DISABLED)
        self.detect_button.config(state=tk.DISABLED)
        self.program_button.config(state=tk.DISABLED)

        thread = threading.Thread(
            target=self.run_auto_detect_cable,
            args=(urjtag_path,),
            daemon=True,
        )
        thread.start()

    def run_auto_detect_cable(self, urjtag_path):
        """
        Tries a few common FT232H/FT2232H configs and looks for a JTAG chain.
        If one looks good, updates self.cable_var.
        """
        candidates = [
            # Your FT232H board
            "cable ft232h vid 0x0403 pid 0x6014",
            # Generic FT2232H candidates (in case you ever swap boards)
            "cable ft2232 vid 0x0403 pid 0x6010 interface 0",
            "cable ft2232 vid 0x0403 pid 0x6010 interface 1",
        ]

        found = None

        for idx, cable_cmd in enumerate(candidates, start=1):
            self.append_log(f"Trying candidate {idx}/{len(candidates)}:\n  {cable_cmd}\n")

            script_lines = [
                cable_cmd,
                "detect",
                "quit",
            ]
            script_content = "\n".join(script_lines) + "\n"

            try:
                tmp = tempfile.NamedTemporaryFile(
                    delete=False, suffix=".jtag", mode="w", encoding="utf-8"
                )
                script_path = tmp.name
                tmp.write(script_content)
                tmp.close()
            except Exception as e:
                self.append_log(f"  Failed to create temp script: {e}\n")
                continue

            try:
                cmd = [urjtag_path, "-n", script_path]
                self.append_log("  Running: " + " ".join(cmd) + "\n")

                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )

                output_lines = []
                for line in process.stdout:
                    output_lines.append(line)
                    self.append_log("    " + line)

                process.wait()
                rc = process.returncode

                out = "".join(output_lines)

                if rc == 0 and self._looks_like_jtag_found(out):
                    self.append_log("  ✅ Looks good, JTAG chain detected.\n\n")
                    found = cable_cmd
                    try:
                        os.remove(script_path)
                    except Exception:
                        pass
                    break
                else:
                    self.append_log(f"  No valid chain (exit {rc}). Trying next...\n\n")

            except FileNotFoundError:
                self.append_log("  ERROR: UrJTAG executable not found.\n")
                break
            except Exception as e:
                self.append_log(f"  Unexpected error: {e}\n")
            finally:
                try:
                    os.remove(script_path)
                except Exception:
                    pass

        if found:
            self.append_log(f"=== Auto-detect success ===\nUsing cable config:\n  {found}\n\n")
            self.after(0, lambda: self.cable_var.set(found))
            self.show_message_async("Cable auto-detect", f"Detected cable:\n{found}")
        else:
            self.append_log("=== Auto-detect failed ===\n"
                            "No working cable configuration found in the candidate list.\n\n")
            self.show_message_async(
                "Cable auto-detect",
                "Could not auto-detect a working FTDI cable.\n"
                "You may need to set the cable line manually."
            )

        # Re-enable buttons
        self.after(0, lambda: self.deps_button.config(state=tk.NORMAL))
        self.after(0, lambda: self.auto_button.config(state=tk.NORMAL))
        self.after(0, lambda: self.detect_button.config(state=tk.NORMAL))
        self.after(0, lambda: self.program_button.config(state=tk.NORMAL))

    def _looks_like_jtag_found(self, output: str) -> bool:
        """
        Heuristic: does UrJTAG output look like it found a device?
        We look for common strings such as 'IR length', 'device', 'Lattice', etc.
        """
        lower = output.lower()
        keywords = [
            "jtag chain",
            "ir length",
            "device",
            "lattice",
            "idcode",
        ]
        return any(k in lower for k in keywords)

    # --- Detect button ---

    def on_detect_clicked(self):
        urjtag_path = self.urjtag_path_var.get().strip()
        cable_cmd = self.cable_var.get().strip()

        if not urjtag_path:
            messagebox.showerror(
                "Error",
                "Please specify the UrJTAG executable path (or leave as 'jtag' if it's on PATH).",
            )
            return

        script_lines = [
            cable_cmd,
            "detect",
            "quit",
        ]
        script_content = "\n".join(script_lines) + "\n"

        try:
            tmp = tempfile.NamedTemporaryFile(
                delete=False, suffix=".jtag", mode="w", encoding="utf-8"
            )
            script_path = tmp.name
            tmp.write(script_content)
            tmp.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create temp script:\n{e}")
            return

        self.append_log("=== Detect Lattice Chip ===\n")
        self.append_log(f"Using UrJTAG: {urjtag_path}\n")
        self.append_log(f"Using script: {script_path}\n\n")

        self.detect_button.config(state=tk.DISABLED)

        thread = threading.Thread(
            target=self.run_urjtag_script,
            args=(urjtag_path, script_path, "detect"),
            daemon=True,
        )
        thread.start()

    # --- Program button ---

    def on_program_clicked(self):
        urjtag_path = self.urjtag_path_var.get().strip()
        svf_path = self.svf_path_var.get().strip()
        cable_cmd = self.cable_var.get().strip()

        if not urjtag_path:
            messagebox.showerror(
                "Error",
                "Please specify the UrJTAG executable path (or leave as 'jtag' if it's on PATH).",
            )
            return

        if not svf_path or not os.path.isfile(svf_path):
            messagebox.showerror("Error", "Please select a valid SVF file.")
            return

        # Build .jtag script: cable + detect + svf + quit
        svf_norm = svf_path.replace("\\", "/")
        script_lines = [
            cable_cmd,
            "detect",
            # IMPORTANT: no quotes around the path for this UrJTAG build
            f"svf {svf_norm}",
            "quit",
        ]
        script_content = "\n".join(script_lines) + "\n"

        try:
            tmp = tempfile.NamedTemporaryFile(
                delete=False, suffix=".jtag", mode="w", encoding="utf-8"
            )
            script_path = tmp.name
            tmp.write(script_content)
            tmp.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create temp script:\n{e}")
            return

        self.append_log("=== Programming started ===\n")
        self.append_log(f"Using UrJTAG: {urjtag_path}\n")
        self.append_log(f"Using script: {script_path}\n")
        self.append_log(f"Using SVF:    {svf_path}\n\n")

        self.program_button.config(state=tk.DISABLED)

        thread = threading.Thread(
            target=self.run_urjtag_script,
            args=(urjtag_path, script_path, "program"),
            daemon=True,
        )
        thread.start()

    # --- Core runner (shared by detect + program) ---

    def run_urjtag_script(self, urjtag_path, script_path, mode):
        """
        mode: "detect" or "program" (for status messages)
        """
        try:
            # Older UrJTAG: script is positional argument, no -s
            cmd = [urjtag_path, "-n", script_path]
            self.append_log("Running: " + " ".join(cmd) + "\n\n")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            for line in process.stdout:
                self.append_log(line)

            process.wait()
            rc = process.returncode

            if rc == 0:
                if mode == "detect":
                    self.append_log("\n=== Detect finished (exit code 0) ===\n")
                    self.show_message_async(
                        "Detect OK",
                        "UrJTAG finished detection.\nCheck the log for the Lattice device ID.",
                    )
                else:
                    self.append_log("\n=== Programming finished (exit code 0) ===\n")
                    self.show_message_async(
                        "Done",
                        "UrJTAG finished programming.\nCheck the log for any warnings or errors.",
                    )
            else:
                self.append_log(f"\n=== {mode.capitalize()} failed (exit code {rc}) ===\n")
                self.show_message_async(
                    "Error",
                    f"UrJTAG exited with code {rc}.\nCheck wiring, cable config and log output.",
                )

        except FileNotFoundError:
            self.append_log("\nERROR: UrJTAG executable not found.\n")
            self.show_message_async(
                "Error",
                "UrJTAG executable not found.\n"
                "Adjust the path at the top or use 'Check Dependencies'.",
            )
        except Exception as e:
            self.append_log(f"\nUnexpected error: {e}\n")
            self.show_message_async("Error", f"Unexpected error:\n{e}")
        finally:
            self.after(0, lambda: self.program_button.config(state=tk.NORMAL))
            self.after(0, lambda: self.detect_button.config(state=tk.NORMAL))
            self.after(0, lambda: self.auto_button.config(state=tk.NORMAL))
            self.after(0, lambda: self.deps_button.config(state=tk.NORMAL))
            try:
                os.remove(script_path)
            except Exception:
                pass

    # --- Helpers ---

    def append_log(self, text: str):
        def _append():
            self.log.insert(tk.END, text)
            self.log.see(tk.END)

        self.after(0, _append)

    def show_message_async(self, title, message):
        self.after(0, lambda: messagebox.showinfo(title, message))


def main():
    app = UrJTAGGui()
    app.mainloop()


if __name__ == "__main__":
    main()
