import os
import glob
import threading
import cv2
import numpy as np
from PIL import Image

import kivy
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.spinner import Spinner
from kivy.uix.slider import Slider
from kivy.uix.progressbar import ProgressBar
from kivy.clock import Clock
from kivy.core.window import Window

# Try loading pillow-heif for HEIC support
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_SUPPORTED = True
except ImportError:
    HEIF_SUPPORTED = False

Window.clearcolor = (0.1, 0.1, 0.12, 1) # Dark theme matching night sky

def load_image(path):
    ext = path.lower()
    if ext.endswith(('.heic', '.heif')):
        if HEIF_SUPPORTED:
            try:
                img = Image.open(path).convert('RGB')
                return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            except Exception as e:
                print(f"Failed to decode HEIC file {path}: {e}")
                return None
        else:
            return None
    else:
        return cv2.imread(path)

def count_supported_images(folder_path):
    if not os.path.exists(folder_path):
        return 0
    extensions = ['*.jpg', '*.jpeg', '*.png', '*.tif', '*.tiff', '*.heic', '*.HEIF']
    paths = []
    for ext in extensions:
        paths.extend(glob.glob(os.path.join(folder_path, ext)))
        paths.extend(glob.glob(os.path.join(folder_path, ext.upper())))
    return len(list(set(paths)))

class StarTrailMobileApp(App):
    def build(self):
        root = BoxLayout(orientation='vertical', padding=15, spacing=12)

        # Title Header
        root.add_widget(Label(text="[b]Star Trail & Timelapse Stacker[/b]", markup=True, font_size=20, size_hint_y=None, height=40))

        # 1. Folder Path Input
        root.add_widget(Label(text="Photos Folder Path:", font_size=14, size_hint_y=None, height=20))
        self.folder_input = TextInput(text="/sdcard/DCIM/Camera", multiline=False, font_size=14, size_hint_y=None, height=45)
        root.add_widget(self.folder_input)

        # Scan Folder Button
        btn_scan = Button(text="Scan Folder for Photos", background_color=(0.2, 0.6, 0.8, 1), size_hint_y=None, height=45)
        btn_scan.bind(on_press=self.scan_folder)
        root.add_widget(btn_scan)

        # 2. Stacking Mode
        root.add_widget(Label(text="Trail Stacking Mode:", font_size=14, size_hint_y=None, height=20))
        self.mode_spinner = Spinner(text="Lighten (Standard Trails)", values=["Lighten (Standard Trails)", "Comet Effect"], size_hint_y=None, height=45)
        root.add_widget(self.mode_spinner)

        # 3. Timelapse Style
        root.add_widget(Label(text="Timelapse Video Style:", font_size=14, size_hint_y=None, height=20))
        self.style_spinner = Spinner(text="Growing Star Trails Video", values=["Growing Star Trails Video", "Normal Timelapse (Raw Photos)", "Generate BOTH Timelapses"], size_hint_y=None, height=45)
        root.add_widget(self.style_spinner)

        # 4. FPS Layout
        fps_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=40, spacing=10)
        fps_layout.add_widget(Label(text="Video FPS (30):", font_size=14))
        self.fps_slider = Slider(min=1, max=60, value=30, step=1)
        self.fps_slider.bind(value=lambda instance, val: self.update_fps_label(val))
        self.fps_label = Label(text="30", font_size=14, size_hint_x=None, width=40)
        fps_layout.add_widget(self.fps_slider)
        fps_layout.add_widget(self.fps_label)
        root.add_widget(fps_layout)

        # 5. Gap Filling Checkbox Layout
        gap_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=40, spacing=10)
        self.gap_checkbox = CheckBox(active=True, size_hint_x=None, width=40)
        gap_layout.add_widget(self.gap_checkbox)
        gap_layout.add_widget(Label(text="Enable Gap Filling", font_size=14, halign='left'))
        gap_layout.children[0].bind(size=gap_layout.children[0].setter('text_size'))
        root.add_widget(gap_layout)

        # 6. Output Options Layout
        out_layout = GridLayout(cols=2, size_hint_y=None, height=90, spacing=5)
        
        self.img_checkbox = CheckBox(active=True, size_hint_x=None, width=40)
        out_layout.add_widget(self.img_checkbox)
        out_layout.add_widget(Label(text="Save Final Star Trail Image (PNG)", font_size=13, halign='left'))

        self.vid_checkbox = CheckBox(active=True, size_hint_x=None, width=40)
        out_layout.add_widget(self.vid_checkbox)
        out_layout.add_widget(Label(text="Generate Timelapse Video (MP4)", font_size=13, halign='left'))
        root.add_widget(out_layout)

        # 7. Action Button & Progress
        self.start_btn = Button(text="Start Processing", background_color=(0.2, 0.7, 0.3, 1), font_size=16, size_hint_y=None, height=55)
        self.start_btn.bind(on_press=self.start_processing_thread)
        root.add_widget(self.start_btn)

        self.progress_bar = ProgressBar(max=100, value=0, size_hint_y=None, height=25)
        root.add_widget(self.progress_bar)

        status_text = "Status: Ready (HEIF Enabled)" if HEIF_SUPPORTED else "Status: Ready (Warning: pillow-heif missing)"
        self.status_label = Label(text=status_text, font_size=13, size_hint_y=None, height=30)
        root.add_widget(self.status_label)

        return root

    def update_fps_label(self, val):
        self.fps_label.text = str(int(val))

    def scan_folder(self, instance):
        folder = self.folder_input.text.strip()
        count = count_supported_images(folder)
        self.status_label.text = f"Found {count} supported images in folder."

    def start_processing_thread(self, instance):
        threading.Thread(target=self.run_processing_task, daemon=True).start()

    def run_processing_task(self):
        folder = self.folder_input.text.strip()
        save_img = self.img_checkbox.active
        save_vid = self.vid_checkbox.active
        stacking_mode = self.mode_spinner.text
        timelapse_style = self.style_spinner.text
        fps = int(self.fps_slider.value)
        gap_fill = self.gap_checkbox.active

        if not save_img and not save_vid:
            Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', "Error: Select at least one output option."))
            return

        extensions = ['*.jpg', '*.jpeg', '*.png', '*.tif', '*.tiff', '*.heic', '*.HEIF']
        image_paths = []
        for ext in extensions:
            image_paths.extend(glob.glob(os.path.join(folder, ext)))
            image_paths.extend(glob.glob(os.path.join(folder, ext.upper())))
        
        image_paths = sorted(list(set(image_paths)))
        total_frames = len(image_paths)

        if total_frames == 0:
            Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', "Error: No images found in folder."))
            return

        Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', f"Reading {total_frames} images..."))
        
        first_frame = load_image(image_paths[0])
        if first_frame is None:
            Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', "Error: Could not read first image."))
            return

        height, width, _ = first_frame.shape
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')

        writer_trail = None
        writer_normal = None
        
        folder_name = os.path.basename(folder) or "star_trail"
        output_img_path = os.path.join(folder, f"{folder_name}_final.png")
        output_vid_path = os.path.join(folder, f"{folder_name}_timelapse.mp4")

        if save_vid:
            base_name, ext = os.path.splitext(output_vid_path)
            if timelapse_style in ["Growing Star Trails Video", "Generate BOTH Timelapses"]:
                path_trail = output_vid_path if timelapse_style == "Growing Star Trails Video" else f"{base_name}_star_trails{ext}"
                writer_trail = cv2.VideoWriter(path_trail, fourcc, fps, (width, height))

            if timelapse_style in ["Normal Timelapse (Raw Photos)", "Generate BOTH Timelapses"]:
                path_normal = output_vid_path if timelapse_style == "Normal Timelapse (Raw Photos)" else f"{base_name}_normal{ext}"
                writer_normal = cv2.VideoWriter(path_normal, fourcc, fps, (width, height))

        master_canvas = first_frame.astype(np.float32)
        history = []

        for idx, path in enumerate(image_paths):
            current_frame = load_image(path)
            if current_frame is None:
                continue

            if stacking_mode == "Lighten (Standard Trails)":
                if gap_fill and idx > 0:
                    prev_frame = history[-1] if len(history) > 0 else current_frame
                    intermediate = cv2.addWeighted(current_frame, 0.5, prev_frame, 0.5, 0)
                    master_canvas = np.maximum(master_canvas, intermediate.astype(np.float32))
                
                master_canvas = np.maximum(master_canvas, current_frame.astype(np.float32))
                
                if gap_fill:
                    history.append(current_frame)
                    if len(history) > 2:
                        history.pop(0)

                trail_frame = master_canvas.astype(np.uint8)

            elif stacking_mode == "Comet Effect":
                decay_factor = 0.96
                master_canvas = master_canvas * decay_factor
                master_canvas = np.maximum(master_canvas, current_frame.astype(np.float32))
                trail_frame = master_canvas.astype(np.uint8)

            if writer_trail:
                writer_trail.write(trail_frame)
            if writer_normal:
                writer_normal.write(current_frame)

            progress = ((idx + 1) / total_frames) * 100
            Clock.schedule_once(lambda dt, p=progress, i=idx+1: self.update_progress(p, i, total_frames))

        if save_img:
            cv2.imwrite(output_img_path, master_canvas.astype(np.uint8), [cv2.IMWRITE_PNG_COMPRESSION, 0])

        if writer_trail:
            writer_trail.release()
        if writer_normal:
            writer_normal.release()

        Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', "Completed Successfully! 🎉 Saved to folder."))

    def update_progress(self, progress, current, total):
        self.progress_bar.value = progress
        self.status_label.text = f"Processing frame {current} of {total} ({progress:.1f}%)"

if __name__ == '__main__':
    StarTrailMobileApp().run()