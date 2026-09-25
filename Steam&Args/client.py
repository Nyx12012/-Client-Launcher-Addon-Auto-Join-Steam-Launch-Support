import ctypes
import re
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog

from tavern_shared import theme, window_chrome

DEFAULT_PORT = "1757"
JOIN_DELAY_MS = 700
SHOW_AFTER_MS = 20000
GAME_CHECK_MS = 2000
ADDRESS_PATTERN = re.compile(r"([A-Za-z0-9._-]+)(?::([0-9]{1,5}))?")
GAME_STARTED_PATTERN = re.compile(r"Game running \(PID (\d+)\)")
LAUNCHER_PLACEHOLDER = "C:\\path\\to\\TavernLauncher - Client.exe"
ADDRESS_HINT = "--join needs a server address, like --join myserver.com:1757"
DIALOG_FUNCTIONS = {
    messagebox: ("showinfo", "showwarning", "showerror", "askquestion", "askokcancel",
                 "askyesno", "askyesnocancel", "askretrycancel"),
    simpledialog: ("askstring", "askinteger", "askfloat"),
}
SYNCHRONIZE = 0x00100000
WAIT_TIMEOUT = 0x00000102


def parse_args(args):
    lowered = [arg.lower() for arg in args]
    hide = "--hide" in lowered
    for index, arg in enumerate(lowered):
        if arg == "--join" or arg.startswith("--join="):
            if "=" in arg:
                value = args[index].split("=", 1)[1]
            elif index + 1 < len(args):
                value = args[index + 1]
            else:
                value = ""
            target, problem = parse_address(value)
            return target, problem, hide
    if "--join-last" in lowered:
        return "last", None, hide
    return None, None, hide


def parse_address(value):
    value = value.strip().strip('"').strip()
    if not value or value.startswith("-"):
        return None, ADDRESS_HINT
    match = ADDRESS_PATTERN.fullmatch(value)
    if not match:
        return None, "'%s' is not a server address. %s" % (value, ADDRESS_HINT)
    host, port = match.group(1), match.group(2) or DEFAULT_PORT
    if not 1 <= int(port) <= 65535:
        return None, "'%s' is not a valid port." % port
    return (host, str(int(port))), None


def _log(app, message, tag):
    try:
        app._print("Auto Join: " + message, tag)
    except Exception:
        pass


def _kernel32():
    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    kernel32.WaitForSingleObject.restype = ctypes.c_uint32
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    return kernel32


def _open_process(pid):
    try:
        kernel32 = _kernel32()
        handle = kernel32.OpenProcess(SYNCHRONIZE, 0, pid)
        return (kernel32, handle) if handle else None
    except Exception:
        return None


def _process_running(process):
    kernel32, handle = process
    return kernel32.WaitForSingleObject(handle, 0) == WAIT_TIMEOUT


def _close_process(process):
    kernel32, handle = process
    kernel32.CloseHandle(handle)


class HiddenLaunch:
    def __init__(self, wanted):
        self.hidden = wanted
        self.app = None
        self.game = None
        self.waiting = []

    def start(self, app):
        if app.state() != "withdrawn":
            app.withdraw()
        for window in app.winfo_children():
            if isinstance(window, tk.Toplevel) and window.state() != "withdrawn":
                window.withdraw()
                self.waiting.append(window)
        original_print = app._print

        def watched_print(message, tag=""):
            original_print(message, tag)
            self.on_log(str(message), tag)

        app._print = watched_print
        for module, names in DIALOG_FUNCTIONS.items():
            for name in names:
                original = getattr(module, name, None)
                if original is not None:
                    setattr(module, name, self.revealing(original))
        app.after(SHOW_AFTER_MS, self.on_timeout)

    def revealing(self, original):
        def dialog(*args, **kwargs):
            self.reveal()
            return original(*args, **kwargs)
        return dialog

    def on_log(self, message, tag):
        if not self.hidden or self.game is not None:
            return
        started = GAME_STARTED_PATTERN.search(message)
        if started:
            self.game = _open_process(int(started.group(1)))
            if self.game is None:
                self.reveal()
            else:
                self.app.after(GAME_CHECK_MS, self.on_game_check)
        elif tag == "err":
            self.reveal()

    def on_timeout(self):
        if self.hidden and self.game is None:
            _log(self.app, "the game hasn't started, so the launcher is showing.", "warn")
            self.reveal()

    def on_game_check(self):
        if _process_running(self.game):
            self.app.after(GAME_CHECK_MS, self.on_game_check)
            return
        _close_process(self.game)
        if self.hidden:
            self.app.destroy()

    def reveal(self):
        if self.hidden and self.app is not None:
            self.hidden = False
            _show_window(self.app)
            for window in self.waiting:
                if window.winfo_exists():
                    _show_window(window)
            self.waiting = []
            self.app.lift()


TARGET, PROBLEM, HIDE = parse_args(sys.argv[1:])
hidden_launch = HiddenLaunch(bool(HIDE and TARGET and not PROBLEM))
_show_window = window_chrome._finish_dark_window


def _finish_dark_window(window):
    if not hidden_launch.hidden:
        _show_window(window)
    elif type(window).__name__ != "ClientLauncher":
        hidden_launch.waiting.append(window)


if hidden_launch.hidden:
    window_chrome._finish_dark_window = _finish_dark_window


def _schedule_join(app):
    if PROBLEM:
        _log(app, PROBLEM, "err")
    elif TARGET:
        app.after(JOIN_DELAY_MS, lambda: _join(app, TARGET))


def _join(app, target):
    if target != "last":
        host, port = target
        app.v_ip.set(host)
        app.v_port.set(port)
    host = app.v_ip.get().strip() or "127.0.0.1"
    port = app.v_port.get().strip() or DEFAULT_PORT
    button = getattr(app, "_action_btn", None)
    if button is None:
        _log(app, "couldn't find the Join Server button.", "err")
    elif str(button.cget("state")) == "disabled":
        _log(app, "the Join Server button is busy, so nothing was joined.", "err")
    else:
        _log(app, "joining %s:%s" % (host, port), "warn")
        button.invoke()


def _find_button(widget, word):
    for child in widget.winfo_children():
        if isinstance(child, tk.Button) and word in str(child.cget("text")).lower():
            return child
        found = _find_button(child, word)
        if found is not None:
            return found
    return None


def _launcher_path():
    if getattr(sys, "frozen", False):
        return sys.executable
    return LAUNCHER_PLACEHOLDER


def _copy(button, text):
    button.clipboard_clear()
    button.clipboard_append(text)
    button.config(text="Copied")

    def reset():
        if button.winfo_exists():
            button.config(text="Copy")

    button.after(1500, reset)


def _option_row(parent, label, text):
    tk.Label(parent, text=label, bg=theme.BG, fg=theme.PARCH, font=("Segoe UI", 9),
             anchor="w").pack(fill="x", pady=(12, 4))
    row = tk.Frame(parent, bg=theme.BG)
    row.pack(fill="x")
    entry = tk.Entry(row, width=72, font=theme.MONO, relief="flat", bd=4,
                     readonlybackground=theme.SURF, fg=theme.PARCH)
    entry.insert(0, text)
    entry.config(state="readonly")
    entry.pack(side="left", fill="x", expand=True, ipady=3)
    copy = theme._btn(row, "Copy", None, font=("Segoe UI", 9), pady=4, padx=12)
    copy.config(command=lambda: _copy(copy, text))
    copy.pack(side="left", padx=(6, 0))
    return entry


def _chrome(name, window):
    step = getattr(window_chrome, name, None)
    if step is not None:
        step(window)


def open_launch_options(parent, name, host, port):
    flags = "--join %s:%s --hide" % (host, port)
    dialog = tk.Toplevel(parent)
    _chrome("_start_hidden", dialog)
    dialog.title("Steam Launch Options")
    dialog.configure(bg=theme.BG)
    dialog.resizable(False, False)
    dialog.transient(parent)
    _chrome("_set_window_icon", dialog)
    body = tk.Frame(dialog, bg=theme.BG)
    body.pack(fill="both", expand=True, padx=18, pady=14)
    tk.Label(body, text=name, bg=theme.BG, fg=theme.AMBER, font=("Georgia", 12, "bold"),
             anchor="w").pack(fill="x")
    _option_row(body, "TavernLauncher added to Steam as a Non-Steam Game:", flags)
    _option_row(body, "TavernLauncher location:", _launcher_path())
    tk.Label(body, text="In Steam, add a Non-Steam Game and paste the location into the file "
                        "window. Then right-click the new entry, open Properties, and paste the "
                        "first line into Launch Options. Leave out --hide if you want to see the "
                        "launcher window.", bg=theme.BG, fg=theme.MUTED,
             font=("Segoe UI", 9), anchor="w", justify="left",
             wraplength=560).pack(fill="x", pady=(12, 0))
    theme._btn(body, "Close", dialog.destroy, font=("Segoe UI", 9), pady=6,
               padx=14).pack(anchor="e", pady=(12, 0))
    _show_window(dialog)
    return dialog


def _show_for_selection(browser):
    server = browser._selected_server()
    if not server:
        return
    address = server.get("address", "")
    host = address.split(":")[0]
    port = address.split(":")[1] if ":" in address else DEFAULT_PORT
    open_launch_options(browser, server.get("name") or host, host, port)


def _add_steam_button(browser, module):
    favorite = _find_button(browser, "favorite")
    if favorite is None:
        return
    make_button = getattr(module, "_btn", theme._btn)
    button = make_button(favorite.master, "Steam Launch Options",
                         lambda: _show_for_selection(browser),
                         font=("Segoe UI", 9), pady=6, padx=10)
    button.pack(side="left", padx=(0, 6))


def _patch_community_browser():
    module = sys.modules.get("client.core.community_browser")
    browser_class = getattr(module, "CommunityBrowser", None)
    if browser_class is None or getattr(browser_class, "_auto_join_patched", False):
        return
    original_build = browser_class._build

    def build(self, *args, **kwargs):
        result = original_build(self, *args, **kwargs)
        try:
            _add_steam_button(self, module)
        except Exception:
            pass
        return result

    browser_class._build = build
    browser_class._auto_join_patched = True


_original_mainloop = tk.Tk.mainloop


def _mainloop(self, n=0):
    if type(self).__name__ == "ClientLauncher" and not getattr(self, "_auto_join_started", False):
        self._auto_join_started = True
        hidden_launch.app = self
        steps = [_patch_community_browser, lambda: _schedule_join(self)]
        if hidden_launch.hidden:
            steps.insert(0, lambda: hidden_launch.start(self))
        for step in steps:
            try:
                step()
            except Exception as error:
                hidden_launch.reveal()
                _log(self, "hit an error: %s" % error, "err")
    return _original_mainloop(self, n)


tk.Tk.mainloop = _mainloop
