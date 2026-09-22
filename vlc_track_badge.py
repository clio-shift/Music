# -*- coding: utf-8 -*-
"""
VLC 播放序号悬浮角标
------------------------------------------------
效果：屏幕上出现一个很小的黑底数字角标，实时显示 VLC 当前正在播放的
播放列表文件"最前面的数字"（比如文件名是"3 大、小三度构唱(4条)"，
角标就显示 3）。角标可以用鼠标拖动，拖到 VLC 图标旁边贴着放即可。

【使用前必须先在 VLC 里开启网页控制接口，一次性设置，步骤如下】
1. 打开 VLC -> 工具(Tools) -> 首选项(Preferences)
2. 左下角"显示设置"选择"全部(All)"
3. 左侧列表找到 接口(Interface) -> 主接口(Main interfaces)
   勾选 "Web"
4. 展开 主接口(Main interfaces) 左边的箭头，点击 Lua 子项
5. 在右侧 "Lua HTTP" 分组里，设置一个密码（Password），
   用户名留空即可，随便设一个比如 1234
6. 点击保存(Save)，完全关闭 VLC 再重新打开一次
7. 把下面 VLC_PASSWORD 改成你刚才设置的密码

然后用 `python vlc_track_badge.py` 运行本脚本即可（需要先装好 Python 3）。
角标默认出现在屏幕右上角，用鼠标左键按住拖动到你想要的位置（比如贴着
VLC 在任务栏的图标），下次启动脚本会记住上次拖动的位置。
"""

import urllib.request
import base64
import re
import time
import json
import threading
import os
import tkinter as tk
import xml.etree.ElementTree as ET

VLC_HOST = "localhost"
VLC_PORT = 8080
VLC_PASSWORD = "1234"
POLL_INTERVAL = 0.4
BADGE_SIZE = 32
FONT_SIZE = 14
POSITION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "badge_pos.json")


def get_vlc_status():
    """Get current VLC status and current playing item name"""
    url = f"http://{VLC_HOST}:{VLC_PORT}/requests/status.xml"
    req = urllib.request.Request(url)
    auth = base64.b64encode(f":{VLC_PASSWORD}".encode()).decode()
    req.add_header("Authorization", f"Basic {auth}")
    with urllib.request.urlopen(req, timeout=1) as resp:
        data = resp.read()
    root = ET.fromstring(data)

    state = root.find("state")
    is_active = state is not None and state.text in ("playing", "paused")

    # Try to get the title from now_playing info first
    filename = None
    for info in root.iter("info"):
        if info.get("name") == "title":
            filename = info.text
            break

    # Fallback to filename if title is not available
    if not filename:
        for info in root.iter("info"):
            if info.get("name") == "filename":
                filename = info.text
                break

    return is_active, filename


def extract_leading_number(filename):
    """Extract leading number from filename"""
    if not filename:
        return None
    m = re.match(r"\s*(\d+)", filename)
    if m:
        return m.group(1)
    return None


class Badge:
    def __init__(self):
        self.last_text = None
        self.running = True

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.88)

        self.label = tk.Label(
            self.root,
            text="...",
            font=("Segoe UI", FONT_SIZE, "bold"),
            fg="white",
            bg="#1a1a1a",
            width=2,
            height=1,
        )
        self.label.pack(fill="both", expand=True)

        x, y = self._load_position()
        self.root.geometry(f"{BADGE_SIZE}x{BADGE_SIZE}+{x}+{y}")

        self.label.bind("<ButtonPress-1>", self._start_move)
        self.label.bind("<B1-Motion>", self._do_move)
        self.label.bind("<ButtonRelease-1>", self._save_position)

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Exit", command=self.root.destroy)
        self.label.bind("<Button-3>", self._show_menu)

    def _show_menu(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)

    def _load_position(self):
        try:
            with open(POSITION_FILE, "r") as f:
                pos = json.load(f)
                return pos.get("x", 40), pos.get("y", 40)
        except Exception:
            sw = self.root.winfo_screenwidth()
            return sw - BADGE_SIZE - 20, 20

    def _save_position(self, event=None):
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        try:
            with open(POSITION_FILE, "w") as f:
                json.dump({"x": x, "y": y}, f)
        except Exception:
            pass

    def _start_move(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _do_move(self, event):
        x = self.root.winfo_pointerx() - self._drag_x
        y = self.root.winfo_pointery() - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def set_text(self, text, bg="#1a1a1a"):
        if text != self.last_text:
            self.label.config(text=text, bg=bg)
            self.last_text = text

    def poll_loop(self):
        while self.running:
            try:
                is_active, filename = get_vlc_status()
                if not is_active:
                    self.set_text("--", bg="#333333")
                else:
                    num = extract_leading_number(filename)
                    if num:
                        self.set_text(num, bg="#1a1a1a")
                    elif filename:
                        self.set_text("?", bg="#7a5c00")
                    else:
                        self.set_text("--", bg="#333333")
            except Exception:
                self.set_text("x", bg="#7a1a1a")
            time.sleep(POLL_INTERVAL)

    def run(self):
        t = threading.Thread(target=self.poll_loop, daemon=True)
        t.start()
        self.root.mainloop()
        self.running = False


if __name__ == "__main__":
    Badge().run()
