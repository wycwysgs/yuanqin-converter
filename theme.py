"""Shared visual language for the toolbox and its floating player."""
import ctypes
import tkinter as tk
from tkinter import ttk

BG = '#101923'
SURFACE = '#192633'
FIELD = '#111e2b'
TEXT = '#e8f0f5'
MUTED = '#9fb2c3'
ACCENT = '#68dec6'
BORDER = '#2b3c4c'
FONT = 'Microsoft YaHei UI'
ICON_DATA = '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'


def setup(root):
    style = ttk.Style(root)
    if getattr(root, '_yuanqin_theme', False): return
    root._yuanqin_theme = True
    style.theme_use('clam')
    root.configure(background=BG)
    root._yuanqin_icon = tk.PhotoImage(master=root, data=ICON_DATA)
    root.iconphoto(True, root._yuanqin_icon)
    root.option_add('*TCombobox*Listbox.background', FIELD)
    root.option_add('*TCombobox*Listbox.foreground', TEXT)
    root.option_add('*TCombobox*Listbox.selectBackground', '#28565b')
    root.option_add('*TCombobox*Listbox.selectForeground', TEXT)
    style.configure('.', font=(FONT, 10), background=BG, foreground=TEXT,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
    style.configure('TFrame', background=BG)
    style.configure('Card.TFrame', background=SURFACE)
    style.configure('CardHeading.TLabel', background=SURFACE, foreground=ACCENT, font=(FONT, 10, 'bold'))
    style.configure('TLabel', background=BG, foreground=TEXT)
    style.configure('Muted.TLabel', foreground=MUTED)
    style.configure('Title.TLabel', font=(FONT, 20, 'bold'))
    style.configure('Brand.TLabel', font=(FONT, 19, 'bold'))
    style.configure('Accent.TLabel', foreground=ACCENT)
    style.configure('Badge.TLabel', background='#213f43', foreground=ACCENT, padding=(10, 4), font=(FONT, 9))
    style.configure('TButton', background='#253746', foreground=TEXT, padding=(12, 7), borderwidth=0, relief='flat')
    style.map('TButton', background=[('disabled', '#202d39'), ('pressed', '#3c5667'), ('active', '#344c5e')],
              foreground=[('disabled', '#667c8c')])
    style.configure('Primary.TButton', background=ACCENT, foreground='#0c2d2b', font=(FONT, 10, 'bold'))
    style.map('Primary.TButton', background=[('disabled', '#294c4b'), ('pressed', '#42bca5'), ('active', '#8cebd8')],
              foreground=[('disabled', '#819e9a'), ('!disabled', '#0c2d2b')])
    style.configure('Danger.TButton', background='#49313e', foreground='#ffc2ca')
    style.map('Danger.TButton', background=[('disabled', '#302a33'), ('active', '#65404c')])
    style.configure('Small.TButton', padding=(9, 4), font=(FONT, 9))
    style.configure('TEntry', fieldbackground=FIELD, foreground=TEXT, insertcolor=TEXT, padding=6, borderwidth=1)
    style.configure('TCombobox', fieldbackground=FIELD, background='#253746', foreground=TEXT, arrowcolor=MUTED, padding=5)
    style.map('TCombobox', fieldbackground=[('readonly', FIELD), ('disabled', '#202d39')],
              foreground=[('disabled', '#718696'), ('readonly', TEXT)], selectbackground=[('readonly', FIELD)],
              selectforeground=[('readonly', TEXT)])
    style.configure('TSpinbox', fieldbackground=FIELD, background='#253746', foreground=TEXT,
                    insertcolor=TEXT, arrowcolor=MUTED, padding=5)
    style.map('TSpinbox', fieldbackground=[('disabled', '#202d39')], foreground=[('disabled', '#718696')])
    style.configure('TCheckbutton', background=BG, foreground=TEXT, padding=(0, 3),
                    indicatorbackground=FIELD, indicatorforeground=ACCENT)
    style.map('TCheckbutton', background=[('active', BG)], foreground=[('disabled', '#718696')],
              indicatorbackground=[('selected', '#347969'), ('disabled', '#243341')])
    style.configure('TLabelframe', background=SURFACE, borderwidth=1, relief='solid')
    style.configure('TLabelframe.Label', background=SURFACE, foreground=ACCENT, font=(FONT, 10, 'bold'))
    style.configure('Treeview', background=FIELD, fieldbackground=FIELD, foreground=TEXT,
                    rowheight=31, borderwidth=0)
    style.map('Treeview', background=[('selected', '#29555b')], foreground=[('selected', '#f0fffb')])
    style.configure('Treeview.Heading', background='#243746', foreground=MUTED, padding=(10, 8),
                    font=(FONT, 9, 'bold'), relief='flat')
    style.map('Treeview.Heading', background=[('active', '#304959')])
    style.configure('TNotebook', background=BG, bordercolor=BG, lightcolor=BG, darkcolor=BG,
                    borderwidth=0, tabmargins=(0, 0, 0, 10))
    style.configure('TNotebook.Tab', padding=(22, 11), background=BG, foreground=MUTED,
                    borderwidth=0, expand=(0, 0, 0, 0))
    style.layout('TNotebook.Tab', [('Notebook.padding', {'sticky': 'nswe', 'children': [('Notebook.label', {'sticky': 'nswe'})]})])
    style.map('TNotebook.Tab', expand=[('selected', (0, 0, 0, 0))], background=[('selected', '#213d42'), ('active', '#233340')],
              foreground=[('selected', ACCENT)])
    style.configure('Horizontal.TProgressbar', troughcolor=FIELD, background=ACCENT, borderwidth=0, thickness=5)
    style.configure('Vertical.TScrollbar', background='#344a59', troughcolor=FIELD, arrowcolor=MUTED,
                    borderwidth=0, arrowsize=12)
    style.map('Vertical.TScrollbar', background=[('active', '#53717d')])
    style.configure('TSeparator', background=BORDER)
    for name, foreground, font in [('Card.TLabel', TEXT, (FONT, 10)), ('CardMuted.TLabel', MUTED, (FONT, 9)),
                                    ('CardTitle.TLabel', TEXT, (FONT, 12, 'bold'))]:
        style.configure(name, background=SURFACE, foreground=foreground, font=font)
    style.configure('Card.TCheckbutton', background=SURFACE)
    style.map('Card.TCheckbutton', background=[('active', SURFACE)])
    dark_titlebar(root)


def dark_titlebar(window):
    """Cosmetic only; older Windows versions simply retain their titlebar."""
    def apply():
        try:
            hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
        except (AttributeError, OSError): pass
    window.after_idle(apply)


def card(parent, title=None, padding=14):
    box = ttk.Frame(parent, style='Card.TFrame', padding=padding)
    if title:
        ttk.Label(box, text=title, style='CardHeading.TLabel').pack(anchor='w', pady=(0, 10))
    return box


def surface(widget):
    """Match basic child surfaces without overriding semantic button styles."""
    for child in widget.winfo_children():
        if isinstance(child, ttk.Frame): child.configure(style='Card.TFrame')
        elif isinstance(child, ttk.Label):
            current = child.cget('style')
            if current != 'CardHeading.TLabel':
                child.configure(style='CardMuted.TLabel' if current == 'Muted.TLabel' else 'Card.TLabel')
        elif isinstance(child, ttk.Checkbutton): child.configure(style='Card.TCheckbutton')
        surface(child)


def list_colors(widget):
    widget.configure(background=FIELD, foreground=TEXT, selectbackground='#29555b',
                     selectforeground='#f0fffb', highlightthickness=1, highlightbackground=BORDER,
                     highlightcolor=ACCENT, borderwidth=0, relief='flat', activestyle='none')
