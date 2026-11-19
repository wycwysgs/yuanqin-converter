"""An ordinary topmost companion window with click-driven game refocusing."""
from pathlib import Path
import ctypes
import logging
import subprocess
import sys
import tkinter as tk
from tkinter import ttk
from wininput import find_games, activate_game, foreground_game, process_elevated, preflight
from theme import setup, list_colors, dark_titlebar


class Overlay:
    def __init__(self, suite, start_hidden=False):
        self.suite, self.player, self.root = suite, suite.player, suite.root
        self.closing, self.pending = False, False
        self.pending_action = 'play'
        self.target = None
        self.ids, self.signature = [], None
        self.window = tk.Toplevel(self.root)
        setup(self.root)
        dark_titlebar(self.window)
        self.window.title('原琴 · 游戏悬浮窗')
        self.window.attributes('-topmost', True)
        self.window.resizable(False, False)
        x = max(0, self.root.winfo_screenwidth() - 455)
        height=min(640,max(540,self.root.winfo_screenheight()-140))
        self.window.geometry(f'420x{height}+{x}+80')
        self.window.protocol('WM_DELETE_WINDOW', self.hide)
        frame = ttk.Frame(self.window, padding=(14, 12)); frame.pack(fill='both', expand=True)
        row = ttk.Frame(frame); row.pack(fill='x')
        ttk.Label(row, text='原琴', font=('Microsoft YaHei UI', 17, 'bold')).pack(side='left')
        ttk.Label(row, text='  游戏演奏', style='Accent.TLabel', font=('Microsoft YaHei UI', 10)).pack(side='left', pady=(6, 0))
        ttk.Button(row, text='打开工具箱 ↗', style='Small.TButton', command=self.show_main).pack(side='right')
        self.game_status = tk.StringVar(value='正在检查原神窗口…')
        ttk.Label(frame, textvariable=self.game_status, wraplength=390, style='Muted.TLabel', font=('Microsoft YaHei UI',9)).pack(anchor='w', pady=(5,0))
        row = ttk.Frame(frame); row.pack(fill='x', pady=4)
        ttk.Button(row, text='检查连接', style='Small.TButton', command=self.diagnose).pack(side='left')
        self.admin_button = ttk.Button(row, text='管理员重开', style='Small.TButton', command=self.relaunch_admin)
        self.admin_button.pack(side='left', padx=6)
        ttk.Button(row, text='收起工具箱', style='Small.TButton', command=self.root.withdraw).pack(side='left')
        self.search = tk.StringVar()
        row = ttk.Frame(frame); row.pack(fill='x', pady=(4,3))
        ttk.Label(row, text='搜索曲名').pack(side='left', padx=(0,6))
        entry = ttk.Entry(row, textvariable=self.search)
        entry.pack(side='left', fill='x', expand=True)
        box = ttk.Frame(frame); box.pack(fill='both', expand=True, pady=5)
        self.list = tk.Listbox(box, height=1, exportselection=False, font=('Microsoft YaHei UI',11))
        list_colors(self.list)
        self.list.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(box, command=self.list.yview);scroll.pack(side='right', fill='y')
        self.list.configure(yscrollcommand=scroll.set)
        self.list.bind('<<ListboxSelect>>', self.select)
        self.search.trace_add('write', lambda *_:self.refresh(force=True))
        self.song = tk.StringVar(value='请选择曲谱')
        ttk.Label(frame, textvariable=self.song, wraplength=390, font=('Microsoft YaHei UI',11,'bold')).pack(anchor='w', pady=(3,0))
        self.mode_button = ttk.Checkbutton(frame, text='三排模式（不勾选为两排）',
            variable=self.player.three_rows, command=self.player.preview)
        self.mode_button.pack(anchor='w', pady=(4,0))
        row = ttk.Frame(frame); row.pack(fill='x', pady=(6,0))
        self.listen_button = ttk.Button(row, text='试听前20秒', style='Small.TButton', command=self.listen)
        self.listen_button.pack(side='left')
        ttk.Button(row, text='停止试听', style='Small.TButton', command=self.player.stop_listen).pack(side='left', padx=6)
        self.test_button = ttk.Button(row, text='测试琴键 A', style='Small.TButton', command=lambda: self.start(test=True))
        self.test_button.pack(side='left')
        row = ttk.Frame(frame); row.pack(fill='x', pady=8)
        self.start_button = ttk.Button(row, text='开始 / 继续', style='Primary.TButton', command=self.start)
        self.start_button.pack(side='left', fill='x', expand=True)
        self.pause_button = ttk.Button(row, text='暂停', command=self.pause)
        self.pause_button.pack(side='left', padx=6)
        self.stop_button = ttk.Button(row, text='停止', style='Danger.TButton', command=self.stop)
        self.stop_button.pack(side='left')
        ttk.Label(frame, textvariable=self.player.status, wraplength=390, font=('Microsoft YaHei UI',9)).pack(anchor='w')
        self.progress = ttk.Progressbar(frame, mode='determinate');self.progress.pack(fill='x', pady=6)
        ttk.Label(frame, textvariable=self.player.position, style='Muted.TLabel', font=('Consolas',10)).pack(anchor='w')
        self.keys = tk.StringVar()
        ttk.Label(frame, textvariable=self.keys, wraplength=390, style='Muted.TLabel', font=('Microsoft YaHei UI',9)).pack(anchor='w', pady=(4,0))
        self.notice = tk.StringVar(value='打开乐器界面并关闭聊天框；游戏用窗口/无边框。')
        ttk.Label(frame, textvariable=self.notice, wraplength=390, foreground='#ebc594', font=('Microsoft YaHei UI',9)).pack(anchor='w', pady=(4,0))
        self.diagnose()
        self.refresh(force=True)
        self.tick_timer = self.root.after(150, self.tick)
        if start_hidden:self.window.withdraw()

    def show(self):
        self.window.deiconify()
        self.window.lift()
        self.window.attributes('-topmost', True)
        self.diagnose()

    def hide(self):
        # Keep a reachable control surface when the floating window is dismissed.
        self.show_main()
        self.window.withdraw()

    def show_main(self):
        self.root.deiconify()
        self.root.lift()

    def diagnose(self):
        games = find_games()
        self.target = games[0] if len(games) == 1 else None
        if not games: text = '未检测到原神，请启动游戏后再点“检查连接”。'
        elif len(games) > 1:text = '检测到多个原神窗口，请只保留要演奏的游戏窗口。'
        else:
            problem = preflight(self.target)
            text = problem or ('原神已连接 · 管理员权限一致' if process_elevated() else '已找到原神 · 可准备演奏')
        self.game_status.set(text)
        self.admin_button.configure(state='disabled' if process_elevated() else 'normal')
        logging.getLogger('yuanqin').info('preflight: %s',text)
        return self.target

    def refresh(self, force=False):
        signature = tuple((iid,str(path)) for iid,path in self.player.paths.items())
        if not force and signature == self.signature: return
        self.signature = signature
        selected = self.player.list.selection()
        selected = selected[0] if selected else None
        query = self.search.get().strip().casefold()
        self.ids = [iid for iid in self.player.paths if query in self.player.song_name(iid).casefold()]
        self.list.delete(0,'end')
        for iid in self.ids:self.list.insert('end',self.player.song_name(iid))
        if selected in self.ids:
            index=self.ids.index(selected);self.list.selection_set(index);self.list.see(index)

    def select(self, event=None):
        if self.player.active:
            self.notice.set('先停止演奏再更换曲谱。');return
        selected=self.list.curselection()
        if not selected or selected[0]>=len(self.ids):return
        iid=self.ids[selected[0]]
        self.player.list.selection_set(iid);self.player.list.see(iid)
        self.player.preview()

    def listen(self):
        if self.pending: return
        self.select()
        self.player.listen()

    def start(self, test=False):
        if self.player.preview_mode:
            self.notice.set('当前是预览模式，不会发送琴键。');return
        if self.pending:return
        if test and self.player.active:
            self.notice.set('请先停止演奏，再测试琴键。');return
        if not self.suite.can_play():
            self.notice.set('正在转换，请等待完成。');return
        if self.player.active and self.player.player.state == 'countdown':return
        self.select() if not self.player.active else None
        target=self.diagnose()
        if not target:return
        problem=preflight(target)
        if problem:
            self.notice.set(problem);return
        if not test and not self.player.active and not self.player.list.selection():
            self.notice.set('请先在曲谱列表中选择一首。');return
        self.notice.set('正在切回原神；请确认已打开乐器演奏界面。')
        self.pending=True
        self.pending_action = 'test' if test else 'play'
        activate_game(target)
        self.await_focus(target,0)

    def await_focus(self,target,attempt):
        if self.closing or not self.pending:return
        if foreground_game()!=target:
            if attempt<15:
                self.root.after(50,lambda:self.await_focus(target,attempt+1));return
            self.pending=False
            self.notice.set('Windows 未切回原神。请自己点击游戏画面，再按开始快捷键。');return
        # Let the mouse button release settle before scheduling notes.
        self.root.after(120,self.begin)

    def begin(self):
        if self.closing or not self.pending:return
        self.pending=False
        if foreground_game()!=self.target:
            self.notice.set('焦点已改变，请重新点击“开始”。');return
        if self.pending_action == 'test':
            self.player.test_key()
            self.notice.set('3秒后只测试一次 A；听到琴声说明游戏收到按键。')
            return
        if self.player.active:
            if self.player.player.state=='paused':self.player.toggle(allow_button=True)
        else:self.player.toggle(allow_button=True)
        self.notice.set('演奏中可随时点“停止”；切出游戏会自动暂停。')

    def pause(self):
        self.pending=False
        if self.player.player.state=='playing':self.player.player.toggle_pause()
        self.notice.set('已暂停。点“开始 / 继续”会切回原神后继续。')

    def stop(self):
        self.pending=False
        self.player.stop()
        self.notice.set('已停止；再次开始将从曲首演奏。')

    def relaunch_admin(self):
        if self.player.preview_mode:
            self.notice.set('预览模式不请求管理员权限。');return
        if self.suite.converter.busy or self.player.active:
            self.notice.set('请等待转换完成并停止演奏，再重开程序。');return
        if process_elevated():return
        if getattr(sys,'frozen',False):
            args=['--overlay'];executable=sys.executable
        else:
            args=[str(Path(__file__).with_name('app.py')),'--overlay'];executable=sys.executable
        shell=ctypes.WinDLL('shell32',use_last_error=True)
        shell.ShellExecuteW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_int]
        shell.ShellExecuteW.restype=ctypes.c_void_p
        result=shell.ShellExecuteW(None,'runas',executable,subprocess.list2cmdline(args),str(Path(executable).parent),1)
        if result and result>32:
            self.suite.close()
        else:self.notice.set('未完成管理员重开。你也可以关闭程序，再右键快捷方式选择“以管理员身份运行”。')

    def tick(self):
        if self.closing or self.suite.closed:return
        self.refresh()
        selected=self.player.list.selection()
        if selected and selected[0] in self.player.paths:
            self.song.set(self.player.song_name(selected[0]))
        self.keys.set(self.player.hotkey_text.get())
        self.progress.configure(maximum=float(self.player.progress['maximum']),value=float(self.player.progress['value']))
        self.list.configure(state='disabled' if self.player.active else 'normal')
        self.mode_button.configure(state='disabled' if self.player.active else 'normal')
        self.start_button.configure(state='disabled' if self.pending else 'normal')
        self.listen_button.configure(state='disabled' if self.player.active or self.pending else 'normal')
        self.test_button.configure(state='disabled' if self.player.active or self.pending else 'normal')
        self.tick_timer = self.root.after(150,self.tick)

    def close(self):
        self.pending=False;self.closing=True
        self.root.after_cancel(self.tick_timer)
        self.window.destroy()
