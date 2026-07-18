import os

# --- HARDWARE SETTINGS ---
CAMERA_INDEX = 0

# Screen
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 480
FPS = 30

# --- PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWN_FACES_DIR = os.path.join(BASE_DIR, 'known_faces')
ATTENDANCE_DIR = os.path.join(BASE_DIR, 'attendance')  # daily CSV logs go here

# --- FACE RECOGNITION / ATTENDANCE ---
# Only these top-level folders inside known_faces are loaded.
# Empty list [] = load every folder.
ENABLED_GROUPS = ["Signass Student", "Students"]

# New students enrolled at the kiosk (E key) are saved into this group
ENROLL_GROUP = "Students"

FACE_MATCH_THRESHOLD = 0.42  # lower = stricter match
ID_INTERVAL = 0.25           # seconds between recognition attempts while verifying
VERIFY_TIMEOUT = 5.0         # seconds before giving up -> NOT RECOGNIZED
GREET_DURATION = 6.0         # seconds the profile/attendance screen stays up
UNKNOWN_DURATION = 3.0       # seconds the NOT RECOGNIZED message stays up
RETRY_COOLDOWN = 4.0         # seconds before the kiosk starts verifying again
REGREET_COOLDOWN = 60.0      # same person won't re-trigger the screen within this

# --- VISUAL THEME ---
COLOR_BG = (0, 0, 0)
COLOR_EYE_CORE = (0, 255, 255)
COLOR_EYE_GLOW = (0, 100, 255)
COLOR_TEXT = (200, 240, 255)
COLOR_FRAME = (0, 255, 255)
COLOR_OK = (0, 255, 120)      # attendance marked
COLOR_WARN = (255, 200, 0)    # already marked

# --- STATES ---
STATE_IDLE = "IDLE"        # eyes idle, waiting for a face
STATE_VERIFY = "VERIFY"    # face present, running recognition
STATE_GREET = "GREET"      # known person, profile + attendance shown
STATE_UNKNOWN = "UNKNOWN"  # face not recognized message
