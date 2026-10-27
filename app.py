import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from converter import load, duration, selected_notes, suggest, convert, unused_path

DEFAULT_SCORE = 'C:/Program Files/BetterGI/User/JsScript/YuanQinAssistant/assets/score'

class App:
    def __init__(self, root):
        self.root, self.data, self.source = root, None, None
        root.title('原琴转换器 · MIDI → GS2')
        root.geometry('800x710')
        root.minsize(730, 670)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', font=('Microsoft YaHei UI', 10))
        style.configure('Title.TLabel', font=('Microsoft YaHei UI', 18, 'bold'))
        frame = ttk.Frame(root, padding=22)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='把 MIDI 变成原琴曲谱', style='Title.TLabel').pack(anchor='w')
        ttk.Label(frame, text='保留歌曲节奏，适配琴键，供 BetterGI 原琴助手播放。').pack(anchor='w', pady=(5,14))
        line = ttk.Frame(frame); line.pack(fill='x')
        ttk.Button(line, text='选择 MIDI 文件…', command=self.open).pack(side='left')
        self.file_label = ttk.Label(line, text='支持 .mid / .midi'); self.file_label.pack(side='left', padx=12)
        self.info = ttk.Label(frame, text='先选择文件，再设置要转换的轨道。')
        self.info.pack(anchor='w', pady=10)
        box = ttk.LabelFrame(frame, text='歌曲轨道（可多选；Ctrl 单击或 Shift 连选）', padding=8)
        box.pack(fill='x')
        self.tracklist = tk.Listbox(box, height=6, selectmode='extended', exportselection=False,
                                    font=('Microsoft YaHei UI', 10))
        self.tracklist.pack(side='left', fill='x', expand=True)
        scroll = ttk.Scrollbar(box, command=self.tracklist.yview); scroll.pack(side='right', fill='y')
        self.tracklist.configure(yscrollcommand=scroll.set)
        options = ttk.Frame(frame); options.pack(fill='x', pady=12)
        self.range = tk.StringVar(value='两排琴键（Q–U / A–J）')
        self.shift, self.speed = tk.StringVar(value='0'), tk.StringVar(value='1.0')
        self.policy, self.drums = tk.StringVar(value='就近修正（向下）'), tk.BooleanVar(value=True)
        ttk.Label(options, text='琴键范围').grid(row=0, column=0, sticky='w')
        ttk.Combobox(options, textvariable=self.range, state='readonly', width=29,
                     values=['两排琴键（Q–U / A–J）','三排诗琴（加 Z–M）']).grid(row=0, column=1, padx=8, sticky='w')
        ttk.Label(options, text='半音处理').grid(row=0, column=2, sticky='w')
        ttk.Combobox(options, textvariable=self.policy, state='readonly', width=20,
                     values=['就近修正（向下）','向上修正','忽略半音']).grid(row=0, column=3, padx=8)
        ttk.Label(options, text='移调（半音）').grid(row=1, column=0, pady=10, sticky='w')
        sl = ttk.Frame(options); sl.grid(row=1,column=1,sticky='w',padx=8)
        ttk.Spinbox(sl, from_=-24, to=24, width=6, textvariable=self.shift).pack(side='left')
        ttk.Button(sl, text='推荐移调', command=self.recommend).pack(side='left', padx=8)
        ttk.Label(options, text='速度倍率').grid(row=1, column=2, sticky='w')
        ttk.Spinbox(options, from_=0.25, to=4, increment=0.05, width=8, textvariable=self.speed).grid(row=1, column=3, sticky='w', padx=8)
        ttk.Checkbutton(frame, text='去除鼓轨（MIDI 通道10）', variable=self.drums).pack(anchor='w')
        ttk.Label(frame, text='推荐移调按音符匹配率计算；半音多或有转调的歌曲仍可能需要试听调整。',
                  foreground='#666666').pack(anchor='w', pady=(5,10))
        row = ttk.Frame(frame); row.pack(fill='x', pady=5)
        ttk.Label(row, text='曲谱标题').pack(side='left')
        self.title = tk.StringVar()
        ttk.Entry(row, textvariable=self.title).pack(side='left',fill='x',expand=True,padx=(12,0))
        row = ttk.Frame(frame); row.pack(fill='x', pady=8)
        ttk.Label(row, text='助手目录').pack(side='left')
        self.score_dir = tk.StringVar(value=DEFAULT_SCORE)
        ttk.Entry(row, textvariable=self.score_dir).pack(side='left',fill='x',expand=True,padx=12)
        ttk.Button(row,text='选择…',command=self.directory).pack(side='left')
        buttons = ttk.Frame(frame); buttons.pack(fill='x',pady=10)
        ttk.Button(buttons,text='生成并另存…',command=lambda:self.export(False)).pack(side='left')
        ttk.Button(buttons,text='生成并安装到助手',command=lambda:self.export(True)).pack(side='left',padx=12)
        self.log = tk.Text(frame,height=6,wrap='word',font=('Microsoft YaHei UI',10),state='disabled',background='#f4f6f8')
        self.log.pack(fill='both',expand=True)
        self.report('选择 MIDI 后默认选中所有有音符的轨道。伴奏过密时，可以只选主旋律轨道。')

    def report(self, message):
        self.log.configure(state='normal'); self.log.delete('1.0','end'); self.log.insert('end',message); self.log.configure(state='disabled')

    def open(self):
        path = filedialog.askopenfilename(filetypes=[('MIDI 文件','*.mid *.midi'),('所有文件','*.*')])
        if not path: return
        try:
            data = load(path)
        except Exception as e:
            messagebox.showerror('无法读取 MIDI',str(e)); return
        self.data, self.source = data, Path(path)
        self.file_label.configure(text=self.source.name[:48])
        self.title.set(self.source.stem)
        self.tracklist.delete(0,'end')
        for i,name,count in data['tracks']:
            self.tracklist.insert('end',f'{i:02d}  {name}  · {count} 个音符')
            if count: self.tracklist.selection_set(i)
        seconds=duration(data)
        self.info.configure(text=f'时长 {int(seconds)//60}分{seconds%60:04.1f}秒 · {len(data["notes"])} 个音符 · {len(data["tracks"])} 个轨道')
        self.recommend()

    def recommend(self):
        if self.data is None: return
        try:
            notes=selected_notes(self.data,set(self.tracklist.curselection()),self.drums.get())
            shift=suggest(notes); self.shift.set(str(shift))
            self.report(f'推荐移调：{shift:+d} 半音。可先用默认设置生成，试听后调整轨道或移调。\n'+ '\n'.join(self.data['warnings'][:3]))
        except Exception as e: messagebox.showerror('无法推荐',str(e))

    def directory(self):
        path=filedialog.askdirectory(title='选择 YuanQinAssistant/assets/score 曲谱目录')
        if path:self.score_dir.set(path)

    def export(self, install):
        if self.data is None:
            messagebox.showinfo('选择文件','请先选择 MIDI 文件。'); return
        try:
            shift=int(self.shift.get())
            if not -24 <= shift <= 24: raise ValueError('移调应为 -24 至 24 半音。')
            low=60 if self.range.get().startswith('两排') else 48
            suffix='两排琴键版' if low==60 else '三排诗琴版'
            title=(self.title.get().strip() or self.source.stem)+'（'+suffix+'）'
            policy={'就近修正（向下）':'nearest','向上修正':'up','忽略半音':'skip'}[self.policy.get()]
            text,stats=convert(self.data,set(self.tracklist.curselection()),low,shift,float(self.speed.get()),self.drums.get(),policy,title)
            if install:
                folder=Path(self.score_dir.get())
                if not folder.is_dir(): raise ValueError('助手曲谱目录不存在。请先选择现有的 assets/score 文件夹。')
                path=unused_path(folder,title)
            else:
                name=unused_path(self.source.parent,title).name
                chosen=filedialog.asksaveasfilename(initialdir=str(self.source.parent),initialfile=name,defaultextension='.gs2',filetypes=[('原琴助手曲谱','*.gs2')])
                if not chosen:return
                path=Path(chosen)
                # Preserve existing files even when a user selects a used name.
                if path.exists():path=unused_path(path.parent,path.stem)
            with path.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
            sec=stats['seconds']
            self.report(f'已生成：{path}\n时长 {int(sec)//60}分{sec%60:04.1f}秒；发声 {stats["output"]} 次。\n'
                        f'八度调整 {stats["octave"]}；半音修正 {stats["corrected"]}；忽略 {stats["skipped"]}；同刻同键合并 {stats["merged"]}。\n'
                        +('重新运行原琴助手刷新列表，再搜索曲谱标题播放。' if install else '把曲谱复制到助手 assets/score 目录，重新运行助手后播放。'))
        except PermissionError:
            messagebox.showerror('目录无法写入','该目录没有写入权限。请使用“生成并另存”，再手动复制曲谱到助手目录。')
        except Exception as e: messagebox.showerror('转换失败',str(e))

if __name__ == '__main__':
    root=tk.Tk(); App(root); root.mainloop()
