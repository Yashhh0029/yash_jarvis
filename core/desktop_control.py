# core/desktop_control.py
"""
Desktop Control – Ultra Stable + Cinematic Version
Fully compatible with command_handler, supports:
✓ Brightness (smooth + instant)
✓ Volume (smooth + instant)
✓ Window control
✓ System actions (lock, restart)
✓ Screenshot (file + clipboard)
✓ Dark mode toggle
✓ Focus assist
"""

import os
import ctypes
import subprocess
import pyautogui
import keyboard
import time


class DesktopControl:

    # ============================================================
    # BRIGHTNESS CONTROL
    # ============================================================
    def _set_brightness(self, level):
        try:
            level = max(0, min(100, int(level)))
            cmd = (
                "(Get-WmiObject -Namespace root/WMI "
                "-Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{})".format(level)
            )
            subprocess.call(["powershell.exe", "-Command", cmd])
        except:
            pass

    def _get_brightness(self):
        try:
            cmd = "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness"
            val = subprocess.check_output(
                ["powershell.exe", "-Command", cmd]
            ).decode().strip()
            return int(val)
        except:
            return 50

    def increase_brightness(self):
        try:
            curr = self._get_brightness()
            self._set_brightness(curr + 15)
        except:
            pass

    def decrease_brightness(self):
        try:
            curr = self._get_brightness()
            self._set_brightness(curr - 15)
        except:
            pass

    # Smooth transition
    def smooth_brightness(self, direction="down"):
        try:
            curr = self._get_brightness()
            target = 10 if direction == "down" else 90
            step = -3 if direction == "down" else 3

            if direction == "down" and curr < target:
                return
            if direction == "up" and curr > target:
                return

            while (direction == "down" and curr > target) or \
                  (direction == "up" and curr < target):

                curr += step
                self._set_brightness(curr)
                time.sleep(0.04)
        except:
            pass

    # ============================================================
    # VOLUME CONTROL
    # ============================================================
    def volume_up(self):
        try:
            keyboard.send("volume_up")
        except:
            pass

    def volume_down(self):
        try:
            keyboard.send("volume_down")
        except:
            pass

    def mute(self):
        try:
            keyboard.send("volume_mute")
        except:
            pass

    def unmute(self):
        try:
            keyboard.send("volume_mute")
        except:
            pass

    def smooth_volume(self, direction="down"):
        try:
            key = "volume_down" if direction == "down" else "volume_up"
            for _ in range(12):
                keyboard.send(key)
                time.sleep(0.05)
        except:
            pass

    # ============================================================
    # WINDOW CONTROL
    # ============================================================
    def show_desktop(self):
        try:
            keyboard.send("windows+d")
        except:
            pass

    def close_window(self):
        try:
            keyboard.send("alt+f4")
        except:
            pass

    def maximize_window(self):
        try:
            keyboard.send("windows+up")
        except:
            pass

    def minimize_window(self):
        try:
            keyboard.send("windows+down")
        except:
            pass

    def next_window(self):
        try:
            keyboard.press("alt")
            keyboard.press("tab")
            keyboard.release("tab")
            keyboard.release("alt")
        except:
            pass

    def previous_window(self):
        try:
            keyboard.press("alt")
            keyboard.press("shift")
            keyboard.press("tab")
            keyboard.release("tab")
            keyboard.release("shift")
            keyboard.release("alt")
        except:
            pass

    # ============================================================
    # SETTINGS / SYSTEM UI
    # ============================================================
    def open_task_manager(self):
        try:
            os.system("start taskmgr")
        except:
            pass

    def open_settings(self):
        try:
            os.system("start ms-settings:")
        except:
            pass

    def open_display_settings(self):
        try:
            os.system("start ms-settings:display")
        except:
            pass

    def open_wifi_settings(self):
        try:
            os.system("start ms-settings:network-wifi")
        except:
            pass

    # ============================================================
    # NIGHT MODE / FOCUS ASSIST
    # ============================================================
    def enable_dark_mode(self):
        try:
            # App + System dark mode
            cmds = [
                r"Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize' -Name AppsUseLightTheme -Value 0",
                r"Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize' -Name SystemUsesLightTheme -Value 0"
            ]
            for c in cmds:
                subprocess.call(["powershell.exe", "-Command", c])
        except:
            pass

    def disable_dark_mode(self):
        try:
            cmds = [
                r"Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize' -Name AppsUseLightTheme -Value 1",
                r"Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize' -Name SystemUsesLightTheme -Value 1"
            ]
            for c in cmds:
                subprocess.call(["powershell.exe", "-Command", c])
        except:
            pass

    def enable_focus_assist(self):
        try:
            os.system("powershell.exe -Command (New-ItemProperty -Path HKCU:\\ControlPanel\\Quick* -Name FocusAssist -Value 2 -Force)")
        except:
            pass

    def disable_focus_assist(self):
        try:
            os.system("powershell.exe -Command (New-ItemProperty -Path HKCU:\\ControlPanel\\Quick* -Name FocusAssist -Value 0 -Force)")
        except:
            pass

    # ============================================================
    # SCREENSHOTS
    # ============================================================
    def screenshot_to_clipboard(self):
        try:
            keyboard.send("printscreen")
        except:
            pass

    def screenshot_to_file(self):
        try:
            filename = f"screenshot_{int(time.time())}.png"
            img = pyautogui.screenshot()
            img.save(filename)
            return filename
        except:
            return None

    # ============================================================
    # SYSTEM CONTROL
    # ============================================================
    def lock_screen(self):
        try:
            ctypes.windll.user32.LockWorkStation()
        except:
            pass

    def restart_system(self):
        try:
            os.system("shutdown /r /t 0")
        except:
            pass
