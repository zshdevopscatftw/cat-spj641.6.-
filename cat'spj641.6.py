#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════════
  Cat's PJ64 1.6 Legacy - N64 Emulator
  MIPS R4300i CPU Simulator + 3D Software Renderer
  
  Includes:
    - CPU Test ROM (MIPS instruction verification)
    - Ultra Mario 3D Bros (AI-Assisted Beta ROM)
  
  (C) 2020-25 Team Flames / Samsoft
═══════════════════════════════════════════════════════════════════════════════════
"""

import pygame
import math
import struct
import random
import sys
from collections import deque

# ═══════════════════════════════════════════════════════════════════════════════
#  MIPS R4300i CPU CORE
# ═══════════════════════════════════════════════════════════════════════════════

class MIPS_R4300i:
    """Complete MIPS R4300i CPU with all major instruction types"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.gpr = [0] * 32          # General purpose registers
        self.pc = 0                   # Program counter
        self.hi = 0                   # HI register (mult/div)
        self.lo = 0                   # LO register (mult/div)
        self.cp0 = [0] * 32          # Coprocessor 0
        self.fpr = [0.0] * 32        # FPU registers
        self.fcr31 = 0               # FPU control
        self.ram = bytearray(4 * 1024 * 1024)  # 4MB RAM
        self.rom = bytearray()
        self.cycles = 0
        self.delay_slot = False
        self.delay_pc = 0
        self.halted = False
        self.output_buffer = []      # For test output
        
        # CP0 defaults
        self.cp0[12] = 0x34000000    # Status
        self.cp0[15] = 0x00000B22    # PRId (R4300i)
    
    def load_rom(self, rom_bytes):
        self.rom = bytearray(rom_bytes)
        self.pc = 0
        copy_len = min(len(self.rom), len(self.ram))
        self.ram[:copy_len] = self.rom[:copy_len]
        self.gpr[29] = 0x801F0000    # Stack pointer
        self.gpr[28] = 0x80000000    # Global pointer
    
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
    
    def read8(self, addr):
        phys = addr & 0x1FFFFFFF
        return self.ram[phys] if phys < len(self.ram) else 0
    
    def write8(self, addr, val):
        phys = addr & 0x1FFFFFFF
        if phys < len(self.ram):
            self.ram[phys] = val & 0xFF
    
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
        
        # SPECIAL (R-type)
        if op == 0x00:
            if funct == 0x00:    # SLL
                self.gpr[rd] = (self.gpr[rt] << shamt) & 0xFFFFFFFF
            elif funct == 0x02:  # SRL
                self.gpr[rd] = (self.gpr[rt] & 0xFFFFFFFF) >> shamt
            elif funct == 0x03:  # SRA
                self.gpr[rd] = (self.sext32(self.gpr[rt]) >> shamt) & 0xFFFFFFFF
            elif funct == 0x04:  # SLLV
                self.gpr[rd] = (self.gpr[rt] << (self.gpr[rs] & 0x1F)) & 0xFFFFFFFF
            elif funct == 0x06:  # SRLV
                self.gpr[rd] = (self.gpr[rt] & 0xFFFFFFFF) >> (self.gpr[rs] & 0x1F)
            elif funct == 0x08:  # JR
                self.delay_slot = True
                self.delay_pc = self.gpr[rs]
            elif funct == 0x09:  # JALR
                self.gpr[rd] = self.pc + 8
                self.delay_slot = True
                self.delay_pc = self.gpr[rs]
            elif funct == 0x0C:  # SYSCALL
                self.handle_syscall()
            elif funct == 0x0D:  # BREAK
                self.halted = True
            elif funct == 0x10:  # MFHI
                self.gpr[rd] = self.hi
            elif funct == 0x11:  # MTHI
                self.hi = self.gpr[rs]
            elif funct == 0x12:  # MFLO
                self.gpr[rd] = self.lo
            elif funct == 0x13:  # MTLO
                self.lo = self.gpr[rs]
            elif funct == 0x18:  # MULT
                res = self.sext32(self.gpr[rs]) * self.sext32(self.gpr[rt])
                self.lo = res & 0xFFFFFFFF
                self.hi = (res >> 32) & 0xFFFFFFFF
            elif funct == 0x19:  # MULTU
                res = (self.gpr[rs] & 0xFFFFFFFF) * (self.gpr[rt] & 0xFFFFFFFF)
                self.lo = res & 0xFFFFFFFF
                self.hi = (res >> 32) & 0xFFFFFFFF
            elif funct == 0x1A:  # DIV
                if self.gpr[rt] != 0:
                    self.lo = int(self.sext32(self.gpr[rs]) / self.sext32(self.gpr[rt])) & 0xFFFFFFFF
                    self.hi = int(self.sext32(self.gpr[rs]) % self.sext32(self.gpr[rt])) & 0xFFFFFFFF
            elif funct == 0x1B:  # DIVU
                if self.gpr[rt] != 0:
                    self.lo = (self.gpr[rs] & 0xFFFFFFFF) // (self.gpr[rt] & 0xFFFFFFFF)
                    self.hi = (self.gpr[rs] & 0xFFFFFFFF) % (self.gpr[rt] & 0xFFFFFFFF)
            elif funct == 0x20:  # ADD
                self.gpr[rd] = (self.gpr[rs] + self.gpr[rt]) & 0xFFFFFFFF
            elif funct == 0x21:  # ADDU
                self.gpr[rd] = (self.gpr[rs] + self.gpr[rt]) & 0xFFFFFFFF
            elif funct == 0x22:  # SUB
                self.gpr[rd] = (self.gpr[rs] - self.gpr[rt]) & 0xFFFFFFFF
            elif funct == 0x23:  # SUBU
                self.gpr[rd] = (self.gpr[rs] - self.gpr[rt]) & 0xFFFFFFFF
            elif funct == 0x24:  # AND
                self.gpr[rd] = self.gpr[rs] & self.gpr[rt]
            elif funct == 0x25:  # OR
                self.gpr[rd] = self.gpr[rs] | self.gpr[rt]
            elif funct == 0x26:  # XOR
                self.gpr[rd] = self.gpr[rs] ^ self.gpr[rt]
            elif funct == 0x27:  # NOR
                self.gpr[rd] = ~(self.gpr[rs] | self.gpr[rt]) & 0xFFFFFFFF
            elif funct == 0x2A:  # SLT
                self.gpr[rd] = 1 if self.sext32(self.gpr[rs]) < self.sext32(self.gpr[rt]) else 0
            elif funct == 0x2B:  # SLTU
                self.gpr[rd] = 1 if (self.gpr[rs] & 0xFFFFFFFF) < (self.gpr[rt] & 0xFFFFFFFF) else 0
        
        # J-type
        elif op == 0x02:  # J
            self.delay_slot = True
            self.delay_pc = ((self.pc + 4) & 0xF0000000) | (target << 2)
        elif op == 0x03:  # JAL
            self.gpr[31] = self.pc + 8
            self.delay_slot = True
            self.delay_pc = ((self.pc + 4) & 0xF0000000) | (target << 2)
        
        # Branch
        elif op == 0x04:  # BEQ
            if self.gpr[rs] == self.gpr[rt]:
                self.delay_slot = True
                self.delay_pc = self.pc + 4 + (self.sext16(imm) << 2)
        elif op == 0x05:  # BNE
            if self.gpr[rs] != self.gpr[rt]:
                self.delay_slot = True
                self.delay_pc = self.pc + 4 + (self.sext16(imm) << 2)
        elif op == 0x06:  # BLEZ
            if self.sext32(self.gpr[rs]) <= 0:
                self.delay_slot = True
                self.delay_pc = self.pc + 4 + (self.sext16(imm) << 2)
        elif op == 0x07:  # BGTZ
            if self.sext32(self.gpr[rs]) > 0:
                self.delay_slot = True
                self.delay_pc = self.pc + 4 + (self.sext16(imm) << 2)
        
        # I-type arithmetic
        elif op == 0x08:  # ADDI
            self.gpr[rt] = (self.gpr[rs] + self.sext16(imm)) & 0xFFFFFFFF
        elif op == 0x09:  # ADDIU
            self.gpr[rt] = (self.gpr[rs] + self.sext16(imm)) & 0xFFFFFFFF
        elif op == 0x0A:  # SLTI
            self.gpr[rt] = 1 if self.sext32(self.gpr[rs]) < self.sext16(imm) else 0
        elif op == 0x0B:  # SLTIU
            self.gpr[rt] = 1 if (self.gpr[rs] & 0xFFFFFFFF) < (self.sext16(imm) & 0xFFFFFFFF) else 0
        elif op == 0x0C:  # ANDI
            self.gpr[rt] = self.gpr[rs] & imm
        elif op == 0x0D:  # ORI
            self.gpr[rt] = self.gpr[rs] | imm
        elif op == 0x0E:  # XORI
            self.gpr[rt] = self.gpr[rs] ^ imm
        elif op == 0x0F:  # LUI
            self.gpr[rt] = (imm << 16) & 0xFFFFFFFF
        
        # Load/Store
        elif op == 0x20:  # LB
            addr = self.gpr[rs] + self.sext16(imm)
            val = self.read8(addr)
            self.gpr[rt] = val if val < 128 else val - 256
        elif op == 0x21:  # LH
            addr = self.gpr[rs] + self.sext16(imm)
            val = struct.unpack('>h', self.ram[(addr & 0x1FFFFFFF):(addr & 0x1FFFFFFF)+2])[0]
            self.gpr[rt] = val & 0xFFFFFFFF
        elif op == 0x23:  # LW
            addr = self.gpr[rs] + self.sext16(imm)
            self.gpr[rt] = self.read32(addr)
        elif op == 0x24:  # LBU
            addr = self.gpr[rs] + self.sext16(imm)
            self.gpr[rt] = self.read8(addr)
        elif op == 0x25:  # LHU
            addr = self.gpr[rs] + self.sext16(imm)
            self.gpr[rt] = struct.unpack('>H', self.ram[(addr & 0x1FFFFFFF):(addr & 0x1FFFFFFF)+2])[0]
        elif op == 0x28:  # SB
            addr = self.gpr[rs] + self.sext16(imm)
            self.write8(addr, self.gpr[rt])
        elif op == 0x29:  # SH
            addr = self.gpr[rs] + self.sext16(imm)
            phys = addr & 0x1FFFFFFF
            if phys + 1 < len(self.ram):
                self.ram[phys:phys+2] = struct.pack('>H', self.gpr[rt] & 0xFFFF)
        elif op == 0x2B:  # SW
            addr = self.gpr[rs] + self.sext16(imm)
            self.write32(addr, self.gpr[rt])
        
        # COP0/COP1 (simplified)
        elif op == 0x10:  # COP0
            cop_op = rs
            if cop_op == 0x00:  # MFC0
                self.gpr[rt] = self.cp0[rd]
            elif cop_op == 0x04:  # MTC0
                self.cp0[rd] = self.gpr[rt]
        
        self.gpr[0] = 0  # $zero always 0
        self.pc = next_pc
        self.cycles += 1
        
        return self.cycles < 2000
    
    def handle_syscall(self):
        """Handle syscall - $v0 = syscall number"""
        syscall = self.gpr[2]  # $v0
        if syscall == 1:  # Print integer
            self.output_buffer.append(str(self.gpr[4]))  # $a0
        elif syscall == 4:  # Print string
            addr = self.gpr[4]
            s = ""
            while True:
                c = self.read8(addr)
                if c == 0:
                    break
                s += chr(c)
                addr += 1
            self.output_buffer.append(s)
        elif syscall == 10:  # Exit
            self.halted = True
    
    def run(self, max_cycles=1000):
        while self.step() and self.cycles < max_cycles:
            pass
        return self.compute_seed()
    
    def compute_seed(self):
        seed = self.cycles
        for i, r in enumerate(self.gpr):
            seed ^= (r * (i + 1)) & 0xFFFFFFFF
        seed ^= self.hi ^ self.lo
        for i in range(0, 256, 4):
            seed ^= self.read32(i)
        return seed & 0xFFFFFFFF
    
    def dump_state(self):
        """Return CPU state for debug"""
        return {
            'pc': self.pc,
            'cycles': self.cycles,
            'gpr': self.gpr.copy(),
            'hi': self.hi,
            'lo': self.lo,
            'output': self.output_buffer.copy()
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  ROM BUILDER - Creates test ROMs and game ROMs
# ═══════════════════════════════════════════════════════════════════════════════

class ROMBuilder:
    """Assembles MIPS instructions into ROM format"""
    
    @staticmethod
    def r_type(rs, rt, rd, shamt, funct):
        return ((rs & 0x1F) << 21) | ((rt & 0x1F) << 16) | ((rd & 0x1F) << 11) | ((shamt & 0x1F) << 6) | (funct & 0x3F)
    
    @staticmethod
    def i_type(op, rs, rt, imm):
        return ((op & 0x3F) << 26) | ((rs & 0x1F) << 21) | ((rt & 0x1F) << 16) | (imm & 0xFFFF)
    
    @staticmethod
    def j_type(op, target):
        return ((op & 0x3F) << 26) | (target & 0x3FFFFFF)
    
    @staticmethod
    def build_n64_header(title, code="TEST", crc1=0x12345678, crc2=0x9ABCDEF0):
        """Build N64 ROM header (64 bytes)"""
        header = bytearray(64)
        # PI BSD Domain 1 register
        struct.pack_into('>I', header, 0, 0x80371240)
        # Clock rate
        struct.pack_into('>I', header, 4, 0x000F1E90)
        # Boot address
        struct.pack_into('>I', header, 8, 0x80000400)
        # Release
        struct.pack_into('>I', header, 12, 0x00001449)
        # CRC1 and CRC2
        struct.pack_into('>I', header, 16, crc1)
        struct.pack_into('>I', header, 20, crc2)
        # Title (20 chars at offset 0x20)
        title_bytes = title.encode('ascii')[:20].ljust(20, b' ')
        header[0x20:0x34] = title_bytes
        # Game code (4 chars at offset 0x3B)
        code_bytes = code.encode('ascii')[:4].ljust(4, b' ')
        header[0x3B:0x3F] = code_bytes
        # Country (USA)
        header[0x3E] = 0x45
        return bytes(header)
    
    @staticmethod
    def create_test_rom():
        """Create CPU test ROM - verifies MIPS instructions"""
        instrs = []
        
        # Test 1: Basic arithmetic
        # $t0 = 10
        instrs.append(ROMBuilder.i_type(0x09, 0, 8, 10))  # ADDIU $t0, $zero, 10
        # $t1 = 20
        instrs.append(ROMBuilder.i_type(0x09, 0, 9, 20))  # ADDIU $t1, $zero, 20
        # $t2 = $t0 + $t1 (should be 30)
        instrs.append(ROMBuilder.r_type(8, 9, 10, 0, 0x21))  # ADDU $t2, $t0, $t1
        
        # Test 2: Subtraction
        # $t3 = $t1 - $t0 (should be 10)
        instrs.append(ROMBuilder.r_type(9, 8, 11, 0, 0x23))  # SUBU $t3, $t1, $t0
        
        # Test 3: Logical operations
        # $t4 = 0xFF00
        instrs.append(ROMBuilder.i_type(0x0D, 0, 12, 0xFF00))  # ORI $t4, $zero, 0xFF00
        # $t5 = 0x0FF0
        instrs.append(ROMBuilder.i_type(0x0D, 0, 13, 0x0FF0))  # ORI $t5, $zero, 0x0FF0
        # $t6 = $t4 AND $t5 (should be 0x0F00)
        instrs.append(ROMBuilder.r_type(12, 13, 14, 0, 0x24))  # AND $t6, $t4, $t5
        
        # Test 4: Shifts
        # $t7 = $t0 << 2 (should be 40)
        instrs.append(ROMBuilder.r_type(0, 8, 15, 2, 0x00))  # SLL $t7, $t0, 2
        
        # Test 5: Multiplication
        # MULT $t0, $t1
        instrs.append(ROMBuilder.r_type(8, 9, 0, 0, 0x18))  # MULT $t0, $t1
        # $s0 = LO (should be 200)
        instrs.append(ROMBuilder.r_type(0, 0, 16, 0, 0x12))  # MFLO $s0
        
        # Test 6: Memory operations
        # Store $t2 to memory
        instrs.append(ROMBuilder.i_type(0x0F, 0, 17, 0x8010))  # LUI $s1, 0x8010
        instrs.append(ROMBuilder.i_type(0x2B, 17, 10, 0))       # SW $t2, 0($s1)
        # Load it back to $s2
        instrs.append(ROMBuilder.i_type(0x23, 17, 18, 0))       # LW $s2, 0($s1)
        
        # Test 7: Branch test
        # $s3 = 0
        instrs.append(ROMBuilder.i_type(0x09, 0, 19, 0))       # ADDIU $s3, $zero, 0
        # if $t0 == $t3: skip (they're both 10)
        instrs.append(ROMBuilder.i_type(0x04, 8, 11, 2))       # BEQ $t0, $t3, +2
        instrs.append(ROMBuilder.i_type(0x09, 0, 0, 0))        # NOP (delay slot)
        instrs.append(ROMBuilder.i_type(0x09, 0, 19, 999))     # ADDIU $s3, $zero, 999 (skipped)
        # $s3 should still be 0
        
        # Test 8: Set on less than
        # $s4 = ($t0 < $t1) ? 1 : 0 (should be 1)
        instrs.append(ROMBuilder.r_type(8, 9, 20, 0, 0x2A))    # SLT $s4, $t0, $t1
        
        # Store results for verification
        # Put key values in specific registers:
        # $v0 = sum of test results as checksum
        instrs.append(ROMBuilder.r_type(10, 11, 2, 0, 0x21))   # ADDU $v0, $t2, $t3
        instrs.append(ROMBuilder.r_type(2, 16, 2, 0, 0x21))    # ADDU $v0, $v0, $s0
        instrs.append(ROMBuilder.r_type(2, 20, 2, 0, 0x21))    # ADDU $v0, $v0, $s4
        
        # BREAK to halt
        instrs.append(ROMBuilder.r_type(0, 0, 0, 0, 0x0D))     # BREAK
        
        # Pad to 4KB minimum
        while len(instrs) < 1024:
            instrs.append(0)
        
        # Build ROM
        header = ROMBuilder.build_n64_header("CPU TEST ROM", "TEST", 0xDEADBEEF, 0xCAFEBABE)
        code = b''.join(struct.pack('>I', i) for i in instrs)
        
        return header + code
    
    @staticmethod
    def create_ultra_mario_rom():
        """
        Create Ultra Mario 3D Bros ROM
        AI-assisted beta ROM with procedural level generation
        """
        instrs = []
        
        # ═══════════════════════════════════════════════════════════════
        # ULTRA MARIO 3D BROS - BOOT CODE
        # Initializes game state, generates level seed, sets up player
        # ═══════════════════════════════════════════════════════════════
        
        # Initialize game state registers
        # $s0 = Player X position (fixed point 8.8)
        # $s1 = Player Y position
        # $s2 = Player Z position  
        # $s3 = Player velocity X
        # $s4 = Player velocity Y
        # $s5 = Player velocity Z
        # $s6 = Game state flags
        # $s7 = Score
        
        # Set initial player position (center of level)
        instrs.append(ROMBuilder.i_type(0x0F, 0, 16, 0x0080))  # LUI $s0, 0x0080
        instrs.append(ROMBuilder.i_type(0x0D, 16, 16, 0x0000)) # ORI $s0, $s0, 0x0000
        instrs.append(ROMBuilder.i_type(0x09, 0, 17, 0x0100))  # ADDIU $s1, $zero, 0x0100 (Y=256)
        instrs.append(ROMBuilder.i_type(0x0F, 0, 18, 0x0080))  # LUI $s2, 0x0080
        
        # Zero velocities
        instrs.append(ROMBuilder.i_type(0x09, 0, 19, 0))       # ADDIU $s3, $zero, 0
        instrs.append(ROMBuilder.i_type(0x09, 0, 20, 0))       # ADDIU $s4, $zero, 0
        instrs.append(ROMBuilder.i_type(0x09, 0, 21, 0))       # ADDIU $s5, $zero, 0
        
        # Game state: bit 0=running, bit 1=jumping, bit 2=grounded
        instrs.append(ROMBuilder.i_type(0x09, 0, 22, 0x05))    # ADDIU $s6, $zero, 5 (running + grounded)
        
        # Score = 0
        instrs.append(ROMBuilder.i_type(0x09, 0, 23, 0))       # ADDIU $s7, $zero, 0
        
        # ═══════════════════════════════════════════════════════════════
        # LEVEL GENERATION SEED
        # Use MIPS math to generate pseudo-random level data
        # ═══════════════════════════════════════════════════════════════
        
        # $t0 = base seed (Mario-themed constant: 0x4D415249 = "MARI")
        instrs.append(ROMBuilder.i_type(0x0F, 0, 8, 0x4D41))   # LUI $t0, 0x4D41
        instrs.append(ROMBuilder.i_type(0x0D, 8, 8, 0x5249))   # ORI $t0, $t0, 0x5249
        
        # $t1 = secondary seed (0x4F333D42 = "O3=B" for "3D Bros")
        instrs.append(ROMBuilder.i_type(0x0F, 0, 9, 0x4F33))   # LUI $t1, 0x4F33
        instrs.append(ROMBuilder.i_type(0x0D, 9, 9, 0x3D42))   # ORI $t1, $t1, 0x3D42
        
        # Generate level parameters via multiplication
        instrs.append(ROMBuilder.r_type(8, 9, 0, 0, 0x19))     # MULTU $t0, $t1
        instrs.append(ROMBuilder.r_type(0, 0, 10, 0, 0x12))    # MFLO $t2 (level width seed)
        instrs.append(ROMBuilder.r_type(0, 0, 11, 0, 0x10))    # MFHI $t3 (level height seed)
        
        # XOR for platform positions
        instrs.append(ROMBuilder.r_type(10, 11, 12, 0, 0x26))  # XOR $t4, $t2, $t3
        
        # Shift for enemy spawn positions
        instrs.append(ROMBuilder.r_type(0, 10, 13, 8, 0x02))   # SRL $t5, $t2, 8
        instrs.append(ROMBuilder.r_type(0, 11, 14, 4, 0x00))   # SLL $t6, $t3, 4
        
        # Combine for coin positions
        instrs.append(ROMBuilder.r_type(13, 14, 15, 0, 0x25))  # OR $t7, $t5, $t6
        
        # ═══════════════════════════════════════════════════════════════
        # PHYSICS CONSTANTS (stored in memory)
        # ═══════════════════════════════════════════════════════════════
        
        # Set up memory base at 0x80100000
        instrs.append(ROMBuilder.i_type(0x0F, 0, 24, 0x8010))  # LUI $t8, 0x8010
        
        # Gravity = 0x0008 (8 in fixed point)
        instrs.append(ROMBuilder.i_type(0x09, 0, 25, 0x0008))  # ADDIU $t9, $zero, 8
        instrs.append(ROMBuilder.i_type(0x2B, 24, 25, 0))      # SW $t9, 0($t8) - gravity
        
        # Jump velocity = 0x0060
        instrs.append(ROMBuilder.i_type(0x09, 0, 25, 0x0060))  # ADDIU $t9, $zero, 96
        instrs.append(ROMBuilder.i_type(0x2B, 24, 25, 4))      # SW $t9, 4($t8) - jump_vel
        
        # Max fall speed = 0x0040
        instrs.append(ROMBuilder.i_type(0x09, 0, 25, 0x0040))  # ADDIU $t9, $zero, 64
        instrs.append(ROMBuilder.i_type(0x2B, 24, 25, 8))      # SW $t9, 8($t8) - max_fall
        
        # Walk speed = 0x0010
        instrs.append(ROMBuilder.i_type(0x09, 0, 25, 0x0010))  # ADDIU $t9, $zero, 16
        instrs.append(ROMBuilder.i_type(0x2B, 24, 25, 12))     # SW $t9, 12($t8) - walk_speed
        
        # Run speed = 0x0020
        instrs.append(ROMBuilder.i_type(0x09, 0, 25, 0x0020))  # ADDIU $t9, $zero, 32
        instrs.append(ROMBuilder.i_type(0x2B, 24, 25, 16))     # SW $t9, 16($t8) - run_speed
        
        # ═══════════════════════════════════════════════════════════════
        # PLATFORM DATA (procedurally generated)
        # Store at 0x80100100
        # ═══════════════════════════════════════════════════════════════
        
        instrs.append(ROMBuilder.i_type(0x09, 24, 24, 0x0100)) # ADDIU $t8, $t8, 0x100
        
        # Generate 8 platforms using seeds
        for i in range(8):
            # Platform X = (seed >> i) & 0x1FF
            instrs.append(ROMBuilder.r_type(0, 12, 25, i, 0x02))   # SRL $t9, $t4, i
            instrs.append(ROMBuilder.i_type(0x0C, 25, 25, 0x1FF))  # ANDI $t9, $t9, 0x1FF
            instrs.append(ROMBuilder.i_type(0x2B, 24, 25, i*16))   # SW $t9, offset($t8)
            
            # Platform Y = 64 + (i * 32)
            instrs.append(ROMBuilder.i_type(0x09, 0, 25, 64 + i*32))
            instrs.append(ROMBuilder.i_type(0x2B, 24, 25, i*16+4))
            
            # Platform width = 32 + ((seed >> (i+8)) & 0x3F)
            instrs.append(ROMBuilder.r_type(0, 15, 25, i+8, 0x02))
            instrs.append(ROMBuilder.i_type(0x0C, 25, 25, 0x3F))
            instrs.append(ROMBuilder.i_type(0x09, 25, 25, 32))
            instrs.append(ROMBuilder.i_type(0x2B, 24, 25, i*16+8))
        
        # ═══════════════════════════════════════════════════════════════
        # GAME LOOP SIMULATION
        # Runs a few iterations to establish initial state
        # ═══════════════════════════════════════════════════════════════
        
        # Loop counter
        instrs.append(ROMBuilder.i_type(0x09, 0, 8, 10))       # ADDIU $t0, $zero, 10
        
        # GAME_LOOP:
        loop_start = len(instrs)
        
        # Apply gravity to Y velocity
        instrs.append(ROMBuilder.i_type(0x09, 20, 20, 0x0008)) # ADDIU $s4, $s4, 8 (gravity)
        
        # Update Y position
        instrs.append(ROMBuilder.r_type(17, 20, 17, 0, 0x23))  # SUBU $s1, $s1, $s4
        
        # Ground collision check: if Y < 64, Y = 64, vel_y = 0
        instrs.append(ROMBuilder.i_type(0x0A, 17, 25, 64))     # SLTI $t9, $s1, 64
        instrs.append(ROMBuilder.i_type(0x04, 25, 0, 3))       # BEQ $t9, $zero, +3 (skip if not grounded)
        instrs.append(ROMBuilder.i_type(0x09, 0, 0, 0))        # NOP (delay slot)
        instrs.append(ROMBuilder.i_type(0x09, 0, 17, 64))      # ADDIU $s1, $zero, 64
        instrs.append(ROMBuilder.i_type(0x09, 0, 20, 0))       # ADDIU $s4, $zero, 0
        
        # Decrement loop counter
        instrs.append(ROMBuilder.i_type(0x09, 8, 8, -1))       # ADDIU $t0, $t0, -1
        
        # Branch if counter > 0
        loop_end = len(instrs)
        branch_offset = loop_start - loop_end - 1
        instrs.append(ROMBuilder.i_type(0x05, 8, 0, branch_offset & 0xFFFF))  # BNE $t0, $zero, loop
        instrs.append(ROMBuilder.i_type(0x09, 0, 0, 0))        # NOP (delay slot)
        
        # ═══════════════════════════════════════════════════════════════
        # FINAL STATE - Set $v0 to game seed for renderer
        # ═══════════════════════════════════════════════════════════════
        
        # $v0 = hash of game state
        instrs.append(ROMBuilder.r_type(16, 17, 2, 0, 0x26))   # XOR $v0, $s0, $s1
        instrs.append(ROMBuilder.r_type(2, 18, 2, 0, 0x26))    # XOR $v0, $v0, $s2
        instrs.append(ROMBuilder.r_type(2, 12, 2, 0, 0x26))    # XOR $v0, $v0, $t4
        instrs.append(ROMBuilder.r_type(2, 15, 2, 0, 0x26))    # XOR $v0, $v0, $t7
        
        # $v1 = platform count (8)
        instrs.append(ROMBuilder.i_type(0x09, 0, 3, 8))        # ADDIU $v1, $zero, 8
        
        # Halt
        instrs.append(ROMBuilder.r_type(0, 0, 0, 0, 0x0D))     # BREAK
        
        # Pad ROM
        while len(instrs) < 2048:
            instrs.append(0)
        
        # Build ROM with header
        header = ROMBuilder.build_n64_header("ULTRA MARIO 3D BROS", "UMAB", 0x55555555, 0xAAAAAAAA)
        code = b''.join(struct.pack('>I', i) for i in instrs)
        
        return header + code


# ═══════════════════════════════════════════════════════════════════════════════
#  3D SOFTWARE RENDERER
# ═══════════════════════════════════════════════════════════════════════════════

class SoftwareRenderer:
    """Simple 3D software renderer with N64-style graphics"""
    
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.z_buffer = [[float('inf')] * width for _ in range(height)]
        self.fov = 60
        self.near = 0.1
        self.far = 1000
        self.aspect = width / height
    
    def clear_zbuffer(self):
        for y in range(self.height):
            for x in range(self.width):
                self.z_buffer[y][x] = float('inf')
    
    def project(self, x, y, z, cam_x, cam_y, cam_z, cam_yaw, cam_pitch):
        """Project 3D point to 2D screen coordinates"""
        # Translate relative to camera
        dx = x - cam_x
        dy = y - cam_y
        dz = z - cam_z
        
        # Rotate around Y axis (yaw)
        cos_yaw = math.cos(cam_yaw)
        sin_yaw = math.sin(cam_yaw)
        rx = dx * cos_yaw - dz * sin_yaw
        rz = dx * sin_yaw + dz * cos_yaw
        
        # Rotate around X axis (pitch)
        cos_pitch = math.cos(cam_pitch)
        sin_pitch = math.sin(cam_pitch)
        ry = dy * cos_pitch - rz * sin_pitch
        final_z = dy * sin_pitch + rz * cos_pitch
        
        # Avoid division by zero
        if final_z <= self.near:
            return None
        
        # Perspective projection
        fov_rad = math.radians(self.fov)
        scale = 1.0 / math.tan(fov_rad / 2)
        
        sx = (rx * scale / final_z) * (self.width / 2) + self.width / 2
        sy = (-ry * scale / final_z) * (self.height / 2) + self.height / 2
        
        return int(sx), int(sy), final_z
    
    def draw_line_3d(self, surface, p1, p2, color, cam):
        """Draw 3D line"""
        proj1 = self.project(p1[0], p1[1], p1[2], *cam)
        proj2 = self.project(p2[0], p2[1], p2[2], *cam)
        
        if proj1 and proj2:
            pygame.draw.line(surface, color, (proj1[0], proj1[1]), (proj2[0], proj2[1]), 2)
    
    def draw_filled_quad(self, surface, points, color, cam):
        """Draw filled 3D quad"""
        projected = []
        for p in points:
            proj = self.project(p[0], p[1], p[2], *cam)
            if proj:
                projected.append((proj[0], proj[1]))
        
        if len(projected) >= 3:
            pygame.draw.polygon(surface, color, projected)
    
    def draw_cube(self, surface, x, y, z, size, color, cam):
        """Draw 3D cube"""
        s = size / 2
        vertices = [
            (x-s, y-s, z-s), (x+s, y-s, z-s), (x+s, y+s, z-s), (x-s, y+s, z-s),
            (x-s, y-s, z+s), (x+s, y-s, z+s), (x+s, y+s, z+s), (x-s, y+s, z+s)
        ]
        edges = [
            (0,1), (1,2), (2,3), (3,0),
            (4,5), (5,6), (6,7), (7,4),
            (0,4), (1,5), (2,6), (3,7)
        ]
        
        for edge in edges:
            self.draw_line_3d(surface, vertices[edge[0]], vertices[edge[1]], color, cam)
    
    def draw_platform(self, surface, x, y, z, width, depth, color, cam):
        """Draw 3D platform"""
        h = 0.2  # Platform height
        # Top face
        top = [(x, y, z), (x+width, y, z), (x+width, y, z+depth), (x, y, z+depth)]
        self.draw_filled_quad(surface, top, color, cam)
        # Front face
        front = [(x, y-h, z+depth), (x+width, y-h, z+depth), (x+width, y, z+depth), (x, y, z+depth)]
        darker = tuple(max(0, c-50) for c in color)
        self.draw_filled_quad(surface, front, darker, cam)


# ═══════════════════════════════════════════════════════════════════════════════
#  GAME CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

class Mario3D:
    """Mario player character"""
    
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z
        self.vx = 0
        self.vy = 0
        self.vz = 0
        self.grounded = True
        self.facing = 0  # Angle
        self.state = "idle"
        self.anim_frame = 0
        self.coins = 0
        self.stars = 0
        self.lives = 3
    
    def update(self, keys, platforms, dt):
        # Horizontal movement
        speed = 8
        if keys[pygame.K_LSHIFT]:
            speed = 12
        
        move_x = 0
        move_z = 0
        
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            move_x = -speed * dt
            self.facing = math.pi
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            move_x = speed * dt
            self.facing = 0
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            move_z = -speed * dt
            self.facing = -math.pi/2
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            move_z = speed * dt
            self.facing = math.pi/2
        
        # Diagonal facing
        if move_x != 0 and move_z != 0:
            self.facing = math.atan2(move_z, move_x)
        
        self.x += move_x
        self.z += move_z
        
        # Jumping
        if (keys[pygame.K_SPACE] or keys[pygame.K_z]) and self.grounded:
            self.vy = 15
            self.grounded = False
            self.state = "jump"
        
        # Gravity
        self.vy -= 30 * dt
        self.y += self.vy * dt
        
        # Ground collision
        self.grounded = False
        for plat in platforms:
            if self.check_platform_collision(plat):
                self.y = plat['y'] + 1
                self.vy = 0
                self.grounded = True
                break
        
        # Floor
        if self.y < 0:
            self.y = 0
            self.vy = 0
            self.grounded = True
        
        # Update state
        if self.grounded:
            if abs(move_x) > 0.1 or abs(move_z) > 0.1:
                self.state = "run"
            else:
                self.state = "idle"
        
        # Animation
        self.anim_frame += dt * 10
    
    def check_platform_collision(self, plat):
        px, py, pz = plat['x'], plat['y'], plat['z']
        pw, pd = plat['width'], plat['depth']
        
        if self.vy > 0:  # Moving up
            return False
        
        if px <= self.x <= px + pw and pz <= self.z <= pz + pd:
            if abs(self.y - py) < 2:
                return True
        return False
    
    def draw(self, surface, renderer, cam):
        # Draw Mario as colored cubes
        # Body (red)
        renderer.draw_cube(surface, self.x, self.y + 0.5, self.z, 1.0, (255, 0, 0), cam)
        # Head (skin)
        renderer.draw_cube(surface, self.x, self.y + 1.3, self.z, 0.8, (255, 200, 150), cam)
        # Hat (red)
        renderer.draw_cube(surface, self.x, self.y + 1.8, self.z, 0.6, (255, 50, 50), cam)


class Coin3D:
    """Collectible coin"""
    
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z
        self.collected = False
        self.rotation = 0
    
    def update(self, dt):
        self.rotation += dt * 3
        # Bob up and down
        self.y += math.sin(self.rotation * 2) * 0.02
    
    def check_collect(self, mario):
        if self.collected:
            return False
        dist = math.sqrt((self.x - mario.x)**2 + (self.y - mario.y)**2 + (self.z - mario.z)**2)
        if dist < 1.5:
            self.collected = True
            return True
        return False
    
    def draw(self, surface, renderer, cam):
        if self.collected:
            return
        # Draw as yellow spinning disc
        color = (255, 220, 0)
        renderer.draw_cube(surface, self.x, self.y, self.z, 0.5, color, cam)


class Goomba3D:
    """Enemy Goomba"""
    
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z
        self.vx = random.choice([-2, 2])
        self.alive = True
        self.patrol_start = x
        self.patrol_range = 5
    
    def update(self, dt):
        if not self.alive:
            return
        
        self.x += self.vx * dt
        
        # Patrol behavior
        if abs(self.x - self.patrol_start) > self.patrol_range:
            self.vx = -self.vx
    
    def check_stomp(self, mario):
        if not self.alive:
            return False
        dist_xz = math.sqrt((self.x - mario.x)**2 + (self.z - mario.z)**2)
        if dist_xz < 1.0 and mario.y > self.y + 0.5 and mario.vy < 0:
            self.alive = False
            return True
        return False
    
    def check_hit(self, mario):
        if not self.alive:
            return False
        dist = math.sqrt((self.x - mario.x)**2 + (self.y - mario.y)**2 + (self.z - mario.z)**2)
        return dist < 1.0
    
    def draw(self, surface, renderer, cam):
        if not self.alive:
            return
        # Brown body
        renderer.draw_cube(surface, self.x, self.y + 0.3, self.z, 0.8, (139, 90, 43), cam)
        # Feet
        renderer.draw_cube(surface, self.x, self.y, self.z, 0.4, (50, 30, 10), cam)


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN EMULATOR
# ═══════════════════════════════════════════════════════════════════════════════

class PJ64Emulator:
    """Cat's PJ64 1.6 Legacy - Main Emulator"""
    
    def __init__(self):
        pygame.init()
        pygame.mixer.init()
        
        self.width = 800
        self.height = 600
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Cat's PJ64 1.6 Legacy - N64 Emulator")
        self.clock = pygame.time.Clock()
        
        # Fonts
        self.font_large = pygame.font.Font(None, 48)
        self.font_med = pygame.font.Font(None, 32)
        self.font_small = pygame.font.Font(None, 24)
        self.font_tiny = pygame.font.Font(None, 18)
        
        # CPU
        self.cpu = MIPS_R4300i()
        
        # Renderer
        self.renderer = SoftwareRenderer(self.width, self.height)
        
        # ROMs
        self.roms = {
            "CPU Test ROM": ROMBuilder.create_test_rom(),
            "Ultra Mario 3D Bros (Beta)": ROMBuilder.create_ultra_mario_rom(),
        }
        self.rom_list = list(self.roms.keys())
        self.selected_rom = 0
        
        # State
        self.mode = "menu"  # menu, boot, game, debug
        self.current_rom = None
        self.running = True
        
        # Game objects (for Ultra Mario)
        self.mario = None
        self.platforms = []
        self.coins = []
        self.enemies = []
        
        # Camera
        self.cam_x = 0
        self.cam_y = 5
        self.cam_z = 15
        self.cam_yaw = 0
        self.cam_pitch = -0.3
        
        # Debug
        self.show_debug = False
        self.boot_timer = 0
        self.boot_messages = []
        
        # Colors
        self.bg_color = (20, 20, 40)
        self.menu_bg = (30, 30, 60)
        self.highlight = (100, 150, 255)
    
    def boot_rom(self, rom_name):
        """Boot selected ROM"""
        self.current_rom = rom_name
        rom_data = self.roms[rom_name]
        
        # Reset CPU
        self.cpu.reset()
        self.cpu.load_rom(rom_data)
        
        # Parse header
        self.boot_messages = []
        self.boot_messages.append(f"Loading: {rom_name}")
        
        if len(rom_data) >= 64:
            title = rom_data[0x20:0x34].decode('ascii', errors='replace').strip()
            self.boot_messages.append(f"ROM Title: {title}")
            crc1 = struct.unpack('>I', rom_data[16:20])[0]
            crc2 = struct.unpack('>I', rom_data[20:24])[0]
            self.boot_messages.append(f"CRC: {crc1:08X} / {crc2:08X}")
        
        self.boot_messages.append("Initializing MIPS R4300i CPU...")
        self.boot_messages.append(f"RAM: 4MB | ROM: {len(rom_data)} bytes")
        
        # Execute ROM code
        self.boot_messages.append("Executing boot code...")
        seed = self.cpu.run(1000)
        self.boot_messages.append(f"Cycles: {self.cpu.cycles} | Seed: {seed:08X}")
        
        # Get CPU state
        state = self.cpu.dump_state()
        self.boot_messages.append(f"$v0: {state['gpr'][2]:08X} | $v1: {state['gpr'][3]:08X}")
        
        if self.cpu.output_buffer:
            self.boot_messages.append(f"Output: {' '.join(self.cpu.output_buffer)}")
        
        self.boot_messages.append("Boot complete!")
        
        # Initialize game if Ultra Mario
        if "Ultra Mario" in rom_name:
            self.init_ultra_mario(seed)
        
        self.mode = "boot"
        self.boot_timer = 0
    
    def init_ultra_mario(self, seed):
        """Initialize Ultra Mario 3D Bros game world"""
        random.seed(seed)
        
        # Create Mario
        self.mario = Mario3D(0, 1, 0)
        
        # Generate platforms from CPU state
        self.platforms = []
        
        # Ground platform
        self.platforms.append({
            'x': -20, 'y': 0, 'z': -20,
            'width': 40, 'depth': 40,
            'color': (34, 139, 34)  # Green grass
        })
        
        # Floating platforms
        num_platforms = (seed >> 8) & 0xF
        num_platforms = max(5, min(12, num_platforms))
        
        for i in range(num_platforms):
            px = ((seed >> (i * 3)) & 0x1F) - 16
            py = 2 + (i * 1.5) + ((seed >> (i * 2 + 8)) & 0x3)
            pz = ((seed >> (i * 4 + 16)) & 0x1F) - 16
            pw = 3 + ((seed >> (i + 24)) & 0x3)
            
            self.platforms.append({
                'x': px, 'y': py, 'z': pz,
                'width': pw, 'depth': 3,
                'color': (139, 90, 43) if i % 2 == 0 else (100, 70, 30)
            })
        
        # Generate coins
        self.coins = []
        num_coins = 10 + ((seed >> 4) & 0xF)
        for i in range(num_coins):
            cx = ((seed >> (i * 5)) & 0x3F) - 32
            cy = 1 + ((seed >> (i * 3 + 10)) & 0x7)
            cz = ((seed >> (i * 4 + 20)) & 0x3F) - 32
            self.coins.append(Coin3D(cx, cy, cz))
        
        # Generate enemies
        self.enemies = []
        num_enemies = 3 + ((seed >> 12) & 0x7)
        for i in range(num_enemies):
            ex = ((seed >> (i * 6)) & 0x3F) - 32
            ez = ((seed >> (i * 5 + 15)) & 0x3F) - 32
            self.enemies.append(Goomba3D(ex, 0.5, ez))
        
        # Reset camera
        self.cam_x = 0
        self.cam_y = 8
        self.cam_z = 20
        self.cam_yaw = 0
        self.cam_pitch = -0.2
    
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            if event.type == pygame.KEYDOWN:
                if self.mode == "menu":
                    if event.key == pygame.K_UP:
                        self.selected_rom = (self.selected_rom - 1) % len(self.rom_list)
                    elif event.key == pygame.K_DOWN:
                        self.selected_rom = (self.selected_rom + 1) % len(self.rom_list)
                    elif event.key == pygame.K_RETURN:
                        self.boot_rom(self.rom_list[self.selected_rom])
                    elif event.key == pygame.K_ESCAPE:
                        self.running = False
                
                elif self.mode == "boot":
                    if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                        self.mode = "game"
                    elif event.key == pygame.K_ESCAPE:
                        self.mode = "menu"
                
                elif self.mode == "game":
                    if event.key == pygame.K_ESCAPE:
                        self.mode = "menu"
                    elif event.key == pygame.K_F1:
                        self.show_debug = not self.show_debug
                    elif event.key == pygame.K_r:
                        if self.mario:
                            self.mario.x = 0
                            self.mario.y = 5
                            self.mario.z = 0
                
                elif self.mode == "debug":
                    if event.key == pygame.K_ESCAPE:
                        self.mode = "game"
    
    def update(self, dt):
        if self.mode == "boot":
            self.boot_timer += dt
        
        elif self.mode == "game":
            keys = pygame.key.get_pressed()
            
            if self.mario:
                self.mario.update(keys, self.platforms, dt)
                
                # Camera follows Mario
                target_x = self.mario.x
                target_y = self.mario.y + 5
                target_z = self.mario.z + 15
                
                self.cam_x += (target_x - self.cam_x) * 2 * dt
                self.cam_y += (target_y - self.cam_y) * 2 * dt
                self.cam_z += (target_z - self.cam_z) * 2 * dt
                
                # Update coins
                for coin in self.coins:
                    coin.update(dt)
                    if coin.check_collect(self.mario):
                        self.mario.coins += 1
                
                # Update enemies
                for enemy in self.enemies:
                    enemy.update(dt)
                    if enemy.check_stomp(self.mario):
                        self.mario.vy = 10  # Bounce
                    elif enemy.check_hit(self.mario):
                        self.mario.lives -= 1
                        self.mario.x = 0
                        self.mario.y = 5
                        self.mario.z = 0
    
    def draw_menu(self):
        self.screen.fill(self.menu_bg)
        
        # Title
        title = self.font_large.render("Cat's PJ64 1.6 Legacy", True, (255, 255, 255))
        self.screen.blit(title, (self.width//2 - title.get_width()//2, 50))
        
        subtitle = self.font_small.render("N64 Emulator - MIPS R4300i Simulator", True, (150, 150, 200))
        self.screen.blit(subtitle, (self.width//2 - subtitle.get_width()//2, 100))
        
        # ROM list
        pygame.draw.rect(self.screen, (40, 40, 80), (100, 150, self.width-200, 300), border_radius=10)
        pygame.draw.rect(self.screen, self.highlight, (100, 150, self.width-200, 300), 2, border_radius=10)
        
        list_title = self.font_med.render("Select ROM:", True, (255, 255, 255))
        self.screen.blit(list_title, (120, 160))
        
        for i, rom_name in enumerate(self.rom_list):
            y = 210 + i * 50
            
            if i == self.selected_rom:
                pygame.draw.rect(self.screen, (60, 60, 120), (110, y-5, self.width-220, 40), border_radius=5)
                color = (255, 255, 100)
                prefix = "► "
            else:
                color = (200, 200, 200)
                prefix = "  "
            
            text = self.font_med.render(f"{prefix}{rom_name}", True, color)
            self.screen.blit(text, (130, y))
            
            # ROM info
            rom_data = self.roms[rom_name]
            info = self.font_tiny.render(f"Size: {len(rom_data)} bytes", True, (120, 120, 150))
            self.screen.blit(info, (150, y + 22))
        
        # Controls
        controls = [
            "↑/↓: Select ROM",
            "Enter: Boot ROM",
            "Esc: Quit"
        ]
        for i, ctrl in enumerate(controls):
            text = self.font_small.render(ctrl, True, (150, 150, 180))
            self.screen.blit(text, (100, 480 + i * 25))
        
        # Footer
        footer = self.font_tiny.render("(C) 2020-25 Team Flames / Samsoft", True, (100, 100, 130))
        self.screen.blit(footer, (self.width//2 - footer.get_width()//2, 570))
    
    def draw_boot(self):
        self.screen.fill((0, 0, 0))
        
        # N64 style boot screen
        logo_y = 100
        
        # Draw N64-style logo (simplified)
        pygame.draw.rect(self.screen, (0, 100, 0), (self.width//2-80, logo_y, 40, 60))
        pygame.draw.rect(self.screen, (255, 0, 0), (self.width//2-30, logo_y, 40, 60))
        pygame.draw.rect(self.screen, (0, 0, 255), (self.width//2+20, logo_y, 40, 60))
        pygame.draw.rect(self.screen, (255, 255, 0), (self.width//2+70, logo_y-20, 40, 80))
        
        title = self.font_large.render("NINTENDO 64", True, (255, 255, 255))
        self.screen.blit(title, (self.width//2 - title.get_width()//2, logo_y + 80))
        
        # Boot messages (typewriter effect)
        y = 220
        for i, msg in enumerate(self.boot_messages):
            if self.boot_timer > i * 0.3:
                # Green terminal text
                text = self.font_small.render(msg, True, (0, 255, 0))
                self.screen.blit(text, (100, y))
            y += 25
        
        # Press start
        if self.boot_timer > len(self.boot_messages) * 0.3 + 0.5:
            if int(self.boot_timer * 2) % 2 == 0:
                prompt = self.font_med.render("Press ENTER to continue", True, (255, 255, 255))
                self.screen.blit(prompt, (self.width//2 - prompt.get_width()//2, 520))
    
    def draw_game(self):
        # Sky gradient
        for y in range(self.height):
            ratio = y / self.height
            r = int(100 * (1 - ratio) + 20 * ratio)
            g = int(150 * (1 - ratio) + 50 * ratio)
            b = int(255 * (1 - ratio) + 100 * ratio)
            pygame.draw.line(self.screen, (r, g, b), (0, y), (self.width, y))
        
        cam = (self.cam_x, self.cam_y, self.cam_z, self.cam_yaw, self.cam_pitch)
        
        # Draw platforms
        for plat in self.platforms:
            self.renderer.draw_platform(
                self.screen, 
                plat['x'], plat['y'], plat['z'],
                plat['width'], plat['depth'],
                plat['color'], cam
            )
        
        # Draw coins
        for coin in self.coins:
            coin.draw(self.screen, self.renderer, cam)
        
        # Draw enemies
        for enemy in self.enemies:
            enemy.draw(self.screen, self.renderer, cam)
        
        # Draw Mario
        if self.mario:
            self.mario.draw(self.screen, self.renderer, cam)
        
        # HUD
        self.draw_hud()
        
        # Debug overlay
        if self.show_debug:
            self.draw_debug()
    
    def draw_hud(self):
        if not self.mario:
            return
        
        # Coins
        coin_text = self.font_med.render(f"★ {self.mario.coins}", True, (255, 220, 0))
        self.screen.blit(coin_text, (20, 20))
        
        # Lives
        lives_text = self.font_med.render(f"♥ {self.mario.lives}", True, (255, 100, 100))
        self.screen.blit(lives_text, (20, 55))
        
        # Game title
        title = self.font_small.render(self.current_rom, True, (255, 255, 255))
        self.screen.blit(title, (self.width - title.get_width() - 20, 20))
        
        # Controls hint
        hint = self.font_tiny.render("WASD/Arrows: Move | Space: Jump | Shift: Run | R: Reset | F1: Debug", True, (200, 200, 200))
        self.screen.blit(hint, (20, self.height - 30))
    
    def draw_debug(self):
        # Semi-transparent background
        debug_surf = pygame.Surface((300, 200))
        debug_surf.set_alpha(200)
        debug_surf.fill((0, 0, 0))
        self.screen.blit(debug_surf, (self.width - 310, 60))
        
        y = 70
        lines = [
            f"FPS: {int(self.clock.get_fps())}",
            f"CPU Cycles: {self.cpu.cycles}",
            f"PC: 0x{self.cpu.pc:08X}",
            f"$v0: 0x{self.cpu.gpr[2]:08X}",
            f"$v1: 0x{self.cpu.gpr[3]:08X}",
        ]
        
        if self.mario:
            lines.extend([
                f"Mario X: {self.mario.x:.2f}",
                f"Mario Y: {self.mario.y:.2f}",
                f"Mario Z: {self.mario.z:.2f}",
                f"Grounded: {self.mario.grounded}",
            ])
        
        for line in lines:
            text = self.font_tiny.render(line, True, (0, 255, 0))
            self.screen.blit(text, (self.width - 300, y))
            y += 18
    
    def draw(self):
        if self.mode == "menu":
            self.draw_menu()
        elif self.mode == "boot":
            self.draw_boot()
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
    print("  Cat's PJ64 1.6 Legacy - N64 Emulator")
    print("  MIPS R4300i CPU + 3D Software Renderer")
    print("  (C) 2020-25 Team Flames / Samsoft")
    print("═" * 60)
    print()
    print("Included ROMs:")
    print("  • CPU Test ROM - MIPS instruction verification")
    print("  • Ultra Mario 3D Bros (Beta) - AI-assisted Mario game")
    print()
    
    emu = PJ64Emulator()
    emu.run()
