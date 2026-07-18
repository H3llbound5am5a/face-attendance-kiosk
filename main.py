import time
import cv2
from config import *
from bot_eyes import BotFace
from bot_attendance import AttendanceLog
# Vision imported inside main to prevent init blocking

def main():
    # 1. START UI FIRST
    print("[INIT] Starting UI...")
    face_ui = BotFace()
    face_ui.draw_loading()

    # 2. LOAD HEAVY MODULES
    print("[INIT] Starting Vision...")
    from bot_vision import BotVision
    vision = BotVision()

    print("[INIT] Loading Attendance Log...")
    attendance = AttendanceLog()
    face_ui.set_stats(attendance.count_today(), attendance.recent())

    # 3. STATE VARIABLES
    state = STATE_IDLE
    face_ui.state = STATE_IDLE

    last_face = time.time()
    state_since = time.time()
    last_id_attempt = 0.0
    cooldown_until = 0.0
    flash_until = 0.0
    was_reloading = False
    last_greeted = {}  # name -> timestamp of last time their screen was shown

    def go_idle(cooldown=0.0):
        nonlocal state, cooldown_until
        state = STATE_IDLE
        face_ui.state = STATE_IDLE
        face_ui.show_eyes()
        face_ui.set_text("")
        cooldown_until = time.time() + cooldown

    def flash(text, duration):
        # Temporary message on the idle screen
        nonlocal flash_until
        face_ui.set_text(text)
        flash_until = time.time() + duration

    def greet(name, frame, status, status_ok):
        nonlocal state, state_since
        last_greeted[name] = time.time()
        details = vision.get_person_details(name)
        prof_img = vision.get_profile_image(name)
        if prof_img is None:
            prof_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_ui.set_text("")
        face_ui.show_profile(prof_img, name, details, status, status_ok)
        face_ui.set_stats(attendance.count_today(), attendance.recent())
        state = STATE_GREET
        face_ui.state = STATE_GREET
        state_since = time.time()

    while face_ui.running:
        now = time.time()

        # --- VISION UPDATE ---
        frame = vision.get_frame()
        debug_frame = None
        has_face = False

        if frame is not None:
            coords = vision.track_face(frame)
            if coords:
                has_face = True
                last_face = now
                if face_ui.mode == "EYES":
                    face_ui.look_at(-coords[0], coords[1])
            if face_ui.debug_mode:
                debug_frame = vision.draw_debug_overlay(frame.copy())

        if not has_face and (now - last_face > 1.0):
            face_ui.look_at(0, 0)

        # --- HOTKEY: R = reload face database (runs on the worker thread) ---
        if face_ui.reload_requested:
            face_ui.reload_requested = False
            vision.request_reload()
            face_ui.set_text("UPDATING FACE DATABASE...")
        if was_reloading and not vision.is_reloading():
            flash(f"{len(set(vision.known_names))} FACES LOADED", 3)
        was_reloading = vision.is_reloading()

        # --- HOTKEY: E = enroll the person in front of the camera ---
        if face_ui.enroll_submit:
            name = face_ui.enroll_submit
            face_ui.enroll_submit = None
            if frame is None or not has_face:
                flash("NO FACE IN VIEW - TRY AGAIN", 3)
            else:
                face_ui.set_text("SAVING...")
                face_ui.update()  # show it before the blocking encode
                if vision.enroll(name, frame):
                    marked_now, time_str = attendance.mark(name, ENROLL_GROUP)
                    greet(name, frame, f"ENROLLED & MARKED  -  {time_str}", True)
                else:
                    flash("NO CLEAR FACE - TRY AGAIN", 3)

        # While typing a name, pause the attendance flow
        if face_ui.enroll_mode:
            face_ui.update(current_frame=debug_frame)
            continue

        # --- STATE MACHINE ---
        if state == STATE_IDLE:
            if face_ui.info_text and now > flash_until and not vision.is_reloading():
                face_ui.set_text("")
            if has_face and now >= cooldown_until and not vision.is_reloading():
                state = STATE_VERIFY
                face_ui.state = STATE_VERIFY
                face_ui.set_text("VERIFYING...")
                state_since = now
                last_id_attempt = 0.0
                vision.get_identify_result()  # drain any stale result

        elif state == STATE_VERIFY:
            if not has_face and (now - last_face > 2.0):
                # Person walked away
                go_idle()
            else:
                # Feed frames to the recognition worker (non-blocking)
                if has_face and frame is not None and (now - last_id_attempt >= ID_INTERVAL):
                    last_id_attempt = now
                    vision.request_identify(frame)

                name = vision.get_identify_result()
                if name and name != "Unknown":
                    if now - last_greeted.get(name, 0) < REGREET_COOLDOWN:
                        # Same person still standing there - don't re-show the screen
                        go_idle(cooldown=RETRY_COOLDOWN)
                    else:
                        marked_now, time_str = attendance.mark(name, vision.get_person_category(name))
                        if marked_now:
                            greet(name, frame, f"ATTENDANCE MARKED  -  {time_str}", True)
                        else:
                            greet(name, frame, f"ALREADY MARKED TODAY  -  {time_str}", False)

                if state == STATE_VERIFY and (now - state_since > VERIFY_TIMEOUT):
                    state = STATE_UNKNOWN
                    face_ui.state = STATE_UNKNOWN
                    face_ui.set_text("FACE NOT RECOGNIZED")
                    state_since = now

        elif state == STATE_UNKNOWN:
            if now - state_since > UNKNOWN_DURATION:
                go_idle(cooldown=RETRY_COOLDOWN)

        elif state == STATE_GREET:
            if now - state_since > GREET_DURATION:
                go_idle(cooldown=RETRY_COOLDOWN)

        face_ui.update(current_frame=debug_frame)

    vision.release()
    face_ui.quit()

if __name__ == "__main__":
    main()
