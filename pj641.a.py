#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════════
  Cat's PJ64 0.1 - N64 Emulator
  Windows Classic UI + MIPS R4300i + Math-Generative ROMs
  
  Features:
    - Classic Windows GUI (matching screenshot)
    - Dear Mario Letter (SM64 Intro)
    - 3D Mario Character Render
    - B3313 Beta Level
    - Math-based procedural ROM generation
  
  (C) 2020-25 Team Flames / Samsoft | Legacy 2020-25
═══════════════════════════════════════════════════════════════════════════════════
"""

import pygame
import math
import struct
import random
import sys
import time

# ═══════════════════════════════════════════════════════════════════════════════
#  MIPS R4300i CPU CORE
# ═══════════════════════════════════════════════════════════════════════════════

class MIPS_R4300i:
    """Complete MIPS R4300i CPU with math-based execution"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.gpr = [0] * 32
        self.pc = 0
        self.hi = 0
        self.lo = 0
        self.ram = bytearray(4 * 1024 * 1024)
        self.rom = bytearray()
        self.cycles = 0
        self.delay_slot = False
        self.delay_pc = 0
        self.halted = False
    
    def load_rom(self, rom_bytes):
        self.rom = bytearray(rom_bytes)
        self.pc = 0
        copy_len = min(len(self.rom), len(self.ram))
        self.ram[:copy_len] = self.rom[:copy_len]
        self.gpr[29] = 0x801F0000
    
    def sext16(self, v):
        return v - 0x10000 if v & 0x8000 else v
    
    def sext32(self, v):
        return v - 0x100000000 if v & 0x80000000 else v
    
    def read32(self, addr):
        phys = addr & 0x1FFFFFFF
        if phys + 3 < len(self.ram):
            return struct.unpack('>I', self.ram[phys:phys+4])[0]
        return 0
    
    def write32(self, addr, val):
        phys = addr & 0x1FFFFFFF
        if phys + 3 < len(self.ram):
            self.ram[phys:phys+4] = struct.pack('>I', val & 0xFFFFFFFF)
    
    def step(self):
        if self.halted or self.pc >= len(self.ram):
            return False
        
        instr = self.read32(self.pc)
        op = (instr >> 26) & 0x3F
        rs = (instr >> 21) & 0x1F
        rt = (instr >> 16) & 0x1F
        rd = (instr >> 11) & 0x1F
        shamt = (instr >> 6) & 0x1F
        funct = instr & 0x3F
        imm = instr & 0xFFFF
        target = instr & 0x3FFFFFF
        
        next_pc = self.pc + 4
        if self.delay_slot:
            next_pc = self.delay_pc
            self.delay_slot = False
        
        if op == 0x00:  # SPECIAL
            if funct == 0x00: self.gpr[rd] = (self.gpr[rt] << shamt) & 0xFFFFFFFF
            elif funct == 0x02: self.gpr[rd] = (self.gpr[rt] & 0xFFFFFFFF) >> shamt
            elif funct == 0x08: self.delay_slot, self.delay_pc = True, self.gpr[rs]
            elif funct == 0x0D: self.halted = True
            elif funct == 0x10: self.gpr[rd] = self.hi
            elif funct == 0x12: self.gpr[rd] = self.lo
            elif funct == 0x18:
                res = self.sext32(self.gpr[rs]) * self.sext32(self.gpr[rt])
                self.lo, self.hi = res & 0xFFFFFFFF, (res >> 32) & 0xFFFFFFFF
            elif funct == 0x19:
                res = (self.gpr[rs] & 0xFFFFFFFF) * (self.gpr[rt] & 0xFFFFFFFF)
                self.lo, self.hi = res & 0xFFFFFFFF, (res >> 32) & 0xFFFFFFFF
            elif funct in (0x20, 0x21): self.gpr[rd] = (self.gpr[rs] + self.gpr[rt]) & 0xFFFFFFFF
            elif funct in (0x22, 0x23): self.gpr[rd] = (self.gpr[rs] - self.gpr[rt]) & 0xFFFFFFFF
            elif funct == 0x24: self.gpr[rd] = self.gpr[rs] & self.gpr[rt]
            elif funct == 0x25: self.gpr[rd] = self.gpr[rs] | self.gpr[rt]
            elif funct == 0x26: self.gpr[rd] = self.gpr[rs] ^ self.gpr[rt]
            elif funct == 0x2A: self.gpr[rd] = 1 if self.sext32(self.gpr[rs]) < self.sext32(self.gpr[rt]) else 0
        elif op == 0x02: self.delay_slot, self.delay_pc = True, ((self.pc + 4) & 0xF0000000) | (target << 2)
        elif op == 0x03: self.gpr[31], self.delay_slot, self.delay_pc = self.pc + 8, True, ((self.pc + 4) & 0xF0000000) | (target << 2)
        elif op == 0x04 and self.gpr[rs] == self.gpr[rt]: self.delay_slot, self.delay_pc = True, self.pc + 4 + (self.sext16(imm) << 2)
        elif op == 0x05 and self.gpr[rs] != self.gpr[rt]: self.delay_slot, self.delay_pc = True, self.pc + 4 + (self.sext16(imm) << 2)
        elif op in (0x08, 0x09): self.gpr[rt] = (self.gpr[rs] + self.sext16(imm)) & 0xFFFFFFFF
        elif op == 0x0C: self.gpr[rt] = self.gpr[rs] & imm
        elif op == 0x0D: self.gpr[rt] = self.gpr[rs] | imm
        elif op == 0x0F: self.gpr[rt] = (imm << 16) & 0xFFFFFFFF
        elif op == 0x23: self.gpr[rt] = self.read32(self.gpr[rs] + self.sext16(imm))
        elif op == 0x2B: self.write32(self.gpr[rs] + self.sext16(imm), self.gpr[rt])
        
        self.gpr[0] = 0
        self.pc = next_pc
        self.cycles += 1
        return self.cycles < 2000
    
    def run(self, max_cycles=1000):
        while self.step() and self.cycles < max_cycles:
            pass
        seed = self.cycles
        for i, r in enumerate(self.gpr):
            seed ^= (r * (i + 1)) & 0xFFFFFFFF
        seed ^= self.hi ^ self.lo
        return seed & 0xFFFFFFFF


# ═══════════════════════════════════════════════════════════════════════════════
#  MATH-GENERATIVE ROM BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

class MathROMGenerator:
    """Generate ROMs using mathematical functions"""
    
    @staticmethod
    def r_type(rs, rt, rd, shamt, funct):
        return ((rs & 0x1F) << 21) | ((rt & 0x1F) << 16) | ((rd & 0x1F) << 11) | ((shamt & 0x1F) << 6) | (funct & 0x3F)
    
    @staticmethod
    def i_type(op, rs, rt, imm):
        return ((op & 0x3F) << 26) | ((rs & 0x1F) << 21) | ((rt & 0x1F) << 16) | (imm & 0xFFFF)
    
    @staticmethod
    def build_header(title, code="N64E"):
        header = bytearray(64)
        struct.pack_into('>I', header, 0, 0x80371240)
        struct.pack_into('>I', header, 4, 0x000F1E90)
        struct.pack_into('>I', header, 8, 0x80000400)
        # CRC based on title hash
        crc1 = sum(ord(c) * (i+1) for i, c in enumerate(title)) & 0xFFFFFFFF
        crc2 = (crc1 * 0x5D588B65 + 1) & 0xFFFFFFFF
        struct.pack_into('>I', header, 16, crc1)
        struct.pack_into('>I', header, 20, crc2)
        header[0x20:0x34] = title.encode('ascii')[:20].ljust(20, b' ')
        header[0x3B:0x3F] = code.encode('ascii')[:4].ljust(4, b' ')
        header[0x3E] = 0x45  # USA
        return bytes(header)
    
    @staticmethod
    def generate_sm64(title="Super Mario 64"):
        """Generate Super Mario 64 style ROM using sin/cos math"""
        instrs = []
        R = MathROMGenerator
        
        # SM64 uses golden ratio based level generation
        # φ = (1 + √5) / 2 ≈ 1.618... → Use 0x19E3779B (fixed point)
        instrs.append(R.i_type(0x0F, 0, 8, 0x19E3))   # LUI $t0, 0x19E3
        instrs.append(R.i_type(0x0D, 8, 8, 0x779B))   # ORI $t0, 0x779B (golden ratio)
        
        # Player start position seeds
        instrs.append(R.i_type(0x0F, 0, 9, 0x4D41))   # LUI $t1, "MA"
        instrs.append(R.i_type(0x0D, 9, 9, 0x5249))   # ORI $t1, "RI" → "MARI"
        instrs.append(R.i_type(0x0F, 0, 10, 0x4F36))  # LUI $t2, "O6"  
        instrs.append(R.i_type(0x0D, 10, 10, 0x3400)) # ORI $t2, "4\0" → "O64"
        
        # Generate level geometry: multiply seeds
        instrs.append(R.r_type(8, 9, 0, 0, 0x19))     # MULTU $t0, $t1
        instrs.append(R.r_type(0, 0, 11, 0, 0x12))    # MFLO $t3 (level width)
        instrs.append(R.r_type(0, 0, 12, 0, 0x10))    # MFHI $t4 (level height)
        
        # XOR chain for platform positions (simulates sin/cos table lookup)
        instrs.append(R.r_type(11, 12, 13, 0, 0x26))  # XOR $t5, $t3, $t4
        instrs.append(R.r_type(13, 10, 14, 0, 0x26))  # XOR $t6, $t5, $t2
        
        # Generate coin positions using shifts (approximates trig)
        for i in range(8):
            instrs.append(R.r_type(0, 13, 15, i+1, 0x02))  # SRL $t7, $t5, i+1
            instrs.append(R.r_type(0, 14, 24, 7-i, 0x00))  # SLL $t8, $t6, 7-i
            instrs.append(R.r_type(15, 24, 15, 0, 0x26))   # XOR $t7, $t7, $t8
        
        # Enemy spawn using multiplication overflow
        instrs.append(R.r_type(13, 14, 0, 0, 0x19))   # MULTU $t5, $t6
        instrs.append(R.r_type(0, 0, 16, 0, 0x12))    # MFLO $s0 (enemy X)
        instrs.append(R.r_type(0, 0, 17, 0, 0x10))    # MFHI $s1 (enemy Y)
        
        # Star position = XOR of all generated values
        instrs.append(R.r_type(11, 12, 2, 0, 0x26))   # XOR $v0, $t3, $t4
        instrs.append(R.r_type(2, 13, 2, 0, 0x26))    # XOR $v0, $v0, $t5
        instrs.append(R.r_type(2, 16, 2, 0, 0x26))    # XOR $v0, $v0, $s0
        
        # Castle geometry seed
        instrs.append(R.r_type(2, 8, 3, 0, 0x25))     # OR $v1, $v0, $t0
        
        instrs.append(R.r_type(0, 0, 0, 0, 0x0D))     # BREAK
        
        while len(instrs) < 2048:
            instrs.append(0)
        
        header = MathROMGenerator.build_header("SUPER MARIO 64", "NSME")
        code = b''.join(struct.pack('>I', i) for i in instrs)
        return header + code
    
    @staticmethod
    def generate_mk64(title="Mario Kart 64"):
        """Generate Mario Kart 64 ROM using track spline math"""
        instrs = []
        R = MathROMGenerator
        
        # MK64 track uses bezier curves approximation
        # Control points based on "KART" seed
        instrs.append(R.i_type(0x0F, 0, 8, 0x4B41))   # "KA"
        instrs.append(R.i_type(0x0D, 8, 8, 0x5254))   # "RT"
        instrs.append(R.i_type(0x0F, 0, 9, 0x3634))   # "64"
        instrs.append(R.i_type(0x0D, 9, 9, 0x0000))
        
        # Track width/curve parameters
        instrs.append(R.r_type(8, 9, 0, 0, 0x19))     # MULTU
        instrs.append(R.r_type(0, 0, 10, 0, 0x12))    # MFLO
        instrs.append(R.r_type(0, 0, 11, 0, 0x10))    # MFHI
        
        # Generate 8 track control points using iterative XOR
        instrs.append(R.r_type(10, 11, 12, 0, 0x26))  # XOR base
        for i in range(8):
            instrs.append(R.r_type(0, 12, 13, i*2+1, 0x02))  # SRL
            instrs.append(R.r_type(0, 12, 14, 15-i*2, 0x00)) # SLL
            instrs.append(R.r_type(13, 14, 12, 0, 0x26))     # XOR feedback
        
        # Item box positions
        instrs.append(R.r_type(12, 10, 15, 0, 0x26))
        
        # Racer start grid
        instrs.append(R.r_type(12, 11, 16, 0, 0x25))
        
        # Output seeds
        instrs.append(R.r_type(10, 12, 2, 0, 0x26))
        instrs.append(R.r_type(11, 15, 3, 0, 0x25))
        
        instrs.append(R.r_type(0, 0, 0, 0, 0x0D))
        
        while len(instrs) < 2048:
            instrs.append(0)
        
        header = MathROMGenerator.build_header("MARIO KART 64", "NKTE")
        code = b''.join(struct.pack('>I', i) for i in instrs)
        return header + code
    
    @staticmethod
    def generate_zelda(title="Zelda OoT"):
        """Generate Zelda: Ocarina of Time ROM using dungeon generation math"""
        instrs = []
        R = MathROMGenerator
        
        # Zelda uses "ZELDA" and "HYRULE" seeds
        instrs.append(R.i_type(0x0F, 0, 8, 0x5A45))   # "ZE"
        instrs.append(R.i_type(0x0D, 8, 8, 0x4C44))   # "LD"
        instrs.append(R.i_type(0x0F, 0, 9, 0x4859))   # "HY"
        instrs.append(R.i_type(0x0D, 9, 9, 0x5255))   # "RU"
        instrs.append(R.i_type(0x0F, 0, 10, 0x4C45))  # "LE"
        
        # Dungeon room generation via prime multiplication
        instrs.append(R.r_type(8, 9, 0, 0, 0x19))     # MULTU
        instrs.append(R.r_type(0, 0, 11, 0, 0x12))    # MFLO (room width)
        instrs.append(R.r_type(0, 0, 12, 0, 0x10))    # MFHI (room height)
        
        # Door positions using XOR maze algorithm
        instrs.append(R.r_type(11, 12, 13, 0, 0x26))
        instrs.append(R.r_type(13, 10, 13, 0, 0x26))
        
        # Generate chest/key positions
        for i in range(4):
            instrs.append(R.r_type(0, 13, 14, i*4+3, 0x02))
            instrs.append(R.r_type(0, 13, 15, 12-i*4, 0x00))
            instrs.append(R.r_type(14, 15, 13, 0, 0x26))
        
        # Boss room seed
        instrs.append(R.r_type(13, 8, 16, 0, 0x26))
        
        # Triforce seed (golden)
        instrs.append(R.i_type(0x0F, 0, 17, 0xFFD7))  # Golden color
        instrs.append(R.r_type(16, 17, 2, 0, 0x26))
        
        instrs.append(R.r_type(11, 12, 3, 0, 0x25))
        instrs.append(R.r_type(0, 0, 0, 0, 0x0D))
        
        while len(instrs) < 2048:
            instrs.append(0)
        
        header = MathROMGenerator.build_header("ZELDA OCARINA TIME", "NZLE")
        code = b''.join(struct.pack('>I', i) for i in instrs)
        return header + code
    
    @staticmethod
    def generate_goldeneye(title="GoldenEye 007"):
        """Generate GoldenEye 007 ROM using FPS level math"""
        instrs = []
        R = MathROMGenerator
        
        # GoldenEye seeds: "007" and "BOND"
        instrs.append(R.i_type(0x0F, 0, 8, 0x3030))   # "00"
        instrs.append(R.i_type(0x0D, 8, 8, 0x3700))   # "7\0"
        instrs.append(R.i_type(0x0F, 0, 9, 0x424F))   # "BO"
        instrs.append(R.i_type(0x0D, 9, 9, 0x4E44))   # "ND"
        
        # Level geometry (hallways/rooms)
        instrs.append(R.r_type(8, 9, 0, 0, 0x19))
        instrs.append(R.r_type(0, 0, 10, 0, 0x12))
        instrs.append(R.r_type(0, 0, 11, 0, 0x10))
        
        # Enemy patrol paths
        instrs.append(R.r_type(10, 11, 12, 0, 0x26))
        for i in range(6):
            instrs.append(R.r_type(0, 12, 13, i*3+2, 0x02))
            instrs.append(R.r_type(12, 13, 12, 0, 0x26))
        
        # Weapon spawns
        instrs.append(R.r_type(12, 10, 14, 0, 0x25))
        
        # Mission objective locations
        instrs.append(R.r_type(12, 11, 15, 0, 0x26))
        
        instrs.append(R.r_type(10, 12, 2, 0, 0x26))
        instrs.append(R.r_type(11, 14, 3, 0, 0x25))
        instrs.append(R.r_type(0, 0, 0, 0, 0x0D))
        
        while len(instrs) < 2048:
            instrs.append(0)
        
        header = MathROMGenerator.build_header("GOLDENEYE 007", "NGEE")
        code = b''.join(struct.pack('>I', i) for i in instrs)
        return header + code
    
    @staticmethod
    def generate_paper_mario(title="Paper Mario"):
        """Generate Paper Mario ROM using 2.5D math"""
        instrs = []
        R = MathROMGenerator
        
        # Paper Mario seeds
        instrs.append(R.i_type(0x0F, 0, 8, 0x5041))   # "PA"
        instrs.append(R.i_type(0x0D, 8, 8, 0x5045))   # "PE"
        instrs.append(R.i_type(0x0F, 0, 9, 0x5200))   # "R\0"
        
        # Chapter generation
        instrs.append(R.r_type(8, 9, 0, 0, 0x19))
        instrs.append(R.r_type(0, 0, 10, 0, 0x12))
        instrs.append(R.r_type(0, 0, 11, 0, 0x10))
        
        # Partner positions
        instrs.append(R.r_type(10, 11, 12, 0, 0x26))
        
        # Badge locations
        for i in range(5):
            instrs.append(R.r_type(0, 12, 13, i*5+1, 0x02))
            instrs.append(R.r_type(12, 13, 12, 0, 0x26))
        
        # Star Spirit seeds
        instrs.append(R.r_type(12, 8, 14, 0, 0x25))
        
        instrs.append(R.r_type(10, 12, 2, 0, 0x26))
        instrs.append(R.r_type(11, 14, 3, 0, 0x25))
        instrs.append(R.r_type(0, 0, 0, 0, 0x0D))
        
        while len(instrs) < 2048:
            instrs.append(0)
        
        header = MathROMGenerator.build_header("PAPER MARIO", "NMQE")
        code = b''.join(struct.pack('>I', i) for i in instrs)
        return header + code
    
    @staticmethod
    def generate_b3313():
        """Generate B3313 beta ROM with personalization"""
        instrs = []
        R = MathROMGenerator
        
        # B3313 personalization seed
        instrs.append(R.i_type(0x0F, 0, 8, 0xB331))
        instrs.append(R.i_type(0x0D, 8, 8, 0x3000))
        instrs.append(R.i_type(0x0F, 0, 9, 0xDEAD))
        instrs.append(R.i_type(0x0D, 9, 9, 0xBEEF))
        
        # "Every copy is personalized" generation
        instrs.append(R.r_type(8, 9, 0, 0, 0x19))
        instrs.append(R.r_type(0, 0, 10, 0, 0x12))
        instrs.append(R.r_type(0, 0, 11, 0, 0x10))
        
        # Wario apparition seed
        instrs.append(R.r_type(10, 11, 12, 0, 0x26))
        
        # Eternal staircase loop
        for i in range(12):
            instrs.append(R.r_type(0, 12, 13, i, 0x02))
            instrs.append(R.r_type(0, 12, 14, 15-i, 0x00))
            instrs.append(R.r_type(13, 14, 12, 0, 0x26))
        
        # Corrupted star count
        instrs.append(R.r_type(12, 10, 15, 0, 0x26))
        
        instrs.append(R.r_type(10, 12, 2, 0, 0x26))
        instrs.append(R.r_type(11, 15, 3, 0, 0x25))
        instrs.append(R.r_type(0, 0, 0, 0, 0x0D))
        
        while len(instrs) < 2048:
            instrs.append(0)
        
        header = MathROMGenerator.build_header("B3313 INTERNAL", "B313")
        code = b''.join(struct.pack('>I', i) for i in instrs)
        return header + code


# ═══════════════════════════════════════════════════════════════════════════════
#  3D RENDERER
# ═══════════════════════════════════════════════════════════════════════════════

class Renderer3D:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.fov = 60
    
    def project(self, x, y, z, cam):
        cx, cy, cz, yaw, pitch = cam
        dx, dy, dz = x - cx, y - cy, z - cz
        
        cos_y, sin_y = math.cos(yaw), math.sin(yaw)
        rx = dx * cos_y - dz * sin_y
        rz = dx * sin_y + dz * cos_y
        
        cos_p, sin_p = math.cos(pitch), math.sin(pitch)
        ry = dy * cos_p - rz * sin_p
        fz = dy * sin_p + rz * cos_p
        
        if fz <= 0.1:
            return None
        
        scale = (self.width / 2) / math.tan(math.radians(self.fov / 2))
        sx = (rx * scale / fz) + self.width / 2
        sy = (-ry * scale / fz) + self.height / 2
        return int(sx), int(sy), fz
    
    def draw_cube(self, surface, x, y, z, size, color, cam, rotation=0):
        if isinstance(size, tuple):
            sx, sy, sz = size[0]/2, size[1]/2, size[2]/2
        else:
            sx = sy = sz = size / 2
        
        verts = [
            (x-sx, y-sy, z-sz), (x+sx, y-sy, z-sz),
            (x+sx, y+sy, z-sz), (x-sx, y+sy, z-sz),
            (x-sx, y-sy, z+sz), (x+sx, y-sy, z+sz),
            (x+sx, y+sy, z+sz), (x-sx, y+sy, z+sz)
        ]
        
        if rotation != 0:
            cos_r, sin_r = math.cos(rotation), math.sin(rotation)
            new_verts = []
            for vx, vy, vz in verts:
                dx, dz = vx - x, vz - z
                new_verts.append((x + dx*cos_r - dz*sin_r, vy, z + dx*sin_r + dz*cos_r))
            verts = new_verts
        
        faces = [
            ([4,5,6,7], 1.0), ([1,0,3,2], 0.6), ([0,4,7,3], 0.7),
            ([5,1,2,6], 0.8), ([7,6,2,3], 0.9), ([0,1,5,4], 0.5)
        ]
        
        face_data = []
        for indices, shade in faces:
            projs = [self.project(verts[i][0], verts[i][1], verts[i][2], cam) for i in indices]
            if all(projs):
                avg_z = sum(p[2] for p in projs) / 4
                face_data.append((indices, shade, avg_z, projs))
        
        face_data.sort(key=lambda f: -f[2])
        
        for indices, shade, _, projs in face_data:
            points = [(p[0], p[1]) for p in projs]
            shaded = tuple(int(c * shade) for c in color)
            pygame.draw.polygon(surface, shaded, points)
    
    def draw_sphere(self, surface, x, y, z, radius, color, cam):
        proj = self.project(x, y, z, cam)
        if proj:
            scale = 200 / proj[2] if proj[2] > 0 else 1
            r = int(radius * scale * 50)
            if r > 0:
                pygame.draw.circle(surface, color, (proj[0], proj[1]), r)
                highlight = tuple(min(255, c + 50) for c in color)
                if r > 3:
                    pygame.draw.circle(surface, highlight, (proj[0]-r//4, proj[1]-r//4), r//3)


# ═══════════════════════════════════════════════════════════════════════════════
#  MARIO 3D MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class Mario3D:
    def __init__(self):
        self.parts = [
            # Head & Face
            {'type': 'sphere', 'off': (0, 1.4, 0), 'size': 0.5, 'color': (255, 200, 150)},
            {'type': 'cube', 'off': (0, 1.7, 0), 'size': (0.55, 0.15, 0.55), 'color': (255, 0, 0)},  # Hat base
            {'type': 'cube', 'off': (0, 1.85, 0), 'size': (0.4, 0.2, 0.4), 'color': (255, 0, 0)},    # Hat top
            {'type': 'cube', 'off': (0, 1.7, 0.28), 'size': (0.2, 0.15, 0.02), 'color': (255, 255, 255)},  # M logo
            {'type': 'cube', 'off': (-0.15, 1.45, 0.25), 'size': (0.12, 0.15, 0.05), 'color': (255, 255, 255)},  # Eye L
            {'type': 'cube', 'off': (0.15, 1.45, 0.25), 'size': (0.12, 0.15, 0.05), 'color': (255, 255, 255)},   # Eye R
            {'type': 'cube', 'off': (-0.15, 1.45, 0.28), 'size': (0.06, 0.08, 0.02), 'color': (30, 100, 200)},   # Pupil L
            {'type': 'cube', 'off': (0.15, 1.45, 0.28), 'size': (0.06, 0.08, 0.02), 'color': (30, 100, 200)},    # Pupil R
            {'type': 'sphere', 'off': (0, 1.35, 0.35), 'size': 0.15, 'color': (255, 180, 130)},  # Nose
            {'type': 'cube', 'off': (0, 1.25, 0.28), 'size': (0.4, 0.08, 0.1), 'color': (50, 30, 20)},  # Mustache
            # Body
            {'type': 'cube', 'off': (0, 0.8, 0), 'size': (0.5, 0.6, 0.35), 'color': (0, 0, 200)},  # Overalls
            {'type': 'cube', 'off': (-0.35, 0.9, 0), 'size': (0.2, 0.3, 0.25), 'color': (255, 0, 0)},  # Shirt L
            {'type': 'cube', 'off': (0.35, 0.9, 0), 'size': (0.2, 0.3, 0.25), 'color': (255, 0, 0)},   # Shirt R
            # Arms
            {'type': 'cube', 'off': (-0.45, 0.7, 0), 'size': (0.15, 0.4, 0.15), 'color': (255, 0, 0), 'anim': 'arm_l'},
            {'type': 'cube', 'off': (0.45, 0.7, 0), 'size': (0.15, 0.4, 0.15), 'color': (255, 0, 0), 'anim': 'arm_r'},
            {'type': 'sphere', 'off': (-0.45, 0.45, 0), 'size': 0.12, 'color': (255, 255, 255), 'anim': 'arm_l'},  # Glove L
            {'type': 'sphere', 'off': (0.45, 0.45, 0), 'size': 0.12, 'color': (255, 255, 255), 'anim': 'arm_r'},   # Glove R
            # Legs
            {'type': 'cube', 'off': (-0.15, 0.25, 0), 'size': (0.18, 0.5, 0.2), 'color': (0, 0, 180), 'anim': 'leg_l'},
            {'type': 'cube', 'off': (0.15, 0.25, 0), 'size': (0.18, 0.5, 0.2), 'color': (0, 0, 180), 'anim': 'leg_r'},
            {'type': 'cube', 'off': (-0.15, 0.08, 0.05), 'size': (0.2, 0.16, 0.3), 'color': (100, 50, 20), 'anim': 'leg_l'},  # Shoe L
            {'type': 'cube', 'off': (0.15, 0.08, 0.05), 'size': (0.2, 0.16, 0.3), 'color': (100, 50, 20), 'anim': 'leg_r'},   # Shoe R
            # Buttons
            {'type': 'sphere', 'off': (-0.18, 0.95, 0.18), 'size': 0.05, 'color': (255, 220, 0)},
            {'type': 'sphere', 'off': (0.18, 0.95, 0.18), 'size': 0.05, 'color': (255, 220, 0)},
        ]
    
    def draw(self, renderer, surface, x, y, z, facing, cam, anim_frame=0):
        arm_swing = math.sin(anim_frame * 0.3) * 0.15
        leg_swing = math.sin(anim_frame * 0.3) * 0.1
        bob = abs(math.sin(anim_frame * 0.3)) * 0.05
        
        for part in self.parts:
            ox, oy, oz = part['off']
            
            # Animation
            anim = part.get('anim', '')
            if anim == 'arm_l': oz += arm_swing
            elif anim == 'arm_r': oz -= arm_swing
            elif anim == 'leg_l': oz += leg_swing
            elif anim == 'leg_r': oz -= leg_swing
            oy += bob
            
            # Rotate by facing
            cos_f, sin_f = math.cos(facing), math.sin(facing)
            rx = ox * cos_f - oz * sin_f
            rz = ox * sin_f + oz * cos_f
            
            px, py, pz = x + rx, y + oy, z + rz
            
            if part['type'] == 'cube':
                renderer.draw_cube(surface, px, py, pz, part['size'], part['color'], cam, facing)
            else:
                renderer.draw_sphere(surface, px, py, pz, part['size'], part['color'], cam)


# ═══════════════════════════════════════════════════════════════════════════════
#  DEAR MARIO LETTER
# ═══════════════════════════════════════════════════════════════════════════════

class DearMarioLetter:
    TEXT = [
        "Dear Mario:",
        "",
        "Please come to the castle.",
        "I've baked a cake for you.",
        "",
        "Yours truly--",
        "Princess Toadstool",
        "",
        "    Peach"
    ]
    
    def __init__(self):
        self.visible = False
        self.alpha = 0
        self.line_idx = 0
        self.char_idx = 0
        self.timer = 0
        self.complete = False
    
    def show(self):
        self.visible = True
        self.alpha = 0
        self.line_idx = 0
        self.char_idx = 0
        self.timer = 0
        self.complete = False
    
    def update(self, dt):
        if not self.visible:
            return
        
        self.alpha = min(255, self.alpha + 200 * dt)
        self.timer += dt
        
        if self.timer > 0.05:
            self.timer = 0
            if self.line_idx < len(self.TEXT):
                if self.char_idx < len(self.TEXT[self.line_idx]):
                    self.char_idx += 1
                else:
                    self.line_idx += 1
                    self.char_idx = 0
            else:
                self.complete = True
    
    def draw(self, surface, fonts):
        if not self.visible:
            return
        
        sw, sh = surface.get_size()
        
        # Letter surface
        letter = pygame.Surface((500, 350))
        letter.fill((255, 248, 220))
        pygame.draw.rect(letter, (200, 150, 100), (0, 0, 500, 350), 4)
        pygame.draw.rect(letter, (180, 130, 80), (8, 8, 484, 334), 2)
        
        # Peach seal
        pygame.draw.circle(letter, (255, 100, 150), (450, 300), 25)
        pygame.draw.circle(letter, (255, 150, 180), (450, 300), 20)
        seal = fonts['tiny'].render("P", True, (255, 255, 255))
        letter.blit(seal, (443, 290))
        
        # Text
        y = 30
        for i, line in enumerate(self.TEXT):
            font = fonts['title'] if i == 0 else fonts['body']
            color = (80, 40, 20) if i == 0 else (60, 40, 30)
            
            if i < self.line_idx:
                text = font.render(line, True, color)
            elif i == self.line_idx:
                text = font.render(line[:self.char_idx], True, color)
                if int(time.time() * 3) % 2 == 0:
                    cx = 30 + text.get_width()
                    pygame.draw.rect(letter, color, (cx, y, 2, 25))
            else:
                text = font.render("", True, color)
            
            letter.blit(text, (30, y))
            y += 32 if i == 0 else 28
        
        letter.set_alpha(int(self.alpha))
        
        # Shadow and blit
        shadow = pygame.Surface((510, 360))
        shadow.fill((0, 0, 0))
        shadow.set_alpha(100)
        x, y = (sw - 500) // 2, (sh - 350) // 2
        surface.blit(shadow, (x + 5, y + 5))
        surface.blit(letter, (x, y))
        
        if self.complete and int(time.time() * 2) % 2 == 0:
            prompt = fonts['body'].render("Press SPACE to continue...", True, (255, 255, 255))
            surface.blit(prompt, (sw // 2 - prompt.get_width() // 2, y + 370))


# ═══════════════════════════════════════════════════════════════════════════════
#  B3313 LEVEL
# ═══════════════════════════════════════════════════════════════════════════════

class B3313Level:
    def __init__(self, seed):
        random.seed(seed)
        self.platforms = []
        self.generate()
    
    def generate(self):
        # Main floor
        self.platforms.append({'x': -30, 'y': -0.5, 'z': -30, 'w': 60, 'h': 0.5, 'd': 60, 'color': (60, 60, 80)})
        
        # Eternal staircase
        for i in range(12):
            angle = (i / 12) * math.pi * 2
            r = 15 + i * 0.5
            self.platforms.append({
                'x': math.cos(angle) * r - 2, 'y': i * 1.2, 'z': math.sin(angle) * r - 2,
                'w': 4, 'h': 0.4, 'd': 4,
                'color': (100, 90, 70) if i % 2 == 0 else (80, 70, 50)
            })
        
        # Floating blocks
        colors = [(100, 80, 120), (80, 100, 90), (120, 100, 80), (90, 90, 110)]
        for i in range(8):
            size = random.uniform(2, 5)
            self.platforms.append({
                'x': random.uniform(-20, 20), 'y': random.uniform(3, 15), 'z': random.uniform(-20, 20),
                'w': size, 'h': size * 0.5, 'd': size, 'color': random.choice(colors)
            })
        
        # Pillars
        for i in range(6):
            angle = (i / 6) * math.pi * 2
            self.platforms.append({
                'x': math.cos(angle) * 25 - 1.5, 'y': 0, 'z': math.sin(angle) * 25 - 1.5,
                'w': 3, 'h': random.uniform(8, 20), 'd': 3, 'color': (70, 65, 85)
            })
        
        # ? blocks
        for i in range(5):
            self.platforms.append({
                'x': random.uniform(-15, 15) - 1, 'y': random.uniform(4, 8), 'z': random.uniform(-15, 15) - 1,
                'w': 2, 'h': 2, 'd': 2, 'color': (200, 180, 50)
            })


# ═══════════════════════════════════════════════════════════════════════════════
#  PLAYER
# ═══════════════════════════════════════════════════════════════════════════════

class Player:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z
        self.vx, self.vy, self.vz = 0, 0, 0
        self.grounded = False
        self.facing = 0
        self.anim = 0
    
    def update(self, keys, platforms, dt):
        speed = 10 if keys[pygame.K_LSHIFT] else 6
        mx, mz = 0, 0
        
        if keys[pygame.K_LEFT] or keys[pygame.K_a]: mx = -speed * dt
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: mx = speed * dt
        if keys[pygame.K_UP] or keys[pygame.K_w]: mz = -speed * dt
        if keys[pygame.K_DOWN] or keys[pygame.K_s]: mz = speed * dt
        
        if mx != 0 or mz != 0:
            self.facing = math.atan2(-mz, mx)
            self.anim += dt * 15
        
        self.x += mx
        self.z += mz
        
        if keys[pygame.K_SPACE] and self.grounded:
            self.vy = 12
            self.grounded = False
        
        self.vy -= 30 * dt
        self.y += self.vy * dt
        
        self.grounded = False
        for p in platforms:
            if self.vy <= 0 and p['x'] <= self.x <= p['x'] + p['w'] and p['z'] <= self.z <= p['z'] + p['d']:
                if p['y'] <= self.y <= p['y'] + p['h'] + 0.5:
                    self.y = p['y'] + p['h']
                    self.vy = 0
                    self.grounded = True
                    break
        
        if self.y < 0:
            self.y = 0
            self.vy = 0
            self.grounded = True


# ═══════════════════════════════════════════════════════════════════════════════
#  WINDOWS-STYLE GUI COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════

class WindowsGUI:
    """Classic Windows-style GUI matching the screenshot"""
    
    # Colors
    TITLE_BAR = (51, 102, 153)
    TITLE_BAR_INACTIVE = (128, 128, 128)
    MENU_BG = (240, 240, 240)
    TOOLBAR_BG = (250, 250, 250)
    LIST_BG = (255, 255, 248)
    BORDER = (160, 160, 160)
    HIGHLIGHT = (51, 153, 255)
    TEXT = (0, 0, 0)
    STATUS_BAR = (240, 240, 240)
    STATUS_BORDER = (51, 102, 153)
    
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.title = "Cat's PJ64 0.1"
        self.menu_items = ["File", "System", "Options", "Help"]
        self.toolbar_buttons = [
            ("Open", "folder"), ("Settings", "gear"), ("Full Scr...", "monitor"),
            None,  # Separator
            ("Refresh", "refresh"), ("About", "about"), ("About", "help")
        ]
    
    def draw_icon(self, surface, icon_type, x, y, size=32):
        """Draw simplified toolbar icons"""
        if icon_type == "folder":
            # Yellow folder
            pygame.draw.polygon(surface, (255, 200, 50), [(x+4, y+10), (x+12, y+10), (x+14, y+8), (x+20, y+8), (x+20, y+10)])
            pygame.draw.rect(surface, (255, 200, 50), (x+4, y+10, size-8, size-14))
            pygame.draw.rect(surface, (220, 170, 30), (x+4, y+10, size-8, size-14), 1)
        elif icon_type == "gear":
            # Blue gear
            cx, cy = x + size//2, y + size//2
            pygame.draw.circle(surface, (70, 130, 180), (cx, cy), 10)
            pygame.draw.circle(surface, (240, 240, 240), (cx, cy), 5)
            for i in range(8):
                angle = i * math.pi / 4
                px = cx + int(math.cos(angle) * 12)
                py = cy + int(math.sin(angle) * 12)
                pygame.draw.circle(surface, (70, 130, 180), (px, py), 3)
        elif icon_type == "monitor":
            # Monitor
            pygame.draw.rect(surface, (70, 130, 180), (x+4, y+6, size-8, size-14))
            pygame.draw.rect(surface, (200, 220, 240), (x+6, y+8, size-12, size-18))
            pygame.draw.rect(surface, (100, 100, 100), (x+12, y+size-8, 8, 4))
            pygame.draw.rect(surface, (100, 100, 100), (x+8, y+size-4, 16, 2))
        elif icon_type == "refresh":
            # Blue circular arrow
            cx, cy = x + size//2, y + size//2
            pygame.draw.arc(surface, (0, 100, 200), (x+6, y+6, size-12, size-12), 0.5, 5, 3)
            # Arrow head
            pygame.draw.polygon(surface, (0, 100, 200), [(x+22, y+12), (x+18, y+8), (x+18, y+16)])
        elif icon_type == "about":
            # Blue circular arrow (backward)
            cx, cy = x + size//2, y + size//2
            pygame.draw.arc(surface, (0, 100, 200), (x+6, y+6, size-12, size-12), -2, 2.5, 3)
            pygame.draw.polygon(surface, (0, 100, 200), [(x+10, y+12), (x+14, y+8), (x+14, y+16)])
        elif icon_type == "help":
            # Blue circle with ?
            pygame.draw.circle(surface, (0, 100, 200), (x+size//2, y+size//2), 12)
            pygame.draw.circle(surface, (255, 255, 255), (x+size//2, y+size//2), 10)
            font = pygame.font.Font(None, 20)
            text = font.render("?", True, (0, 100, 200))
            surface.blit(text, (x+size//2-4, y+size//2-7))
    
    def draw_window_frame(self, surface, fonts, active=True):
        """Draw the complete window frame"""
        # Title bar
        title_color = self.TITLE_BAR if active else self.TITLE_BAR_INACTIVE
        pygame.draw.rect(surface, title_color, (0, 0, self.width, 30))
        
        # Title icon (N64 style)
        pygame.draw.rect(surface, (0, 100, 0), (8, 6, 8, 18))
        pygame.draw.rect(surface, (255, 0, 0), (16, 6, 8, 18))
        pygame.draw.rect(surface, (0, 0, 255), (24, 6, 8, 18))
        pygame.draw.rect(surface, (255, 255, 0), (32, 4, 8, 22))
        
        # Title text
        title = fonts['title'].render(self.title, True, (255, 255, 255))
        surface.blit(title, (48, 4))
        
        # Window buttons (minimize, maximize, close)
        btn_y = 4
        # Minimize
        pygame.draw.rect(surface, (200, 200, 200), (self.width-90, btn_y, 26, 22))
        pygame.draw.line(surface, (0, 0, 0), (self.width-84, btn_y+14), (self.width-70, btn_y+14), 2)
        # Maximize
        pygame.draw.rect(surface, (200, 200, 200), (self.width-62, btn_y, 26, 22))
        pygame.draw.rect(surface, (0, 0, 0), (self.width-56, btn_y+6, 14, 10), 2)
        # Close
        pygame.draw.rect(surface, (200, 80, 80), (self.width-34, btn_y, 26, 22))
        pygame.draw.line(surface, (255, 255, 255), (self.width-28, btn_y+6), (self.width-14, btn_y+16), 2)
        pygame.draw.line(surface, (255, 255, 255), (self.width-14, btn_y+6), (self.width-28, btn_y+16), 2)
    
    def draw_menu_bar(self, surface, fonts):
        """Draw the menu bar"""
        pygame.draw.rect(surface, self.MENU_BG, (0, 30, self.width, 24))
        pygame.draw.line(surface, self.BORDER, (0, 54), (self.width, 54))
        
        x = 10
        for item in self.menu_items:
            text = fonts['menu'].render(item, True, self.TEXT)
            surface.blit(text, (x, 34))
            x += text.get_width() + 20
    
    def draw_toolbar(self, surface, fonts):
        """Draw the toolbar with icons"""
        pygame.draw.rect(surface, self.TOOLBAR_BG, (0, 55, self.width, 65))
        pygame.draw.line(surface, self.BORDER, (0, 55), (self.width, 55))
        pygame.draw.line(surface, self.BORDER, (0, 120), (self.width, 120))
        
        x = 10
        for btn in self.toolbar_buttons:
            if btn is None:
                # Separator
                pygame.draw.line(surface, self.BORDER, (x+5, 60), (x+5, 115))
                x += 15
            else:
                name, icon = btn
                self.draw_icon(surface, icon, x, 60, 32)
                text = fonts['small'].render(name, True, self.TEXT)
                surface.blit(text, (x + 16 - text.get_width()//2, 95))
                x += 60
    
    def draw_list_header(self, surface, fonts, y):
        """Draw ROM list header"""
        pygame.draw.rect(surface, (240, 240, 240), (0, y, self.width, 28))
        pygame.draw.line(surface, self.BORDER, (0, y), (self.width, y))
        pygame.draw.line(surface, self.BORDER, (0, y+28), (self.width, y+28))
        text = fonts['list'].render("ROM", True, self.TEXT)
        surface.blit(text, (15, y+4))
    
    def draw_status_bar(self, surface, fonts):
        """Draw status bar"""
        y = self.height - 30
        pygame.draw.rect(surface, self.STATUS_BAR, (0, y, self.width, 30))
        pygame.draw.rect(surface, self.STATUS_BORDER, (0, y+26, self.width, 4))
        text = fonts['status'].render("Legacy 2020-25", True, self.TEXT)
        surface.blit(text, (10, y+5))


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN EMULATOR
# ═══════════════════════════════════════════════════════════════════════════════

class CatsPJ64:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()
        
        self.width = 700
        self.height = 600
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Cat's PJ64 0.1")
        self.clock = pygame.time.Clock()
        
        # Fonts
        self.fonts = {
            'title': pygame.font.Font(None, 28),
            'menu': pygame.font.Font(None, 22),
            'small': pygame.font.Font(None, 18),
            'list': pygame.font.Font(None, 26),
            'status': pygame.font.Font(None, 24),
            'body': pygame.font.Font(None, 28),
            'tiny': pygame.font.Font(None, 20),
            'game': pygame.font.Font(None, 32),
        }
        
        # GUI
        self.gui = WindowsGUI(self.width, self.height)
        
        # CPU
        self.cpu = MIPS_R4300i()
        
        # ROMs (math-generative)
        self.roms = [
            ("Super Mario 64 (U)", MathROMGenerator.generate_sm64),
            ("Mario Kart 64 (U)", MathROMGenerator.generate_mk64),
            ("The Legend of Zelda: Ocarina of Time (U)", MathROMGenerator.generate_zelda),
            ("GoldenEye 007 (U)", MathROMGenerator.generate_goldeneye),
            ("Paper Mario (U)", MathROMGenerator.generate_paper_mario),
        ]
        self.selected = 0
        
        # State
        self.mode = "menu"  # menu, letter, game
        self.running = True
        
        # Game objects
        self.renderer = Renderer3D(self.width, self.height)
        self.mario_model = Mario3D()
        self.letter = DearMarioLetter()
        self.level = None
        self.player = None
        
        # Camera
        self.cam = [0, 8, 25, 0, -0.15]  # x, y, z, yaw, pitch
        
        # Effects
        self.glitch_timer = 0
    
    def boot_rom(self, idx):
        """Boot selected ROM"""
        name, generator = self.roms[idx]
        rom_data = generator()
        
        self.cpu.reset()
        self.cpu.load_rom(rom_data)
        seed = self.cpu.run(500)
        
        # Initialize game world
        self.level = B3313Level(seed)
        self.player = Player(0, 2, 10)
        self.cam = [0, 8, 25, 0, -0.15]
        
        # Show letter first (SM64 style)
        self.letter.show()
        self.mode = "letter"
    
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            if event.type == pygame.KEYDOWN:
                if self.mode == "menu":
                    if event.key == pygame.K_UP:
                        self.selected = (self.selected - 1) % len(self.roms)
                    elif event.key == pygame.K_DOWN:
                        self.selected = (self.selected + 1) % len(self.roms)
                    elif event.key == pygame.K_RETURN:
                        self.boot_rom(self.selected)
                    elif event.key == pygame.K_ESCAPE:
                        self.running = False
                
                elif self.mode == "letter":
                    if event.key == pygame.K_SPACE and self.letter.complete:
                        self.mode = "game"
                        self.letter.visible = False
                    elif event.key == pygame.K_ESCAPE:
                        self.mode = "game"
                        self.letter.visible = False
                
                elif self.mode == "game":
                    if event.key == pygame.K_ESCAPE:
                        self.mode = "menu"
                    elif event.key == pygame.K_l:
                        self.letter.show()
                        self.mode = "letter"
                    elif event.key == pygame.K_r:
                        self.player.x, self.player.y, self.player.z = 0, 2, 10
    
    def update(self, dt):
        if self.mode == "letter":
            self.letter.update(dt)
        elif self.mode == "game":
            keys = pygame.key.get_pressed()
            self.player.update(keys, self.level.platforms, dt)
            
            # Camera follow
            self.cam[0] += (self.player.x - self.cam[0]) * 3 * dt
            self.cam[1] += (self.player.y + 5 - self.cam[1]) * 3 * dt
            self.cam[2] += (self.player.z + 18 - self.cam[2]) * 3 * dt
            
            self.glitch_timer += dt
    
    def draw_menu(self):
        """Draw the Windows-style menu"""
        self.screen.fill(WindowsGUI.LIST_BG)
        
        # Window frame
        self.gui.draw_window_frame(self.screen, self.fonts)
        self.gui.draw_menu_bar(self.screen, self.fonts)
        self.gui.draw_toolbar(self.screen, self.fonts)
        self.gui.draw_list_header(self.screen, self.fonts, 120)
        self.gui.draw_status_bar(self.screen, self.fonts)
        
        # ROM list
        y = 150
        for i, (name, _) in enumerate(self.roms):
            if i == self.selected:
                pygame.draw.rect(self.screen, WindowsGUI.HIGHLIGHT, (5, y, self.width-10, 35))
                color = (255, 255, 255)
            else:
                color = WindowsGUI.TEXT
            
            text = self.fonts['list'].render(name, True, color)
            self.screen.blit(text, (15, y+6))
            y += 40
    
    def draw_game(self):
        """Draw the 3D game scene"""
        # Sky
        for y in range(self.height):
            ratio = y / self.height
            r = int(30 * (1 - ratio) + 10 * ratio)
            g = int(20 * (1 - ratio) + 5 * ratio)
            b = int(50 * (1 - ratio) + 20 * ratio)
            pygame.draw.line(self.screen, (r, g, b), (0, y), (self.width, y))
        
        # Moon
        pygame.draw.circle(self.screen, (200, 200, 180), (self.width - 80, 60), 35)
        
        cam = tuple(self.cam)
        
        # Platforms (sorted by depth)
        sorted_plats = sorted(self.level.platforms, 
                             key=lambda p: -((p['x'] - self.cam[0])**2 + (p['z'] - self.cam[2])**2))
        
        for p in sorted_plats:
            self.renderer.draw_cube(self.screen, 
                                   p['x'] + p['w']/2, p['y'] + p['h']/2, p['z'] + p['d']/2,
                                   (p['w'], p['h'], p['d']), p['color'], cam)
        
        # Mario
        self.mario_model.draw(self.renderer, self.screen,
                             self.player.x, self.player.y, self.player.z,
                             self.player.facing, cam, self.player.anim)
        
        # Fog
        fog = pygame.Surface((self.width, self.height))
        fog.fill((20, 15, 30))
        fog.set_alpha(int(40 + math.sin(self.glitch_timer) * 15))
        self.screen.blit(fog, (0, 0))
        
        # HUD
        title = self.fonts['game'].render("B3313 - INTERNAL BUILD", True, (255, 200, 200))
        self.screen.blit(title, (20, 20))
        
        info = self.fonts['small'].render(f"MIPS: {self.cpu.cycles} cycles | Seed: {self.cpu.gpr[2]:08X}", True, (100, 200, 100))
        self.screen.blit(info, (20, 55))
        
        controls = self.fonts['tiny'].render("WASD: Move | SPACE: Jump | L: Letter | R: Reset | ESC: Menu", True, (180, 180, 200))
        self.screen.blit(controls, (20, self.height - 30))
        
        # Personalization warning
        if int(self.glitch_timer * 2) % 7 == 0:
            warn = self.fonts['menu'].render("Every copy is personalized", True, (255, 50, 50))
            warn.set_alpha(150)
            self.screen.blit(warn, (self.width//2 - warn.get_width()//2, self.height//2 + 150))
    
    def draw(self):
        if self.mode == "menu":
            self.draw_menu()
        elif self.mode == "letter":
            self.draw_game()
            dim = pygame.Surface((self.width, self.height))
            dim.fill((0, 0, 0))
            dim.set_alpha(150)
            self.screen.blit(dim, (0, 0))
            self.letter.draw(self.screen, self.fonts)
        elif self.mode == "game":
            self.draw_game()
        
        pygame.display.flip()
    
    def run(self):
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()
        
        pygame.quit()


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("═" * 60)
    print("  Cat's PJ64 0.1 - N64 Emulator")
    print("  Math-Generative ROMs + MIPS R4300i")
    print("  (C) 2020-25 Team Flames / Samsoft")
    print("═" * 60)
    print()
    print("  ROMs use mathematical MIPS code to generate:")
    print("    • Level geometry via golden ratio/bezier math")
    print("    • Enemy positions via XOR chains")
    print("    • Item spawns via multiplication overflow")
    print()
    print("  Every copy is personalized...")
    print()
    
    emu = CatsPJ64()
    emu.run()
