import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from converter import load, duration, arrange_notes, suggest, white_rate
from batch import Job, Options, run_batch
from theme import setup, card, surface, list_colors, FIELD, MUTED, TEXT

DEFAULT_SCORE = 'C:/Program Files/BetterGI/User/JsScript/YuanQinAssistant/assets/score'
POLICIES = {'就近修正（向下）': 'nearest', '向上修正': 'up', '忽略半音': 'skip'}
ARRANGEMENTS = {'完整伴奏': 'full', '简化伴奏（每组最多3音）': 'simple', '主旋律（优先最高音）': 'melody'}


class App:
    def __init__(self, root, parent=None, on_complete=None, can_convert=lambda: True, local_folder=None):
        self.root = root
        self.on_complete, self.can_convert = on_complete, can_convert
        self.local_folder = Path(local_folder) if local_folder else None
        self.jobs, self.current = {}, None
        self.busy, self.events, self.last_folder = False, queue.Queue(), None
        self.closing = False
        self.serial = 0
        if parent is None:
            root.title('原琴转换器 · 批量 MIDI → GS2')
            root.geometry('960x820')
            root.minsize(860, 760)
            root.protocol('WM_DELETE_WINDOW', self.close)
        setup(root)
        frame = ttk.Frame(parent if parent is not None else root, padding=(2, 6, 8, 12))
        frame.pack(fill='both', expand=True)
        heading = ttk.Frame(frame); heading.pack(fill='x', pady=(0, 14))
        ttk.Label(heading, text='把旋律带进游戏', style='Title.TLabel').pack(side='left')
        ttk.Label(heading, text='MIDI  →  GS2', style='Badge.TLabel').pack(side='right', pady=4)
        queue_card = card(frame, '转换队列'); queue_card.pack(fill='both', expand=True, pady=(0, 12))
        toolbar = ttk.Frame(queue_card); toolbar.pack(fill='x')
        self.edit_buttons = []
        for text, command in [('添加 MIDI（可多选）…', self.open), ('添加文件夹…', self.add_folder),
                              ('移除选中', self.remove), ('清空', self.clear)]:
            button = ttk.Button(toolbar, text=text, command=command, style='Primary.TButton' if not self.edit_buttons else 'TButton')
            button.pack(side='left', padx=(0, 8)); self.edit_buttons.append(button)
        self.count = ttk.Label(toolbar, text='0 首'); self.count.pack(side='right')
        box = ttk.Frame(queue_card); box.pack(fill='both', expand=True, pady=(10, 8))
        self.filelist = ttk.Treeview(box, columns=('name', 'status'), show='headings', height=4,
                                     selectmode='extended')
        self.filelist.heading('name', text='歌曲 / MIDI 文件')
        self.filelist.heading('status', text='转换状态')
        self.filelist.column('name', width=640); self.filelist.column('status', width=160, stretch=False)
        self.filelist.pack(side='left', fill='both', expand=True)
        scrollbar = ttk.Scrollbar(box, command=self.filelist.yview); scrollbar.pack(side='right', fill='y')
        self.filelist.configure(yscrollcommand=scrollbar.set)
        self.filelist.bind('<<TreeviewSelect>>', self.preview)
        self.info = ttk.Label(queue_card, text='添加 MIDI 或文件夹开始转换；Ctrl / Shift 可多选。', style='Muted.TLabel', wraplength=810)
        self.info.pack(anchor='w')
        detail_card = card(frame, '歌曲与转换设置'); detail_card.pack(fill='x', pady=(0, 12))
        ttk.Label(detail_card, text='当前歌曲轨道 · 默认全选有音符的轨道，Ctrl / Shift 可多选', style='Muted.TLabel').pack(anchor='w', pady=(0, 6))
        box = ttk.Frame(detail_card); box.pack(fill='x')
        self.tracklist = tk.Listbox(box, height=3, selectmode='extended', exportselection=False,
                                   font=('Microsoft YaHei UI', 10))
        self.tracklist.pack(side='left', fill='x', expand=True)
        list_colors(self.tracklist)
        scrollbar = ttk.Scrollbar(box, command=self.tracklist.yview); scrollbar.pack(side='right', fill='y')
        self.tracklist.configure(yscrollcommand=scrollbar.set)
        row = ttk.Frame(detail_card); row.pack(fill='x', pady=(10, 6))
        ttk.Label(row, text='当前曲名').pack(side='left')
        self.title = tk.StringVar()
        ttk.Entry(row, textvariable=self.title).pack(side='left', fill='x', expand=True, padx=(10, 0))
        options = ttk.Frame(detail_card); options.pack(fill='x', pady=6)
        self.shift, self.speed = tk.StringVar(value='0'), tk.StringVar(value='1.0')
        self.policy = tk.StringVar(value='就近修正（向下）')
        self.drums, self.auto_shift = tk.BooleanVar(value=True), tk.BooleanVar(value=True)
        self.arrangement = tk.StringVar(value='完整伴奏')
        ttk.Label(options, text='输出格式').grid(row=0, column=0, sticky='w')
        ttk.Label(options, text='通用曲谱 · 演奏时选择两排 / 三排', style='Muted.TLabel').grid(row=0, column=1, padx=8, sticky='w')
        ttk.Label(options, text='半音处理').grid(row=0, column=2, sticky='w')
        ttk.Combobox(options, textvariable=self.policy, state='readonly', width=19,
            values=list(POLICIES)).grid(row=0, column=3, padx=8, sticky='w')
        ttk.Label(options, text='当前歌曲移调').grid(row=1, column=0, pady=8, sticky='w')
        part = ttk.Frame(options); part.grid(row=1, column=1, padx=8, sticky='w')
        self.shift_input = ttk.Spinbox(part, from_=-24, to=24, width=5, textvariable=self.shift)
        self.shift_input.pack(side='left')
        self.recommend_button = ttk.Button(part, text='推荐', command=self.recommend)
        self.recommend_button.pack(side='left', padx=8)
        ttk.Label(options, text='速度倍率').grid(row=1, column=2, sticky='w')
        ttk.Spinbox(options, from_=0.25, to=4, increment=0.05, width=8, textvariable=self.speed).grid(row=1, column=3, padx=8, sticky='w')
        ttk.Label(options, text='伴奏模式').grid(row=2, column=0, sticky='w')
        arrangement_input = ttk.Combobox(options, textvariable=self.arrangement, values=list(ARRANGEMENTS), state='readonly', width=27)
        arrangement_input.grid(row=2, column=1, padx=8, sticky='w')
        arrangement_input.bind('<<ComboboxSelected>>', lambda _: self.recommend() if self.auto_shift.get() else None)
        ttk.Label(options, text='保留伴奏，或突出主旋律。', style='Muted.TLabel').grid(row=2, column=2, columnspan=2, sticky='w')
        row = ttk.Frame(detail_card); row.pack(fill='x', pady=(4, 0))
        ttk.Checkbutton(row, text='每首自动推荐移调', variable=self.auto_shift, command=self.shift_mode).pack(side='left')
        ttk.Checkbutton(row, text='去除鼓轨（MIDI 通道10）', variable=self.drums).pack(side='left', padx=20)
        self.shift_mode()
        export_card = card(frame, '导出曲谱'); export_card.pack(fill='x', before=detail_card, pady=(0, 12))
        row = ttk.Frame(export_card); row.pack(fill='x', pady=(0, 10))
        ttk.Label(row, text='助手目录').pack(side='left')
        self.score_dir = tk.StringVar(value=DEFAULT_SCORE)
        ttk.Entry(row, textvariable=self.score_dir).pack(side='left', fill='x', expand=True, padx=10)
        ttk.Button(row, text='选择…', command=self.directory).pack(side='left')
        row = ttk.Frame(export_card); row.pack(fill='x')
        self.local_button = None
        if self.local_folder:
            self.local_button = ttk.Button(row, text='转换并加入曲库', style='Primary.TButton', command=lambda: self.export(False, local=True))
            self.local_button.pack(side='left', padx=(0, 10))
            self.edit_buttons.append(self.local_button)
        self.save_button = ttk.Button(row, text='批量另存…', command=lambda: self.export(False))
        self.save_button.pack(side='left')
        self.install_button = ttk.Button(row, text='批量安装到助手', command=lambda: self.export(True))
        self.install_button.pack(side='left', padx=10)
        ttk.Button(row, text='打开输出目录', command=self.open_output).pack(side='left')
        self.status = tk.StringVar(value='等待添加 MIDI 文件')
        ttk.Label(frame, textvariable=self.status, style='Accent.TLabel').pack(anchor='w')
        self.progress = ttk.Progressbar(frame, mode='determinate'); self.progress.pack(fill='x', pady=5)
        self.log = tk.Text(frame, height=4, wrap='word', font=('Microsoft YaHei UI', 9),
                           state='disabled', background=FIELD, foreground=MUTED, insertbackground=TEXT,
                           relief='flat', borderwidth=0, highlightthickness=0, padx=10, pady=8)
        self.log.pack(fill='both', expand=True)
        for panel in (queue_card, detail_card, export_card): surface(panel)
        self.report('文件选择窗口内按 Ctrl 或 Shift 多选。重复添加会自动去重；同名输出自动编号。')
        self.poll_timer = root.after(100, self.poll)

    def report(self, message, append=False):
        self.log.configure(state='normal')
        if not append: self.log.delete('1.0', 'end')
        self.log.insert('end', message + '\n'); self.log.see('end'); self.log.configure(state='disabled')

    def open(self):
        if self.busy: return
        paths = filedialog.askopenfilenames(title='选择 MIDI（Ctrl / Shift 多选）',
            filetypes=[('MIDI 文件', '*.mid *.midi'), ('所有文件', '*.*')])
        self.add_paths(paths)

    def add_folder(self):
        if self.busy: return
        folder = filedialog.askdirectory(title='添加文件夹内全部 MIDI（包含子文件夹）')
        if not folder: return
        try:
            paths = sorted(p for p in Path(folder).rglob('*') if p.is_file() and p.suffix.lower() in ('.mid', '.midi'))
            if not paths: messagebox.showinfo('没有 MIDI', '该文件夹及子文件夹中没有 .mid 或 .midi 文件。')
            self.add_paths(paths)
        except Exception as exc: messagebox.showerror('无法添加文件夹', str(exc))

    def add_paths(self, paths):
        if self.busy: return
        seen = {os.path.normcase(str(job.path.resolve())) for job in self.jobs.values()}
        added = []
        for value in paths:
            path = Path(value)
            key = os.path.normcase(str(path.resolve()))
            if key in seen or path.suffix.lower() not in ('.mid', '.midi'): continue
            seen.add(key); self.serial += 1
            iid = str(self.serial)
            self.jobs[iid] = Job(path=path, title=path.stem)
            self.filelist.insert('', 'end', iid=iid, values=(path.name, '待转换'))
            added.append(iid)
        self.count.configure(text=f'{len(self.jobs)} 首')
        if added:
            self.status.set(f'新增 {len(added)} 首，队列共 {len(self.jobs)} 首')
            self.filelist.selection_set(added[0]); self.filelist.focus(added[0]); self.filelist.see(added[0])

    def save_current(self):
        if self.current not in self.jobs: return
        job = self.jobs[self.current]
        job.title = self.title.get().strip() or job.path.stem
        if job.data is not None:
            job.tracks = set(self.tracklist.curselection())
        if not self.auto_shift.get():
            shift = int(self.shift.get())
            if not -24 <= shift <= 24: raise ValueError('移调应为 -24 至 24 半音。')
            job.shift = shift

    def preview(self, event=None):
        if self.busy: return
        selected = self.filelist.selection()
        iid = self.filelist.focus()
        if iid not in selected: iid = selected[0] if selected else None
        if iid is None or iid == self.current: return
        try:
            self.save_current()
        except Exception as exc:
            messagebox.showerror('当前歌曲设置无效', str(exc))
            self.filelist.selection_set(self.current); self.filelist.focus(self.current)
            return
        self.current = iid
        job = self.jobs[iid]
        self.title.set(job.title); self.shift.set(str(job.shift)); self.tracklist.delete(0, 'end')
        try:
            if job.data is None: job.data = load(job.path)
            data = job.data
            if job.tracks is None: job.tracks = {i for i, _, count in data['tracks'] if count}
            for i, name, count in data['tracks']:
                self.tracklist.insert('end', f'{i:02d}  {name}  · {count} 个音符')
                if i in job.tracks: self.tracklist.selection_set(i)
            seconds = duration(data)
            self.info.configure(text=f'{job.path.name[:48]} · {int(seconds)//60}分{seconds%60:04.1f}秒 · {len(data["notes"])} 个音符')
            if self.auto_shift.get(): self.recommend()
        except Exception as exc:
            self.info.configure(text='该文件暂时无法读取；批量转换时会报告失败并继续其他歌曲。')
            self.filelist.set(iid, 'status', '读取失败')
            self.report(f'{job.path.name}：{exc}')

    def shift_mode(self):
        self.shift_input.configure(state='disabled' if self.auto_shift.get() else 'normal')

    def recommend(self):
        if self.busy or self.current not in self.jobs: return
        job = self.jobs[self.current]
        if job.data is None: return
        try:
            notes = arrange_notes(job.data, set(self.tracklist.curselection()), self.drums.get(), ARRANGEMENTS[self.arrangement.get()])
            shift = suggest(notes, job.data)
            self.shift.set(str(shift)); job.shift = shift
            self.report(f'{job.path.name}：推荐移调 {shift:+d} 半音；按时长加权的白键适配率 '
                        f'{white_rate(notes, 0, job.data):.0%} → {white_rate(notes, shift, job.data):.0%}。\n'
                        + '\n'.join(dict.fromkeys(job.data['warnings'])))
        except Exception as exc: self.report(str(exc))

    def remove(self):
        if self.busy: return
        for iid in self.filelist.selection():
            self.jobs.pop(iid, None); self.filelist.delete(iid)
            if iid == self.current: self.current = None
        self.after_removal()

    def clear(self):
        if self.busy: return
        for iid in self.filelist.get_children(): self.filelist.delete(iid)
        self.jobs.clear(); self.current = None; self.after_removal()

    def after_removal(self):
        self.count.configure(text=f'{len(self.jobs)} 首')
        if self.current is None:
            self.tracklist.delete(0, 'end'); self.title.set(''); self.shift.set('0')
            self.info.configure(text='点击队列中的歌曲，可单独调整它的轨道、标题和手动移调。')
        self.status.set(f'队列共 {len(self.jobs)} 首')

    def directory(self):
        if self.busy: return
        path = filedialog.askdirectory(title='选择 YuanQinAssistant/assets/score 曲谱目录')
        if path: self.score_dir.set(path)

    def open_output(self):
        folder = self.last_folder or Path(self.score_dir.get())
        if folder.is_dir(): os.startfile(str(folder))
        else: messagebox.showinfo('目录不存在', '先完成转换或选择现有的助手目录。')

    def export(self, install, local=False):
        if self.busy: return
        if not self.can_convert():
            self.status.set('请先停止演奏，再开始转换。'); return
        if not self.jobs:
            messagebox.showinfo('添加 MIDI', '请先添加一个或多个 MIDI 文件。'); return
        try:
            self.save_current()
            options = Options(auto_shift=self.auto_shift.get(), speed=float(self.speed.get()),
                              no_drums=self.drums.get(), policy=POLICIES[self.policy.get()],
                              arrangement=ARRANGEMENTS[self.arrangement.get()])
            options.check()
            if local:
                self.local_folder.mkdir(parents=True, exist_ok=True)
                folder = str(self.local_folder)
            elif install: folder = self.score_dir.get().strip()
            else:
                folder = filedialog.askdirectory(title='选择批量输出文件夹', initialdir=str(next(iter(self.jobs.values())).path.parent))
                if not folder: return
            if not Path(folder).is_dir(): raise ValueError('输出目录不存在，请选择现有文件夹。')
            jobs = [Job(j.path, j.title, set(j.tracks) if j.tracks is not None else None, j.shift, j.data)
                    for j in self.jobs.values()]
            self.run_ids = list(self.jobs)
            self.last_folder = Path(folder)
            self.busy = True
            for button in self.edit_buttons + [self.save_button, self.install_button]: button.configure(state='disabled')
            self.progress.configure(maximum=len(jobs), value=0)
            self.status.set(f'正在转换 0 / {len(jobs)} 首')
            self.report('开始转换队列中的全部歌曲；本次设置已固定。')
            for iid in self.run_ids: self.filelist.set(iid, 'status', '待转换')
            threading.Thread(target=self.worker, args=(jobs, folder, options), daemon=True).start()
        except Exception as exc: messagebox.showerror('无法开始转换', str(exc))

    def worker(self, jobs, folder, options):
        try:
            result = run_batch(jobs, folder, options, self.events.put)
            self.events.put(dict(kind='done', result=result))
        except Exception as exc:
            self.events.put(dict(kind='fatal', error=str(exc)))

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event['kind']
                if kind in ('start', 'success', 'failure'):
                    iid = self.run_ids[event['index']]
                    status = {'start': '转换中…', 'success': '成功', 'failure': '失败'}[kind]
                    if kind == 'success': status = f'成功 · {len(event["paths"])} 份'
                    self.filelist.set(iid, 'status', status)
                    self.filelist.see(iid)
                    if kind == 'failure': self.report(f'失败：{event["name"]} — {event["error"]}', True)
                    elif kind == 'success':
                        row = event['rows'][0]
                        self.report(f'成功：{event["name"]} · 移调 {row["移调"]:+d} · 半音修正 {row["半音修正"]}'
                                    f' · 简化 {row["简化音符"]} 音 · 白键适配 {row["白键适配前"]}% → {row["白键适配后"]}%', True)
                elif kind == 'progress':
                    self.progress.configure(value=event['done'])
                    self.status.set(f'正在转换 {event["done"]} / {event["total"]} 首')
                elif kind in ('done', 'fatal'):
                    self.busy = False
                    for button in self.edit_buttons + [self.save_button, self.install_button]: button.configure(state='normal')
                    if kind == 'fatal':
                        self.status.set('转换未完成'); self.report(event['error'], True)
                    else:
                        result = event['result']
                        summary = f'完成：成功 {result["succeeded"]} 首，失败 {result["failed"]} 首，共生成 {result["outputs"]} 份曲谱'
                        self.status.set(summary); self.report(summary, True)
                        if result['report']: self.report('详细记录：' + result['report'], True)
                        if result['report_error']: self.report('记录保存失败：' + result['report_error'], True)
                        if self.on_complete:
                            self.on_complete(result)
                            self.report('成功生成的曲谱已加入演奏页；选中后切回游戏，按开始快捷键演奏。', True)
                        else:
                            self.report('在原琴助手中刷新曲谱列表即可查看。', True)
        except queue.Empty: pass
        if not self.closing: self.poll_timer = self.root.after(100, self.poll)

    def shutdown(self):
        self.closing = True
        self.root.after_cancel(self.poll_timer)

    def close(self):
        if self.busy:
            messagebox.showinfo('正在转换', '请等待本批转换结束后再关闭窗口。'); return
        self.shutdown()
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()
