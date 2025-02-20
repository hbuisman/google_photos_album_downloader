import faulthandler
faulthandler.enable(all_threads=True)
import tkinter as tk
from tkinter import messagebox
import threading
import io
import requests
import os
from PIL import Image, ImageTk
from multiprocessing import Queue

import photos_api

class AlbumDownloaderApp:
    def __init__(self, master):
        self.master = master
        master.title("Google Photos Album Downloader")
        
        self.service = None
        self.albums = []
        self.album_vars = []  # List of tuples (album, BooleanVar)
        self.album_images = []   # to hold references of cover images
        self.service_lock = threading.Lock()

        # Button to start album search.
        self.search_button = tk.Button(master, text="Search Albums", command=self.search_albums)
        self.search_button.pack(pady=10)

        # Frame for album list with checkboxes.
        self.album_frame = tk.Frame(master)
        self.album_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create a canvas and scrollbar for the album list (in case many albums are returned).
        self.scrollbar = tk.Scrollbar(self.album_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas = tk.Canvas(self.album_frame, yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.canvas.yview)
        self.album_list_frame = tk.Frame(self.canvas)
        # Store the window ID so we can update its width when the canvas resizes
        self.album_list_window = self.canvas.create_window((0,0), window=self.album_list_frame, anchor='nw')
        self.album_list_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        # Bind mouse scroll events when mouse enters/leaves the canvas
        self.canvas.bind("<Enter>", lambda event: self._bind_mousewheel())
        self.canvas.bind("<Leave>", lambda event: self._unbind_mousewheel())
        
        # Button to download selected albums.
        self.download_button = tk.Button(master, text="Download Selected Albums", command=self.download_selected_albums)
        self.download_button.pack(pady=10)

        # Status label.
        self.status_label = tk.Label(master, text="Status: Ready")
        self.status_label.pack(pady=5)
    
    def search_albums(self):
        # Disable search button to avoid multiple clicks.
        self.search_button.config(state=tk.DISABLED)
        self.status_label.config(text="Status: Authenticating and searching albums...")
        # Run the album search in a separate thread.
        threading.Thread(target=self.threaded_search).start()

    def threaded_search(self):
        try:
            # Authenticate and build the service.
            self.service = photos_api.authenticate()
            highlight_albums = photos_api.list_highlight_albums(self.service)
            self.albums = highlight_albums
            # Schedule the update_album_list to run on the main thread.
            self.master.after(0, self.update_album_list)
            self.set_status("Status: Found {} album(s).".format(len(highlight_albums)))
        except Exception as e:
            self.set_status("Error: " + str(e))
            messagebox.showerror("Error", str(e))
        finally:
            self.search_button.config(state=tk.NORMAL)

    def update_album_list(self):
        # Clear any existing contents in the album list.
        for widget in self.album_list_frame.winfo_children():
            widget.destroy()
        self.album_vars = []
        self.album_images = []  # clear saved images
        self.current_album_index = 0
        self.process_next_album()

    def process_next_album(self):
        if self.current_album_index < len(self.albums):
            album = self.albums[self.current_album_index]
            row_frame = tk.Frame(self.album_list_frame)
            row_frame.pack(fill=tk.X, pady=5, padx=5)

            # Fetch album cover if available
            cover_url = album.get("coverPhotoBaseUrl")
            photo = None
            if cover_url:
                cover_url_resized = cover_url + "=w150-h150"
                try:
                    response = requests.get(cover_url_resized)
                    if response.status_code == 200:
                        image_data = response.content
                        image = Image.open(io.BytesIO(image_data))
                        try:
                            resample_filter = Image.Resampling.LANCZOS
                        except AttributeError:
                            resample_filter = Image.LANCZOS
                        image = image.resize((100, 100), resample=resample_filter)
                        photo = ImageTk.PhotoImage(image)
                    else:
                        print(f"Failed to fetch cover image: {cover_url_resized}, status: {response.status_code}")
                except Exception as e:
                    print("Exception while fetching cover image:", e)
            if photo:
                img_label = tk.Label(row_frame, image=photo)
                img_label.pack(side=tk.LEFT, padx=5)
                self.album_images.append(photo)

            # Checkbox with album title (default checked)
            var = tk.BooleanVar(value=True)
            cb = tk.Checkbutton(row_frame, text=album.get('title', 'Untitled'), variable=var)
            cb.pack(side=tk.LEFT, padx=5)
            self.album_vars.append((album, var))

            # Add an info label to show how many files are already downloaded for this album.
            info_label = tk.Label(row_frame, text="Checking downloads...")
            info_label.pack(side=tk.LEFT, padx=5)
            
            # Spawn a thread to update the info label (so the UI isn't blocked)
            threading.Thread(target=self.update_album_skip_info, args=(info_label, album), daemon=True).start()

            self.current_album_index += 1
            self.status_label.config(text=f"Listing album {self.current_album_index} of {len(self.albums)}: {album.get('title', 'Untitled')}")
            self.master.after(50, self.process_next_album)
        else:
            self.status_label.config(text=f"Status: Found {len(self.albums)} album(s).")

    def download_selected_albums(self):
        # Gather selected albums from checkboxes.
        selected_albums = [album for album, var in self.album_vars if var.get()]
        if not selected_albums:
            messagebox.showinfo("No selection", "Please select at least one album to download.")
            return
        self.set_status("Status: Downloading selected albums...")
        # Start download in a separate thread.
        threading.Thread(target=self.threaded_download, args=(selected_albums,)).start()

    def threaded_download(self, albums):
        for album in albums:
            album_title = album.get('title', 'Untitled')
            album_id = album.get('id')
            self.set_status(f"Downloading album: {album_title}")
            
            with self.service_lock:
                total_files = photos_api.count_album_media_items(self.service, album_id)
            
            photos_api.download_album_photos(
                self.service, album_id, album_title,
                lambda: None  # no progress update since progress bars are removed
            )
        self.set_status("Status: Download complete.")
        messagebox.showinfo("Complete", "Download of selected albums complete.")
    
    def set_status(self, message):
        # Update status label in the main thread.
        self.master.after(0, lambda: self.status_label.config(text=message))
        
    def on_canvas_configure(self, event):
        # Ensure the album list frame width matches the canvas width on resize.
        self.canvas.itemconfig(self.album_list_window, width=event.width)

    def _on_mousewheel(self, event):
        # For Windows and Mac
        if event.delta:
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        else:
            # For Linux systems using Button-4 and Button-5 events
            if event.num == 4:
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.canvas.yview_scroll(1, "units")

    def _bind_mousewheel(self):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_mousewheel(self):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def update_album_skip_info(self, info_label, album):
        """
        For a given album, count the total media items and the number of files
        already downloaded locally, then update the info label.
        """
        folder_name = os.path.join('downloads', album.get('title', 'Untitled').replace(" ", "_"))
        try:
            with self.service_lock:
                total = photos_api.count_album_media_items(self.service, album.get('id'))
        except Exception as e:
            total = None
        downloaded = 0
        if os.path.exists(folder_name):
            downloaded = len([fname for fname in os.listdir(folder_name) if os.path.isfile(os.path.join(folder_name, fname))])
        if total is not None:
            msg = f"Already downloaded: {downloaded}/{total}"
        else:
            msg = f"Already downloaded: {downloaded}"
        self.master.after(0, lambda: info_label.config(text=msg))

    def reset_progress(self, progressbar):
        try:
            progressbar.config(value=0)
        except Exception as e:
            print("Error resetting progress bar:", e)

if __name__ == "__main__":
    root = tk.Tk()
    app = AlbumDownloaderApp(root)
    root.mainloop() 