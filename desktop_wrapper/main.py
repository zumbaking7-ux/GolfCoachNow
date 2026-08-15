import tkinter as tk
from tkinter import filedialog, messagebox
import requests
import threading
import os

API_URL = "https://golfcoachnow.pythonanywhere.com/upload"


def select_and_upload():
    file_path = filedialog.askopenfilename(
        title="Select Video",
        filetypes=[("Video files", "*.mp4 *.mov"), ("MP4", "*.mp4"), ("MOV", "*.mov")],
    )
    if not file_path:
        return

    file_name = os.path.basename(file_path)
    status_label.config(text=f"Uploading: {file_name}...")
    select_btn.config(state=tk.DISABLED)
    result_text.delete("1.0", tk.END)

    threading.Thread(target=upload_video, args=(file_path,), daemon=True).start()


def upload_video(file_path):
    try:
        with open(file_path, "rb") as f:
            response = requests.post(
                API_URL,
                files={"file": (os.path.basename(file_path), f)},
                timeout=120,
            )
        response.raise_for_status()
        data = response.json()
        show_result(data)
    except requests.ConnectionError:
        show_error("Backend not available.")
    except requests.RequestException:
        show_error("Upload failed. Try again.")
    except Exception:
        show_error("Upload failed. Try again.")


def show_result(data):
    def update():
        fault = data.get("dominant_fault", "N/A")
        correction = data.get("correction", "No correction returned.")
        result_text.delete("1.0", tk.END)
        result_text.insert(tk.END, f"Dominant Fault: {fault}\n\nCorrection: {correction}")
        status_label.config(text="Done.")
        select_btn.config(state=tk.NORMAL)

    root.after(0, update)


def show_error(msg):
    def update():
        status_label.config(text="")
        select_btn.config(state=tk.NORMAL)
        messagebox.showerror("Error", msg)

    root.after(0, update)


root = tk.Tk()
root.title("GolfCoachNow — Video Upload")
root.geometry("500x400")
root.resizable(False, False)

select_btn = tk.Button(root, text="Select Video", command=select_and_upload, height=2, width=20)
select_btn.pack(pady=20)

status_label = tk.Label(root, text="", anchor="w")
status_label.pack(fill=tk.X, padx=20)

result_text = tk.Text(root, wrap=tk.WORD, height=15)
result_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=(5, 20))

root.mainloop()
