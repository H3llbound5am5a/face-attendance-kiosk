import cv2
import numpy as np
import mediapipe as mp
import face_recognition
import os
import re
import time
import threading
from PIL import Image, ImageOps
from config import *

def load_image_oriented(path):
    """Like face_recognition.load_image_file, but applies EXIF rotation first.
    Phone photos are often stored sideways with an EXIF orientation tag;
    without this the face detector sees a rotated face and finds nothing."""
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    return np.array(img.convert('RGB'))

class BotVision:
    def __init__(self):
        print("[VISION] Initializing Camera...")
        self.cap = cv2.VideoCapture(CAMERA_INDEX)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, FPS)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        print("[VISION] Loading MediaPipe...")
        self.mp_face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )
        self.last_mesh = None  # cached results for the debug overlay

        self.known_encodings = []
        self.known_names = []
        self.face_database = {}
        self.face_details = {}
        self.face_category = {}

        self.last_id_score = 1.0
        self._dlib_lock = threading.Lock()  # dlib calls from worker + enroll

        self._load_known_faces()

        # --- CAMERA GRABBER THREAD (main loop never blocks on camera IO) ---
        self._latest_frame = None
        self._frame_lock = threading.Lock()
        self._running = True
        threading.Thread(target=self._grab_loop, daemon=True).start()

        # --- RECOGNITION WORKER THREAD (identify without freezing the UI) ---
        self._id_event = threading.Event()
        self._id_frame = None
        self._id_result = None
        self._id_busy = False
        self._reload_requested = False
        threading.Thread(target=self._id_loop, daemon=True).start()

    # ------------------------------------------------------------------
    # FACE DATABASE
    # ------------------------------------------------------------------
    def _load_known_faces(self):
        print("------------------------------------------------")
        print(f"[MEMORY] Scanning {KNOWN_FACES_DIR}...")

        if not os.path.exists(KNOWN_FACES_DIR):
            try: os.makedirs(KNOWN_FACES_DIR)
            except: pass
            return

        self.known_encodings = []
        self.known_names = []
        self.face_database = {}
        self.face_details = {}
        self.face_category = {}

        count = 0
        for root, dirs, files in os.walk(KNOWN_FACES_DIR):
            for filename in files:
                if filename.lower().endswith(('.jpg', '.png', '.jpeg')):
                    path = os.path.join(root, filename)
                    name = os.path.splitext(filename)[0]
                    # Category = top-level group folder under known_faces
                    # (people may sit in their own subfolder inside a group)
                    rel = os.path.relpath(root, KNOWN_FACES_DIR)
                    category = "General" if rel == "." else rel.split(os.sep)[0]

                    if ENABLED_GROUPS and category not in ENABLED_GROUPS:
                        continue

                    try:
                        img = load_image_oriented(path)
                        # Downscale just for detection - full-res phone photos
                        # (12MP+) take several seconds each on the Pi otherwise.
                        h, w = img.shape[:2]
                        max_dim = max(h, w)
                        detect_img = img
                        if max_dim > 800:
                            scale = 800 / max_dim
                            detect_img = cv2.resize(img, (int(w * scale), int(h * scale)))
                        with self._dlib_lock:
                            encodings = face_recognition.face_encodings(detect_img)
                        if encodings:
                            self._register(name, category, encodings[0], img)

                            txt_path = os.path.join(root, f"{name}.txt")
                            if os.path.exists(txt_path):
                                try:
                                    with open(txt_path, 'r') as f:
                                        content = f.read().strip()
                                        if content: self.face_details[name] = content
                                except: pass

                            print(f"[{category.upper()}] > Loaded: {name}")
                            count += 1
                    except: pass
        print(f"[MEMORY] Database Ready. {count} identities loaded.")
        print("------------------------------------------------")

    def _register(self, name, category, encoding, img_rgb):
        """Add one identity to the in-memory database."""
        self.known_encodings.append(encoding)
        self.known_names.append(name)
        self.face_category[name] = category

        disp_img = img_rgb
        h, w = disp_img.shape[:2]
        if h > 400:
            scale = 400 / h
            disp_img = cv2.resize(disp_img, (int(w*scale), 400))
        self.face_database[name] = disp_img

    def enroll(self, name, frame):
        """Capture the face in the current frame as a new Student.
        Saves the photo to known_faces/<ENROLL_GROUP>/<name>/ and adds the
        encoding live (no restart needed). Returns True on success."""
        safe = re.sub(r"[^A-Za-z0-9 ._'-]", "", name).strip()
        if not safe: return False

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        with self._dlib_lock:
            locs = face_recognition.face_locations(rgb)
            encs = face_recognition.face_encodings(rgb, locs)
        if not encs:
            print(f"[ENROLL] No clear face in frame for '{safe}'")
            return False

        # Crop generously around the face for the saved profile photo
        top, right, bottom, left = locs[0]
        fh, fw = bottom - top, right - left
        y1 = max(0, top - fh // 2); y2 = min(frame.shape[0], bottom + fh // 2)
        x1 = max(0, left - fw // 2); x2 = min(frame.shape[1], right + fw // 2)
        face_img_rgb = rgb[y1:y2, x1:x2]

        person_dir = os.path.join(KNOWN_FACES_DIR, ENROLL_GROUP, safe)
        os.makedirs(person_dir, exist_ok=True)
        img_path = os.path.join(person_dir, f"{safe}.jpg")
        cv2.imwrite(img_path, cv2.cvtColor(face_img_rgb, cv2.COLOR_RGB2BGR))
        try:
            with open(os.path.join(person_dir, f"{safe}.txt"), 'w') as f:
                f.write("Student")
        except: pass

        self._register(safe, ENROLL_GROUP, encs[0], face_img_rgb)
        self.face_details[safe] = "Student"
        print(f"[ENROLL] Saved new student: {safe} -> {img_path}")
        return True

    def get_profile_image(self, name):
        return self.face_database.get(name)

    def get_person_details(self, name):
        return self.face_details.get(name, "Authorized Personnel")

    def get_person_category(self, name):
        return self.face_category.get(name, "General")

    # ------------------------------------------------------------------
    # PER-FRAME TRACKING (fast path - runs on a downscaled frame)
    # ------------------------------------------------------------------
    def track_face(self, frame):
        small = cv2.resize(frame, (320, 240))
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        results = self.mp_face_mesh.process(rgb)
        self.last_mesh = results
        if results.multi_face_landmarks:
            lm = results.multi_face_landmarks[0].landmark
            x_vals = [lm[1].x, lm[152].x]
            y_vals = [lm[1].y, lm[152].y]
            return (sum(x_vals)/2 - 0.5)*2, (sum(y_vals)/2 - 0.5)*2
        return None

    def draw_debug_overlay(self, frame):
        # Reuses the mesh from track_face (landmarks are normalized,
        # so they draw correctly on the full-size frame)
        results = self.last_mesh
        if results and results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                mp.solutions.drawing_utils.draw_landmarks(
                    image=frame,
                    landmark_list=face_landmarks,
                    connections=mp.solutions.face_mesh.FACEMESH_TESSELATION)

        score = self.last_id_score
        color = (0, 255, 0) if score < FACE_MATCH_THRESHOLD else (0, 0, 255)
        label = "MATCH" if score < FACE_MATCH_THRESHOLD else "UNKNOWN"
        cv2.rectangle(frame, (5, 5), (320, 85), (0, 0, 0), -1)
        cv2.putText(frame, f"DIST: {score:.3f} [{label}]", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        cv2.putText(frame, f"THRESHOLD: {FACE_MATCH_THRESHOLD}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        return frame

    # ------------------------------------------------------------------
    # RECOGNITION (blocking core + async worker interface)
    # ------------------------------------------------------------------
    def identify_user(self, frame):
        small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        with self._dlib_lock:
            locs = face_recognition.face_locations(rgb)
            encs = face_recognition.face_encodings(rgb, locs, model="small")

        if not encs:
            self.last_id_score = 1.0
            return "Unknown"

        face_distances = face_recognition.face_distance(self.known_encodings, encs[0])

        if len(face_distances) > 0:
            best_match_index = np.argmin(face_distances)
            score = face_distances[best_match_index]
            self.last_id_score = score
            print(f"[ID CHECK] Match: {self.known_names[best_match_index]} | Score: {score:.3f}")
            if score < FACE_MATCH_THRESHOLD:
                return self.known_names[best_match_index]

        self.last_id_score = 1.0
        return "Unknown"

    def request_identify(self, frame):
        """Non-blocking: hand a frame to the worker if it is free."""
        if self._id_busy or self._reload_requested: return
        self._id_frame = frame.copy()
        self._id_event.set()

    def get_identify_result(self):
        """Returns a name / 'Unknown' once per completed check, else None."""
        result = self._id_result
        self._id_result = None
        return result

    def request_reload(self):
        self._reload_requested = True
        self._id_event.set()

    def is_reloading(self):
        return self._reload_requested

    def _id_loop(self):
        while self._running:
            self._id_event.wait(timeout=0.5)
            if not self._running: break
            self._id_event.clear()

            if self._reload_requested:
                self._load_known_faces()
                self._reload_requested = False
                continue

            frame = self._id_frame
            self._id_frame = None
            if frame is None: continue

            self._id_busy = True
            try:
                self._id_result = self.identify_user(frame)
            except Exception as e:
                print(f"[ID ERROR] {e}")
            self._id_busy = False

    # ------------------------------------------------------------------
    # CAMERA
    # ------------------------------------------------------------------
    def _grab_loop(self):
        while self._running:
            if self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    with self._frame_lock:
                        self._latest_frame = frame
                else:
                    time.sleep(0.05)
            else:
                time.sleep(0.2)

    def get_frame(self):
        with self._frame_lock:
            if self._latest_frame is None: return None
            return self._latest_frame.copy()

    def release(self):
        self._running = False
        self._id_event.set()
        time.sleep(0.1)
        self.cap.release()
