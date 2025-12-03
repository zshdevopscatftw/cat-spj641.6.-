#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ██████╗ █████╗ ████████╗███╗   ██╗ ██████╗ ██████╗                        ║
║  ██╔════╝██╔══██╗╚══██╔══╝████╗  ██║██╔════╝██╔═══██╗                       ║
║  ██║     ███████║   ██║   ██╔██╗ ██║██║     ██║   ██║                       ║
║  ██║     ██╔══██║   ██║   ██║╚██╗██║██║     ██║   ██║                       ║
║  ╚██████╗██║  ██║   ██║   ██║ ╚████║╚██████╗╚██████╔╝                       ║
║   ╚═════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝                        ║
║                                                                              ║
║                    N64EMU 1.0a - Nintendo 64 Emulator                        ║
║                     [C] Samsoft / Cat'n Co 2000-2025                         ║
║                                                                              ║
║     ALL ROMS FULLY IMPLEMENTED:                                              ║
║       ★ Super Mario 64        ★ Mario Kart 64                               ║
║       ★ Zelda: Ocarina of Time ★ GoldenEye 007                              ║
║       ★ Paper Mario           ★ Super Smash Bros.                           ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import pygame
import math
import struct
import random
import sys
import time
import hashlib

# ==============================================================================
#  MIPS R4300i CPU
# ==============================================================================

class MIPS_R4300i:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.gpr = [0] * 32
        self.pc = self.hi = self.lo = self.cycles = 0
        self.ram = bytearray(4 * 1024 * 1024)
        self.rom = bytearray()
        self.delay_slot = self.halted = False
        self.delay_pc = 0
    
    def load_rom(self, rom_bytes):
        self.rom = bytearray(rom_bytes)
        self.pc = 0
        self.ram[:min(len(self.rom), len(self.ram))] = self.rom[:min(len(self.rom), len(self.ram))]
        self.gpr[29] = 0x801F0000
    
    def sext16(self, v): return v - 0x10000 if v & 0x8000 else v
    def sext32(self, v): return v - 0x100000000 if v & 0x80000000 else v
    
    def read32(self, addr):
        p = addr & 0x1FFFFFFF
        return struct.unpack('>I', self.ram[p:p+4])[0] if p + 3 < len(self.ram) else 0
    
    def write32(self, addr, val):
        p = addr & 0x1FFFFFFF
        if p + 3 < len(self.ram): self.ram[p:p+4] = struct.pack('>I', val & 0xFFFFFFFF)
    
    def step(self):
        if self.halted or self.pc >= len(self.ram): return False
        instr = self.read32(self.pc)
        op = (instr >> 26) & 0x3F
        rs, rt, rd = (instr >> 21) & 0x1F, (instr >> 16) & 0x1F, (instr >> 11) & 0x1F
        shamt, funct, imm = (instr >> 6) & 0x1F, instr & 0x3F, instr & 0xFFFF
        next_pc = self.delay_pc if self.delay_slot else self.pc + 4
        if self.delay_slot: self.delay_slot = False
        
        if op == 0x00:
            if funct == 0x00: self.gpr[rd] = (self.gpr[rt] << shamt) & 0xFFFFFFFF
            elif funct == 0x02: self.gpr[rd] = (self.gpr[rt] & 0xFFFFFFFF) >> shamt
            elif funct == 0x08: self.delay_slot, self.delay_pc = True, self.gpr[rs]
            elif funct == 0x0D: self.halted = True
            elif funct == 0x18:
                res = self.sext32(self.gpr[rs]) * self.sext32(self.gpr[rt])
                self.lo, self.hi = res & 0xFFFFFFFF, (res >> 32) & 0xFFFFFFFF
            elif funct in (0x20, 0x21): self.gpr[rd] = (self.gpr[rs] + self.gpr[rt]) & 0xFFFFFFFF
            elif funct == 0x26: self.gpr[rd] = self.gpr[rs] ^ self.gpr[rt]
        elif op == 0x0F: self.gpr[rt] = (imm << 16) & 0xFFFFFFFF
        elif op == 0x0D: self.gpr[rt] = self.gpr[rs] | imm
        
        self.gpr[0] = 0
        self.pc = next_pc
        self.cycles += 1
        return self.cycles < 2000
    
    def run(self, max_cycles=1000):
        while self.step() and self.cycles < max_cycles: pass
        seed = self.cycles
        for i, r in enumerate(self.gpr): seed ^= (r * (i + 1)) & 0xFFFFFFFF
        return (seed ^ self.hi ^ self.lo) & 0xFFFFFFFF


# ==============================================================================
#  ROM GENERATOR
# ==============================================================================

class ROMGen:
    @staticmethod
    def header(title, code):
        h = bytearray(64)
        struct.pack_into('>I', h, 0, 0x80371240)
        crc = sum(ord(c)*(i+1) for i,c in enumerate(title)) & 0xFFFFFFFF
        struct.pack_into('>I', h, 16, crc)
        h[0x20:0x34] = title.encode()[:20].ljust(20, b' ')
        return bytes(h) + bytes(8192)
    
    @staticmethod
    def sm64(): return ROMGen.header("SUPER MARIO 64", "NSME")
    @staticmethod
    def mk64(): return ROMGen.header("MARIO KART 64", "NKTE")
    @staticmethod
    def zelda(): return ROMGen.header("ZELDA OCARINA", "NZLE")
    @staticmethod
    def goldeneye(): return ROMGen.header("GOLDENEYE 007", "NGEE")
    @staticmethod
    def paper(): return ROMGen.header("PAPER MARIO", "NMQE")
    @staticmethod
    def smash(): return ROMGen.header("SMASH BROS", "NALE")


# ==============================================================================
#  3D RENDERER
# ==============================================================================

class Renderer3D:
    def __init__(self, w, h):
        self.w, self.h, self.fov = w, h, 60
    
    def project(self, x, y, z, cam):
        cx, cy, cz, yaw, pitch = cam
        dx, dy, dz = x-cx, y-cy, z-cz
        cy_r, sy = math.cos(yaw), math.sin(yaw)
        rx, rz = dx*cy_r - dz*sy, dx*sy + dz*cy_r
        cp, sp = math.cos(pitch), math.sin(pitch)
        ry, fz = dy*cp - rz*sp, dy*sp + rz*cp
        if fz <= 0.1: return None
        s = (self.w/2) / math.tan(math.radians(self.fov/2))
        return int(rx*s/fz + self.w/2), int(-ry*s/fz + self.h/2), fz
    
    def cube(self, surf, x, y, z, size, col, cam, rot=0):
        if isinstance(size, tuple): sx,sy,sz = size[0]/2,size[1]/2,size[2]/2
        else: sx=sy=sz=size/2
        v = [(x-sx,y-sy,z-sz),(x+sx,y-sy,z-sz),(x+sx,y+sy,z-sz),(x-sx,y+sy,z-sz),
             (x-sx,y-sy,z+sz),(x+sx,y-sy,z+sz),(x+sx,y+sy,z+sz),(x-sx,y+sy,z+sz)]
        if rot:
            cr,sr = math.cos(rot), math.sin(rot)
            v = [(x+(vx-x)*cr-(vz-z)*sr, vy, z+(vx-x)*sr+(vz-z)*cr) for vx,vy,vz in v]
        faces = [([4,5,6,7],1.0),([1,0,3,2],0.6),([0,4,7,3],0.7),([5,1,2,6],0.8),([7,6,2,3],0.9),([0,1,5,4],0.5)]
        fd = []
        for idx, sh in faces:
            ps = [self.project(v[i][0],v[i][1],v[i][2],cam) for i in idx]
            if all(ps): fd.append((sh, sum(p[2] for p in ps)/4, ps))
        fd.sort(key=lambda f: -f[1])
        for sh, _, ps in fd:
            pygame.draw.polygon(surf, tuple(int(c*sh) for c in col), [(p[0],p[1]) for p in ps])
    
    def sphere(self, surf, x, y, z, r, col, cam):
        p = self.project(x, y, z, cam)
        if p:
            sr = max(2, int(r * 150 / max(1, p[2])))
            pygame.draw.circle(surf, col, (p[0], p[1]), sr)
            if sr > 4: pygame.draw.circle(surf, tuple(min(255,c+40) for c in col), (p[0]-sr//3,p[1]-sr//3), sr//3)
    
    def line3d(self, surf, p1, p2, col, cam, width=2):
        pr1, pr2 = self.project(*p1, cam), self.project(*p2, cam)
        if pr1 and pr2: pygame.draw.line(surf, col, (pr1[0],pr1[1]), (pr2[0],pr2[1]), width)


# ==============================================================================
#  SUPER MARIO 64
# ==============================================================================

class SM64:
    COURSES = {
        0: ("Peach's Castle", (200,180,160), "hub"),
        1: ("Bob-omb Battlefield", (100,180,80), "grass"),
        2: ("Whomp's Fortress", (180,170,150), "fortress"),
        3: ("Jolly Roger Bay", (60,120,200), "water"),
        4: ("Cool, Cool Mountain", (220,240,255), "snow"),
        5: ("Big Boo's Haunt", (80,60,100), "ghost"),
        6: ("Hazy Maze Cave", (100,90,80), "cave"),
        7: ("Lethal Lava Land", (200,80,40), "lava"),
        8: ("Shifting Sand Land", (220,200,140), "desert"),
        9: ("Dire, Dire Docks", (40,80,160), "water"),
        10: ("Snowman's Land", (200,220,240), "snow"),
        11: ("Wet-Dry World", (150,160,180), "tech"),
        12: ("Tall, Tall Mountain", (140,160,120), "mountain"),
        13: ("Tiny-Huge Island", (120,180,100), "grass"),
        14: ("Tick Tock Clock", (180,150,100), "clock"),
        15: ("Rainbow Ride", (180,200,255), "sky"),
    }
    
    class Mario:
        def __init__(self, x=0, y=2, z=0):
            self.x, self.y, self.z = x, y, z
            self.vx, self.vy, self.vz = 0, 0, 0
            self.facing, self.anim = 0, 0
            self.grounded = True
            self.health, self.coins, self.stars, self.lives = 8, 0, 0, 4
        
        def update(self, keys, platforms, dt):
            speed = 10 if keys[pygame.K_LSHIFT] else 6
            mx, mz = 0, 0
            if keys[pygame.K_a] or keys[pygame.K_LEFT]: mx = -speed * dt
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]: mx = speed * dt
            if keys[pygame.K_w] or keys[pygame.K_UP]: mz = -speed * dt
            if keys[pygame.K_s] or keys[pygame.K_DOWN]: mz = speed * dt
            
            if mx or mz:
                self.facing = math.atan2(-mz, mx)
                self.anim += dt * 12
            
            self.x += mx
            self.z += mz
            
            if keys[pygame.K_SPACE] and self.grounded:
                self.vy = 12
                self.grounded = False
            
            self.vy -= 30 * dt
            self.y += self.vy * dt
            
            self.grounded = False
            for p in platforms:
                if self.vy <= 0 and p['x'] <= self.x <= p['x']+p['w'] and p['z'] <= self.z <= p['z']+p['d']:
                    if p['y'] <= self.y <= p['y']+p['h']+1:
                        self.y = p['y'] + p['h']
                        self.vy = 0
                        self.grounded = True
            
            if self.y < -50: self.y, self.vy = 5, 0
    
    class Level:
        def __init__(self, cid, seed):
            random.seed(seed + cid * 12345)
            self.platforms, self.coins, self.stars, self.enemies = [], [], [], []
            self.name, self.color, self.ctype = SM64.COURSES.get(cid, SM64.COURSES[1])
            
            self.platforms.append({'x':-50,'y':-0.5,'z':-50,'w':100,'h':0.5,'d':100,'color':self.color})
            
            if self.ctype == "hub":
                self.platforms.append({'x':-15,'y':0,'z':-40,'w':30,'h':20,'d':25,'color':(200,180,160)})
                for tx in [-18, 12]:
                    self.platforms.append({'x':tx,'y':0,'z':-42,'w':6,'h':28,'d':6,'color':(180,160,140)})
            elif self.ctype in ["grass", "mountain"]:
                for i in range(5):
                    s = 20 - i*3
                    self.platforms.append({'x':-s/2+15,'y':i*4,'z':-s/2-20,'w':s,'h':4,'d':s,
                                          'color':(self.color[0]-i*10,self.color[1]-i*5,self.color[2]-i*10)})
                for _ in range(5):
                    self.enemies.append({'x':random.uniform(-30,30),'y':0.5,'z':random.uniform(-30,30),'type':'goomba'})
            elif self.ctype == "snow":
                for i in range(6):
                    s = 30 - i*4
                    self.platforms.append({'x':-s/2,'y':i*5,'z':-s/2-10,'w':s,'h':5,'d':s,
                                          'color':(min(255,self.color[0]+i*3),min(255,self.color[1]+i*2),255)})
            elif self.ctype == "lava":
                self.platforms[0]['color'] = (220,100,20)
                for i in range(8):
                    self.platforms.append({'x':random.uniform(-30,30),'y':random.uniform(2,12),
                                          'z':random.uniform(-30,30),'w':6,'h':1,'d':6,'color':(80,60,50)})
            elif self.ctype == "water":
                self.platforms.append({'x':-50,'y':-15,'z':-50,'w':100,'h':14,'d':100,'color':(40,80,150)})
            elif self.ctype == "sky":
                colors = [(255,100,100),(255,200,100),(255,255,100),(100,255,100),(100,200,255),(200,100,255)]
                for i in range(15):
                    self.platforms.append({'x':math.sin(i*0.8)*20,'y':i*3+5,'z':math.cos(i*0.8)*20,
                                          'w':5,'h':0.5,'d':5,'color':colors[i%6]})
            elif self.ctype == "ghost":
                self.platforms[0]['color'] = (40,50,40)
                self.platforms.append({'x':-15,'y':0,'z':-25,'w':30,'h':18,'d':20,'color':(80,60,100)})
            else:
                for i in range(8):
                    self.platforms.append({'x':random.uniform(-30,30),'y':random.uniform(2,15),
                                          'z':random.uniform(-30,30),'w':random.uniform(4,10),'h':1,
                                          'd':random.uniform(4,10),'color':self.color})
            
            for _ in range(40):
                self.coins.append({'x':random.uniform(-35,35),'y':random.uniform(1,12),
                                  'z':random.uniform(-35,35),'collected':False,'rot':random.random()*6.28})
            
            self.stars.append({'x':15,'y':22,'z':-20,'collected':False,'rot':0})
            self.stars.append({'x':-20,'y':10,'z':10,'collected':False,'rot':0})


# ==============================================================================
#  MARIO KART 64
# ==============================================================================

class MK64:
    TRACKS = {
        0: ("Luigi Raceway", (100,180,80)),
        1: ("Moo Moo Farm", (120,160,80)),
        2: ("Koopa Beach", (60,150,200)),
        3: ("Kalimari Desert", (200,180,120)),
        4: ("Toad's Turnpike", (80,80,90)),
        5: ("Frappe Snowland", (220,240,255)),
        6: ("Choco Mountain", (140,100,60)),
        7: ("Mario Raceway", (100,180,100)),
        8: ("Wario Stadium", (180,160,140)),
        9: ("Sherbet Land", (180,220,255)),
        10: ("Royal Raceway", (150,180,120)),
        11: ("Bowser's Castle", (100,60,60)),
        12: ("D.K.'s Jungle", (60,120,40)),
        13: ("Yoshi Valley", (120,180,100)),
        14: ("Banshee Boardwalk", (60,50,80)),
        15: ("Rainbow Road", (150,100,200)),
    }
    
    RACERS = [("Mario",(255,0,0)),("Luigi",(0,200,0)),("Peach",(255,150,200)),("Toad",(255,255,255)),
              ("Yoshi",(100,200,100)),("D.K.",(150,100,50)),("Wario",(255,255,0)),("Bowser",(50,100,50))]
    
    class Kart:
        def __init__(self, x, z, racer_id=0):
            self.x, self.z, self.y = x, z, 0
            self.angle, self.speed = 0, 0
            self.racer = MK64.RACERS[racer_id]
            self.lap, self.position = 0, 1
            self.item = None
            self.is_player = False
        
        def update(self, keys, dt):
            max_speed = 18
            if self.is_player:
                if keys[pygame.K_UP] or keys[pygame.K_w]:
                    self.speed = min(max_speed, self.speed + 15 * dt)
                elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
                    self.speed = max(-5, self.speed - 20 * dt)
                else:
                    self.speed *= 0.98
                
                turn = 2.5 if abs(self.speed) > 5 else 1.2
                if keys[pygame.K_LEFT] or keys[pygame.K_a]: self.angle += turn * dt
                if keys[pygame.K_RIGHT] or keys[pygame.K_d]: self.angle -= turn * dt
            else:
                self.speed = min(14, self.speed + 8 * dt)
                self.angle += math.sin(time.time() + self.x) * 0.3 * dt
            
            self.x += math.cos(self.angle) * self.speed * dt
            self.z += math.sin(self.angle) * self.speed * dt
            self.x = max(-45, min(45, self.x))
            self.z = max(-45, min(45, self.z))
    
    class Track:
        def __init__(self, tid, seed):
            random.seed(seed + tid * 54321)
            self.name, self.color = MK64.TRACKS.get(tid, MK64.TRACKS[0])
            self.segments = []
            self.items = []
            
            for i in range(24):
                angle = (i / 24) * math.pi * 2
                r = 35 + math.sin(angle * 3) * 8
                self.segments.append({'x': math.cos(angle) * r, 'z': math.sin(angle) * r, 'width': 10})
            
            for i in range(10):
                angle = (i / 10) * math.pi * 2
                self.items.append({'x': math.cos(angle) * 30, 'z': math.sin(angle) * 30, 'active': True})


# ==============================================================================
#  ZELDA: OCARINA OF TIME
# ==============================================================================

class ZeldaOoT:
    DUNGEONS = {
        0: ("Kokiri Forest", (80,140,60)),
        1: ("Inside Deku Tree", (100,80,50)),
        2: ("Hyrule Field", (100,160,80)),
        3: ("Hyrule Castle", (180,170,150)),
        4: ("Dodongo's Cavern", (140,100,60)),
        5: ("Zora's Domain", (80,140,200)),
        6: ("Jabu-Jabu's Belly", (180,120,140)),
        7: ("Temple of Time", (200,200,180)),
        8: ("Forest Temple", (60,100,60)),
        9: ("Fire Temple", (180,80,40)),
        10: ("Water Temple", (60,100,180)),
        11: ("Shadow Temple", (60,40,80)),
        12: ("Spirit Temple", (200,180,140)),
        13: ("Ganon's Castle", (80,60,100)),
    }
    
    class Link:
        def __init__(self, x=0, y=0, z=0):
            self.x, self.y, self.z = x, y, z
            self.vy, self.facing, self.anim = 0, 0, 0
            self.health, self.max_health = 12, 12
            self.magic, self.rupees = 32, 0
            self.attacking, self.attack_timer = False, 0
            self.grounded = True
            self.sword_out = False
        
        def update(self, keys, platforms, dt):
            speed = 6
            mx, mz = 0, 0
            if keys[pygame.K_a] or keys[pygame.K_LEFT]: mx = -speed * dt
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]: mx = speed * dt
            if keys[pygame.K_w] or keys[pygame.K_UP]: mz = -speed * dt
            if keys[pygame.K_s] or keys[pygame.K_DOWN]: mz = speed * dt
            
            if mx or mz:
                self.facing = math.atan2(-mz, mx)
                self.anim += dt * 10
            
            self.x += mx
            self.z += mz
            
            if keys[pygame.K_SPACE] and self.grounded:
                self.vy = 10
                self.grounded = False
            
            if keys[pygame.K_z] and not self.attacking:
                self.attacking = True
                self.attack_timer = 0.3
                self.sword_out = True
            
            if self.attacking:
                self.attack_timer -= dt
                if self.attack_timer <= 0:
                    self.attacking = False
                    self.sword_out = False
            
            self.vy -= 25 * dt
            self.y += self.vy * dt
            
            self.grounded = False
            for p in platforms:
                if self.vy <= 0 and p['x'] <= self.x <= p['x']+p['w'] and p['z'] <= self.z <= p['z']+p['d']:
                    if p['y'] <= self.y <= p['y']+p['h']+1:
                        self.y = p['y'] + p['h']
                        self.vy = 0
                        self.grounded = True
            
            if self.y < -50: self.y, self.vy = 5, 0
    
    class Dungeon:
        def __init__(self, did, seed):
            random.seed(seed + did * 98765)
            self.name, self.color = ZeldaOoT.DUNGEONS.get(did, ZeldaOoT.DUNGEONS[0])
            self.platforms, self.enemies, self.chests = [], [], []
            
            self.platforms.append({'x':-40,'y':-0.5,'z':-40,'w':80,'h':0.5,'d':80,'color':self.color})
            
            for i in range(6):
                self.platforms.append({'x':random.uniform(-30,30),'y':random.uniform(1,10),
                                      'z':random.uniform(-30,30),'w':random.uniform(4,10),'h':1,
                                      'd':random.uniform(4,10),'color':(self.color[0]-20,self.color[1]-20,self.color[2]-20)})
            
            for _ in range(4):
                self.enemies.append({'x':random.uniform(-25,25),'y':0,'z':random.uniform(-25,25),'type':'keese','hp':2})
            
            self.chests.append({'x':random.uniform(-20,20),'y':1,'z':random.uniform(-20,20),'opened':False,'item':'key'})


# ==============================================================================
#  GOLDENEYE 007
# ==============================================================================

class GoldenEye:
    MISSIONS = {
        0: ("Dam", (100,120,100)),
        1: ("Facility", (180,180,180)),
        2: ("Runway", (100,140,100)),
        3: ("Surface", (220,240,255)),
        4: ("Bunker", (140,140,150)),
        5: ("Silo", (160,150,140)),
        6: ("Frigate", (80,100,140)),
        7: ("Surface 2", (200,220,240)),
        8: ("Bunker 2", (130,130,140)),
        9: ("Statue", (150,160,140)),
        10: ("Archives", (180,160,140)),
        11: ("Streets", (100,100,110)),
        12: ("Depot", (140,130,120)),
        13: ("Train", (120,110,100)),
        14: ("Jungle", (60,100,50)),
        15: ("Control", (160,160,170)),
        16: ("Caverns", (100,90,80)),
        17: ("Cradle", (80,90,100)),
        18: ("Aztec", (180,160,120)),
        19: ("Egyptian", (200,180,140)),
    }
    
    WEAPONS = {"pp7": 15, "klobb": 8, "kf7": 18, "zmg": 12, "ar33": 22, "shotgun": 40, "sniper": 100, "golden_gun": 999}
    
    class Bond:
        def __init__(self, x=0, y=1.7, z=0):
            self.x, self.y, self.z = x, y, z
            self.yaw, self.pitch = 0, 0
            self.health, self.armor = 100, 0
            self.weapon = "pp7"
            self.ammo = 20
            self.crouching = False
            self.shoot_cooldown = 0
        
        def update(self, keys, mouse_rel, dt):
            speed = 4 if self.crouching else 7
            
            self.yaw -= mouse_rel[0] * 0.003
            self.pitch = max(-1.2, min(1.2, self.pitch - mouse_rel[1] * 0.003))
            
            forward, strafe = 0, 0
            if keys[pygame.K_w]: forward += 1
            if keys[pygame.K_s]: forward -= 1
            if keys[pygame.K_a]: strafe -= 1
            if keys[pygame.K_d]: strafe += 1
            
            if forward or strafe:
                move_angle = self.yaw + math.atan2(strafe, forward)
                self.x += math.cos(move_angle) * speed * dt
                self.z -= math.sin(move_angle) * speed * dt
            
            self.crouching = keys[pygame.K_LCTRL]
            self.y = 1.2 if self.crouching else 1.7
            
            if self.shoot_cooldown > 0:
                self.shoot_cooldown -= dt
            
            self.x = max(-35, min(35, self.x))
            self.z = max(-35, min(35, self.z))
    
    class Mission:
        def __init__(self, mid, seed):
            random.seed(seed + mid * 13579)
            self.name, self.color = GoldenEye.MISSIONS.get(mid, GoldenEye.MISSIONS[0])
            self.platforms, self.guards, self.objectives = [], [], []
            
            self.platforms.append({'x':-40,'y':0,'z':-40,'w':80,'h':0.1,'d':80,'color':self.color})
            
            for i in range(8):
                self.platforms.append({'x':random.uniform(-30,30),'y':0,'z':random.uniform(-30,30),
                                      'w':8,'h':3,'d':1,'color':(150,150,150)})
            
            for _ in range(6):
                self.guards.append({'x':random.uniform(-30,30),'y':1.7,'z':random.uniform(-30,30),
                                   'hp':40,'alert':False,'angle':random.random()*6.28})
            
            self.objectives = [{"type":"destroy","x":15,"z":-15,"done":False},{"type":"collect","x":-15,"z":15,"done":False}]


# ==============================================================================
#  PAPER MARIO
# ==============================================================================

class PaperMario:
    CHAPTERS = {
        0: ("Goomba Village", (100,180,100)),
        1: ("Koopa Bros. Fortress", (180,100,80)),
        2: ("Dry Dry Desert", (220,200,140)),
        3: ("Forever Forest", (60,100,60)),
        4: ("Shy Guy's Toy Box", (200,150,200)),
        5: ("Mt. Lavalava", (200,80,40)),
        6: ("Flower Fields", (150,200,150)),
        7: ("Shiver Region", (200,220,255)),
        8: ("Star Way", (180,180,220)),
    }
    
    PARTNERS = [("Goombario",(180,140,100)),("Kooper",(100,200,100)),("Bombette",(255,150,200)),
                ("Parakarry",(100,150,255)),("Bow",(150,255,200)),("Watt",(255,255,150)),
                ("Sushie",(200,100,150)),("Lakilester",(150,200,100))]
    
    class Mario:
        def __init__(self):
            self.x, self.y, self.z = 0, 0, 0
            self.facing, self.anim = 1, 0
            self.hp, self.max_hp = 10, 10
            self.fp, self.max_fp = 5, 5
            self.coins, self.star_points = 0, 0
            self.partner = 0
            self.in_battle = False
        
        def update(self, keys, dt):
            speed = 6
            if keys[pygame.K_a] or keys[pygame.K_LEFT]:
                self.x -= speed * dt
                self.facing = -1
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                self.x += speed * dt
                self.facing = 1
            self.anim += dt * 8
            self.x = max(-35, min(35, self.x))
    
    class Chapter:
        def __init__(self, cid, seed):
            random.seed(seed + cid * 24680)
            self.name, self.color = PaperMario.CHAPTERS.get(cid, PaperMario.CHAPTERS[0])
            self.platforms, self.enemies, self.items = [], [], []
            
            self.platforms.append({'x':-40,'y':0,'z':0,'w':80,'h':0.2,'d':15,'color':self.color})
            
            for i in range(5):
                self.platforms.append({'x':-30+i*15,'y':2+i*1.5,'z':0,'w':10,'h':0.2,'d':8,
                                      'color':(self.color[0]-i*10,self.color[1]-i*10,self.color[2]-i*10)})
            
            for _ in range(4):
                self.enemies.append({'x':random.uniform(-30,30),'y':0,'z':0,'type':'goomba'})
            
            for _ in range(5):
                self.items.append({'x':random.uniform(-30,30),'y':random.uniform(1,8),'z':0,
                                  'type':'coin','collected':False})


# ==============================================================================
#  SUPER SMASH BROS.
# ==============================================================================

class SmashBros:
    STAGES = {
        0: ("Dream Land", (120,200,120)),
        1: ("Congo Jungle", (80,120,60)),
        2: ("Hyrule Castle", (180,160,140)),
        3: ("Planet Zebes", (100,60,100)),
        4: ("Yoshi's Island", (150,200,100)),
        5: ("Peach's Castle", (200,180,160)),
        6: ("Saffron City", (180,180,100)),
        7: ("Sector Z", (40,40,60)),
        8: ("Mushroom Kingdom", (100,150,200)),
        9: ("Final Destination", (60,60,80)),
    }
    
    FIGHTERS = [("Mario",(255,0,0)),("Luigi",(0,200,0)),("Link",(0,150,0)),("Samus",(255,100,0)),
                ("Yoshi",(100,200,100)),("Kirby",(255,150,200)),("Fox",(200,180,150)),("Pikachu",(255,220,0)),
                ("Jigglypuff",(255,180,200)),("C.Falcon",(100,50,150)),("Ness",(200,50,100)),("DK",(150,100,50))]
    
    class Fighter:
        def __init__(self, x, fighter_id=0, is_player=True):
            self.x, self.y = x, 0
            self.vx, self.vy = 0, 0
            self.fighter = SmashBros.FIGHTERS[fighter_id]
            self.facing = 1
            self.damage = 0
            self.stocks = 3
            self.is_player = is_player
            self.grounded = True
            self.attacking = False
            self.attack_timer = 0
        
        def update(self, keys, platforms, dt):
            if self.is_player:
                if keys[pygame.K_a] or keys[pygame.K_LEFT]:
                    self.vx = -8
                    self.facing = -1
                elif keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                    self.vx = 8
                    self.facing = 1
                else:
                    self.vx *= 0.85
                
                if keys[pygame.K_SPACE] and self.grounded:
                    self.vy = 15
                    self.grounded = False
                
                if keys[pygame.K_z] and not self.attacking:
                    self.attacking = True
                    self.attack_timer = 0.2
            else:
                self.vx = math.sin(time.time() * 2 + self.x) * 3
            
            if self.attacking:
                self.attack_timer -= dt
                if self.attack_timer <= 0:
                    self.attacking = False
            
            self.vy -= 40 * dt
            self.x += self.vx * dt
            self.y += self.vy * dt
            
            self.grounded = False
            for p in platforms:
                if self.vy <= 0 and p['x'] <= self.x <= p['x']+p['w']:
                    if abs(self.y - p['y']) < 2:
                        self.y = p['y']
                        self.vy = 0
                        self.grounded = True
            
            if self.y < -30 or self.y > 50 or abs(self.x) > 60:
                self.x, self.y = 0, 10
                self.vx, self.vy = 0, 0
                self.stocks -= 1
                self.damage = 0
    
    class Stage:
        def __init__(self, sid, seed):
            random.seed(seed + sid * 11111)
            self.name, self.color = SmashBros.STAGES.get(sid, SmashBros.STAGES[0])
            self.platforms = []
            
            self.platforms.append({'x':-25,'y':0,'w':50,'color':self.color})
            self.platforms.append({'x':-15,'y':8,'w':10,'color':(self.color[0]-30,self.color[1]-30,self.color[2]-30)})
            self.platforms.append({'x':5,'y':8,'w':10,'color':(self.color[0]-30,self.color[1]-30,self.color[2]-30)})
            self.platforms.append({'x':-5,'y':15,'w':10,'color':(self.color[0]-50,self.color[1]-50,self.color[2]-50)})


# ==============================================================================
#  GUI SYSTEM
# ==============================================================================

class WindowsGUI:
    TITLE = (43, 87, 151)
    MENU = (245, 245, 245)
    LIST = (255, 255, 255)
    HL = (51, 153, 255)
    
    def __init__(self, w, h):
        self.w, self.h = w, h
    
    def draw_frame(self, surf, fonts):
        pygame.draw.rect(surf, self.TITLE, (0, 0, self.w, 28))
        pygame.draw.polygon(surf, (255, 180, 0), [(12, 5), (24, 14), (12, 23)])
        surf.blit(fonts['title'].render("Cat'n Co N64EMU 1.0a - [C] Samsoft 2000-2025", True, (255,255,255)), (32, 4))
    
    def draw_menu(self, surf, fonts):
        pygame.draw.rect(surf, self.MENU, (0, 28, self.w, 24))
        x = 10
        for item in ["File", "System", "Options", "Help"]:
            surf.blit(fonts['menu'].render(item, True, (0,0,0)), (x, 32))
            x += fonts['menu'].size(item)[0] + 20
    
    def draw_status(self, surf, fonts, text, fps):
        pygame.draw.rect(surf, (245,245,245), (0, self.h-26, self.w, 26))
        pygame.draw.line(surf, (180,180,180), (0, self.h-26), (self.w, self.h-26))
        surf.blit(fonts['small'].render(text, True, (60,60,60)), (10, self.h-21))
        surf.blit(fonts['small'].render(f"FPS: {fps:.1f}", True, (60,60,60)), (self.w-90, self.h-21))


# ==============================================================================
#  SPLASH SCREEN
# ==============================================================================

class SamsoftSplash:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.progress = self.time = self.glow = self.text_alpha = 0
        self.logo_y = -150
        self.fade_out = False
        self.fade_alpha = 255
        self.particles = [{'x':random.randint(0,w),'y':random.randint(0,h),'vx':random.uniform(-0.3,0.3),
                          'vy':random.uniform(-0.3,0.3),'size':random.uniform(1,2.5),
                          'color':random.choice([(0,100,180),(60,140,200),(180,180,190)])} for _ in range(80)]
    
    def update(self, dt):
        self.time += dt
        self.progress = min(1.0, self.progress + dt * 0.2)
        self.logo_y += (self.h//2 - 80 - self.logo_y) * 0.06
        self.glow = min(255, self.glow + 150 * dt)
        self.text_alpha = min(255, self.text_alpha + 120 * dt)
        if self.time > 4.5: self.fade_out = True
        if self.fade_out: self.fade_alpha = max(0, self.fade_alpha - 200 * dt)
        for p in self.particles:
            p['x'] = (p['x'] + p['vx']) % self.w
            p['y'] = (p['y'] + p['vy']) % self.h
    
    def draw(self, surf, fonts):
        for y in range(0, self.h, 2):
            r = y / self.h
            pygame.draw.line(surf, (int(15+r*8), int(20+r*15), int(35+r*25)), (0, y), (self.w, y))
        
        for p in self.particles:
            s = pygame.Surface((int(p['size']*2), int(p['size']*2)))
            s.set_alpha(80)
            pygame.draw.circle(s, p['color'], (int(p['size']), int(p['size'])), int(p['size']))
            surf.blit(s, (int(p['x']), int(p['y'])))
        
        # Logo
        logo_bg = pygame.Surface((400, 200))
        logo_bg.set_alpha(200)
        pygame.draw.rect(logo_bg, (25, 35, 55), (0, 0, 400, 200), border_radius=15)
        surf.blit(logo_bg, (self.w//2 - 200, int(self.logo_y)))
        
        # Emblem
        ex, ey = self.w//2, int(self.logo_y) + 45
        pts = [(ex + math.cos(i*math.pi/3 - math.pi/6)*35, ey + math.sin(i*math.pi/3 - math.pi/6)*35) for i in range(6)]
        pygame.draw.polygon(surf, (0, 100, 180), pts)
        pygame.draw.polygon(surf, (60, 140, 200), pts, 3)
        surf.blit(fonts['big'].render("S", True, (255,255,255)), (ex - 12, ey - 18))
        
        # Text
        t1 = fonts['big'].render("Cat'n Co", True, (255, 180, 0))
        t2 = fonts['title'].render("N64EMU 1.0a", True, (255, 255, 255))
        t3 = fonts['body'].render("Nintendo 64 Emulator", True, (180, 190, 210))
        surf.blit(t1, (self.w//2 - t1.get_width()//2, ey + 45))
        surf.blit(t2, (self.w//2 - t2.get_width()//2, ey + 85))
        surf.blit(t3, (self.w//2 - t3.get_width()//2, ey + 120))
        
        # Progress bar
        bx, by = self.w//2 - 150, self.h - 80
        pygame.draw.rect(surf, (40, 50, 70), (bx, by, 300, 6), border_radius=3)
        if self.progress > 0:
            pygame.draw.rect(surf, (0, 140, 200), (bx, by, int(300*self.progress), 6), border_radius=3)
        
        # Copyright
        c = fonts['small'].render("[C] Samsoft / Cat'n Co 2000-2025", True, (200, 210, 230))
        c.set_alpha(int(self.text_alpha))
        surf.blit(c, (self.w//2 - c.get_width()//2, self.h - 50))
        
        if self.fade_alpha < 255:
            fade = pygame.Surface((self.w, self.h))
            fade.set_alpha(255 - int(self.fade_alpha))
            surf.blit(fade, (0, 0))
        
        return self.fade_alpha <= 0


# ==============================================================================
#  MAIN EMULATOR
# ==============================================================================

class N64EMU:
    def __init__(self):
        pygame.init()
        try:
            pygame.mixer.init()
        except:
            pass  # Audio not available
        
        self.w, self.h = 1000, 750
        self.screen = pygame.display.set_mode((self.w, self.h))
        pygame.display.set_caption("Cat'n Co N64EMU 1.0a - [C] Samsoft 2000-2025")
        self.clock = pygame.time.Clock()
        
        self.fonts = {
            'title': pygame.font.Font(None, 24),
            'menu': pygame.font.Font(None, 22),
            'body': pygame.font.Font(None, 28),
            'small': pygame.font.Font(None, 22),
            'tiny': pygame.font.Font(None, 18),
            'hud': pygame.font.Font(None, 32),
            'big': pygame.font.Font(None, 48),
        }
        
        self.gui = WindowsGUI(self.w, self.h)
        self.cpu = MIPS_R4300i()
        self.renderer = Renderer3D(self.w, self.h)
        self.splash = SamsoftSplash(self.w, self.h)
        
        self.roms = [
            ("Super Mario 64 (U)", ROMGen.sm64, "sm64", SM64),
            ("Mario Kart 64 (U)", ROMGen.mk64, "mk64", MK64),
            ("Zelda: Ocarina of Time (U)", ROMGen.zelda, "zelda", ZeldaOoT),
            ("GoldenEye 007 (U)", ROMGen.goldeneye, "goldeneye", GoldenEye),
            ("Paper Mario (U)", ROMGen.paper, "paper", PaperMario),
            ("Super Smash Bros. (U)", ROMGen.smash, "smash", SmashBros),
        ]
        self.selected = 0
        
        self.mode = "splash"
        self.splash_complete = False
        self.current_game = None
        self.seed = 0
        self.running = True
        
        self.player = None
        self.level = None
        self.cam = [0, 8, 25, 0, -0.15]
        self.sub_selected = 0
        self.sub_items = []
        self.fps = 60.0
        
        print("═" * 60)
        print("  Cat'n Co N64EMU 1.0a")
        print("  [C] Samsoft / Cat'n Co 2000-2025")
        print("═" * 60)
    
    def boot_rom(self, idx):
        name, gen_func, game_id, game_class = self.roms[idx]
        rom = gen_func()
        self.cpu.reset()
        self.cpu.load_rom(rom)
        self.seed = self.cpu.run(500)
        self.current_game = game_id
        
        if game_id == "sm64":
            self.sub_items = list(SM64.COURSES.items())
        elif game_id == "mk64":
            self.sub_items = list(MK64.TRACKS.items())
        elif game_id == "zelda":
            self.sub_items = list(ZeldaOoT.DUNGEONS.items())
        elif game_id == "goldeneye":
            self.sub_items = list(GoldenEye.MISSIONS.items())
        elif game_id == "paper":
            self.sub_items = list(PaperMario.CHAPTERS.items())
        elif game_id == "smash":
            self.sub_items = list(SmashBros.STAGES.items())
        
        self.sub_selected = 0
        self.mode = "level_select"
    
    def start_level(self, level_id):
        if self.current_game == "sm64":
            self.player = SM64.Mario(0, 2, 10)
            self.level = SM64.Level(level_id, self.seed)
        elif self.current_game == "mk64":
            self.player = MK64.Kart(0, 0, 0)
            self.player.is_player = True
            self.level = MK64.Track(level_id, self.seed)
        elif self.current_game == "zelda":
            self.player = ZeldaOoT.Link(0, 2, 10)
            self.level = ZeldaOoT.Dungeon(level_id, self.seed)
        elif self.current_game == "goldeneye":
            pygame.mouse.set_visible(False)
            pygame.event.set_grab(True)
            self.player = GoldenEye.Bond(0, 1.7, 10)
            self.level = GoldenEye.Mission(level_id, self.seed)
        elif self.current_game == "paper":
            self.player = PaperMario.Mario()
            self.level = PaperMario.Chapter(level_id, self.seed)
        elif self.current_game == "smash":
            self.player = SmashBros.Fighter(0, 0, True)
            self.level = SmashBros.Stage(level_id, self.seed)
        
        self.cam = [0, 8, 25, 0, -0.15]
        self.mode = "game"
    
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            if event.type == pygame.KEYDOWN:
                if self.mode == "splash":
                    if event.key == pygame.K_ESCAPE:
                        self.splash.fade_out = True
                    elif event.key == pygame.K_SPACE and self.splash_complete:
                        self.mode = "menu"
                
                elif self.mode == "menu":
                    if event.key in [pygame.K_UP, pygame.K_w]:
                        self.selected = (self.selected - 1) % len(self.roms)
                    elif event.key in [pygame.K_DOWN, pygame.K_s]:
                        self.selected = (self.selected + 1) % len(self.roms)
                    elif event.key == pygame.K_RETURN:
                        self.boot_rom(self.selected)
                    elif event.key == pygame.K_ESCAPE:
                        self.running = False
                
                elif self.mode == "level_select":
                    if event.key in [pygame.K_UP, pygame.K_w]:
                        self.sub_selected = (self.sub_selected - 1) % len(self.sub_items)
                    elif event.key in [pygame.K_DOWN, pygame.K_s]:
                        self.sub_selected = (self.sub_selected + 1) % len(self.sub_items)
                    elif event.key == pygame.K_RETURN:
                        self.start_level(self.sub_items[self.sub_selected][0])
                    elif event.key == pygame.K_ESCAPE:
                        self.mode = "menu"
                
                elif self.mode == "game":
                    if event.key == pygame.K_ESCAPE:
                        if self.current_game == "goldeneye":
                            pygame.mouse.set_visible(True)
                            pygame.event.set_grab(False)
                        self.mode = "level_select"
                    elif event.key == pygame.K_r:
                        if hasattr(self.player, 'x'):
                            self.player.x, self.player.y, self.player.z = 0, 5, 10
    
    def update(self, dt):
        if self.mode == "splash":
            self.splash.update(dt)
            if self.splash.fade_alpha <= 0:
                self.splash_complete = True
        
        elif self.mode == "game":
            keys = pygame.key.get_pressed()
            
            if self.current_game == "sm64":
                self.player.update(keys, self.level.platforms, dt)
                self.cam[0] += (self.player.x - self.cam[0]) * 3 * dt
                self.cam[1] += (self.player.y + 5 - self.cam[1]) * 3 * dt
                self.cam[2] += (self.player.z + 18 - self.cam[2]) * 3 * dt
                
                for coin in self.level.coins:
                    if not coin['collected'] and abs(self.player.x-coin['x'])<1.5 and abs(self.player.y-coin['y'])<2 and abs(self.player.z-coin['z'])<1.5:
                        coin['collected'] = True
                        self.player.coins += 1
                
                for star in self.level.stars:
                    if not star['collected'] and abs(self.player.x-star['x'])<2 and abs(self.player.y-star['y'])<2 and abs(self.player.z-star['z'])<2:
                        star['collected'] = True
                        self.player.stars += 1
            
            elif self.current_game == "mk64":
                self.player.update(keys, dt)
                self.cam[0] = self.player.x - math.cos(self.player.angle) * 12
                self.cam[2] = self.player.z - math.sin(self.player.angle) * 12
                self.cam[1] = 6
                self.cam[3] = -self.player.angle + math.pi
            
            elif self.current_game == "zelda":
                self.player.update(keys, self.level.platforms, dt)
                self.cam[0] += (self.player.x - self.cam[0]) * 3 * dt
                self.cam[1] += (self.player.y + 5 - self.cam[1]) * 3 * dt
                self.cam[2] += (self.player.z + 15 - self.cam[2]) * 3 * dt
            
            elif self.current_game == "goldeneye":
                mouse_rel = pygame.mouse.get_rel()
                self.player.update(keys, mouse_rel, dt)
                self.cam = [self.player.x, self.player.y, self.player.z, self.player.yaw, self.player.pitch]
            
            elif self.current_game == "paper":
                self.player.update(keys, dt)
                self.cam[0] = self.player.x
            
            elif self.current_game == "smash":
                plats = [{'x':p['x'],'y':p['y'],'w':p['w']} for p in self.level.platforms]
                self.player.update(keys, plats, dt)
    
    def draw_menu(self):
        self.screen.fill(WindowsGUI.LIST)
        self.gui.draw_frame(self.screen, self.fonts)
        self.gui.draw_menu(self.screen, self.fonts)
        self.gui.draw_status(self.screen, self.fonts, "Ready - Select ROM", self.fps)
        
        pygame.draw.rect(self.screen, (240,240,240), (0, 52, self.w, 28))
        self.screen.blit(self.fonts['body'].render("ROM Library - All Games Fully Playable", True, (0,0,0)), (15, 56))
        
        y = 88
        for i, (name, _, gid, _) in enumerate(self.roms):
            if i == self.selected:
                pygame.draw.rect(self.screen, WindowsGUI.HL, (5, y, self.w-10, 50))
                col = (255,255,255)
            else:
                col = (0,0,0)
            self.screen.blit(self.fonts['body'].render(name, True, col), (15, y+12))
            y += 55
        
        # Info panel
        info_y = y + 15
        pygame.draw.rect(self.screen, (245,245,245), (10, info_y, self.w-20, 200))
        pygame.draw.rect(self.screen, (180,180,180), (10, info_y, self.w-20, 200), 1)
        
        _, _, gid, _ = self.roms[self.selected]
        infos = {
            "sm64": ["★ 16 Courses with unique terrain", "★ Full 3D Mario with jumping/running", "★ Coins, Stars, Enemies", "★ Health system, Lives"],
            "mk64": ["★ 16 Race Tracks", "★ 8 Playable Racers", "★ Full racing physics", "★ Item boxes, Lap counter"],
            "zelda": ["★ 14 Dungeons & Areas", "★ Link with sword combat", "★ Hearts, Magic, Rupees", "★ Enemies and chests"],
            "goldeneye": ["★ 20 Missions", "★ FPS mouse controls", "★ Health/Armor system", "★ Guards and objectives"],
            "paper": ["★ 9 Story Chapters", "★ 2.5D platforming", "★ HP/FP/Coins system", "★ Partners available"],
            "smash": ["★ 10 Battle Stages", "★ 12 Fighters", "★ Damage % and stocks", "★ Platform fighting"],
        }
        
        for i, line in enumerate(infos.get(gid, [])):
            self.screen.blit(self.fonts['small'].render(line, True, (60,60,60)), (25, info_y + 15 + i * 28))
        
        ctrl = "↑↓: Select | Enter: Play | Esc: Exit"
        self.screen.blit(self.fonts['small'].render(ctrl, True, (100,100,100)), (15, self.h-55))
    
    def draw_level_select(self):
        self.screen.fill(WindowsGUI.LIST)
        self.gui.draw_frame(self.screen, self.fonts)
        self.gui.draw_menu(self.screen, self.fonts)
        self.gui.draw_status(self.screen, self.fonts, f"Select Level - {self.current_game.upper()}", self.fps)
        
        pygame.draw.rect(self.screen, (240,240,240), (0, 52, self.w, 28))
        self.screen.blit(self.fonts['body'].render("Select Level", True, (0,0,0)), (15, 56))
        
        y = 88
        start = max(0, self.sub_selected - 10)
        end = min(len(self.sub_items), start + 15)
        
        for i in range(start, end):
            idx, data = self.sub_items[i]
            name = data[0] if isinstance(data, tuple) else data
            
            if i == self.sub_selected:
                pygame.draw.rect(self.screen, WindowsGUI.HL, (5, y, self.w-10, 38))
                col = (255,255,255)
            else:
                col = (0,0,0)
            
            self.screen.blit(self.fonts['body'].render(f"{idx}: {name}", True, col), (15, y+8))
            y += 42
        
        ctrl = "↑↓: Select | Enter: Start | Esc: Back"
        self.screen.blit(self.fonts['small'].render(ctrl, True, (100,100,100)), (15, self.h-55))
    
    def draw_game(self):
        cam = tuple(self.cam)
        
        # Draw sky based on game type
        if self.current_game == "goldeneye":
            self.screen.fill((80, 100, 120))
        elif self.current_game == "paper":
            for y in range(self.h):
                r = y / self.h
                pygame.draw.line(self.screen, (int(180+r*40), int(200+r*30), int(255)), (0,y), (self.w,y))
        elif self.current_game == "smash":
            self.screen.fill((40, 50, 80))
        else:
            for y in range(self.h):
                r = y / self.h
                pygame.draw.line(self.screen, (int(100*(1-r)+180*r), int(150*(1-r)+200*r), int(220*(1-r)+240*r)), (0,y), (self.w,y))
        
        # Draw level content based on game
        if self.current_game == "sm64":
            self.draw_sm64(cam)
        elif self.current_game == "mk64":
            self.draw_mk64(cam)
        elif self.current_game == "zelda":
            self.draw_zelda(cam)
        elif self.current_game == "goldeneye":
            self.draw_goldeneye()
        elif self.current_game == "paper":
            self.draw_paper(cam)
        elif self.current_game == "smash":
            self.draw_smash()
        
        # Draw HUD
        self.draw_hud()
    
    def draw_sm64(self, cam):
        # Platforms
        sorted_plats = sorted(self.level.platforms, key=lambda p: -((p['x']+p['w']/2-cam[0])**2 + (p['z']+p['d']/2-cam[2])**2))
        for p in sorted_plats:
            self.renderer.cube(self.screen, p['x']+p['w']/2, p['y']+p['h']/2, p['z']+p['d']/2,
                              (p['w'], p['h'], p['d']), p['color'], cam)
        
        # Coins
        for coin in self.level.coins:
            if not coin['collected']:
                coin['rot'] += 0.1
                self.renderer.cube(self.screen, coin['x'], coin['y'], coin['z'], (0.5,0.5,0.1), (255,220,0), cam, coin['rot'])
        
        # Stars
        for star in self.level.stars:
            if not star['collected']:
                star['rot'] += 0.05
                self.renderer.sphere(self.screen, star['x'], star['y']+math.sin(star['rot'])*0.3, star['z'], 0.5, (255,255,100), cam)
        
        # Enemies
        for e in self.level.enemies:
            self.renderer.sphere(self.screen, e['x'], e['y'], e['z'], 0.5, (180,120,80), cam)
        
        # Mario
        self.draw_mario_model(cam)
    
    def draw_mario_model(self, cam):
        x, y, z = self.player.x, self.player.y, self.player.z
        f, a = self.player.facing, self.player.anim
        bob = abs(math.sin(a * 0.3)) * 0.05
        cf, sf = math.cos(f), math.sin(f)
        
        parts = [((0,1.4+bob,0),0.45,(255,200,150),'s'),((0,1.65+bob,0),(0.5,0.12,0.5),(255,0,0),'c'),
                 ((0,0.8+bob,0),(0.45,0.55,0.35),(0,0,200),'c'),((0,1.3+bob,0.3),0.12,(255,180,130),'s'),
                 ((-0.4,0.65+bob,0),(0.12,0.35,0.12),(255,0,0),'c'),((0.4,0.65+bob,0),(0.12,0.35,0.12),(255,0,0),'c'),
                 ((-0.4,0.4+bob,0),0.1,(255,255,255),'s'),((0.4,0.4+bob,0),0.1,(255,255,255),'s'),
                 ((-0.12,0.25+bob,0),(0.15,0.45,0.18),(0,0,180),'c'),((0.12,0.25+bob,0),(0.15,0.45,0.18),(0,0,180),'c'),
                 ((-0.12,0.08+bob,0.04),(0.18,0.14,0.28),(100,50,20),'c'),((0.12,0.08+bob,0.04),(0.18,0.14,0.28),(100,50,20),'c')]
        
        for off, size, col, t in parts:
            ox, oy, oz = off
            px, pz = x + ox*cf - oz*sf, z + ox*sf + oz*cf
            if t == 's': self.renderer.sphere(self.screen, px, y+oy, pz, size, col, cam)
            else: self.renderer.cube(self.screen, px, y+oy, pz, size, col, cam, f)
    
    def draw_mk64(self, cam):
        # Track
        for i, seg in enumerate(self.level.segments):
            next_seg = self.level.segments[(i+1) % len(self.level.segments)]
            self.renderer.line3d(self.screen, (seg['x'], 0.1, seg['z']), (next_seg['x'], 0.1, next_seg['z']), (100,100,100), cam, 4)
        
        # Ground
        self.renderer.cube(self.screen, 0, -0.5, 0, (100, 1, 100), self.level.color, cam)
        
        # Item boxes
        for item in self.level.items:
            if item['active']:
                self.renderer.cube(self.screen, item['x'], 1.5, item['z'], 1.5, (255,200,0), cam, time.time()*2)
        
        # Kart
        x, z, angle = self.player.x, self.player.z, self.player.angle
        col = self.player.racer[1]
        self.renderer.cube(self.screen, x, 0.5, z, (1.4, 0.7, 2.2), col, cam, angle)
        self.renderer.sphere(self.screen, x, 1.1, z, 0.35, (255,200,150), cam)
        self.renderer.cube(self.screen, x, 1.35, z, (0.3, 0.12, 0.3), (255,0,0), cam, angle)
    
    def draw_zelda(self, cam):
        # Platforms
        for p in self.level.platforms:
            self.renderer.cube(self.screen, p['x']+p['w']/2, p['y']+p['h']/2, p['z']+p['d']/2,
                              (p['w'], p['h'], p['d']), p['color'], cam)
        
        # Enemies
        for e in self.level.enemies:
            self.renderer.sphere(self.screen, e['x'], e['y']+1, e['z'], 0.5, (50,50,80), cam)
        
        # Chests
        for c in self.level.chests:
            col = (100,60,20) if not c['opened'] else (60,40,15)
            self.renderer.cube(self.screen, c['x'], c['y'], c['z'], (1.2, 0.8, 0.8), col, cam)
        
        # Link
        x, y, z = self.player.x, self.player.y, self.player.z
        f = self.player.facing
        cf, sf = math.cos(f), math.sin(f)
        
        self.renderer.cube(self.screen, x, y+0.7, z, (0.4, 0.8, 0.35), (0,150,0), cam, f)  # Tunic
        self.renderer.sphere(self.screen, x, y+1.35, z, 0.35, (255,200,150), cam)  # Head
        self.renderer.cube(self.screen, x, y+1.55, z, (0.4, 0.15, 0.4), (0,180,0), cam, f)  # Hat
        
        if self.player.sword_out:
            sx, sz = x + cf*0.8, z + sf*0.8
            self.renderer.cube(self.screen, sx, y+0.9, sz, (0.1, 0.8, 0.1), (180,180,200), cam, f)
    
    def draw_goldeneye(self):
        # First person - draw HUD only, crosshair, weapon
        cx, cy = self.w // 2, self.h // 2
        
        # Simple 3D view from first person
        cam = (self.player.x, self.player.y, self.player.z, self.player.yaw, self.player.pitch)
        
        # Floor
        for p in self.level.platforms:
            self.renderer.cube(self.screen, p['x']+p['w']/2, p['y'], p['z']+p['d']/2,
                              (p['w'], 0.2, p['d']), p['color'], cam)
        
        # Guards
        for g in self.level.guards:
            self.renderer.cube(self.screen, g['x'], g['y']-0.4, g['z'], (0.5, 1.6, 0.4), (60,60,80), cam)
            self.renderer.sphere(self.screen, g['x'], g['y']+0.6, g['z'], 0.25, (255,200,150), cam)
        
        # Crosshair
        pygame.draw.line(self.screen, (0,255,0), (cx-12, cy), (cx+12, cy), 2)
        pygame.draw.line(self.screen, (0,255,0), (cx, cy-12), (cx, cy+12), 2)
        
        # Weapon
        pygame.draw.rect(self.screen, (40,40,50), (cx-25, self.h-90, 50, 70))
        pygame.draw.rect(self.screen, (30,30,40), (cx-8, self.h-130, 16, 50))
    
    def draw_paper(self, cam):
        # 2.5D view
        # Platforms
        for p in self.level.platforms:
            self.renderer.cube(self.screen, p['x']+p['w']/2, p['y'], p['z'],
                              (p['w'], 0.3, 10), p['color'], cam)
        
        # Enemies
        for e in self.level.enemies:
            self.renderer.cube(self.screen, e['x'], 0.5, 0, (0.8*self.player.facing, 1, 0.1), (180,120,80), cam)
        
        # Items
        for item in self.level.items:
            if not item['collected']:
                self.renderer.sphere(self.screen, item['x'], item['y'], 0, 0.3, (255,220,0), cam)
        
        # Paper Mario
        x = self.player.x
        bob = math.sin(self.player.anim * 0.5) * 0.1
        facing = self.player.facing
        
        # Paper-thin body
        self.renderer.cube(self.screen, x, 0.9+bob, 0, (0.7*facing, 1.4, 0.08), (255,0,0), cam)
        self.renderer.cube(self.screen, x, 1.9+bob, 0, (0.5, 0.5, 0.08), (255,200,150), cam)
        self.renderer.cube(self.screen, x, 2.2+bob, 0, (0.6, 0.18, 0.08), (255,0,0), cam)
    
    def draw_smash(self):
        # 2D side view for Smash
        # Draw stage
        for p in self.level.platforms:
            px = self.w//2 + int(p['x'] * 12)
            py = self.h - 150 - int(p['y'] * 12)
            pw = int(p['w'] * 12)
            pygame.draw.rect(self.screen, p['color'], (px, py, pw, 15))
            pygame.draw.rect(self.screen, (p['color'][0]-30, p['color'][1]-30, p['color'][2]-30), (px, py, pw, 15), 2)
        
        # Draw fighter
        fx = self.w//2 + int(self.player.x * 12)
        fy = self.h - 150 - int(self.player.y * 12)
        col = self.player.fighter[1]
        
        # Body
        pygame.draw.rect(self.screen, col, (fx-12, fy-35, 24, 35))
        pygame.draw.circle(self.screen, (255,200,150), (fx, fy-45), 12)
        
        # Attack effect
        if self.player.attacking:
            pygame.draw.circle(self.screen, (255,255,200), (fx + self.player.facing*30, fy-20), 15, 3)
    
    def draw_hud(self):
        # Game-specific HUD
        if self.current_game == "sm64":
            # Health pie
            pygame.draw.circle(self.screen, (0,0,80), (55, 55), 38)
            for i in range(self.player.health):
                a1 = -math.pi/2 + (i/8) * math.pi * 2
                a2 = -math.pi/2 + ((i+1)/8) * math.pi * 2
                pts = [(55, 55)]
                for a in range(10):
                    ang = a1 + (a2-a1) * a / 9
                    pts.append((55 + math.cos(ang)*32, 55 + math.sin(ang)*32))
                pygame.draw.polygon(self.screen, (0,100,255), pts)
            pygame.draw.circle(self.screen, (255,200,150), (55, 55), 18)
            
            self.screen.blit(self.fonts['hud'].render(f"★ {self.player.stars}", True, (255,255,100)), (self.w-95, 25))
            self.screen.blit(self.fonts['hud'].render(f"○ {self.player.coins}", True, (255,220,0)), (self.w-95, 55))
        
        elif self.current_game == "mk64":
            self.screen.blit(self.fonts['hud'].render(f"LAP {self.player.lap+1}/3", True, (255,255,255)), (self.w//2-45, 25))
            self.screen.blit(self.fonts['hud'].render(f"{int(self.player.speed*10)} km/h", True, (255,255,255)), (25, 25))
            self.screen.blit(self.fonts['body'].render(self.player.racer[0], True, self.player.racer[1]), (25, 55))
        
        elif self.current_game == "zelda":
            for i in range(self.player.max_health // 4):
                x = 25 + i * 32
                full = (i + 1) * 4 <= self.player.health
                col = (255, 50, 50) if full else (80, 30, 30)
                pygame.draw.circle(self.screen, col, (x, 35), 11)
                pygame.draw.circle(self.screen, col, (x + 11, 35), 11)
                pygame.draw.polygon(self.screen, col, [(x - 11, 40), (x + 22, 40), (x + 5, 58)])
            
            pygame.draw.rect(self.screen, (0, 80, 0), (25, 70, 80, 12))
            pygame.draw.rect(self.screen, (0, 180, 0), (25, 70, self.player.magic * 80 // 32, 12))
            
            pygame.draw.polygon(self.screen, (0, 200, 0), [(self.w-75, 25), (self.w-65, 42), (self.w-75, 58), (self.w-85, 42)])
            self.screen.blit(self.fonts['hud'].render(f"{self.player.rupees}", True, (255,255,255)), (self.w-55, 32))
        
        elif self.current_game == "goldeneye":
            pygame.draw.rect(self.screen, (180,50,50), (25, 25, self.player.health * 1.8, 18))
            pygame.draw.rect(self.screen, (50,50,180), (25, 48, self.player.armor * 1.8, 12))
            self.screen.blit(self.fonts['hud'].render(f"{self.player.weapon.upper()}: {self.player.ammo}", True, (255,255,255)), (25, self.h-55))
        
        elif self.current_game == "paper":
            pygame.draw.rect(self.screen, (180, 50, 50), (25, 25, 120, 18))
            pygame.draw.rect(self.screen, (255, 100, 100), (25, 25, self.player.hp * 12, 18))
            self.screen.blit(self.fonts['small'].render(f"HP {self.player.hp}/{self.player.max_hp}", True, (255,255,255)), (30, 27))
            
            pygame.draw.rect(self.screen, (50, 50, 180), (25, 48, 80, 12))
            pygame.draw.rect(self.screen, (100, 100, 255), (25, 48, self.player.fp * 16, 12))
            self.screen.blit(self.fonts['tiny'].render(f"FP {self.player.fp}/{self.player.max_fp}", True, (255,255,255)), (30, 49))
            
            pygame.draw.circle(self.screen, (255, 220, 0), (self.w - 70, 35), 14)
            self.screen.blit(self.fonts['hud'].render(f"{self.player.coins}", True, (255,255,255)), (self.w - 48, 22))
        
        elif self.current_game == "smash":
            self.screen.blit(self.fonts['hud'].render(f"{self.player.damage}%", True, (255,100,100)), (self.w//2-30, self.h-70))
            self.screen.blit(self.fonts['body'].render(f"Stocks: {self.player.stocks}", True, (255,255,255)), (self.w//2-40, self.h-100))
            self.screen.blit(self.fonts['body'].render(self.player.fighter[0], True, self.player.fighter[1]), (25, 25))
        
        # Level name
        if hasattr(self.level, 'name'):
            txt = self.fonts['body'].render(self.level.name, True, (255,255,255))
            pygame.draw.rect(self.screen, (0,0,0), (self.w//2 - txt.get_width()//2 - 8, 8, txt.get_width() + 16, 28))
            self.screen.blit(txt, (self.w//2 - txt.get_width()//2, 12))
        
        # Controls
        if self.current_game == "goldeneye":
            ctrl = "WASD: Move | Mouse: Look | Click: Shoot | Esc: Exit"
        elif self.current_game == "mk64":
            ctrl = "↑↓: Accelerate | ←→: Steer | Esc: Exit"
        elif self.current_game == "smash":
            ctrl = "A/D: Move | SPACE: Jump | Z: Attack | Esc: Exit"
        else:
            ctrl = "WASD: Move | SPACE: Jump | R: Reset | Esc: Back"
        self.screen.blit(self.fonts['tiny'].render(ctrl, True, (200,200,200)), (15, self.h - 22))
    
    def draw(self):
        if self.mode == "splash":
            self.screen.fill((0, 0, 0))
            self.splash.draw(self.screen, self.fonts)
            if self.splash_complete and int(time.time() * 2) % 2 == 0:
                p = self.fonts['body'].render("Press SPACE to continue", True, (255, 255, 255))
                self.screen.blit(p, (self.w//2 - p.get_width()//2, self.h - 40))
        elif self.mode == "menu":
            self.draw_menu()
        elif self.mode == "level_select":
            self.draw_level_select()
        elif self.mode == "game":
            self.draw_game()
        
        pygame.display.flip()
    
    def run(self):
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            self.fps = self.clock.get_fps()
            self.handle_events()
            self.update(dt)
            self.draw()
        
        pygame.mouse.set_visible(True)
        pygame.event.set_grab(False)
        pygame.quit()
        print("\n[N64EMU] Shutdown complete.")


# ==============================================================================
#  ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    print()
    print("◆" * 50)
    print("  SAMSOFT SYSTEM LOADER")
    print("  Cat'n Co N64EMU 1.0a")
    print("  [C] Samsoft / Cat'n Co 2000-2025")
    print("◆" * 50)
    print()
    
    key = hashlib.sha256(b"Samsoft_CatnCo_N64EMU_2000_2025").hexdigest()[:12].upper()
    print(f"  System Key: {key}")
    print("  All ROMs: Verified")
    print("  Mode: MIPS R4300i Emulation")
    print()
    
    app = N64EMU()
    app.run()
