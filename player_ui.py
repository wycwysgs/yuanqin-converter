import math
import os
from pathlib import Path
import queue
import sys
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from score import load_score, adapt_score, Score
from audition import Audition
from song_name import clean_title, source_rank
from engine import Player, Settings
from wininput import Keyboard, Hotkeys, HOTKEY_CHOICES, foreground_game, modifiers_held, preflight
from theme import setup, card, surface

DEFAULT_SCORE = Path('C:/Program Files/BetterGI/User/JsScript/YuanQinAssistant/assets/score')
ACTIVE = {'countdown', 'playing', 'paused'}


def clock(seconds):
    return f'{int(seconds)//60:02d}:{int(seconds)%60:02d}'


class App:
    def __init__(self, root, register_hotkeys=True, parent=None, can_play=lambda: True, library_dir=None, initial=None):
        self.root = root
        self.can_play = can_play
        self.library_dir = library_dir or (lambda: DEFAULT_SCORE)
        self.events = queue.Queue()
        self.paths, self.cache, self.run_ids = {}, {}, []
        self.folders = set()
        self.library_changed = lambda: None
        self.audition = Audition(self.events.put)
        self.serial, self.active, self.closing = 0, False, False
        self.preview_mode = not register_hotkeys
        self.hotkey_pending = False
        self.hotkeys = None
        self.player = Player(Keyboard(), foreground_game, modifiers_held, self.events.put, check_target=preflight)
        if parent is None:
            root.title('原琴播放器 · GS2 游戏演奏')
            root.geometry('940x720'); root.minsize(860, 660)
            root.protocol('WM_DELETE_WINDOW', self.close)
        setup(root)
        frame = ttk.Frame(parent if parent is not None else root, padding=(2, 6, 8, 12)); frame.pack(fill='both', expand=True)
        heading = ttk.Frame(frame); heading.pack(fill='x', pady=(0, 14))
        ttk.Label(heading, text='今天想弹哪一首？', style='Title.TLabel').pack(side='left')
        ttk.Label(heading, text='原神 · 乐器演奏', style='Badge.TLabel').pack(side='right', pady=4)
        library_card = card(frame, '我的曲库'); library_card.pack(fill='both', expand=True, pady=(0, 12))
        toolbar = ttk.Frame(library_card); toolbar.pack(fill='x')
        self.edit_buttons = []
        for text, command in [('添加曲谱…', self.open), ('添加文件夹…', self.folder),
                              ('读取助手曲谱', self.library), ('移除选中', self.remove), ('清空', self.clear)]:
            button = ttk.Button(toolbar, text=text, command=command, style='Primary.TButton' if not self.edit_buttons else 'TButton')
            button.pack(side='left', padx=(0, 7)); self.edit_buttons.append(button)
        box = ttk.Frame(library_card); box.pack(fill='both', expand=True, pady=10)
        self.list = ttk.Treeview(box, columns=('name', 'length'), show='headings', height=7, selectmode='browse')
        self.list.heading('name', text='曲谱（点击选择一首）'); self.list.heading('length', text='时长 / 状态')
        self.list.column('name', width=670); self.list.column('length', width=130, stretch=False)
        self.list.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(box, command=self.list.yview); scroll.pack(side='right', fill='y')
        self.list.configure(yscrollcommand=scroll.set)
        self.list.bind('<<TreeviewSelect>>', self.preview)
        self.info = tk.StringVar(value='添加或读取曲谱后，先在原神中打开乐器演奏界面。')
        ttk.Label(library_card, textvariable=self.info, style='Muted.TLabel', wraplength=810).pack(anchor='w')
        settings_card = card(frame, '演奏设置'); settings_card.pack(fill='x', pady=(0, 12))
        row = ttk.Frame(settings_card); row.pack(fill='x', pady=(0, 8))
        self.speed, self.countdown, self.gap = tk.StringVar(value='1.0'), tk.StringVar(value='3'), tk.StringVar(value='2')
        self.inputs = []
        for text, variable, start, end, increment in [('速度倍率', self.speed, 0.25, 4, 0.05),
                ('开始倒计时（秒）', self.countdown, 1, 15, 1), ('连播间隔（秒）', self.gap, 0, 30, 1)]:
            ttk.Label(row, text=text).pack(side='left', padx=(0, 6))
            widget = ttk.Spinbox(row, from_=start, to=end, increment=increment, textvariable=variable, width=5)
            widget.pack(side='left', padx=(0, 18)); self.inputs.append(widget)
        self.continuous = tk.BooleanVar(value=False)
        mode_row = ttk.Frame(settings_card); mode_row.pack(fill='x')
        self.continuous_button = ttk.Checkbutton(mode_row, text='连播曲库中的全部歌曲', variable=self.continuous)
        self.continuous_button.pack(anchor='w')
        self.three_rows = tk.BooleanVar(value=True)
        self.mode_button = ttk.Checkbutton(mode_row, text='三排模式（不勾选为两排）',
                                          variable=self.three_rows, command=self.preview)
        self.continuous_button.pack_configure(side='left')
        self.mode_button.pack(side='left', padx=28)
        row = ttk.Frame(settings_card); row.pack(fill='x', pady=(10, 6))
        self.play_key, self.stop_key = tk.StringVar(value='F8'), tk.StringVar(value='F9')
        self.hotkey_inputs = []
        for text, variable in [('开始 / 暂停', self.play_key), ('立即停止', self.stop_key)]:
            ttk.Label(row, text=text).pack(side='left', padx=(0, 6))
            widget = ttk.Combobox(row, textvariable=variable, values=HOTKEY_CHOICES, state='readonly', width=5)
            widget.pack(side='left', padx=(0, 14)); self.hotkey_inputs.append(widget)
        self.apply_button = ttk.Button(row, text='应用快捷键', command=self.apply_hotkeys)
        self.apply_button.pack(side='left')
        self.hotkey_text = tk.StringVar(value='正在注册快捷键…')
        ttk.Label(settings_card, textvariable=self.hotkey_text, style='Muted.TLabel', wraplength=810).pack(anchor='w')
        controls = card(frame); controls.pack(fill='x', before=settings_card, pady=(0, 12))
        row = ttk.Frame(controls); row.pack(fill='x', pady=(0, 10))
        self.play_button = ttk.Button(row, text='准备演奏 / 暂停', style='Primary.TButton', command=self.toggle)
        self.play_button.pack(side='left', ipadx=12)
        ttk.Button(row, text='停止', style='Danger.TButton', command=self.stop).pack(side='left', padx=10)
        ttk.Button(row, text='打开曲谱目录', style='Small.TButton', command=self.open_folder).pack(side='right')
        self.listen_button = ttk.Button(row, text='试听前20秒', command=self.listen)
        self.listen_button.pack(side='left', padx=(4, 6))
        ttk.Button(row, text='停止试听', command=self.stop_listen).pack(side='left')
        self.test_button = ttk.Button(settings_card, text='测试琴键 A', style='Small.TButton', command=self.test_key)
        self.test_button.pack(anchor='e', pady=(4, 0))
        self.status = tk.StringVar(value='等待选择曲谱')
        ttk.Label(controls, textvariable=self.status, wraplength=810).pack(anchor='w')
        self.progress = ttk.Progressbar(controls, mode='determinate'); self.progress.pack(fill='x', pady=8)
        self.position = tk.StringVar(value='00:00 / 00:00')
        ttk.Label(controls, textvariable=self.position, style='Muted.TLabel', font=('Consolas', 10)).pack(anchor='w')
        ttk.Label(frame, text='切出游戏或按住 Ctrl / Alt / Shift 等修饰键会自动暂停；切回游戏后按开始键继续。\n'
                  '程序只检查原神是否在前台，不能判断是否已打开乐器界面；开始前请关闭聊天框。',
                  style='Muted.TLabel', wraplength=810).pack(anchor='w', pady=(12, 0))
        for panel in (library_card, settings_card, controls): surface(panel)
        if initial:
            for name in ('speed', 'countdown', 'gap', 'continuous', 'three_rows', 'play_key', 'stop_key'):
                if name in initial: getattr(self, name).set(initial[name])
        if register_hotkeys: self.apply_hotkeys()
        self.poll_timer = root.after(40, self.poll)

    def apply_hotkeys(self):
        if self.active: return
        if self.play_key.get() == self.stop_key.get():
            messagebox.showerror('快捷键冲突', '开始和停止不能使用同一个快捷键。'); return
        if self.hotkeys: self.hotkeys.close()
        self.hotkey_pending = True
        self.hotkeys = Hotkeys(self.events.put, self.play_key.get(), self.stop_key.get())

    def add_paths(self, paths):
        if self.active: return
        seen = {os.path.normcase(str(path.resolve())) for path in self.paths.values()}
        songs = {self.song_name(iid).casefold(): iid for iid in self.paths}
        added = []
        for value in paths:
            path = Path(value)
            identity = os.path.normcase(str(path.resolve()))
            if identity in seen or path.suffix.lower() != '.gs2': continue
            seen.add(identity)
            name = clean_title(path.stem)
            existing = songs.get(name.casefold())
            if existing is not None:
                old = self.paths[existing]
                if source_rank(path.stem) > source_rank(old.stem):
                    self.paths[existing] = path
                    self.cache.pop(existing, None)
                    self.list.item(existing, values=(name, '未读取'))
                continue
            self.serial += 1
            iid = str(self.serial); self.paths[iid] = path
            songs[name.casefold()] = iid
            self.list.insert('', 'end', iid=iid, values=(name, '未读取'))
            added.append(iid)
        if added:
            self.list.selection_set(added[0]); self.list.focus(added[0]); self.list.see(added[0])
        self.status.set(f'共 {len(self.paths)} 首曲谱')
        self.preview()
        self.library_changed()

    def song_name(self, iid):
        return clean_title(self.paths[iid].stem)

    def playback_score(self, iid):
        return adapt_score(self.get_score(iid), self.three_rows.get())

    def open(self):
        if self.active: return
        self.add_paths(filedialog.askopenfilenames(title='选择 GS2 曲谱（可多选）',
            initialdir=str(self.library_dir()) if Path(self.library_dir()).is_dir() else None,
            filetypes=[('原琴曲谱', '*.gs2')]))

    def folder(self):
        if self.active: return
        folder = filedialog.askdirectory(title='添加文件夹及子文件夹中的 GS2',
            initialdir=str(self.library_dir()) if Path(self.library_dir()).is_dir() else None)
        if folder:
            try:
                self.folders.add(str(Path(folder).resolve()))
                self.add_paths(sorted(p for p in Path(folder).rglob('*') if p.is_file() and p.suffix.lower() == '.gs2'))
            except Exception as exc: messagebox.showerror('无法读取目录', str(exc))

    def library(self):
        if self.active: return
        library = Path(self.library_dir())
        if library.is_dir(): self.add_paths(sorted(library.glob('*.gs2')))
        else: messagebox.showinfo('未找到助手目录', '请用“添加文件夹”选择你保存 .gs2 的位置。')

    def get_score(self, iid):
        path = self.paths[iid]
        stamp = (path.stat().st_mtime_ns, path.stat().st_size)
        if iid not in self.cache or self.cache[iid][0] != stamp:
            score = load_score(path)
            self.cache[iid] = stamp, score
        score = self.cache[iid][1]
        self.list.set(iid, 'length', clock(score.seconds))
        return score

    def preview(self, event=None):
        if self.active: return
        selected = self.list.selection()
        if not selected: return
        try:
            score = self.playback_score(selected[0])
            warning = f' · 略过{score.skipped}个无法映射的音符' if score.skipped else ''
            mode = '三排模式' if self.three_rows.get() else '两排模式'
            self.info.set(f'{score.title[:50]} · {clock(score.seconds)} · {score.notes} 个琴键音符 · {mode}' + warning)
        except Exception as exc:
            self.list.set(selected[0], 'length', '读取失败')
            self.info.set('无法读取：' + str(exc))

    def remove(self):
        if self.active: return
        for iid in self.list.selection():
            self.paths.pop(iid, None); self.cache.pop(iid, None); self.list.delete(iid)
        self.info.set('点击一首曲谱后，按开始快捷键演奏。')
        self.status.set(f'共 {len(self.paths)} 首曲谱')
        self.library_changed()

    def clear(self):
        if self.active: return
        for iid in self.list.get_children(): self.list.delete(iid)
        self.paths.clear(); self.cache.clear()
        self.folders.clear()
        self.info.set('添加或读取曲谱后，先在原神中打开乐器演奏界面。')
        self.status.set('已清空列表')
        self.library_changed()

    def listen(self):
        if self.active:
            self.status.set('先停止游戏演奏，再试听。'); return
        if not self.can_play():
            self.status.set('请等待转换完成后试听。'); return
        selected = self.list.selection()
        if not selected:
            self.status.set('请先选择一首曲谱。'); return
        try:
            speed = float(self.speed.get())
            if not math.isfinite(speed) or not .25 <= speed <= 4: raise ValueError('速度倍率应为0.25–4。')
            self.audition.start(self.playback_score(selected[0]), speed)
            self.status.set('正在生成试听音频（合成音色，不向游戏发送按键）…')
        except Exception as exc: self.status.set('无法试听：' + str(exc))

    def stop_listen(self):
        self.audition.stop()
        self.status.set('已停止试听。')

    def test_key(self):
        if self.preview_mode:
            self.status.set('预览模式不会发送测试琴键。'); return
        if self.active or not self.can_play():
            self.status.set('先停止演奏并等待转换完成，再测试琴键。'); return
        try:
            target = foreground_game()
            if target:
                issue = preflight(target)
                if issue: raise ValueError(issue)
            self.audition.stop()
            self.run_ids = []
            self.set_active(True)
            sample = Score(Path('琴键自检'), '测试琴键 A（仅一次）', ((0., ('A',)),), .2, 1)
            if not self.player.start([sample], Settings(countdown=3, gap=0)):
                self.set_active(False)
        except Exception as exc:
            self.set_active(False); self.status.set(str(exc))

    def open_folder(self):
        folder = Path(self.library_dir())
        selected = self.list.selection()
        if selected: folder = self.paths[selected[0]].parent
        if folder.is_dir(): os.startfile(str(folder))

    def set_active(self, value):
        self.active = value
        for widget in self.edit_buttons + self.inputs + [self.continuous_button, self.mode_button, self.apply_button, self.listen_button, self.test_button]:
            widget.configure(state='disabled' if value else 'normal')
        for widget in self.hotkey_inputs: widget.configure(state='disabled' if value else 'readonly')
        self.play_button.configure(text='开始 / 暂停' if value else '准备演奏 / 暂停')

    def toggle(self, allow_button=False):
        if self.preview_mode:
            self.status.set('界面预览模式，不会发送按键。'); return
        if not self.can_play():
            self.status.set('正在转换，请等待完成后再演奏。'); return
        if self.active:
            self.player.toggle_pause(); return
        if not allow_button and (not self.hotkeys or not self.hotkeys.ready.is_set()):
            self.status.set('开始前必须注册可用的开始键和停止键；请在上方更换或应用快捷键。'); return
        try:
            target = foreground_game()
            if target:
                issue = preflight(target)
                if issue: raise ValueError(issue)
            ids = list(self.paths) if self.continuous.get() else list(self.list.selection())
            if not ids: raise ValueError('请先添加并选择曲谱。')
            speed, countdown, gap = float(self.speed.get()), float(self.countdown.get()), float(self.gap.get())
            if not math.isfinite(speed) or not 0.25 <= speed <= 4: raise ValueError('速度倍率应为0.25–4。')
            if not math.isfinite(countdown) or not 1 <= countdown <= 15: raise ValueError('倒计时应为1–15秒。')
            if not math.isfinite(gap) or not 0 <= gap <= 30: raise ValueError('连播间隔应为0–30秒。')
            scores = []
            for iid in ids:
                try: scores.append(self.playback_score(iid))
                except Exception as exc:
                    self.list.set(iid, 'length', '读取失败')
                    raise ValueError(f'{self.paths[iid].name}：{exc}') from exc
            self.run_ids = ids
            self.audition.stop()
            self.set_active(True)
            self.progress.configure(value=0)
            self.position.set('00:00 / 00:00')
            if not self.player.start(scores, Settings(speed, countdown, gap)):
                self.set_active(False)
        except Exception as exc: self.status.set(str(exc))

    def stop(self):
        self.audition.stop()
        self.player.stop()
        self.status.set('已停止；再次开始会从曲首播放。')

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event['kind']
                if kind in ('state', 'notice', 'error', 'finished', 'hotkeys'):
                    logging.getLogger('yuanqin').info('%s: %s', kind, event.get('message', ''))
                if kind == 'toggle': self.toggle()
                elif kind == 'stop': self.stop()
                elif kind == 'hotkeys':
                    self.hotkey_pending = False
                    self.hotkey_text.set(event['message'])
                elif kind in ('state', 'notice', 'error', 'finished'): self.status.set(event['message'])
                elif kind == 'audition':
                    if not self.active and event.get('generation') == self.audition.generation: self.status.set(event['message'])
                elif kind == 'song':
                    if event['index'] < len(self.run_ids):
                        self.list.selection_set(self.run_ids[event['index']])
                        self.list.see(self.run_ids[event['index']])
                    self.info.set('当前演奏：' + event['title'])
                    self.progress.configure(maximum=max(event['seconds'], .01), value=0)
                elif kind == 'progress':
                    self.progress.configure(value=event['seconds'])
                    self.position.set(clock(event['seconds']) + ' / ' + clock(event['total']))
                elif kind == 'idle': self.set_active(False)
        except queue.Empty: pass
        if not self.closing: self.poll_timer = self.root.after(40, self.poll)

    def close(self):
        self.audition.stop()
        if self.audition.thread: self.audition.thread.join(timeout=1)
        self.player.stop()
        if self.player.thread: self.player.thread.join(timeout=1)
        if self.hotkeys: self.hotkeys.close()
        self.closing = True
        self.root.after_cancel(self.poll_timer)
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    preview = '--preview' in sys.argv
    app = App(root, register_hotkeys=not preview)
    if preview: app.hotkey_text.set('界面预览模式：未启用全局快捷键和演奏。')
    root.after(150, app.library)
    root.mainloop()
