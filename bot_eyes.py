import pygame
import time
import math
import random
import datetime
import cv2
import numpy as np
from config import *

COLOR_DIM = (100, 140, 160)

class BotFace:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Attendance Kiosk")
        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self.w, self.h = self.screen.get_size()
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()

        self.running = True
        self.state = STATE_IDLE
        self.info_text = ""
        self.debug_mode = False
        self.mode = "EYES"
        self.profile_surf = None
        self.profile_data = {}

        # Stats shown on the idle screen
        self.today_count = 0
        self.recent_checkins = []  # (time_str, name) newest first

        # Kiosk hotkey flags (read + cleared by main loop)
        self.reload_requested = False
        self.enroll_mode = False
        self.enroll_buffer = ""
        self.enroll_submit = None

        # Geometry
        self.eye_w = int(self.w * 0.22)
        self.eye_h = int(self.h * 0.55)

        self.left_x = int(self.w * 0.32)
        self.right_x = int(self.w * 0.68)
        self.center_y = int(self.h * 0.5)

        # Eyelids
        self.current_top_lid = 0.0
        self.current_bot_lid = 0.0
        self.current_lid_angle = 0.0
        self.target_top_lid = 0.0
        self.target_bot_lid = 0.0
        self.target_lid_angle = 0.0

        # Pupils
        self.pupil_x = 0.0
        self.pupil_y = 0.0
        self.target_pupil_x = 0.0
        self.target_pupil_y = 0.0

        self.blink_timer = time.time()
        self.next_blink = time.time() + random.uniform(2, 6)
        self.is_blinking = False
        self.glow_surf = self._create_glow()

        try:
            self.font = pygame.font.Font(None, int(self.h * 0.08))
            self.big_font = pygame.font.Font(None, int(self.h * 0.12))
            self.detail_font = pygame.font.Font(None, int(self.h * 0.06))
            self.small_font = pygame.font.Font(None, int(self.h * 0.05))
        except:
            self.font = pygame.font.SysFont('Arial', int(self.h * 0.08))
            self.big_font = pygame.font.SysFont('Arial', int(self.h * 0.12))
            self.detail_font = pygame.font.SysFont('Arial', int(self.h * 0.06))
            self.small_font = pygame.font.SysFont('Arial', int(self.h * 0.05))

    def _create_glow(self):
        # Oval Glow
        gw = int(self.eye_w * 1.8)
        gh = int(self.eye_h * 1.8)
        surf = pygame.Surface((gw, gh), pygame.SRCALPHA)
        for i in range(20):
            w = gw - (i * (gw // 20))
            h = gh - (i * (gh // 20))
            alpha = 5 + i * 2
            r = pygame.Rect(0, 0, w, h)
            r.center = (gw // 2, gh // 2)
            pygame.draw.ellipse(surf, (*COLOR_EYE_GLOW, alpha), r)
        return surf

    def show_eyes(self): self.mode = "EYES"

    def show_profile(self, image_rgb, name, details, status_text="", status_ok=True):
        self.mode = "PROFILE"
        h = datetime.datetime.now().hour
        greeting = "Good Morning" if h < 12 else ("Good Afternoon" if h < 18 else "Good Evening")
        self.profile_data = {
            "greeting": greeting,
            "name": name,
            "details": details,
            "status": status_text,
            "status_color": COLOR_OK if status_ok else COLOR_WARN,
        }

        if image_rgb is None:
            image_rgb = np.zeros((400, 400, 3), dtype=np.uint8)
            cv2.putText(image_rgb, "NO DATA", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)

        h, w = image_rgb.shape[:2]
        target_h = int(self.h * 0.55)
        scale = target_h / h
        target_w = int(w * scale)
        img_resized = cv2.resize(image_rgb, (target_w, target_h))
        self.profile_surf = pygame.image.frombuffer(img_resized.tobytes(), img_resized.shape[1::-1], "RGB")

    def set_stats(self, count, recent):
        self.today_count = count
        self.recent_checkins = recent

    def wrap_text(self, text, font, max_width):
        words = text.split(' ')
        lines = []
        current_line = []
        for word in words:
            test_line = ' '.join(current_line + [word])
            if font.size(test_line)[0] < max_width:
                current_line.append(word)
            else:
                lines.append(' '.join(current_line))
                current_line = [word]
        lines.append(' '.join(current_line))
        return lines

    def look_at(self, x, y):
        self.target_pupil_x = x * 30
        self.target_pupil_y = y * 30

    def update_physics(self):
        now = time.time()
        if now > self.next_blink:
            self.is_blinking, self.blink_timer = True, now
            self.next_blink = now + random.uniform(2, 6)

        blink_offset = 0.0
        if self.is_blinking:
            t = (now - self.blink_timer) / 0.15
            if t >= 1: self.is_blinking = False
            else: blink_offset = 1.0 - abs(math.cos(t * math.pi))

        is_contact = (math.sqrt(self.pupil_x**2 + self.pupil_y**2) < 10)

        if self.state == STATE_IDLE:
            self.target_top_lid, self.target_bot_lid, self.target_lid_angle = 0.25, 0.25, 0
        elif self.state == STATE_VERIFY:
            if is_contact: self.target_top_lid, self.target_bot_lid = -0.1, 0.5
            else: self.target_top_lid, self.target_bot_lid = -0.1, -0.1
            self.target_lid_angle = 0
        elif self.state == STATE_GREET:
            self.target_top_lid, self.target_bot_lid, self.target_lid_angle = -0.2, 0.4, 0
        elif self.state == STATE_UNKNOWN:
            self.target_top_lid, self.target_bot_lid, self.target_lid_angle = 0.35, 0.35, 12

        if self.is_blinking:
            self.target_top_lid += blink_offset
            self.target_bot_lid += blink_offset

        s = 0.2
        self.current_top_lid += (self.target_top_lid - self.current_top_lid) * s
        self.current_bot_lid += (self.target_bot_lid - self.current_bot_lid) * s
        self.current_lid_angle += (self.target_lid_angle - self.current_lid_angle) * s
        self.pupil_x += (self.target_pupil_x - self.pupil_x) * 0.1
        self.pupil_y += (self.target_pupil_y - self.pupil_y) * 0.1

    def draw_loading(self):
        """Simple loading screen to show while Vision init happens"""
        self.screen.fill(COLOR_BG)
        t = self.font.render("INITIALIZING SYSTEMS...", True, COLOR_EYE_CORE)
        self.screen.blit(t, t.get_rect(center=(self.w//2, self.h//2)))
        pygame.display.flip()

    def draw_complex_eye(self, x, y, is_right):
        # Glow
        self.screen.blit(self.glow_surf, self.glow_surf.get_rect(center=(x+self.pupil_x, y+self.pupil_y)))

        # Core (ELLIPSE)
        core_rect = pygame.Rect(0, 0, self.eye_w, self.eye_h)
        core_rect.center = (x+self.pupil_x, y+self.pupil_y)
        pygame.draw.ellipse(self.screen, COLOR_EYE_CORE, core_rect)

        # Lids
        top_h = int(self.eye_h * 1.5)
        top_y = y - (self.eye_h//2) - top_h + (self.current_top_lid * (self.eye_h/2))
        bot_h = int(self.eye_h * 1.5)
        bot_y = y + (self.eye_h//2) - (self.current_bot_lid * (self.eye_h/2))

        angle = self.current_lid_angle if is_right else -self.current_lid_angle
        lid = pygame.Surface((self.eye_w * 2, top_h), pygame.SRCALPHA)
        lid.fill(COLOR_BG)

        self.screen.blit(pygame.transform.rotate(lid, angle), pygame.transform.rotate(lid, angle).get_rect(center=(x, top_y + top_h//2)))
        self.screen.blit(pygame.transform.rotate(lid, -angle), pygame.transform.rotate(lid, -angle).get_rect(center=(x, bot_y + bot_h//2)))

    def draw_clock(self):
        now = datetime.datetime.now()
        t = self.small_font.render(now.strftime("%I:%M %p  |  %a %d %b %Y"), True, COLOR_DIM)
        self.screen.blit(t, t.get_rect(center=(self.w//2, 30)))

    def draw_stats(self):
        t = self.small_font.render(f"TODAY: {self.today_count} CHECKED IN", True, COLOR_DIM)
        self.screen.blit(t, (20, 15))
        y = 15 + int(self.h * 0.055)
        for time_str, name in self.recent_checkins:
            t = self.small_font.render(f"{time_str}  {name}", True, (60, 90, 105))
            self.screen.blit(t, (20, y))
            y += int(self.h * 0.05)

    def draw_enroll_overlay(self):
        dim = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 190))
        self.screen.blit(dim, (0, 0))

        cx, cy = self.w // 2, self.h // 2
        title = self.font.render("ENROLL NEW STUDENT", True, COLOR_EYE_CORE)
        self.screen.blit(title, title.get_rect(center=(cx, cy - int(self.h*0.18))))

        # Input box with blinking cursor
        cursor = "_" if int(time.time() * 2) % 2 == 0 else " "
        entry = self.big_font.render(self.enroll_buffer + cursor, True, COLOR_TEXT)
        box = entry.get_rect(center=(cx, cy))
        pygame.draw.rect(self.screen, COLOR_FRAME, box.inflate(60, 30), 2, border_radius=10)
        self.screen.blit(entry, box)

        hint1 = self.small_font.render("TYPE THE STUDENT'S NAME  -  LOOK AT THE CAMERA", True, COLOR_DIM)
        hint2 = self.small_font.render("ENTER = SAVE      ESC = CANCEL", True, COLOR_DIM)
        self.screen.blit(hint1, hint1.get_rect(center=(cx, cy + int(self.h*0.15))))
        self.screen.blit(hint2, hint2.get_rect(center=(cx, cy + int(self.h*0.21))))

    def _handle_enroll_key(self, e):
        if e.key == pygame.K_ESCAPE:
            self.enroll_mode = False
            self.enroll_buffer = ""
        elif e.key == pygame.K_RETURN:
            name = self.enroll_buffer.strip()
            if name:
                self.enroll_submit = name
            self.enroll_mode = False
            self.enroll_buffer = ""
        elif e.key == pygame.K_BACKSPACE:
            self.enroll_buffer = self.enroll_buffer[:-1]
        elif e.unicode and len(self.enroll_buffer) < 30:
            if e.unicode.isalnum() or e.unicode in " .-_'":
                self.enroll_buffer += e.unicode

    def update(self, current_frame=None):
        for e in pygame.event.get():
            if self.enroll_mode and e.type == pygame.KEYDOWN:
                self._handle_enroll_key(e)
                continue
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key in (pygame.K_q, pygame.K_ESCAPE)):
                self.running = False
            elif e.type == pygame.MOUSEBUTTONDOWN or (e.type == pygame.KEYDOWN and e.key == pygame.K_d):
                self.debug_mode = not self.debug_mode
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_r:
                self.reload_requested = True
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_e:
                self.enroll_mode = True
                self.enroll_buffer = ""

        self.update_physics()
        self.screen.fill(COLOR_BG)

        if self.debug_mode and current_frame is not None:
            fr = cv2.cvtColor(current_frame, cv2.COLOR_BGR2RGB)
            h, w = fr.shape[:2]
            scale = self.h / h
            fr = cv2.resize(fr, (int(w*scale), self.h))
            self.screen.blit(pygame.image.frombuffer(fr.tobytes(), fr.shape[1::-1], "RGB"), (0,0))
            fps_t = self.small_font.render(f"{self.clock.get_fps():.0f} FPS", True, (0, 255, 0))
            self.screen.blit(fps_t, (self.w - fps_t.get_width() - 20, 15))
        elif self.mode == "EYES":
            self.draw_complex_eye(self.left_x, self.center_y, False)
            self.draw_complex_eye(self.right_x, self.center_y, True)
            self.draw_clock()
            self.draw_stats()
            if self.info_text:
                t = self.font.render(self.info_text, True, COLOR_TEXT)
                self.screen.blit(t, t.get_rect(center=(self.w//2, self.h - 50)))
            elif self.state == STATE_IDLE:
                t = self.small_font.render("LOOK AT THE CAMERA TO MARK ATTENDANCE", True, COLOR_DIM)
                self.screen.blit(t, t.get_rect(center=(self.w//2, self.h - 40)))
        elif self.mode == "PROFILE":
            if self.profile_surf:
                r = self.profile_surf.get_rect(center=(int(self.w*0.35), self.h//2))
                pygame.draw.rect(self.screen, COLOR_FRAME, r.inflate(10,10), 3, border_radius=15)
                self.screen.blit(self.profile_surf, r)

            sx, sy = int(self.w*0.6), int(self.h*0.18)
            dy = int(self.h*0.08)
            max_width = int(self.w * 0.35)

            # Greeting + Name
            greet_t = self.detail_font.render(self.profile_data.get('greeting', '') + ",", True, COLOR_DIM)
            self.screen.blit(greet_t, (sx, sy))
            name_t = self.font.render(self.profile_data.get('name', 'Unknown'), True, COLOR_TEXT)
            self.screen.blit(name_t, (sx, sy + dy))

            # Details (Wrapped)
            details = self.profile_data.get('details', '')
            lines = self.wrap_text(details, self.detail_font, max_width)
            for i, line in enumerate(lines):
                t = self.detail_font.render(line, True, COLOR_TEXT)
                self.screen.blit(t, (sx, sy + (i+2.5)*dy))

            # Attendance status
            status = self.profile_data.get('status', '')
            if status:
                color = self.profile_data.get('status_color', COLOR_OK)
                s_lines = self.wrap_text(status, self.detail_font, max_width)
                base_y = sy + (len(lines)+3.2)*dy
                for i, line in enumerate(s_lines):
                    t = self.detail_font.render(line, True, color)
                    self.screen.blit(t, (sx, base_y + i*dy))

        if self.enroll_mode:
            self.draw_enroll_overlay()

        pygame.display.flip()
        self.clock.tick(FPS)

    def set_text(self, t): self.info_text = t
    def quit(self): pygame.quit()
