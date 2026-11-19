"""One application for MIDI conversion and GS2 game playback."""
from pathlib import Path
import sys
import os
import math
import logging
from logging.handlers import RotatingFileHandler
import tkinter as tk
from tkinter import ttk, messagebox
from converter_ui import App as ConverterPane, DEFAULT_SCORE, POLICIES, ARRANGEMENTS
from player_ui import App as PlayerPane
from overlay import Overlay
from preferences import read_preferences, write_preferences, player_preferences, path_list
from theme import setup, BG


def application_dir():
    return Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent


class ScrollPage(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, background=BG)
        scroll = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        scroll.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.content = ttk.Frame(self.canvas)
        self.item = self.canvas.create_window(0, 0, window=self.content, anchor='nw')
        self.content.bind('<Configure>', self.layout)
        self.canvas.bind('<Configure>', self.layout)
        self.bind_all('<MouseWheel>', self.wheel, add='+')

    def layout(self, event=None):
        width = self.canvas.winfo_width()
        height = max(self.canvas.winfo_height(), self.content.winfo_reqheight())
        self.canvas.itemconfigure(self.item, width=width, height=height)
        self.canvas.configure(scrollregion=(0, 0, width, height))

    def wheel(self, event):
        if not self.winfo_ismapped(): return
        hovered = self.winfo_containing(event.x_root, event.y_root)
        # Track lists and logs retain their own native mouse-wheel behavior.
        if isinstance(hovered, (tk.Listbox, tk.Text, ttk.Treeview)): return
        while hovered is not None:
            if hovered == self:
                self.canvas.yview_scroll(-int(event.delta / 120), 'units')
                return
            hovered = getattr(hovered, 'master', None)


class App:
    def __init__(self, root, register_hotkeys=True, load_library=True, settings_path=None):
        self.root = root
        self.closed = False
        self.last_result = None
        self.settings_path = Path(settings_path) if settings_path else (
            Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'YuanQinToolbox' / 'settings.json' if register_hotkeys else None)
        self.preferences = read_preferences(self.settings_path) if self.settings_path else {}
        self.save_timer = None
        self.loading_library = load_library
        root.title('原琴工具箱 3.4 · 转换与演奏')
        height = min(900, max(640, root.winfo_screenheight() - 100))
        root.geometry(f'1060x{height}')
        root.minsize(920, 640)
        setup(root)
        header = ttk.Frame(root, padding=(26, 20, 26, 16)); header.pack(fill='x')
        brand = ttk.Frame(header); brand.pack(side='left')
        ttk.Label(brand, text='原琴工具箱', style='Brand.TLabel').pack(anchor='w')
        ttk.Label(brand, text='让喜欢的旋律，在提瓦特响起。', style='Muted.TLabel').pack(anchor='w', pady=(4, 0))
        self.switch_after = tk.BooleanVar(value=True)
        ttk.Button(header, text='打开游戏悬浮窗  ↗', style='Primary.TButton', command=lambda:self.overlay.show()).pack(side='right')
        ttk.Checkbutton(header, text='转换后进入演奏页', variable=self.switch_after).pack(side='right', padx=18)
        self.tabs = ttk.Notebook(root); self.tabs.pack(fill='both', expand=True, padx=22, pady=(0, 18))
        self.convert_page = ScrollPage(self.tabs)
        self.play_page = ScrollPage(self.tabs)
        self.tabs.add(self.convert_page, text='01   MIDI 转换')
        self.tabs.add(self.play_page, text='02   曲库与演奏')
        self.converter = ConverterPane(root, parent=self.convert_page.content,
            on_complete=self.converted, can_convert=self.can_convert,
            local_folder=application_dir()/'曲谱')
        self.player = PlayerPane(root, parent=self.play_page.content,
            register_hotkeys=register_hotkeys, can_play=self.can_play,
            library_dir=lambda: Path(self.converter.score_dir.get()),
            initial=player_preferences(self.preferences.get('player')))
        if not register_hotkeys:
            self.player.hotkey_text.set('预览模式：未启用快捷键和演奏。')
            self.player.apply_button.configure(state='disabled')
        self.overlay = Overlay(self,start_hidden=True)
        self.restore_preferences()
        self.player.library_changed = self.schedule_save
        for variable in self.preference_variables().values(): variable.trace_add('write', self.schedule_save)
        self.player.list.bind('<<TreeviewSelect>>', self.schedule_save, add='+')
        self.overlay.window.bind('<Configure>', self.overlay_moved, add='+')
        root.protocol('WM_DELETE_WINDOW', self.close)
        if load_library: root.after(150, self.load_existing)

    def can_convert(self):
        return not self.player.active

    def can_play(self):
        return not self.converter.busy

    def load_existing(self):
        if self.closed: return
        remembered = path_list(self.preferences.get('paths'))
        self.player.add_paths(Path(path) for path in remembered if Path(path).is_file())
        folders = [Path(self.converter.score_dir.get()), application_dir()/'曲谱']
        for folder in folders:
            if folder.is_dir(): self.player.add_paths(sorted(folder.glob('*.gs2')))
        for value in path_list(self.preferences.get('folders')):
            folder = Path(value)
            self.player.folders.add(str(folder))
            try:
                if folder.is_dir(): self.player.add_paths(sorted(folder.rglob('*.gs2')))
            except OSError as exc: logging.getLogger('yuanqin').warning('曲库目录读取失败：%s', exc)
        selected = self.preferences.get('selected')
        for iid, path in self.player.paths.items():
            if str(path.resolve()) == selected:
                self.player.list.selection_set(iid); self.player.list.see(iid); self.player.preview(); break
        self.loading_library = False
        self.schedule_save()

    def preference_variables(self):
        values = {'switch_after': self.switch_after}
        for name in ('speed', 'countdown', 'gap', 'continuous', 'three_rows', 'play_key', 'stop_key'):
            values['player.' + name] = getattr(self.player, name)
        for name in ('speed', 'policy', 'drums', 'auto_shift', 'arrangement', 'score_dir'):
            values['converter.' + name] = getattr(self.converter, name)
        return values

    def restore_preferences(self):
        converter = self.preferences.get('converter')
        if not isinstance(converter, dict): converter = {}
        for name in ('drums', 'auto_shift'):
            if isinstance(converter.get(name), bool): getattr(self.converter, name).set(converter[name])
        for name, choices in [('policy', POLICIES), ('arrangement', ARRANGEMENTS)]:
            if isinstance(converter.get(name), str) and converter[name] in choices: getattr(self.converter, name).set(converter[name])
        value = converter.get('score_dir')
        if isinstance(value, str) and value.strip(): self.converter.score_dir.set(value)
        try:
            speed = float(converter.get('speed', 1))
            if math.isfinite(speed) and .25 <= speed <= 4: self.converter.speed.set(str(speed))
        except (TypeError, ValueError): pass
        self.converter.shift_mode()
        if isinstance(self.preferences.get('switch_after'), bool): self.switch_after.set(self.preferences['switch_after'])
        position = self.preferences.get('overlay_position')
        if isinstance(position, list) and len(position) == 2 and all(type(v) is int for v in position):
            x = min(max(0, position[0]), max(0, self.root.winfo_screenwidth()-420))
            y = min(max(0, position[1]), max(0, self.root.winfo_screenheight()-200))
            self.overlay.window.geometry(f'+{x}+{y}')

    def overlay_moved(self, event):
        if event.widget == self.overlay.window: self.schedule_save()

    def schedule_save(self, *unused):
        if self.closed or self.loading_library or not self.settings_path: return
        if self.save_timer: self.root.after_cancel(self.save_timer)
        self.save_timer = self.root.after(700, self.save_preferences)

    def save_preferences(self):
        self.save_timer = None
        if not self.settings_path or self.loading_library: return
        try:
            values = {name: variable.get() for name, variable in self.preference_variables().items()}
            player = player_preferences({name.split('.', 1)[1]: value for name, value in values.items() if name.startswith('player.')})
            converter = {name.split('.', 1)[1]: value for name, value in values.items() if name.startswith('converter.')}
            selected = self.player.list.selection()
            state = dict(schema=1, player=player, converter=converter, switch_after=self.switch_after.get(),
                         paths=[str(path.resolve()) for path in self.player.paths.values()],
                         folders=sorted(self.player.folders),
                         selected=str(self.player.paths[selected[0]].resolve()) if selected else None,
                         overlay_position=[self.overlay.window.winfo_x(), self.overlay.window.winfo_y()])
            write_preferences(self.settings_path, state)
        except (OSError, ValueError, tk.TclError) as exc:
            logging.getLogger('yuanqin').warning('保存设置失败：%s', exc)

    def converted(self, result):
        self.last_result = result
        paths = [row['输出'] for row in result['rows'] if row['结果'] == '成功']
        if not paths: return
        self.player.add_paths(paths)
        self.player.status.set(f'已收到 {len(paths)} 份曲谱，可先“试听前20秒”，再切回原神演奏。')
        if self.switch_after.get(): self.tabs.select(self.play_page)

    def close(self):
        if self.converter.busy:
            messagebox.showinfo('正在转换', '请等待本批转换结束后再关闭窗口。')
            return
        self.closed = True
        if self.save_timer: self.root.after_cancel(self.save_timer)
        self.save_preferences()
        self.converter.shutdown()
        self.overlay.close()
        self.player.close()


if __name__ == '__main__':
    try:
        log = logging.getLogger('yuanqin');log.setLevel(logging.INFO)
        handler = RotatingFileHandler(application_dir()/'原琴运行日志.txt',maxBytes=1_000_000,backupCount=1,encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        log.addHandler(handler)
        log.info('start version=3.4 preview=%s', '--preview' in sys.argv)
    except OSError: pass
    root = tk.Tk()
    def report_callback(exc,value,trace):
        logging.getLogger('yuanqin').error('window callback error',exc_info=(exc,value,trace))
        messagebox.showerror('窗口错误',str(value))
    root.report_callback_exception=report_callback
    preview = '--preview' in sys.argv
    app = App(root, register_hotkeys=not preview)
    if '--play' in sys.argv: app.tabs.select(app.play_page)
    if '--main' not in sys.argv:
        def floating_start():
            app.overlay.show()
            root.withdraw()
        root.after(300,floating_start)
    root.mainloop()
