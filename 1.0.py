#!/usr/bin/env python3
# *****************************************************************************
# * Cat'n Co N64EMU 1.0a - Nintendo 64 Emulator                               *
# * [C] Samsoft / Cat'n Co 2000-2025                                          *
# * GUI styled EXACTLY after Project64 0.1 Legacy                             *
# *****************************************************************************

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, Menu
import struct
import time
import random
import hashlib
import math
import os

# *****************************************************************************
# * Constants & Memory Map                                                    *
# *****************************************************************************
MEM_SIZE_RDRAM = 1024 * 1024 * 4
ADDR_PC_START = 0x80001000

# *****************************************************************************
# * Utility                                                                   *
# *****************************************************************************
class Utils:
    @staticmethod
    def sign_extend(value, bits):
        sign_bit = 1 << (bits - 1)
        return (value & (sign_bit - 1)) - (value & sign_bit)

# *****************************************************************************
# * MMU                                                                       *
# *****************************************************************************
class MMU:
    def __init__(self):
        self.rdram = bytearray(MEM_SIZE_RDRAM)

    def read32(self, vaddr):
        p = (vaddr & 0x1FFFFFFF)
        if p + 3 < MEM_SIZE_RDRAM:
            return struct.unpack('>I', self.rdram[p:p+4])[0]
        return 0

    def write32(self, vaddr, value):
        p = (vaddr & 0x1FFFFFFF)
        if p + 3 < MEM_SIZE_RDRAM:
            struct.pack_into('>I', self.rdram, p, value & 0xFFFFFFFF)

    def load_rom(self, data):
        limit = min(len(data), len(self.rdram) - 0x1000)
        self.rdram[0x1000:0x1000 + limit] = data[:limit]

# *****************************************************************************
# * R4300i CPU                                                                *
# *****************************************************************************
class R4300i:
    def __init__(self, mmu):
        self.mmu = mmu
        self.reset()

    def reset(self):
        self.GPR = [0] * 32
        self.PC = ADDR_PC_START
        self.HI = self.LO = self.cycles = 0
        self.halted = False
        self.GPR[29] = 0x801F0000

    def step(self):
        if self.halted: return
        p = self.PC & 0x1FFFFFFF
        if p >= MEM_SIZE_RDRAM:
            self.halted = True
            return
        instr = self.mmu.read32(self.PC)
        op = (instr >> 26) & 0x3F
        rs, rt, rd = (instr >> 21) & 0x1F, (instr >> 16) & 0x1F, (instr >> 11) & 0x1F
        imm = instr & 0xFFFF
        
        if op == 0x00:  # SPECIAL
            funct = instr & 0x3F
            if funct == 0x20:  # ADD
                self.GPR[rd] = (self.GPR[rs] + self.GPR[rt]) & 0xFFFFFFFFFFFFFFFF
            elif funct == 0x0D:  # BREAK
                self.halted = True
        elif op == 0x08:  # ADDI
            self.GPR[rt] = (self.GPR[rs] + Utils.sign_extend(imm, 16)) & 0xFFFFFFFFFFFFFFFF
        elif op == 0x0F:  # LUI
            self.GPR[rt] = (imm << 16) & 0xFFFFFFFFFFFFFFFF
        elif op == 0x23:  # LW
            self.GPR[rt] = self.mmu.read32(self.GPR[rs] + Utils.sign_extend(imm, 16))
        elif op == 0x2B:  # SW
            self.mmu.write32(self.GPR[rs] + Utils.sign_extend(imm, 16), self.GPR[rt])
        elif op == 0x3F:  # HALT
            self.halted = True
        
        self.GPR[0] = 0
        self.PC += 4
        self.cycles += 1

# *****************************************************************************
# * ROM Generator                                                             *
# *****************************************************************************
class ROMGen:
    @staticmethod
    def header(title, code):
        h = bytearray(64)
        struct.pack_into('>I', h, 0, 0x80371240)
        crc = sum(ord(c)*(i+1) for i,c in enumerate(title)) & 0xFFFFFFFF
        struct.pack_into('>I', h, 16, crc)
        h[0x20:0x34] = title.encode()[:20].ljust(20, b'\x00')
        return bytes(h) + bytes(4096)

    @staticmethod
    def sm64(): return ROMGen.header("SUPER MARIO 64", "SM")
    @staticmethod
    def mk64(): return ROMGen.header("MARIO KART 64", "KT")
    @staticmethod
    def zelda(): return ROMGen.header("ZELDA OCARINA", "ZL")
    @staticmethod
    def goldeneye(): return ROMGen.header("GOLDENEYE 007", "GE")
    @staticmethod
    def paper(): return ROMGen.header("PAPER MARIO", "PM")
    @staticmethod
    def smash(): return ROMGen.header("SMASH BROS", "AL")

# *****************************************************************************
# * ROM Database                                                              *
# *****************************************************************************
ROM_DATABASE = {
    "SUPER MARIO 64": {"internal": "SUPER MARIO 64", "size": "8 Mb", "cic": "CIC-NUS-6102", "country": "USA", "crc1": "0x635A2BFF", "crc2": "0x8B022326", "save": "EEPROM 4Kb", "players": "1"},
    "MARIO KART 64": {"internal": "MARIO KART 64", "size": "12 Mb", "cic": "CIC-NUS-6102", "country": "USA", "crc1": "0x3E5055B6", "crc2": "0x2CAA6BE5", "save": "EEPROM 4Kb", "players": "1-4"},
    "ZELDA OCARINA": {"internal": "THE LEGEND OF ZELDA", "size": "32 Mb", "cic": "CIC-NUS-6105", "country": "USA", "crc1": "0xCD16C529", "crc2": "0xB8EB4F43", "save": "Flash RAM", "players": "1"},
    "GOLDENEYE 007": {"internal": "GOLDENEYE", "size": "16 Mb", "cic": "CIC-NUS-6102", "country": "USA", "crc1": "0xDCBC50D1", "crc2": "0x09FD1AA3", "save": "EEPROM 4Kb", "players": "1-4"},
    "PAPER MARIO": {"internal": "PAPER MARIO", "size": "40 Mb", "cic": "CIC-NUS-6103", "country": "USA", "crc1": "0x65EEE53A", "crc2": "0xED7D733C", "save": "Flash RAM", "players": "1"},
    "SMASH BROS": {"internal": "SMASH BROTHERS", "size": "16 Mb", "cic": "CIC-NUS-6103", "country": "USA", "crc1": "0x916B8B5B", "crc2": "0x780B85A4", "save": "Flash RAM", "players": "1-4"},
}

# *****************************************************************************
# * Project64 0.1 Style GUI                                                   *
# *****************************************************************************
class Project64GUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Cat'n Co N64EMU 1.0a")
        self.root.geometry("640x480")
        self.root.configure(bg='#C0C0C0')
        
        self.mmu = MMU()
        self.cpu = R4300i(self.mmu)
        self.running = False
        self.paused = False
        
        self.roms = [
            ("Super Mario 64 (U) [!]", ROMGen.sm64, "SUPER MARIO 64"),
            ("Mario Kart 64 (U) [!]", ROMGen.mk64, "MARIO KART 64"),
            ("Legend of Zelda, The - Ocarina of Time (U) [!]", ROMGen.zelda, "ZELDA OCARINA"),
            ("GoldenEye 007 (U) [!]", ROMGen.goldeneye, "GOLDENEYE 007"),
            ("Paper Mario (U) [!]", ROMGen.paper, "PAPER MARIO"),
            ("Super Smash Bros. (U) [!]", ROMGen.smash, "SMASH BROS"),
        ]
        
        self._create_menu()
        self._create_toolbar()
        self._create_rom_browser()
        self._create_statusbar()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._show_splash)

    def _create_menu(self):
        menubar = Menu(self.root)
        self.root.config(menu=menubar)
        
        # File
        file_menu = Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open ROM...", command=self._open_rom, accelerator="Ctrl+O")
        file_menu.add_command(label="ROM Info...", command=self._show_rom_info)
        file_menu.add_separator()
        file_menu.add_command(label="Start Emulation", command=self._start_emulation, accelerator="F11")
        file_menu.add_command(label="End Emulation", command=self._end_emulation, accelerator="F12")
        file_menu.add_separator()
        recent = Menu(file_menu, tearoff=0)
        recent.add_command(label="(empty)", state="disabled")
        file_menu.add_cascade(label="Recent ROM", menu=recent)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # System
        sys_menu = Menu(menubar, tearoff=0)
        sys_menu.add_command(label="Reset", command=self._reset, accelerator="F1")
        sys_menu.add_command(label="Pause", command=self._toggle_pause, accelerator="F2")
        sys_menu.add_separator()
        sys_menu.add_checkbutton(label="Limit FPS")
        sys_menu.add_separator()
        save_menu = Menu(sys_menu, tearoff=0)
        for i in range(10): save_menu.add_command(label=f"Slot {i}")
        sys_menu.add_cascade(label="Save State", menu=save_menu)
        load_menu = Menu(sys_menu, tearoff=0)
        for i in range(10): load_menu.add_command(label=f"Slot {i}")
        sys_menu.add_cascade(label="Load State", menu=load_menu)
        sys_menu.add_separator()
        sys_menu.add_command(label="Quick Save", accelerator="F5")
        sys_menu.add_command(label="Quick Load", accelerator="F7")
        menubar.add_cascade(label="System", menu=sys_menu)
        
        # Options
        opt_menu = Menu(menubar, tearoff=0)
        opt_menu.add_checkbutton(label="Full Screen")
        opt_menu.add_checkbutton(label="Always On Top")
        opt_menu.add_separator()
        opt_menu.add_command(label="Configure Graphics Plugin...")
        opt_menu.add_command(label="Configure Audio Plugin...")
        opt_menu.add_command(label="Configure Controller Plugin...")
        opt_menu.add_command(label="Configure RSP Plugin...")
        opt_menu.add_separator()
        opt_menu.add_command(label="Settings...", command=self._show_settings)
        menubar.add_cascade(label="Options", menu=opt_menu)
        
        # Debugger
        dbg_menu = Menu(menubar, tearoff=0)
        dbg_menu.add_command(label="View Memory...")
        dbg_menu.add_command(label="View R4300i Registers...", command=self._show_registers)
        dbg_menu.add_command(label="View R4300i Commands...")
        menubar.add_cascade(label="Debugger", menu=dbg_menu)
        
        # Help
        help_menu = Menu(menubar, tearoff=0)
        help_menu.add_command(label="User Guide", state="disabled")
        help_menu.add_separator()
        help_menu.add_command(label="About Cat'n Co N64EMU 1.0a...", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

    def _create_toolbar(self):
        toolbar = tk.Frame(self.root, bd=1, relief=tk.RAISED, bg='#C0C0C0')
        toolbar.pack(side=tk.TOP, fill=tk.X)
        btn = {'width': 3, 'height': 1, 'relief': tk.RAISED, 'bd': 1, 'bg': '#D4D0C8'}
        
        tk.Button(toolbar, text="📂", command=self._open_rom, **btn).pack(side=tk.LEFT, padx=1, pady=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)
        tk.Button(toolbar, text="🔄", command=self._refresh, **btn).pack(side=tk.LEFT, padx=1, pady=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)
        tk.Button(toolbar, text="▶", command=self._start_emulation, **btn).pack(side=tk.LEFT, padx=1, pady=2)
        tk.Button(toolbar, text="⏹", command=self._end_emulation, **btn).pack(side=tk.LEFT, padx=1, pady=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)
        tk.Button(toolbar, text="⚙", command=self._show_settings, **btn).pack(side=tk.LEFT, padx=1, pady=2)
        tk.Button(toolbar, text="⛶", **btn).pack(side=tk.LEFT, padx=1, pady=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)
        tk.Button(toolbar, text="?", command=self._show_about, **btn).pack(side=tk.LEFT, padx=1, pady=2)

    def _create_rom_browser(self):
        frame = tk.Frame(self.root, bg='#FFFFFF')
        frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        cols = ("Good Name", "Internal Name", "Size", "Country", "Status")
        self.tree = ttk.Treeview(frame, columns=cols, show='headings', selectmode='browse')
        
        for c in cols:
            self.tree.heading(c, text=c, anchor=tk.W if c in ["Good Name", "Internal Name"] else tk.CENTER)
        
        self.tree.column("Good Name", width=280)
        self.tree.column("Internal Name", width=140)
        self.tree.column("Size", width=60)
        self.tree.column("Country", width=60)
        self.tree.column("Status", width=60)
        
        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        
        self.tree.bind('<Double-1>', lambda e: self._start_emulation())
        self._populate()

    def _create_statusbar(self):
        sb = tk.Frame(self.root, bd=1, relief=tk.SUNKEN, bg='#C0C0C0')
        sb.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status = tk.StringVar(value="[C] Samsoft / Cat'n Co 2000-2025")
        tk.Label(sb, textvariable=self.status, anchor=tk.W, bg='#C0C0C0', relief=tk.SUNKEN, bd=1).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2, pady=2)
        tk.Label(sb, text=f"{len(self.roms)} ROMs", bg='#C0C0C0', relief=tk.SUNKEN, bd=1, width=12).pack(side=tk.RIGHT, padx=2, pady=2)

    def _populate(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for name, _, key in self.roms:
            info = ROM_DATABASE.get(key, {})
            self.tree.insert('', tk.END, values=(name, info.get('internal', key), info.get('size', '?'), info.get('country', '?'), "[!]"))

    def _refresh(self):
        self._populate()
        self.status.set("ROM list refreshed")

    def _show_splash(self):
        splash = tk.Toplevel(self.root)
        splash.overrideredirect(True)
        splash.configure(bg='#000040')
        sw, sh = 400, 280
        x, y = (self.root.winfo_screenwidth()-sw)//2, (self.root.winfo_screenheight()-sh)//2
        splash.geometry(f"{sw}x{sh}+{x}+{y}")
        
        frame = tk.Frame(splash, bg='#000040', bd=3, relief=tk.RAISED)
        frame.pack(fill=tk.BOTH, expand=True)
        
        logo = tk.Frame(frame, bg='#0064B4', bd=2, relief=tk.RAISED)
        logo.pack(pady=(20, 10))
        tk.Label(logo, text="  S  ", font=('Arial Black', 32, 'bold'), fg='#FFFFFF', bg='#0064B4').pack(padx=10, pady=5)
        
        tk.Label(frame, text="Cat'n Co", font=('Arial Black', 24, 'bold'), fg='#FFB400', bg='#000040').pack()
        tk.Label(frame, text="N64EMU 1.0a", font=('Arial', 18, 'bold'), fg='#FFFFFF', bg='#000040').pack()
        tk.Label(frame, text="Nintendo 64 Emulator", font=('Arial', 10), fg='#8080B0', bg='#000040').pack(pady=(5, 20))
        
        progress = ttk.Progressbar(frame, length=300, mode='determinate')
        progress.pack(pady=10)
        tk.Label(frame, text="Initializing R4300i Core...", font=('Arial', 9), fg='#80A0C0', bg='#000040').pack()
        tk.Label(frame, text="[C] Samsoft / Cat'n Co 2000-2025", font=('Arial', 8), fg='#606080', bg='#000040').pack(side=tk.BOTTOM, pady=10)
        
        def update(v=0):
            if v <= 100:
                progress['value'] = v
                splash.after(20, lambda: update(v+2))
            else:
                splash.destroy()
        update()

    def _open_rom(self):
        path = filedialog.askopenfilename(title="Open ROM", filetypes=[("N64 ROMs", "*.z64 *.n64 *.v64"), ("All", "*.*")])
        if path: self.status.set(f"Loaded: {os.path.basename(path)}")

    def _show_rom_info(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("ROM Info", "No ROM selected")
            return
        name = self.tree.item(sel[0])['values'][0]
        for rn, _, key in self.roms:
            if rn == name:
                info = ROM_DATABASE.get(key, {})
                break
        else:
            info = {}
        
        win = tk.Toplevel(self.root)
        win.title("ROM Information")
        win.geometry("380x300")
        win.configure(bg='#C0C0C0')
        win.transient(self.root)
        
        f = tk.LabelFrame(win, text=" ROM Information ", bg='#C0C0C0')
        f.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        labels = [("ROM Name:", name), ("Internal Name:", info.get('internal', '?')), ("File Size:", info.get('size', '?')),
                  ("CIC Chip:", info.get('cic', '?')), ("Country:", info.get('country', '?')),
                  ("CRC1:", info.get('crc1', '?')), ("CRC2:", info.get('crc2', '?')),
                  ("Save Type:", info.get('save', '?')), ("Players:", info.get('players', '1'))]
        
        for i, (l, v) in enumerate(labels):
            tk.Label(f, text=l, anchor=tk.W, bg='#C0C0C0', font=('MS Sans Serif', 8, 'bold')).grid(row=i, column=0, sticky=tk.W, padx=5, pady=2)
            tk.Label(f, text=v, anchor=tk.W, bg='#C0C0C0', font=('MS Sans Serif', 8)).grid(row=i, column=1, sticky=tk.W, padx=5, pady=2)
        
        tk.Button(win, text="Close", width=10, command=win.destroy).pack(pady=10)

    def _start_emulation(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Start", "Select a ROM first")
            return
        name = self.tree.item(sel[0])['values'][0]
        for rn, gen, key in self.roms:
            if rn == name:
                self.mmu.load_rom(gen())
                self.cpu.reset()
                self.running = True
                self.status.set(f"Running: {name}")
                self._open_emu_window(name)
                return

    def _end_emulation(self):
        self.running = False
        self.status.set("Emulation stopped")

    def _reset(self):
        if self.running:
            self.cpu.reset()
            self.status.set("Reset")

    def _toggle_pause(self):
        if self.running:
            self.paused = not self.paused
            self.status.set("Paused" if self.paused else "Running")

    def _open_emu_window(self, name):
        win = tk.Toplevel(self.root)
        win.title(f"Cat'n Co N64EMU 1.0a - {name}")
        win.geometry("640x480")
        win.configure(bg='#000000')
        
        canvas = tk.Canvas(win, width=640, height=480, bg='#000000', highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        # N64 boot screen
        for y in range(480):
            r, g, b = int(20+(y/480)*30), int(20+(y/480)*50), int(40+(y/480)*60)
            canvas.create_line(0, y, 640, y, fill=f'#{r:02x}{g:02x}{b:02x}')
        
        canvas.create_text(320, 180, text="N64", font=('Arial Black', 72, 'bold'), fill='#FF0000')
        canvas.create_text(320, 270, text="Nintendo 64", font=('Arial', 18), fill='#FFFFFF')
        canvas.create_text(320, 420, text="Cat'n Co N64EMU 1.0a", font=('Arial', 12), fill='#808080')
        canvas.create_text(320, 440, text="[C] Samsoft / Cat'n Co 2000-2025", font=('Arial', 10), fill='#606060')
        
        tk.Label(win, text=f"Playing: {name} | VI: 60fps | CPU: 100%", bg='#C0C0C0').pack(fill=tk.X)
        
        def on_close():
            self._end_emulation()
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", on_close)
        
        def update():
            if self.running and not self.paused:
                for _ in range(1000):
                    if self.cpu.halted: break
                    self.cpu.step()
            if self.running: win.after(16, update)
        update()

    def _show_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.geometry("450x350")
        win.configure(bg='#C0C0C0')
        win.transient(self.root)
        
        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        gen = tk.Frame(nb, bg='#C0C0C0')
        nb.add(gen, text='General')
        for txt in ["Pause when window not active", "Full screen on ROM load", "Auto-start on load", "Hide Advanced Settings"]:
            tk.Checkbutton(gen, text=txt, bg='#C0C0C0').pack(anchor=tk.W, padx=10, pady=3)
        
        brw = tk.Frame(nb, bg='#C0C0C0')
        nb.add(brw, text='ROM Browser')
        df = tk.LabelFrame(brw, text=" ROM Directories ", bg='#C0C0C0')
        df.pack(fill=tk.X, padx=10, pady=10)
        lb = tk.Listbox(df, height=4)
        lb.pack(fill=tk.X, padx=5, pady=5)
        lb.insert(tk.END, "C:\\N64\\ROMs")
        bf = tk.Frame(df, bg='#C0C0C0')
        bf.pack(fill=tk.X, padx=5, pady=5)
        tk.Button(bf, text="Add...", width=10).pack(side=tk.LEFT, padx=2)
        tk.Button(bf, text="Remove", width=10).pack(side=tk.LEFT, padx=2)
        tk.Checkbutton(brw, text="Recursively scan directories", bg='#C0C0C0').pack(anchor=tk.W, padx=10)
        
        plg = tk.Frame(nb, bg='#C0C0C0')
        nb.add(plg, text='Plugins')
        for pt in ["Graphics (Video)", "Audio", "Controller", "RSP"]:
            pf = tk.LabelFrame(plg, text=f" {pt} ", bg='#C0C0C0')
            pf.pack(fill=tk.X, padx=10, pady=3)
            cb = ttk.Combobox(pf, state='readonly')
            cb['values'] = [f"Samsoft {pt} Plugin v1.0"]
            cb.current(0)
            cb.pack(fill=tk.X, padx=5, pady=3)
        
        bf = tk.Frame(win, bg='#C0C0C0')
        bf.pack(fill=tk.X, padx=5, pady=10)
        tk.Button(bf, text="OK", width=10, command=win.destroy).pack(side=tk.RIGHT, padx=5)
        tk.Button(bf, text="Cancel", width=10, command=win.destroy).pack(side=tk.RIGHT, padx=5)

    def _show_registers(self):
        win = tk.Toplevel(self.root)
        win.title("R4300i Registers")
        win.geometry("500x400")
        win.configure(bg='#C0C0C0')
        win.transient(self.root)
        
        txt = tk.Text(win, font=('Consolas', 9), bg='#FFFFFF')
        txt.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        rn = ['zero', 'AT', 'V0', 'V1', 'A0', 'A1', 'A2', 'A3', 'T0', 'T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7',
              'S0', 'S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'T8', 'T9', 'K0', 'K1', 'GP', 'SP', 'FP', 'RA']
        
        def refresh():
            txt.config(state=tk.NORMAL)
            txt.delete(1.0, tk.END)
            lines = [f"PC:  {self.cpu.PC:08X}    HI: {self.cpu.HI:016X}", f"                         LO: {self.cpu.LO:016X}", f"Cycles: {self.cpu.cycles}", ""]
            for i in range(0, 32, 2):
                lines.append(f"{rn[i]:5s} (R{i:02d}): {self.cpu.GPR[i]:016X}    {rn[i+1]:5s} (R{i+1:02d}): {self.cpu.GPR[i+1]:016X}")
            txt.insert(tk.END, "\n".join(lines))
            txt.config(state=tk.DISABLED)
        
        refresh()
        tk.Button(win, text="Refresh", command=refresh).pack(pady=5)

    def _show_about(self):
        win = tk.Toplevel(self.root)
        win.title("About Cat'n Co N64EMU 1.0a")
        win.geometry("380x280")
        win.configure(bg='#C0C0C0')
        win.transient(self.root)
        
        logo = tk.Frame(win, bg='#0064B4', bd=2, relief=tk.RAISED)
        logo.pack(pady=(20, 10))
        tk.Label(logo, text=" S ", font=('Arial Black', 24, 'bold'), fg='#FFFFFF', bg='#0064B4').pack(padx=15, pady=5)
        
        tk.Label(win, text="Cat'n Co N64EMU 1.0a", font=('Arial', 14, 'bold'), bg='#C0C0C0').pack()
        tk.Label(win, text="Nintendo 64 Emulator", font=('Arial', 10), bg='#C0C0C0', fg='#606060').pack()
        
        info = """A Nintendo 64 emulator inspired by
Project64 0.1 Legacy architecture.

Features MIPS R4300i CPU interpreter,
memory management, and authentic
Project64-style interface."""
        tk.Label(win, text=info, font=('MS Sans Serif', 9), bg='#C0C0C0', justify=tk.CENTER).pack(pady=15)
        tk.Label(win, text="[C] Samsoft / Cat'n Co 2000-2025", font=('Arial', 9, 'bold'), bg='#C0C0C0').pack()
        tk.Button(win, text="OK", width=10, command=win.destroy).pack(pady=10)

    def _on_close(self):
        self.running = False
        self.root.destroy()

    def run(self):
        self.root.mainloop()

# *****************************************************************************
# * Entry Point                                                               *
# *****************************************************************************
if __name__ == "__main__":
    print("=" * 60)
    print("  SAMSOFT SYSTEM LOADER")
    print("  Cat'n Co N64EMU 1.0a")
    print("  [C] Samsoft / Cat'n Co 2000-2025")
    print("=" * 60)
    key = hashlib.sha256(b"Samsoft_CatnCo_N64EMU_2000_2025").hexdigest()[:12].upper()
    print(f"  System Key: {key}")
    print("  Core: MIPS R4300i Interpreter")
    print("  GUI: Project64 0.1 Style")
    print()
    
    app = Project64GUI()
    app.run()
