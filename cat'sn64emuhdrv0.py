import math
import pygame
import sys
import random
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from enum import Enum, auto

# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                        CAT'S N64 EMU v1.0                                 ║
# ║                   Simulated Super Mario 64 Engine                         ║
# ║                         by Team Flames                                    ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60
GRAVITY = 0.5
FRICTION = 0.85

class GameState(Enum):
    TITLE = auto()
    FILE_SELECT = auto()
    CASTLE = auto()
    LEVEL = auto()
    STAR_GET = auto()
    PAUSE = auto()

class MarioAction(Enum):
    IDLE = auto()
    WALKING = auto()
    RUNNING = auto()
    JUMPING = auto()
    DOUBLE_JUMP = auto()
    TRIPLE_JUMP = auto()
    LONG_JUMP = auto()
    BACKFLIP = auto()
    WALL_KICK = auto()
    GROUND_POUND = auto()
    DIVE = auto()
    SLIDING = auto()
    SWIMMING = auto()
    CLIMBING = auto()
    FALLING = auto()

@dataclass
class Vector3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    
    def __add__(self, other):
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)
    
    def __sub__(self, other):
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)
    
    def __mul__(self, scalar):
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)
    
    def magnitude(self):
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)
    
    def normalize(self):
        m = self.magnitude()
        if m > 0:
            return Vector3(self.x/m, self.y/m, self.z/m)
        return Vector3()
    
    def dot(self, other):
        return self.x*other.x + self.y*other.y + self.z*other.z

@dataclass
class Camera:
    position: Vector3 = field(default_factory=Vector3)
    target: Vector3 = field(default_factory=Vector3)
    angle: float = 0.0
    distance: float = 300.0
    height: float = 150.0
    mode: str = "lakitu"
    
    def update(self, mario_pos: Vector3):
        target_x = mario_pos.x - math.sin(math.radians(self.angle)) * self.distance
        target_z = mario_pos.z - math.cos(math.radians(self.angle)) * self.distance
        self.position.x += (target_x - self.position.x) * 0.1
        self.position.z += (target_z - self.position.z) * 0.1
        self.position.y = mario_pos.y + self.height
        self.target = mario_pos

@dataclass
class Mario:
    position: Vector3 = field(default_factory=lambda: Vector3(0, 100, 0))
    velocity: Vector3 = field(default_factory=Vector3)
    facing_angle: float = 0.0
    action: MarioAction = MarioAction.IDLE
    health: int = 8
    coins: int = 0
    stars: int = 0
    lives: int = 4
    on_ground: bool = False
    jump_count: int = 0
    wall_kick_timer: int = 0
    invincible_timer: int = 0
    cap: str = "normal"
    size: float = 1.0
    
    def get_forward_vel(self):
        return math.sqrt(self.velocity.x**2 + self.velocity.z**2)

@dataclass
class Platform:
    position: Vector3
    width: float
    height: float
    depth: float
    color: Tuple[int, int, int]
    platform_type: str = "solid"
    moving: bool = False
    move_range: float = 0
    move_speed: float = 0
    move_offset: float = 0

@dataclass  
class Coin:
    position: Vector3
    collected: bool = False
    coin_type: str = "yellow"
    rotation: float = 0

@dataclass
class Star:
    position: Vector3
    star_id: int
    collected: bool = False
    rotation: float = 0

@dataclass
class Enemy:
    position: Vector3
    enemy_type: str
    health: int = 1
    velocity: Vector3 = field(default_factory=Vector3)
    active: bool = True
    facing: float = 0
    state: str = "idle"

@dataclass
class Level:
    name: str
    platforms: List[Platform] = field(default_factory=list)
    coins: List[Coin] = field(default_factory=list)
    stars: List[Star] = field(default_factory=list)
    enemies: List[Enemy] = field(default_factory=list)
    spawn_point: Vector3 = field(default_factory=Vector3)
    sky_color: Tuple[int, int, int] = (100, 150, 255)
    music_id: int = 0

class SimulatedROM:
    """Simulated N64 ROM - generates game data procedurally"""
    
    def __init__(self):
        self.header = {
            "title": "SUPER MARIO 64 SIM",
            "region": "E",
            "version": "1.0",
            "crc1": 0xA03CF036,
            "crc2": 0x4A55A2FC
        }
        self.levels = self._generate_levels()
        
    def _generate_levels(self) -> Dict[int, Level]:
        levels = {}
        
        # Bob-omb Battlefield (simulated)
        bob_omb = Level(
            name="Bob-omb Battlefield",
            spawn_point=Vector3(0, 50, 0),
            sky_color=(135, 206, 235)
        )
        
        # Main ground
        bob_omb.platforms.append(Platform(
            Vector3(0, 0, 0), 1000, 20, 1000, (34, 139, 34), "grass"
        ))
        
        # Mountain
        for i in range(5):
            bob_omb.platforms.append(Platform(
                Vector3(300, 50 + i*80, 300),
                200 - i*30, 40, 200 - i*30,
                (139, 90, 43), "rock"
            ))
        
        # Floating platforms
        for i in range(8):
            angle = i * 45
            x = math.cos(math.radians(angle)) * 400
            z = math.sin(math.radians(angle)) * 400
            bob_omb.platforms.append(Platform(
                Vector3(x, 100 + random.randint(-20, 50), z),
                80, 15, 80,
                (150, 75, 0), "wood"
            ))
        
        # Chain Chomp area
        bob_omb.platforms.append(Platform(
            Vector3(-300, 30, -200), 150, 30, 150, (100, 100, 100), "stone"
        ))
        
        # Coins
        for i in range(50):
            bob_omb.coins.append(Coin(
                Vector3(
                    random.randint(-400, 400),
                    random.randint(50, 200),
                    random.randint(-400, 400)
                )
            ))
        
        # Ring of coins
        for i in range(8):
            angle = i * 45
            bob_omb.coins.append(Coin(
                Vector3(
                    math.cos(math.radians(angle)) * 150,
                    80,
                    math.sin(math.radians(angle)) * 150
                )
            ))
        
        # Stars
        bob_omb.stars.append(Star(Vector3(300, 450, 300), 1))  # Top of mountain
        bob_omb.stars.append(Star(Vector3(-300, 150, -200), 2))  # Chain chomp star
        bob_omb.stars.append(Star(Vector3(0, 100, -400), 3))  # Race star
        bob_omb.stars.append(Star(Vector3(200, 200, -200), 4))  # Floating island
        bob_omb.stars.append(Star(Vector3(-200, 80, 300), 5))  # Behind bars
        bob_omb.stars.append(Star(Vector3(0, 300, 0), 6))  # 100 coins
        
        # Enemies
        for i in range(5):
            bob_omb.enemies.append(Enemy(
                Vector3(random.randint(-300, 300), 50, random.randint(-300, 300)),
                "goomba"
            ))
        bob_omb.enemies.append(Enemy(Vector3(-300, 60, -200), "chain_chomp", 99))
        bob_omb.enemies.append(Enemy(Vector3(100, 50, 100), "bob_omb"))
        
        levels[1] = bob_omb
        
        # Whomp's Fortress (simulated)
        whomps = Level(
            name="Whomp's Fortress",
            spawn_point=Vector3(0, 50, 0),
            sky_color=(180, 200, 255)
        )
        
        # Base platform
        whomps.platforms.append(Platform(
            Vector3(0, 0, 0), 400, 20, 400, (180, 180, 180), "stone"
        ))
        
        # Fortress walls and ramps
        for i in range(8):
            whomps.platforms.append(Platform(
                Vector3(i * 50 - 175, i * 60 + 30, 0),
                100, 20, 150,
                (160, 160, 160), "stone"
            ))
        
        # Tower
        for i in range(6):
            whomps.platforms.append(Platform(
                Vector3(200, i * 80 + 50, 200),
                120 - i*10, 30, 120 - i*10,
                (140, 140, 140), "brick"
            ))
        
        # Rotating platforms (simulated as stationary for now)
        whomps.platforms.append(Platform(
            Vector3(-100, 200, -100), 60, 10, 200, (139, 69, 19), "wood", True, 100, 2
        ))
        
        # Coins
        for i in range(40):
            whomps.coins.append(Coin(
                Vector3(
                    random.randint(-200, 200),
                    random.randint(50, 400),
                    random.randint(-200, 200)
                )
            ))
        
        # Stars
        whomps.stars.append(Star(Vector3(200, 500, 200), 1))  # Top of tower
        whomps.stars.append(Star(Vector3(-150, 300, -150), 2))  # Whomp boss
        whomps.stars.append(Star(Vector3(0, 250, 150), 3))  # Shoot into wild
        
        # Enemies
        for i in range(3):
            whomps.enemies.append(Enemy(
                Vector3(random.randint(-150, 150), 50, random.randint(-150, 150)),
                "whomp", 3
            ))
        whomps.enemies.append(Enemy(Vector3(200, 480, 200), "whomp_king", 10))
        
        levels[2] = whomps
        
        # Cool Cool Mountain (simulated)
        ccm = Level(
            name="Cool Cool Mountain",
            spawn_point=Vector3(0, 500, 0),
            sky_color=(200, 220, 255)
        )
        
        # Peak
        ccm.platforms.append(Platform(
            Vector3(0, 500, 0), 200, 30, 200, (255, 255, 255), "snow"
        ))
        
        # Slide down the mountain (platforms)
        for i in range(15):
            angle = i * 24
            radius = 100 + i * 30
            height = 480 - i * 30
            ccm.platforms.append(Platform(
                Vector3(
                    math.cos(math.radians(angle)) * radius,
                    height,
                    math.sin(math.radians(angle)) * radius
                ),
                120, 20, 120,
                (240, 248, 255), "ice"
            ))
        
        # Base
        ccm.platforms.append(Platform(
            Vector3(0, 0, 0), 800, 30, 800, (255, 250, 250), "snow"
        ))
        
        # Cabin
        ccm.platforms.append(Platform(
            Vector3(-200, 30, -200), 100, 80, 100, (139, 90, 43), "wood"
        ))
        
        # Coins
        for i in range(60):
            ccm.coins.append(Coin(
                Vector3(
                    random.randint(-300, 300),
                    random.randint(50, 480),
                    random.randint(-300, 300)
                )
            ))
        
        # Blue coins on slide
        for i in range(5):
            ccm.coins.append(Coin(
                Vector3(i * 50, 400 - i * 30, i * 50),
                coin_type="blue"
            ))
        
        # Stars
        ccm.stars.append(Star(Vector3(0, 520, 0), 1))  # Race penguin
        ccm.stars.append(Star(Vector3(-200, 80, -200), 2))  # Baby penguin
        ccm.stars.append(Star(Vector3(300, 100, 300), 3))  # Big penguin race
        
        # Enemies
        ccm.enemies.append(Enemy(Vector3(0, 510, 0), "penguin"))
        for i in range(3):
            ccm.enemies.append(Enemy(
                Vector3(random.randint(-200, 200), 50, random.randint(-200, 200)),
                "snowman"
            ))
        
        levels[3] = ccm
        
        # Castle Grounds (hub)
        castle = Level(
            name="Castle Grounds",
            spawn_point=Vector3(0, 50, -500),
            sky_color=(135, 206, 250)
        )
        
        # Main ground
        castle.platforms.append(Platform(
            Vector3(0, 0, 0), 2000, 30, 2000, (34, 139, 34), "grass"
        ))
        
        # Castle structure
        castle.platforms.append(Platform(
            Vector3(0, 30, 300), 400, 200, 300, (220, 180, 140), "brick"
        ))
        
        # Castle door platform
        castle.platforms.append(Platform(
            Vector3(0, 30, 100), 100, 10, 50, (150, 150, 150), "stone"
        ))
        
        # Moat (visual only)
        castle.platforms.append(Platform(
            Vector3(0, 5, 0), 600, 5, 150, (64, 164, 223), "water"
        ))
        
        # Trees (as tall platforms)
        for i in range(10):
            angle = random.randint(0, 360)
            dist = random.randint(400, 800)
            castle.platforms.append(Platform(
                Vector3(
                    math.cos(math.radians(angle)) * dist,
                    50,
                    math.sin(math.radians(angle)) * dist
                ),
                30, 100, 30,
                (101, 67, 33), "tree"
            ))
        
        # Coins around castle
        for i in range(20):
            castle.coins.append(Coin(
                Vector3(
                    random.randint(-400, 400),
                    50,
                    random.randint(-400, 200)
                )
            ))
        
        levels[0] = castle
        
        return levels

class N64CPU:
    """Simulated MIPS R4300i CPU"""
    
    def __init__(self):
        self.registers = [0] * 32
        self.pc = 0
        self.hi = 0
        self.lo = 0
        self.cp0 = [0] * 32
        self.cp1 = [0.0] * 32  # FPU
        self.cycles = 0
        
    def tick(self, cycles=1):
        self.cycles += cycles

class N64RDP:
    """Simulated Reality Display Processor"""
    
    def __init__(self):
        self.frame_buffer = None
        self.z_buffer = None
        self.texture_cache = {}
        
    def render_triangle(self, v1, v2, v3, color):
        pass  # Handled by Pygame

class N64RSP:
    """Simulated Reality Signal Processor"""
    
    def __init__(self):
        self.dmem = bytearray(4096)
        self.imem = bytearray(4096)

class N64Emulator:
    """Main N64 Emulator Core"""
    
    def __init__(self):
        pygame.init()
        pygame.mixer.init()
        
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Cat's N64 EMU - Super Mario 64")
        self.clock = pygame.time.Clock()
        
        # Hardware simulation
        self.cpu = N64CPU()
        self.rdp = N64RDP()
        self.rsp = N64RSP()
        
        # ROM
        self.rom = SimulatedROM()
        
        # Game state
        self.state = GameState.TITLE
        self.mario = Mario()
        self.camera = Camera()
        self.current_level_id = 0
        self.current_level: Optional[Level] = None
        
        # Input
        self.keys_pressed = set()
        self.stick_x = 0
        self.stick_y = 0
        
        # Fonts
        self.font_large = pygame.font.Font(None, 72)
        self.font_medium = pygame.font.Font(None, 48)
        self.font_small = pygame.font.Font(None, 32)
        
        # Title screen animation
        self.title_timer = 0
        self.title_mario_face_angle = 0
        
        # Star collection animation
        self.star_get_timer = 0
        self.collected_star_id = 0
        
        # Generate sounds
        self._init_sounds()
        
    def _init_sounds(self):
        """Generate simple sound effects"""
        self.sounds = {}
        
        # Jump sound
        jump_sound = pygame.mixer.Sound(buffer=self._generate_tone(440, 0.1))
        self.sounds["jump"] = jump_sound
        
        # Coin sound  
        coin_sound = pygame.mixer.Sound(buffer=self._generate_tone(880, 0.05))
        self.sounds["coin"] = coin_sound
        
        # Star sound
        star_sound = pygame.mixer.Sound(buffer=self._generate_tone(660, 0.3))
        self.sounds["star"] = star_sound
        
    def _generate_tone(self, frequency, duration):
        """Generate a simple sine wave tone"""
        sample_rate = 44100
        n_samples = int(sample_rate * duration)
        buf = bytes(int(127 + 127 * math.sin(2 * math.pi * frequency * i / sample_rate)) 
                   for i in range(n_samples))
        return buf
        
    def project_3d_to_2d(self, point: Vector3) -> Tuple[int, int, float]:
        """Project 3D point to 2D screen coordinates"""
        # Translate relative to camera
        rel_x = point.x - self.camera.position.x
        rel_y = point.y - self.camera.position.y
        rel_z = point.z - self.camera.position.z
        
        # Rotate around Y axis based on camera angle
        angle_rad = math.radians(self.camera.angle)
        rot_x = rel_x * math.cos(angle_rad) - rel_z * math.sin(angle_rad)
        rot_z = rel_x * math.sin(angle_rad) + rel_z * math.cos(angle_rad)
        
        # Perspective projection
        if rot_z <= 10:
            rot_z = 10
            
        fov = 500
        screen_x = SCREEN_WIDTH // 2 + int(rot_x * fov / rot_z)
        screen_y = SCREEN_HEIGHT // 2 - int((rel_y - 100) * fov / rot_z)
        
        return screen_x, screen_y, rot_z
    
    def handle_input(self):
        """Handle controller/keyboard input"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                self.keys_pressed.add(event.key)
                
                if self.state == GameState.TITLE:
                    if event.key == pygame.K_RETURN:
                        self.state = GameState.FILE_SELECT
                        
                elif self.state == GameState.FILE_SELECT:
                    if event.key == pygame.K_RETURN:
                        self.load_level(0)  # Castle grounds
                        self.state = GameState.CASTLE
                        
                elif self.state == GameState.CASTLE or self.state == GameState.LEVEL:
                    if event.key == pygame.K_SPACE and self.mario.on_ground:
                        self._do_jump()
                    elif event.key == pygame.K_SPACE and not self.mario.on_ground:
                        self._do_air_action()
                    elif event.key == pygame.K_z:
                        self._do_crouch_action()
                    elif event.key == pygame.K_ESCAPE:
                        self.state = GameState.PAUSE
                    elif event.key == pygame.K_1:
                        self.load_level(1)
                        self.state = GameState.LEVEL
                    elif event.key == pygame.K_2:
                        self.load_level(2)
                        self.state = GameState.LEVEL
                    elif event.key == pygame.K_3:
                        self.load_level(3)
                        self.state = GameState.LEVEL
                    elif event.key == pygame.K_0:
                        self.load_level(0)
                        self.state = GameState.CASTLE
                        
                elif self.state == GameState.PAUSE:
                    if event.key == pygame.K_ESCAPE:
                        self.state = GameState.LEVEL if self.current_level_id > 0 else GameState.CASTLE
                        
                elif self.state == GameState.STAR_GET:
                    if event.key == pygame.K_RETURN and self.star_get_timer > 120:
                        self.load_level(0)
                        self.state = GameState.CASTLE
                        
            elif event.type == pygame.KEYUP:
                self.keys_pressed.discard(event.key)
                
        # Analog stick simulation
        self.stick_x = 0
        self.stick_y = 0
        if pygame.K_LEFT in self.keys_pressed or pygame.K_a in self.keys_pressed:
            self.stick_x = -1
        if pygame.K_RIGHT in self.keys_pressed or pygame.K_d in self.keys_pressed:
            self.stick_x = 1
        if pygame.K_UP in self.keys_pressed or pygame.K_w in self.keys_pressed:
            self.stick_y = 1
        if pygame.K_DOWN in self.keys_pressed or pygame.K_s in self.keys_pressed:
            self.stick_y = -1
            
        # Camera control
        if pygame.K_q in self.keys_pressed:
            self.camera.angle -= 3
        if pygame.K_e in self.keys_pressed:
            self.camera.angle += 3
            
        return True
    
    def _do_jump(self):
        """Handle jump action"""
        if self.mario.on_ground:
            forward_speed = self.mario.get_forward_vel()
            
            if forward_speed > 5:
                if self.mario.jump_count == 0:
                    self.mario.velocity.y = 12
                    self.mario.action = MarioAction.JUMPING
                    self.mario.jump_count = 1
                elif self.mario.jump_count == 1:
                    self.mario.velocity.y = 15
                    self.mario.action = MarioAction.DOUBLE_JUMP
                    self.mario.jump_count = 2
                elif self.mario.jump_count == 2:
                    self.mario.velocity.y = 18
                    self.mario.action = MarioAction.TRIPLE_JUMP
                    self.mario.jump_count = 0
            else:
                self.mario.velocity.y = 12
                self.mario.action = MarioAction.JUMPING
                self.mario.jump_count = 0
                
            self.mario.on_ground = False
            self.sounds["jump"].play()
    
    def _do_air_action(self):
        """Handle air actions"""
        if self.mario.wall_kick_timer > 0:
            # Wall kick
            self.mario.velocity.y = 14
            self.mario.velocity.x = -self.mario.velocity.x * 0.5
            self.mario.velocity.z = -self.mario.velocity.z * 0.5
            self.mario.action = MarioAction.WALL_KICK
            self.mario.wall_kick_timer = 0
            self.sounds["jump"].play()
    
    def _do_crouch_action(self):
        """Handle crouch/ground pound"""
        if not self.mario.on_ground:
            # Ground pound
            self.mario.velocity.y = -20
            self.mario.velocity.x = 0
            self.mario.velocity.z = 0
            self.mario.action = MarioAction.GROUND_POUND
        elif self.mario.get_forward_vel() > 8:
            # Long jump
            angle_rad = math.radians(self.mario.facing_angle)
            self.mario.velocity.y = 10
            self.mario.velocity.x = math.sin(angle_rad) * 15
            self.mario.velocity.z = math.cos(angle_rad) * 15
            self.mario.action = MarioAction.LONG_JUMP
            self.mario.on_ground = False
            self.sounds["jump"].play()
        else:
            # Backflip
            self.mario.velocity.y = 16
            angle_rad = math.radians(self.mario.facing_angle + 180)
            self.mario.velocity.x = math.sin(angle_rad) * 5
            self.mario.velocity.z = math.cos(angle_rad) * 5
            self.mario.action = MarioAction.BACKFLIP
            self.mario.on_ground = False
            self.sounds["jump"].play()
    
    def load_level(self, level_id: int):
        """Load a level from the simulated ROM"""
        if level_id in self.rom.levels:
            self.current_level = self.rom.levels[level_id]
            self.current_level_id = level_id
            self.mario.position = Vector3(
                self.current_level.spawn_point.x,
                self.current_level.spawn_point.y,
                self.current_level.spawn_point.z
            )
            self.mario.velocity = Vector3()
            self.mario.on_ground = False
            self.camera.angle = 0
            
            # Reset collectibles for this level
            for coin in self.current_level.coins:
                coin.collected = False
            for enemy in self.current_level.enemies:
                enemy.active = True
    
    def update_mario(self):
        """Update Mario's physics and state"""
        # Movement based on stick input
        if self.stick_x != 0 or self.stick_y != 0:
            # Calculate intended direction based on camera
            cam_angle = math.radians(self.camera.angle)
            
            # Forward/back relative to camera
            fwd_x = math.sin(cam_angle) * self.stick_y
            fwd_z = math.cos(cam_angle) * self.stick_y
            
            # Left/right relative to camera
            side_x = math.sin(cam_angle + math.pi/2) * self.stick_x
            side_z = math.cos(cam_angle + math.pi/2) * self.stick_x
            
            move_x = fwd_x + side_x
            move_z = fwd_z + side_z
            
            # Normalize
            mag = math.sqrt(move_x**2 + move_z**2)
            if mag > 0:
                move_x /= mag
                move_z /= mag
            
            # Apply acceleration
            accel = 0.8 if self.mario.on_ground else 0.3
            self.mario.velocity.x += move_x * accel
            self.mario.velocity.z += move_z * accel
            
            # Update facing angle
            self.mario.facing_angle = math.degrees(math.atan2(move_x, move_z))
            
            if self.mario.on_ground:
                speed = self.mario.get_forward_vel()
                if speed > 2:
                    self.mario.action = MarioAction.RUNNING if speed > 6 else MarioAction.WALKING
        else:
            if self.mario.on_ground:
                self.mario.action = MarioAction.IDLE
                self.mario.jump_count = 0
        
        # Speed cap
        max_speed = 12 if self.mario.on_ground else 15
        current_speed = self.mario.get_forward_vel()
        if current_speed > max_speed:
            scale = max_speed / current_speed
            self.mario.velocity.x *= scale
            self.mario.velocity.z *= scale
        
        # Apply gravity
        if not self.mario.on_ground:
            gravity = GRAVITY * 1.5 if self.mario.action == MarioAction.GROUND_POUND else GRAVITY
            self.mario.velocity.y -= gravity
            
            if self.mario.velocity.y < 0:
                self.mario.action = MarioAction.FALLING
        
        # Apply friction
        if self.mario.on_ground:
            self.mario.velocity.x *= FRICTION
            self.mario.velocity.z *= FRICTION
        
        # Update position
        self.mario.position.x += self.mario.velocity.x
        self.mario.position.y += self.mario.velocity.y
        self.mario.position.z += self.mario.velocity.z
        
        # Collision with platforms
        self.mario.on_ground = False
        if self.current_level:
            for platform in self.current_level.platforms:
                if self._check_platform_collision(platform):
                    break
        
        # Wall kick timer
        if self.mario.wall_kick_timer > 0:
            self.mario.wall_kick_timer -= 1
        
        # Death plane
        if self.mario.position.y < -500:
            self.mario.lives -= 1
            if self.mario.lives > 0:
                self.load_level(self.current_level_id)
            else:
                self.state = GameState.TITLE
                self.mario = Mario()
    
    def _check_platform_collision(self, platform: Platform) -> bool:
        """Check and resolve collision with a platform"""
        # Update moving platforms
        if platform.moving:
            platform.move_offset += platform.move_speed * 0.02
            offset = math.sin(platform.move_offset) * platform.move_range
            # Apply offset to platform position for collision
        
        px, py, pz = platform.position.x, platform.position.y, platform.position.z
        hw, hh, hd = platform.width/2, platform.height/2, platform.depth/2
        
        mx, my, mz = self.mario.position.x, self.mario.position.y, self.mario.position.z
        
        # Check if Mario is within platform bounds horizontally
        if (px - hw < mx < px + hw and pz - hd < mz < pz + hd):
            # Check vertical collision (landing on top)
            if py + hh - 5 < my < py + hh + 50 and self.mario.velocity.y <= 0:
                self.mario.position.y = py + hh
                self.mario.velocity.y = 0
                self.mario.on_ground = True
                return True
                
        # Wall collision
        margin = 20
        if (px - hw - margin < mx < px + hw + margin and 
            pz - hd - margin < mz < pz + hd + margin and
            py < my < py + platform.height):
            # Push Mario out
            if mx < px:
                if self.mario.velocity.x > 0:
                    self.mario.velocity.x = 0
                    self.mario.wall_kick_timer = 10
            else:
                if self.mario.velocity.x < 0:
                    self.mario.velocity.x = 0
                    self.mario.wall_kick_timer = 10
                    
        return False
    
    def update_collectibles(self):
        """Update coins, stars, and other collectibles"""
        if not self.current_level:
            return
            
        mario_pos = self.mario.position
        
        # Coins
        for coin in self.current_level.coins:
            if coin.collected:
                continue
            coin.rotation += 5
            
            # Check collection
            dx = coin.position.x - mario_pos.x
            dy = coin.position.y - mario_pos.y
            dz = coin.position.z - mario_pos.z
            dist = math.sqrt(dx*dx + dy*dy + dz*dz)
            
            if dist < 40:
                coin.collected = True
                self.mario.coins += 5 if coin.coin_type == "blue" else 1
                self.sounds["coin"].play()
                
                # Health recovery
                if self.mario.health < 8:
                    self.mario.health = min(8, self.mario.health + 1)
        
        # Stars
        for star in self.current_level.stars:
            if star.collected:
                continue
            star.rotation += 3
            
            # Check collection
            dx = star.position.x - mario_pos.x
            dy = star.position.y - mario_pos.y
            dz = star.position.z - mario_pos.z
            dist = math.sqrt(dx*dx + dy*dy + dz*dz)
            
            if dist < 50:
                star.collected = True
                self.mario.stars += 1
                self.collected_star_id = star.star_id
                self.star_get_timer = 0
                self.state = GameState.STAR_GET
                self.sounds["star"].play()
    
    def update_enemies(self):
        """Update enemy behavior"""
        if not self.current_level:
            return
            
        mario_pos = self.mario.position
        
        for enemy in self.current_level.enemies:
            if not enemy.active:
                continue
                
            # Simple AI - move towards Mario
            dx = mario_pos.x - enemy.position.x
            dz = mario_pos.z - enemy.position.z
            dist = math.sqrt(dx*dx + dz*dz)
            
            if enemy.enemy_type == "goomba":
                if dist < 300 and dist > 30:
                    enemy.velocity.x = (dx / dist) * 1.5
                    enemy.velocity.z = (dz / dist) * 1.5
                    enemy.position.x += enemy.velocity.x
                    enemy.position.z += enemy.velocity.z
                    enemy.facing = math.degrees(math.atan2(dx, dz))
                    
                # Check if Mario stomps
                if dist < 40:
                    if self.mario.velocity.y < 0 and mario_pos.y > enemy.position.y + 20:
                        enemy.active = False
                        self.mario.velocity.y = 10
                    elif self.mario.invincible_timer <= 0:
                        self.mario.health -= 1
                        self.mario.invincible_timer = 60
                        # Knockback
                        self.mario.velocity.x = -dx/dist * 10
                        self.mario.velocity.z = -dz/dist * 10
                        self.mario.velocity.y = 8
                        
            elif enemy.enemy_type == "bob_omb":
                if dist < 200:
                    enemy.velocity.x = (dx / dist) * 2
                    enemy.velocity.z = (dz / dist) * 2
                    enemy.position.x += enemy.velocity.x
                    enemy.position.z += enemy.velocity.z
                    
            elif enemy.enemy_type == "chain_chomp":
                # Bounces in place
                enemy.position.y = 60 + math.sin(pygame.time.get_ticks() * 0.01) * 20
                
        # Update invincibility
        if self.mario.invincible_timer > 0:
            self.mario.invincible_timer -= 1
    
    def render_title_screen(self):
        """Render the title screen"""
        self.screen.fill((0, 0, 50))
        
        self.title_timer += 1
        
        # Animated background stars
        for i in range(50):
            x = (i * 73 + self.title_timer) % SCREEN_WIDTH
            y = (i * 47) % SCREEN_HEIGHT
            brightness = 100 + int(50 * math.sin(self.title_timer * 0.05 + i))
            pygame.draw.circle(self.screen, (brightness, brightness, brightness), (x, y), 2)
        
        # Title
        title_y = 150 + int(math.sin(self.title_timer * 0.05) * 10)
        title = self.font_large.render("SUPER MARIO 64", True, (255, 215, 0))
        title_rect = title.get_rect(center=(SCREEN_WIDTH//2, title_y))
        
        # Shadow
        shadow = self.font_large.render("SUPER MARIO 64", True, (100, 50, 0))
        self.screen.blit(shadow, (title_rect.x + 4, title_rect.y + 4))
        self.screen.blit(title, title_rect)
        
        # Subtitle
        sub = self.font_small.render("Cat's N64 EMU - Simulated Edition", True, (200, 200, 200))
        self.screen.blit(sub, sub.get_rect(center=(SCREEN_WIDTH//2, 220)))
        
        # Mario face (simplified)
        self.title_mario_face_angle += 0.5
        face_x = SCREEN_WIDTH // 2
        face_y = 350
        
        # Face circle
        pygame.draw.circle(self.screen, (255, 200, 150), (face_x, face_y), 80)
        
        # Hat
        pygame.draw.arc(self.screen, (255, 0, 0), 
                       (face_x - 90, face_y - 100, 180, 100), 
                       0, math.pi, 20)
        pygame.draw.ellipse(self.screen, (255, 0, 0),
                           (face_x - 70, face_y - 80, 140, 40))
        
        # M logo on hat
        m_text = self.font_small.render("M", True, (255, 255, 255))
        self.screen.blit(m_text, m_text.get_rect(center=(face_x, face_y - 60)))
        
        # Eyes
        eye_offset = int(math.sin(self.title_mario_face_angle * 0.1) * 5)
        pygame.draw.ellipse(self.screen, (255, 255, 255), 
                           (face_x - 35 + eye_offset, face_y - 20, 25, 30))
        pygame.draw.ellipse(self.screen, (255, 255, 255), 
                           (face_x + 10 + eye_offset, face_y - 20, 25, 30))
        pygame.draw.circle(self.screen, (0, 100, 200), 
                          (face_x - 22 + eye_offset, face_y - 5), 8)
        pygame.draw.circle(self.screen, (0, 100, 200), 
                          (face_x + 22 + eye_offset, face_y - 5), 8)
        
        # Nose
        pygame.draw.ellipse(self.screen, (200, 100, 100), 
                           (face_x - 20, face_y + 5, 40, 30))
        
        # Mustache
        pygame.draw.ellipse(self.screen, (50, 30, 20), 
                           (face_x - 50, face_y + 30, 45, 25))
        pygame.draw.ellipse(self.screen, (50, 30, 20), 
                           (face_x + 5, face_y + 30, 45, 25))
        
        # Press Start
        if self.title_timer % 60 < 40:
            start = self.font_medium.render("PRESS ENTER", True, (255, 255, 255))
            self.screen.blit(start, start.get_rect(center=(SCREEN_WIDTH//2, 500)))
        
        # Credits
        credit = self.font_small.render("© Team Flames / Samsoft", True, (150, 150, 150))
        self.screen.blit(credit, credit.get_rect(center=(SCREEN_WIDTH//2, 570)))
    
    def render_file_select(self):
        """Render file select screen"""
        self.screen.fill((50, 50, 100))
        
        title = self.font_large.render("SELECT FILE", True, (255, 215, 0))
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH//2, 80)))
        
        # File slots
        for i in range(4):
            y = 180 + i * 100
            color = (100, 100, 150) if i == 0 else (70, 70, 100)
            pygame.draw.rect(self.screen, color, (150, y, 500, 80), border_radius=10)
            pygame.draw.rect(self.screen, (200, 200, 200), (150, y, 500, 80), 3, border_radius=10)
            
            if i == 0:
                # Active file
                file_text = self.font_medium.render(f"MARIO A", True, (255, 255, 255))
                stars_text = self.font_small.render(f"★ {self.mario.stars}", True, (255, 215, 0))
            else:
                file_text = self.font_medium.render(f"MARIO {chr(65+i)}", True, (150, 150, 150))
                stars_text = self.font_small.render("NEW", True, (150, 150, 150))
                
            self.screen.blit(file_text, (180, y + 15))
            self.screen.blit(stars_text, (550, y + 25))
        
        hint = self.font_small.render("Press ENTER to start", True, (200, 200, 200))
        self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH//2, 550)))
    
    def render_game(self):
        """Render the 3D game world"""
        if not self.current_level:
            return
            
        # Sky
        self.screen.fill(self.current_level.sky_color)
        
        # Collect all objects for depth sorting
        render_objects = []
        
        # Platforms
        for platform in self.current_level.platforms:
            screen_x, screen_y, depth = self.project_3d_to_2d(platform.position)
            if depth > 0:
                render_objects.append((depth, "platform", platform, screen_x, screen_y))
        
        # Coins
        for coin in self.current_level.coins:
            if coin.collected:
                continue
            screen_x, screen_y, depth = self.project_3d_to_2d(coin.position)
            if depth > 0:
                render_objects.append((depth, "coin", coin, screen_x, screen_y))
        
        # Stars
        for star in self.current_level.stars:
            if star.collected:
                continue
            screen_x, screen_y, depth = self.project_3d_to_2d(star.position)
            if depth > 0:
                render_objects.append((depth, "star", star, screen_x, screen_y))
        
        # Enemies
        for enemy in self.current_level.enemies:
            if not enemy.active:
                continue
            screen_x, screen_y, depth = self.project_3d_to_2d(enemy.position)
            if depth > 0:
                render_objects.append((depth, "enemy", enemy, screen_x, screen_y))
        
        # Mario
        screen_x, screen_y, depth = self.project_3d_to_2d(self.mario.position)
        if depth > 0:
            render_objects.append((depth, "mario", self.mario, screen_x, screen_y))
        
        # Sort by depth (far to near)
        render_objects.sort(key=lambda x: -x[0])
        
        # Render all objects
        for obj in render_objects:
            depth, obj_type, data, sx, sy = obj
            scale = max(0.1, 500 / depth)
            
            if obj_type == "platform":
                self._render_platform(data, sx, sy, scale)
            elif obj_type == "coin":
                self._render_coin(data, sx, sy, scale)
            elif obj_type == "star":
                self._render_star(data, sx, sy, scale)
            elif obj_type == "enemy":
                self._render_enemy(data, sx, sy, scale)
            elif obj_type == "mario":
                self._render_mario(sx, sy, scale)
        
        # HUD
        self._render_hud()
    
    def _render_platform(self, platform: Platform, sx: int, sy: int, scale: float):
        """Render a platform"""
        w = int(platform.width * scale * 0.5)
        h = int(platform.height * scale * 0.3)
        
        if w < 2 or h < 2:
            return
            
        # Get color based on type
        color = platform.color
        if platform.platform_type == "ice":
            color = (200, 220, 255)
        elif platform.platform_type == "water":
            color = (64, 164, 223)
            
        # Draw top face
        pygame.draw.rect(self.screen, color, 
                        (sx - w//2, sy - h, w, h))
        
        # Draw front face (darker)
        dark_color = (max(0, color[0]-50), max(0, color[1]-50), max(0, color[2]-50))
        pygame.draw.rect(self.screen, dark_color,
                        (sx - w//2, sy, w, int(platform.height * scale * 0.2)))
        
        # Outline
        pygame.draw.rect(self.screen, (0, 0, 0), 
                        (sx - w//2, sy - h, w, h + int(platform.height * scale * 0.2)), 1)
    
    def _render_coin(self, coin: Coin, sx: int, sy: int, scale: float):
        """Render a coin"""
        size = int(15 * scale)
        if size < 2:
            return
            
        # Animate width based on rotation
        width = int(abs(math.cos(math.radians(coin.rotation))) * size)
        width = max(2, width)
        
        color = (255, 215, 0) if coin.coin_type == "yellow" else (100, 149, 237)
        pygame.draw.ellipse(self.screen, color, 
                           (sx - width//2, sy - size//2, width, size))
        pygame.draw.ellipse(self.screen, (255, 255, 200) if coin.coin_type == "yellow" else (150, 200, 255),
                           (sx - width//4, sy - size//4, width//2, size//2))
    
    def _render_star(self, star: Star, sx: int, sy: int, scale: float):
        """Render a power star"""
        size = int(25 * scale)
        if size < 3:
            return
            
        # Star points
        points = []
        for i in range(10):
            angle = math.radians(star.rotation + i * 36 - 90)
            r = size if i % 2 == 0 else size * 0.5
            px = sx + math.cos(angle) * r
            py = sy + math.sin(angle) * r
            points.append((px, py))
        
        pygame.draw.polygon(self.screen, (255, 215, 0), points)
        pygame.draw.polygon(self.screen, (255, 255, 200), points, 2)
        
        # Eyes
        eye_size = max(2, int(3 * scale))
        pygame.draw.circle(self.screen, (0, 0, 0), (sx - int(5*scale), sy - int(2*scale)), eye_size)
        pygame.draw.circle(self.screen, (0, 0, 0), (sx + int(5*scale), sy - int(2*scale)), eye_size)
    
    def _render_enemy(self, enemy: Enemy, sx: int, sy: int, scale: float):
        """Render an enemy"""
        size = int(30 * scale)
        if size < 3:
            return
            
        if enemy.enemy_type == "goomba":
            # Body
            pygame.draw.ellipse(self.screen, (139, 90, 43), 
                               (sx - size//2, sy - size, size, size))
            # Feet
            pygame.draw.ellipse(self.screen, (50, 30, 20),
                               (sx - size//2 - 5, sy - size//4, size//3, size//4))
            pygame.draw.ellipse(self.screen, (50, 30, 20),
                               (sx + size//4, sy - size//4, size//3, size//4))
            # Eyes
            pygame.draw.ellipse(self.screen, (255, 255, 255),
                               (sx - size//3, sy - size + size//4, size//4, size//3))
            pygame.draw.ellipse(self.screen, (255, 255, 255),
                               (sx + size//8, sy - size + size//4, size//4, size//3))
            # Angry eyebrows
            pygame.draw.line(self.screen, (0, 0, 0),
                            (sx - size//3, sy - size + size//4),
                            (sx - size//8, sy - size + size//3), 2)
            pygame.draw.line(self.screen, (0, 0, 0),
                            (sx + size//3, sy - size + size//4),
                            (sx + size//8, sy - size + size//3), 2)
                            
        elif enemy.enemy_type == "bob_omb":
            # Body
            pygame.draw.circle(self.screen, (30, 30, 30), (sx, sy - size//2), size//2)
            # Eyes
            pygame.draw.circle(self.screen, (255, 255, 255), (sx - size//6, sy - size//2 - size//8), size//8)
            pygame.draw.circle(self.screen, (255, 255, 255), (sx + size//6, sy - size//2 - size//8), size//8)
            # Fuse
            pygame.draw.line(self.screen, (200, 150, 100), (sx, sy - size), (sx, sy - size - size//3), 3)
            # Spark
            pygame.draw.circle(self.screen, (255, 200, 50), (sx, sy - size - size//3), size//8)
            
        elif enemy.enemy_type == "chain_chomp":
            # Chain
            for i in range(5):
                pygame.draw.circle(self.screen, (50, 50, 50), 
                                  (sx - size + i*size//4, sy - size//2 + i*5), size//8)
            # Body
            pygame.draw.circle(self.screen, (30, 30, 30), (sx, sy - size), size)
            # Eyes
            pygame.draw.circle(self.screen, (255, 255, 255), (sx - size//3, sy - size - size//4), size//4)
            pygame.draw.circle(self.screen, (255, 255, 255), (sx + size//3, sy - size - size//4), size//4)
            pygame.draw.circle(self.screen, (255, 0, 0), (sx - size//3, sy - size - size//4), size//8)
            pygame.draw.circle(self.screen, (255, 0, 0), (sx + size//3, sy - size - size//4), size//8)
            # Mouth
            pygame.draw.arc(self.screen, (255, 255, 255),
                           (sx - size//2, sy - size - size//4, size, size//2),
                           0.2, math.pi - 0.2, 5)
                           
        elif enemy.enemy_type == "whomp" or enemy.enemy_type == "whomp_king":
            body_size = size * 2 if enemy.enemy_type == "whomp_king" else size
            # Body
            pygame.draw.rect(self.screen, (150, 150, 150),
                            (sx - body_size//2, sy - body_size*2, body_size, body_size*2))
            # Face
            pygame.draw.rect(self.screen, (200, 200, 200),
                            (sx - body_size//2 + 5, sy - body_size*2 + 10, body_size - 10, body_size))
            # Eyes
            pygame.draw.circle(self.screen, (0, 0, 0),
                              (sx - body_size//4, sy - body_size*1.5), body_size//8)
            pygame.draw.circle(self.screen, (0, 0, 0),
                              (sx + body_size//4, sy - body_size*1.5), body_size//8)
    
    def _render_mario(self, sx: int, sy: int, scale: float):
        """Render Mario"""
        size = int(40 * scale * self.mario.size)
        if size < 5:
            return
            
        # Blink when invincible
        if self.mario.invincible_timer > 0 and self.mario.invincible_timer % 10 < 5:
            return
        
        # Body
        pygame.draw.ellipse(self.screen, (0, 0, 200),  # Blue overalls
                           (sx - size//3, sy - size, size*2//3, size*2//3))
        
        # Head
        pygame.draw.circle(self.screen, (255, 200, 150),  # Skin
                          (sx, sy - size - size//4), size//3)
        
        # Hat
        pygame.draw.arc(self.screen, (255, 0, 0),
                       (sx - size//2, sy - size - size//2, size, size//2),
                       0, math.pi, max(3, size//10))
        pygame.draw.ellipse(self.screen, (255, 0, 0),
                           (sx - size//3, sy - size - size//2, size*2//3, size//6))
        
        # M on hat
        if size > 15:
            m_font = pygame.font.Font(None, max(12, size//3))
            m = m_font.render("M", True, (255, 255, 255))
            self.screen.blit(m, m.get_rect(center=(sx, sy - size - size//3)))
        
        # Mustache
        pygame.draw.ellipse(self.screen, (50, 30, 20),
                           (sx - size//4, sy - size - size//8, size//4, size//10))
        pygame.draw.ellipse(self.screen, (50, 30, 20),
                           (sx, sy - size - size//8, size//4, size//10))
        
        # Legs/feet
        pygame.draw.ellipse(self.screen, (139, 69, 19),  # Brown shoes
                           (sx - size//3, sy - size//4, size//4, size//4))
        pygame.draw.ellipse(self.screen, (139, 69, 19),
                           (sx + size//10, sy - size//4, size//4, size//4))
        
        # Action indicator
        if self.mario.action == MarioAction.TRIPLE_JUMP:
            # Star effect
            for i in range(5):
                angle = pygame.time.get_ticks() * 0.01 + i * 72
                px = sx + math.cos(angle) * size
                py = sy - size//2 + math.sin(angle) * size//2
                pygame.draw.circle(self.screen, (255, 255, 0), (int(px), int(py)), 3)
    
    def _render_hud(self):
        """Render the heads-up display"""
        # Health meter (pie)
        center_x, center_y = 70, 70
        radius = 40
        
        # Background
        pygame.draw.circle(self.screen, (50, 50, 50), (center_x, center_y), radius + 5)
        pygame.draw.circle(self.screen, (0, 0, 100), (center_x, center_y), radius)
        
        # Health wedges
        for i in range(8):
            angle_start = math.radians(-90 + i * 45)
            angle_end = math.radians(-90 + (i + 1) * 45)
            
            if i < self.mario.health:
                color = (0, 255, 0) if self.mario.health > 2 else (255, 255, 0)
                if self.mario.health <= 1:
                    color = (255, 0, 0)
                    
                points = [(center_x, center_y)]
                for a in range(int(math.degrees(angle_start)), int(math.degrees(angle_end)) + 1, 5):
                    px = center_x + math.cos(math.radians(a)) * (radius - 5)
                    py = center_y + math.sin(math.radians(a)) * (radius - 5)
                    points.append((px, py))
                points.append((center_x, center_y))
                
                if len(points) > 2:
                    pygame.draw.polygon(self.screen, color, points)
        
        # Lives
        lives_text = self.font_small.render(f"×{self.mario.lives}", True, (255, 255, 255))
        self.screen.blit(lives_text, (120, 55))
        
        # Coins
        pygame.draw.circle(self.screen, (255, 215, 0), (SCREEN_WIDTH - 150, 50), 15)
        coin_text = self.font_small.render(f"×{self.mario.coins}", True, (255, 255, 255))
        self.screen.blit(coin_text, (SCREEN_WIDTH - 125, 40))
        
        # Stars
        star_text = self.font_small.render(f"★×{self.mario.stars}", True, (255, 215, 0))
        self.screen.blit(star_text, (SCREEN_WIDTH - 100, 80))
        
        # Level name
        if self.current_level:
            level_text = self.font_small.render(self.current_level.name, True, (255, 255, 255))
            self.screen.blit(level_text, level_text.get_rect(center=(SCREEN_WIDTH//2, 30)))
        
        # Controls hint
        controls = self.font_small.render("WASD:Move Q/E:Camera SPACE:Jump Z:Action 1-3:Levels", True, (200, 200, 200))
        self.screen.blit(controls, (10, SCREEN_HEIGHT - 30))
    
    def render_star_get(self):
        """Render star collection screen"""
        # Darken background
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.fill((0, 0, 0))
        overlay.set_alpha(180)
        self.screen.blit(overlay, (0, 0))
        
        self.star_get_timer += 1
        
        # Animated star
        star_y = 200 + int(math.sin(self.star_get_timer * 0.1) * 20)
        size = 80 + int(math.sin(self.star_get_timer * 0.15) * 10)
        
        # Star with glow
        for glow in range(3, 0, -1):
            glow_size = size + glow * 20
            alpha = 100 - glow * 30
            glow_color = (255, 215, 0)
            points = []
            for i in range(10):
                angle = math.radians(self.star_get_timer * 2 + i * 36 - 90)
                r = glow_size if i % 2 == 0 else glow_size * 0.5
                px = SCREEN_WIDTH//2 + math.cos(angle) * r
                py = star_y + math.sin(angle) * r
                points.append((px, py))
            s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            pygame.draw.polygon(s, (*glow_color, alpha), points)
            self.screen.blit(s, (0, 0))
        
        # Main star
        points = []
        for i in range(10):
            angle = math.radians(self.star_get_timer * 2 + i * 36 - 90)
            r = size if i % 2 == 0 else size * 0.5
            px = SCREEN_WIDTH//2 + math.cos(angle) * r
            py = star_y + math.sin(angle) * r
            points.append((px, py))
        pygame.draw.polygon(self.screen, (255, 215, 0), points)
        pygame.draw.polygon(self.screen, (255, 255, 200), points, 3)
        
        # Star eyes
        pygame.draw.circle(self.screen, (0, 0, 0), (SCREEN_WIDTH//2 - 20, star_y - 10), 8)
        pygame.draw.circle(self.screen, (0, 0, 0), (SCREEN_WIDTH//2 + 20, star_y - 10), 8)
        
        # Text
        if self.star_get_timer > 30:
            star_text = self.font_large.render("STAR GET!", True, (255, 255, 255))
            self.screen.blit(star_text, star_text.get_rect(center=(SCREEN_WIDTH//2, 380)))
        
        if self.star_get_timer > 60:
            count_text = self.font_medium.render(f"You now have {self.mario.stars} star{'s' if self.mario.stars != 1 else ''}!", 
                                                  True, (255, 215, 0))
            self.screen.blit(count_text, count_text.get_rect(center=(SCREEN_WIDTH//2, 450)))
        
        if self.star_get_timer > 120:
            hint = self.font_small.render("Press ENTER to continue", True, (200, 200, 200))
            self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH//2, 520)))
    
    def render_pause(self):
        """Render pause menu"""
        # Darken
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.fill((0, 0, 0))
        overlay.set_alpha(150)
        self.screen.blit(overlay, (0, 0))
        
        pause_text = self.font_large.render("PAUSED", True, (255, 255, 255))
        self.screen.blit(pause_text, pause_text.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 50)))
        
        hint = self.font_small.render("Press ESC to resume", True, (200, 200, 200))
        self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2 + 50)))
    
    def run(self):
        """Main game loop"""
        running = True
        
        while running:
            running = self.handle_input()
            
            # Update CPU cycles (simulated)
            self.cpu.tick(93750000 // FPS)  # ~93.75 MHz
            
            if self.state == GameState.TITLE:
                self.render_title_screen()
                
            elif self.state == GameState.FILE_SELECT:
                self.render_file_select()
                
            elif self.state in (GameState.CASTLE, GameState.LEVEL):
                self.update_mario()
                self.update_collectibles()
                self.update_enemies()
                self.camera.update(self.mario.position)
                self.render_game()
                
            elif self.state == GameState.STAR_GET:
                self.render_star_get()
                
            elif self.state == GameState.PAUSE:
                self.render_game()
                self.render_pause()
            
            pygame.display.flip()
            self.clock.tick(FPS)
        
        pygame.quit()

def main():
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║           CAT'S N64 EMU - Super Mario 64 Simulator            ║")
    print("║                      by Team Flames                           ║")
    print("╠═══════════════════════════════════════════════════════════════╣")
    print("║  Controls:                                                    ║")
    print("║    WASD / Arrow Keys - Move Mario                             ║")
    print("║    Q / E - Rotate Camera                                      ║")
    print("║    SPACE - Jump (tap multiple times for double/triple jump)   ║")
    print("║    Z - Crouch action (ground pound, long jump, backflip)      ║")
    print("║    1-3 - Quick warp to levels                                 ║")
    print("║    0 - Return to Castle                                       ║")
    print("║    ESC - Pause                                                ║")
    print("╠═══════════════════════════════════════════════════════════════╣")
    print("║  Simulated Levels:                                            ║")
    print("║    0 - Castle Grounds (Hub)                                   ║")
    print("║    1 - Bob-omb Battlefield                                    ║")
    print("║    2 - Whomp's Fortress                                       ║")
    print("║    3 - Cool Cool Mountain                                     ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print()
    print("Starting emulator...")
    
    emu = N64Emulator()
    emu.run()

if __name__ == "__main__":
    main()
