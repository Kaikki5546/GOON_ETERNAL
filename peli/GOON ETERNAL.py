import pygame
import math
import sys
import random
import time
import os
import heapq
import json
from pypresence import Presence

# --- Discord RPC Setup ---
client_id = '1499380659955699742'
RPC = None
start_time = time.time()

try:
    RPC = Presence(client_id)
    RPC.connect()
    print("Discord Rich Presence connected!")
except Exception as e:
    print(f"Discord not detected: {e}")

def update_discord(level, score):
    if RPC:
        try:
            state = "Fighting DRACULA!" if level == 10 else ("Fighting KILLDOZER!" if level == 5 else f"Level {level}")
            RPC.update(
                state=state,
                details=f"Score: {score}",
                large_image="load.png",
                large_text="Goon Eternal",
                start=start_time
            )
        except Exception as e:
            print(f"RPC Update failed: {e}")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
WIDTH, HEIGHT = 960, 640
MAP_PANEL_W   = 400          # sidebar width for minimap
TOTAL_WIDTH   = WIDTH + MAP_PANEL_W
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
MEDIA_PATH = os.path.join(BASE_PATH, "media")
SAVE_FILE     = os.path.join(BASE_PATH, "savegame.json")
SETTINGS_FILE = os.path.join(BASE_PATH, "settings.json")
FPS           = 60
TILE_SIZE     = 64
FOV           = math.pi / 2          # 90 deg FOV (was 60 deg) -- wider, more immersive
HALF_FOV      = FOV / 2
NUM_RAYS      = WIDTH                # One ray per pixel column -- maximum sharpness
MAX_DEPTH     = 40                   # Longer draw distance (was 25)

ITEM_AMMO    = "ammo"
ITEM_HEALTH  = "health"
ITEM_KEY     = "key"
ITEM_TOKEN   = "token"
ITEM_TRAP    = "trap"

CELL_FLOOR    = 0
CELL_WALL     = 1
CELL_DOOR     = 2
CELL_EXITDOOR = 3

ENEMY_RESPAWN_TICKS = 600
BOSS_LEVEL = 10
MINI_BOSS_LEVEL = 5
DEMO_LEVEL = 99   # Sentinel for the custom hand-crafted demo arena

# Weapons
WEAPON_PISTOL  = 'pistol'
WEAPON_SHOTGUN = 'shotgun'
WEAPON_SMG     = 'smg'
WEAPON_ORDER   = [WEAPON_PISTOL, WEAPON_SHOTGUN, WEAPON_SMG]

# Kill streak thresholds and bonuses
STREAK_THRESHOLDS = [3, 5, 8, 12]      # kills within STREAK_WINDOW ticks
STREAK_WINDOW     = 180                  # ~3 seconds at 60fps
STREAK_NAMES      = ["TRIPLE KILL!", "KILLING SPREE!", "RAMPAGE!", "GODLIKE!"]
STREAK_COLORS     = [(255,200,50), (255,120,30), (255,50,50), (220,0,255)]

# Enemy alert flash duration (frames before chase starts)
ENEMY_ALERT_FRAMES = 30

# Mouse sensitivity (horizontal only, Doom 64 style)
MOUSE_SENSITIVITY = 0.003

# ---------------------------------------------------------------------------
# Color Palette (Hot pink / dark gothic theme)
# ---------------------------------------------------------------------------
COL_ACCENT      = (255, 20, 147)
COL_ACCENT2     = (200, 0, 100)
COL_GOLD        = (255, 215, 0)
COL_DARK        = (10, 0, 20)
COL_PANEL       = (18, 4, 32)
COL_PANEL_EDGE  = (80, 0, 60)
COL_RED         = (220, 30, 50)
COL_GREEN       = (0, 210, 120)
COL_BLUE        = (0, 180, 255)
COL_WHITE       = (255, 255, 255)
COL_BOSS        = (120, 0, 200)
COL_BOSS_BRIGHT = (200, 60, 255)

# ---------------------------------------------------------------------------
# Map generator
# ---------------------------------------------------------------------------
KEYCARD_COLORS = ['red', 'blue', 'green']

def _flood_fill_reachable(grid, W, H, start_tx, start_ty):
    """BFS flood-fill from (start_tx, start_ty) on CELL_FLOOR/CELL_DOOR tiles.
    Returns set of (tx, ty) tile coords reachable without crossing walls."""
    passable = {CELL_FLOOR, CELL_DOOR}
    visited = set()
    queue = [(start_tx, start_ty)]
    while queue:
        nxt = []
        for cx, cy in queue:
            if (cx, cy) in visited:
                continue
            if cx < 0 or cx >= W or cy < 0 or cy >= H:
                continue
            if grid[cy][cx] not in passable:
                continue
            visited.add((cx, cy))
            for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                nb = (cx+dx, cy+dy)
                if nb not in visited:
                    nxt.append(nb)
        queue = nxt
    return visited


def generate_map(rng, level=1, run_seed=0):
    if level == BOSS_LEVEL:
        return generate_boss_arena(rng)
    if level == MINI_BOSS_LEVEL:
        return generate_miniboss_arena(rng)
    if level == DEMO_LEVEL:
        return generate_demo_arena()

    # Use a combined seed so the map is unique per (run, level) pair
    map_rng = random.Random(run_seed * 10000 + level * 997 + 13)

    W = min(120, 70 + (level - 1) * 7)
    H = min(120, 70 + (level - 1) * 7)
    grid = [[CELL_WALL] * W for _ in range(H)]
    rooms = []

    def carve(x1, y1, x2, y2):
        for ry in range(max(1, y1), min(H-1, y2)):
            for rx in range(max(1, x1), min(W-1, x2)):
                grid[ry][rx] = CELL_FLOOR

    def h_corridor(y, x1, x2):
        for rx in range(min(x1, x2), max(x1, x2)+1):
            if 0 < rx < W-1 and 0 < y < H-1:
                grid[y][rx] = CELL_FLOOR

    def v_corridor(x, y1, y2):
        for ry in range(min(y1, y2), max(y1, y2)+1):
            if 0 < x < W-1 and 0 < ry < H-1:
                grid[ry][x] = CELL_FLOOR

    # ---- Room placement -------------------------------------------------
    target_rooms = 20 + level * 3
    attempts = 0
    while len(rooms) < target_rooms and attempts < target_rooms * 40:
        attempts += 1
        rw = map_rng.randint(4, 11)
        rh = map_rng.randint(4, 11)
        rx = map_rng.randint(2, W - rw - 2)
        ry = map_rng.randint(2, H - rh - 2)
        if any(rx < ox+ow+2 and rx+rw+2 > ox and ry < oy+oh+2 and ry+rh+2 > oy
               for ox, oy, ow, oh in rooms):
            continue
        carve(rx, ry, rx+rw, ry+rh)
        rooms.append((rx, ry, rw, rh))

    if len(rooms) < 4:
        # Degenerate case: recurse with a different seed offset
        return generate_map(rng, level, run_seed + 1)

    # ---- Corridor network (connect ALL rooms in a chain) ----------------
    door_list = []
    corridor_bends = []
    map_rng.shuffle(rooms)
    for i in range(1, len(rooms)):
        ax = rooms[i-1][0] + rooms[i-1][2]//2
        ay = rooms[i-1][1] + rooms[i-1][3]//2
        bx = rooms[i][0]   + rooms[i][2]//2
        by = rooms[i][1]   + rooms[i][3]//2
        if map_rng.random() < 0.5:
            h_corridor(ay, ax, bx)
            v_corridor(bx, ay, by)
            corridor_bends.append((bx, ay))
        else:
            v_corridor(ax, ay, by)
            h_corridor(by, ax, bx)
            corridor_bends.append((ax, by))

    # ---- Interior pillars (decorative obstacles in large rooms) ---------
    for rx, ry, rw, rh in rooms:
        if rw >= 6 and rh >= 6 and map_rng.random() < 0.4:
            px = rx + map_rng.randint(2, rw-2)
            py = ry + map_rng.randint(2, rh-2)
            if 1 < px < W-2 and 1 < py < H-2:
                grid[py][px] = CELL_WALL

    # ---- Extra corridor spurs (organic feel) ----------------------------
    for _ in range(level * 4):
        rx = map_rng.randint(2, W-3)
        ry = map_rng.randint(2, H-3)
        if grid[ry][rx] == CELL_FLOOR:
            d = map_rng.choice([(0,1),(0,-1),(1,0),(-1,0)])
            for step in range(map_rng.randint(2, 5)):
                nx = rx + d[0]*step
                ny = ry + d[1]*step
                if 1 < nx < W-2 and 1 < ny < H-2:
                    grid[ny][nx] = CELL_FLOOR

    # ---- Door placement -------------------------------------------------
    door_candidates = []
    for dy in range(2, H-2):
        for dx in range(2, W-2):
            if grid[dy][dx] != CELL_FLOOR:
                continue
            h_door = (grid[dy-1][dx] == CELL_WALL and grid[dy+1][dx] == CELL_WALL and
                      grid[dy][dx-1] == CELL_FLOOR and grid[dy][dx+1] == CELL_FLOOR)
            v_door = (grid[dy][dx-1] == CELL_WALL and grid[dy][dx+1] == CELL_WALL and
                      grid[dy-1][dx] == CELL_FLOOR and grid[dy+1][dx] == CELL_FLOOR)
            if h_door or v_door:
                door_candidates.append((dx, dy))

    map_rng.shuffle(door_candidates)
    doors_placed = 0
    target_doors = max(6, len(rooms) // 2)
    for (dx, dy) in door_candidates:
        if doors_placed >= target_doors:
            break
        adj_door = any(grid[dy+ddy][dx+ddx] == CELL_DOOR
                       for ddx, ddy in [(0,1),(0,-1),(1,0),(-1,0),(0,2),(0,-2),(2,0),(-2,0)]
                       if 0 <= dx+ddx < W and 0 <= dy+ddy < H)
        if not adj_door:
            grid[dy][dx] = CELL_DOOR
            door_list.append((dy, dx))
            doors_placed += 1

    # ---- Player start + exit room ---------------------------------------
    start_room = rooms[0]
    scx = start_room[0] + start_room[2]//2
    scy = start_room[1] + start_room[3]//2
    end_room = max(rooms[1:], key=lambda r: abs(r[0]+r[2]//2-scx)+abs(r[1]+r[3]//2-scy))

    player_start_tx = start_room[0] + 1
    player_start_ty = start_room[1] + 1
    # Guarantee start tile is floor
    grid[player_start_ty][player_start_tx] = CELL_FLOOR
    player_start = (
        player_start_tx * TILE_SIZE + TILE_SIZE//2,
        player_start_ty * TILE_SIZE + TILE_SIZE//2,
    )

    # ---- Exit door: embed in a wall face inside the end room -----------
    # Try each wall face of the end room until we find one that backs onto a wall
    ex_cx = end_room[0] + end_room[2]//2
    ex_cy = end_room[1] + end_room[3]//2
    placed_exit = False
    for dy_off, dx_off in [(-1,0),(1,0),(0,-1),(0,1)]:
        tx, ty = ex_cx + dx_off, ex_cy + dy_off
        if 1 < tx < W-2 and 1 < ty < H-2 and grid[ty][tx] == CELL_WALL:
            # Check the tile beyond is also wall (so it's a proper wall face)
            beyond_x, beyond_y = tx + dx_off, ty + dy_off
            if 0 < beyond_x < W-1 and 0 < beyond_y < H-1 and grid[beyond_y][beyond_x] == CELL_WALL:
                # Make sure the centre it's adjacent to is floor
                if grid[ex_cy][ex_cx] == CELL_FLOOR:
                    grid[ty][tx] = CELL_EXITDOOR
                    exit_pos = (ty, tx)
                    placed_exit = True
                    break
    if not placed_exit:
        # Fallback: place inside the room centre (always floor)
        grid[ex_cy][ex_cx] = CELL_EXITDOOR
        exit_pos = (ex_cy, ex_cx)

    # ---- Reachability flood-fill ----------------------------------------
    start_flood_tx = player_start_tx
    start_flood_ty = player_start_ty
    reachable = _flood_fill_reachable(grid, W, H, start_flood_tx, start_flood_ty)

    # If exit is not reachable, force a floor corridor to it
    ex_tile_tx, ex_tile_ty = exit_pos[1], exit_pos[0]
    # The exit door tile itself isn't floor, but the adjacent floor cell should be reachable
    exit_adj_reachable = any(
        (ex_tile_tx+dx, ex_tile_ty+dy) in reachable
        for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]
    )
    if not exit_adj_reachable:
        # Carve a direct corridor from start room centre to exit room centre
        mid_x = (scx + end_room[0]+end_room[2]//2) // 2
        h_corridor(scy, scx, mid_x)
        h_corridor(ex_cy, mid_x, end_room[0]+end_room[2]//2)
        v_corridor(mid_x, scy, ex_cy)
        reachable = _flood_fill_reachable(grid, W, H, start_flood_tx, start_flood_ty)

    # ---- Dead-end loot rooms --------------------------------------------
    loot_rooms = []
    loot_rng = random.Random(run_seed * 3333 + level * 77 + 5)
    bend_candidates = list(corridor_bends)
    loot_rng.shuffle(bend_candidates)
    loot_count = 2 + (level // 3)
    placed_loot = 0
    for bx2, by2 in bend_candidates:
        if placed_loot >= loot_count:
            break
        dirs = [(0,1),(0,-1),(1,0),(-1,0)]
        loot_rng.shuffle(dirs)
        for ddx, ddy in dirs:
            lrx = bx2 + ddx * 4
            lry = by2 + ddy * 4
            lrw = loot_rng.randint(3, 5)
            lrh = loot_rng.randint(3, 5)
            # Bounds check with safe border margin
            if lrx < 2 or lrx+lrw > W-2 or lry < 2 or lry+lrh > H-2:
                continue
            overlap = any(grid[ry3][rx3] != CELL_WALL
                          for ry3 in range(lry, lry+lrh)
                          for rx3 in range(lrx, lrx+lrw))
            if overlap:
                continue
            carve(lrx, lry, lrx+lrw, lry+lrh)
            # Short connection corridor
            conn_tx = lrx + lrw//2
            conn_ty = lry + lrh//2
            h_corridor(by2, bx2, conn_tx)
            v_corridor(conn_tx, by2, conn_ty)
            # Verify loot room is reachable from player start
            loot_reachable = _flood_fill_reachable(grid, W, H, start_flood_tx, start_flood_ty)
            if (conn_tx, conn_ty) in loot_reachable:
                loot_rooms.append((conn_tx, conn_ty))
                placed_loot += 1
            else:
                # Undo: fill the room back
                for ry3 in range(lry, lry+lrh):
                    for rx3 in range(lrx, lrx+lrw):
                        grid[ry3][rx3] = CELL_WALL
            break  # try next bend

    # Refresh reachable set after loot rooms
    reachable = _flood_fill_reachable(grid, W, H, start_flood_tx, start_flood_ty)

    # ---- Key/item config ------------------------------------------------
    keycard_color = KEYCARD_COLORS[(level - 1) % len(KEYCARD_COLORS)]
    keys_needed = 2 if (level % 3 != 0) else 3
    key_pos = key_pos2 = key_pos3 = None
    secret_walls = []  # removed feature

    # ---- Wall art positions ---------------------------------------------
    art_positions = []
    art_rng = random.Random(run_seed * 7777 + level * 13 + 11)
    art_candidates = []
    for ry2 in range(1, H-1):
        for rx2 in range(1, W-1):
            if grid[ry2][rx2] == CELL_WALL:
                for ddx, ddy in [(0,1),(0,-1),(1,0),(-1,0)]:
                    nx2, ny2 = rx2+ddx, ry2+ddy
                    if 0 <= nx2 < W and 0 <= ny2 < H and grid[ny2][nx2] == CELL_FLOOR:
                        art_candidates.append((rx2, ry2, ddx, ddy))
                        break
    art_rng.shuffle(art_candidates)
    art_count = min(40, max(10, level * 5))
    art_positions = art_candidates[:art_count]

    return (grid, player_start, exit_pos, key_pos, door_list, W, H, art_positions,
            keycard_color, keys_needed, key_pos2, key_pos3, loot_rooms, secret_walls)


def generate_demo_arena():
    """Hand-crafted demo map: wide open rooms with clear sightlines.

    Layout (each cell = 1 tile, W=H=40):

      All outer border = WALL
      Central hub room: cols 16-23, rows 16-23  (8x8 open)
      North room:       cols 16-23, rows  3-13  (8x10 open)
      South room:       cols 16-23, rows 26-36  (8x10 open)
      East room:        cols 26-36, rows 16-23  (10x8 open)
      West room:        cols  3-13, rows 16-23  (10x8 open)
      Corridors connecting each room to hub are 4 tiles wide -- no narrow squeezes.

    Player spawns in the hub centre facing east.
    Key is placed in the north room (open floor, nowhere to hide).
    Exit door is on the south wall of the south room.
    Enemies are pre-placed at fixed world coords returned alongside the map.
    """
    W, H = 40, 40
    grid = [[CELL_WALL] * W for _ in range(H)]

    def carve(x1, y1, x2, y2):
        for ry in range(y1, y2 + 1):
            for rx in range(x1, x2 + 1):
                if 0 <= rx < W and 0 <= ry < H:
                    grid[ry][rx] = CELL_FLOOR

    # Central hub
    carve(16, 16, 23, 23)

    # North room
    carve(16,  3, 23, 13)
    # North corridor (already open -- rooms share column range)
    carve(17, 13, 22, 16)   # wide 6-tile connector

    # South room
    carve(16, 26, 23, 36)
    # South corridor
    carve(17, 23, 22, 26)

    # East room
    carve(26, 16, 36, 23)
    # East corridor
    carve(23, 17, 26, 22)

    # West room
    carve( 3, 16, 13, 23)
    # West corridor
    carve(13, 17, 16, 22)

    # A few decorative pillars inside rooms for cover variety (not blocking sightlines)
    pillar_spots = [
        (5, 18), (5, 21), (11, 18), (11, 21),   # west room corners
        (28, 18), (28, 21), (34, 18), (34, 21),  # east room corners
        (18,  5), (21,  5), (18, 11), (21, 11),  # north room corners
        (18, 28), (21, 28), (18, 34), (21, 34),  # south room corners
    ]
    for px, py in pillar_spots:
        if 0 < px < W - 1 and 0 < py < H - 1 and grid[py][px] == CELL_FLOOR:
            grid[py][px] = CELL_WALL

    # Exit door on south wall of south room (row 36 is last floor row _ put door at 37)
    exit_tx, exit_ty = 19, 36
    grid[exit_ty][exit_tx] = CELL_EXITDOOR
    exit_pos = (exit_ty, exit_tx)

    # Player spawns in hub centre, facing east
    player_start = (
        19 * TILE_SIZE + TILE_SIZE // 2,
        19 * TILE_SIZE + TILE_SIZE // 2,
    )

    # Key is in north room, centre
    key_pos = (
        19 * TILE_SIZE + TILE_SIZE // 2,
         8 * TILE_SIZE + TILE_SIZE // 2,
    )

    door_list = []
    art_positions = []

    return (grid, player_start, exit_pos, key_pos, door_list, W, H, art_positions,
            'red', 1, None, None, [], [])


def generate_miniboss_arena(rng):
    """Dedicated arena for the Killdozer mini-boss on level 5.
    Open rectangular room with corner pillars and side alcoves.
    Player spawns at south end, Killdozer at north end.
    Exit door is on the NORTH wall -- locked until the boss key is picked up.
    """
    W, H = 50, 50
    grid = [[CELL_WALL] * W for _ in range(H)]

    # Carve main arena floor (leave 2-tile wall border)
    for ry in range(2, H - 2):
        for rx in range(2, W - 2):
            grid[ry][rx] = CELL_FLOOR

    # Corner pillars -- give the player cover
    pillar_spots = [
        (4, 4), (5, 4), (4, 5),
        (44, 4), (45, 4), (45, 5),
        (4, 44), (5, 44), (4, 45),
        (44, 44), (45, 44), (45, 45),
    ]
    for px, py in pillar_spots:
        if 2 < px < W - 2 and 2 < py < H - 2:
            grid[py][px] = CELL_WALL

    # Mid-lane obstacles (two rows of cover blocks)
    for px in range(10, 40, 6):
        grid[20][px] = CELL_WALL
        grid[21][px] = CELL_WALL
        grid[29][px] = CELL_WALL
        grid[30][px] = CELL_WALL

    # Side alcoves carved into the east/west walls for extra ammo/health
    for ry in range(18, 32):
        grid[ry][0] = CELL_FLOOR
        grid[ry][1] = CELL_FLOOR
        grid[ry][W-1] = CELL_FLOOR
        grid[ry][W-2] = CELL_FLOOR

    # Clear centre of arena for Killdozer spawn
    mb_cx, mb_cy = W // 2, H // 2
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            if 0 < mb_cx+dx < W-1 and 0 < mb_cy+dy < H-1:
                grid[mb_cy+dy][mb_cx+dx] = CELL_FLOOR

    # Exit door: mid-north wall -- locked until boss killed + key collected
    exit_tx = W // 2
    exit_ty = 1
    grid[exit_ty][exit_tx] = CELL_EXITDOOR
    exit_pos = (exit_ty, exit_tx)

    # Player spawns at south end, boss at centre
    player_start = (
        (W // 2) * TILE_SIZE + TILE_SIZE // 2,
        (H - 6)  * TILE_SIZE + TILE_SIZE // 2,
    )
    # Dummy key_pos (boss drops the real key at its location)
    key_pos = (mb_cx * TILE_SIZE + TILE_SIZE // 2,
               mb_cy * TILE_SIZE + TILE_SIZE // 2)

    door_list = []
    art_positions = []

    return (grid, player_start, exit_pos, key_pos, door_list, W, H, art_positions,
            'red', 1, None, None, [], [])


def generate_boss_arena(rng):
    W, H = 60, 60
    grid = [[CELL_WALL] * W for _ in range(H)]

    for ry in range(3, H-3):
        for rx in range(3, W-3):
            grid[ry][rx] = CELL_FLOOR

    pillar_positions = [
        (8, 8),  (8, 20),  (8, 40),  (8, 52),
        (20, 8), (20, 52),
        (30, 8), (30, 52),
        (40, 8), (40, 52),
        (52, 8), (52, 20), (52, 40), (52, 52),
        (15, 15), (15, 45),
        (45, 15), (45, 45),
        (20, 30), (40, 30),
        (30, 15), (30, 45),
    ]
    for px, py in pillar_positions:
        if abs(px - 30) <= 5 and abs(py - 30) <= 5:
            continue
        if 3 < px < W - 3 and 3 < py < H - 3:
            grid[py][px] = CELL_WALL
            if px + 1 < W - 3:
                grid[py][px + 1] = CELL_WALL
            if py + 1 < H - 3:
                grid[py + 1][px] = CELL_WALL

    # Centre cleared for Dracula spawn -- always floor
    boss_cx, boss_cy = W // 2, H // 2
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            if 0 < boss_cx+dx < W-1 and 0 < boss_cy+dy < H-1:
                grid[boss_cy+dy][boss_cx+dx] = CELL_FLOOR

    # Player spawns at south end, boss at arena centre
    player_start = (5 * TILE_SIZE + TILE_SIZE // 2, (H-5) * TILE_SIZE + TILE_SIZE // 2)
    boss_spawn   = (boss_cx * TILE_SIZE + TILE_SIZE // 2,
                    boss_cy * TILE_SIZE + TILE_SIZE // 2)

    exit_pos = (3, 30)
    key_pos  = boss_spawn   # boss drops at its own position
    door_list = []
    art_positions = []

    return (grid, player_start, exit_pos, key_pos, door_list, W, H, art_positions,
            'red', 0, None, None, [], [])


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------
class SpriteObject:
    def __init__(self, x, y, img, item_type=None):
        self.x, self.y  = float(x), float(y)
        self.img        = img
        self.alive      = True
        self.item_type  = item_type

    @property
    def is_item(self):
        return self.item_type is not None


class Enemy(SpriteObject):
    def __init__(self, x, y, img, speed, health, damage, is_flying=False):
        super().__init__(x, y, img)
        self.speed           = speed
        self.health          = health
        self.damage          = damage
        self.is_flying       = is_flying
        self.damage_cooldown = 0
        self.path            = []
        self.path_timer      = 0
        self.path_target     = (-1, -1)
        self.state           = 'roam'
        self.detect_range    = TILE_SIZE * 7
        self.roam_timer      = 0
        self.ranged_range    = TILE_SIZE * 6
        self.ranged_cooldown = 0
        self.ranged_projectiles = []
        self.alerted_timer   = 0   # frames of alert flash before chase


class Rotta(Enemy):
    def __init__(self, x, y, img, level):
        hp     = min(6, max(2, 2 + (level - 1)))
        if level > 5:
            hp = int(hp * (1.0 + (level - 5) * 0.3))
        speed  = 4.5 + level * 0.15
        if level > 5:
            speed *= (1.0 + (level - 5) * 0.25)
        damage = 4
        super().__init__(x, y, img, speed, hp, damage, is_flying=False)
        self.is_rotta        = True
        self.zz_timer        = 0
        self.zz_period       = 18
        self.zz_side         = 1
        self.zz_strength     = 2.8


class DraculaBoss(Enemy):
    def __init__(self, x, y, img):
        speed  = 2.5
        health = 350
        damage = 14
        super().__init__(x, y, img, speed, health, damage, is_flying=True)
        self.is_boss            = True
        self.max_health         = 350
        self.detect_range       = TILE_SIZE * 999
        self.state              = 'chase'
        self.summon_timer       = 0
        self.summon_cooldown    = 320
        self.phase              = 1
        self.phase2_entered     = False
        self.teleport_timer     = 0
        self.rage_aura          = 0

        self.invinc_thresholds  = [175]
        self.invinc_heal_target = None
        self.invinc_active      = False
        self.invinc_timer       = 0
        self.INVINC_DURATION    = 280
        self.invinc_pulse       = 0

        self.dash_timer         = 0
        self.dash_cooldown      = 480
        self.is_dashing         = False
        self.dash_duration      = 0
        self.dash_vx            = 0.0
        self.dash_vy            = 0.0
        self.dash_telegraph     = 0   # warning frames before dash

        self.nova_timer         = 0
        self.nova_cooldown      = 600
        self.nova_charge        = 0   # charge-up indicator
        self.nova_projectiles   = []

        # Blood rain: vertical homing projectiles that fall on player position
        self.rain_timer         = 0
        self.rain_cooldown      = 540
        self.rain_active        = False
        self.rain_drops         = []   # falling pillars of damage
        self.rain_warnings      = []   # red circles showing impact zones

        self.strafe_angle       = 0.0


class KilldozerBoss(Enemy):
    """Mini-boss on level 5.  Three attacks + phase 2 at 60 hp."""
    def __init__(self, x, y, img):
        super().__init__(x, y, img, speed=2.2, health=120, damage=14, is_flying=False)
        self.is_boss       = True
        self.is_miniboss   = True
        self.max_health    = 120
        self.detect_range  = TILE_SIZE * 999
        self.state         = 'chase'
        self.phase         = 1
        self.phase2_entered= False
        self.ranged_projectiles = []

        self.damage_cooldown = 0

        self.charge_cooldown  = 240
        self.charge_timer     = 90
        self.charging         = False
        self.charge_vx        = 0.0
        self.charge_vy        = 0.0
        self.charge_tracking  = 0
        self.TRACK_FRAMES     = 50
        self.charge_lock_x    = 0
        self.charge_lock_y    = 0

        self.summon_cooldown  = 420
        self.summon_timer     = 180

        self.blitz_cooldown   = 540
        self.blitz_timer      = 240
        self.blitz_active     = False
        self.blitz_duration   = 0
        self.blitz_shoot_timer= 0

        self.nova_projectiles = []


# ---------------------------------------------------------------------------
# Texture helpers
# ---------------------------------------------------------------------------
def level_wall_palette(level):
    t = max(0.0, min(1.0, (level - 1) / 8.0))
    M = (int(80-60*t),  int(5-5*t),   int(40+10*t))
    A = (int(210-130*t), int(35-35*t), int(110+100*t))
    B = (int(175-120*t), int(20-20*t), int(85+115*t))
    C = (int(230-140*t), int(60-60*t), int(130+90*t))
    return M, A, B, C

def make_brick_texture(size, level=1):
    s = pygame.Surface((size, size))
    MORTAR, A, B, C = level_wall_palette(level)
    rng2 = random.Random(level * 77 + 11)
    rows = 6
    bh = size // rows
    mt = max(1, size // 48)
    s.fill(MORTAR)
    for row in range(rows):
        y0 = row * bh + mt
        h_ = bh - mt
        off = (size // (rows * 2)) if row % 2 else 0
        bw_full = size // 2
        for col in range(-1, rows):
            x0 = col * bw_full + off + mt
            bw = bw_full - mt
            rgb = [A, B, C][(row * 3 + col) % 3]
            pygame.draw.rect(s, rgb, (x0, y0, bw, h_))
            pygame.draw.line(s, tuple(min(255, c + 40) for c in rgb), (x0, y0), (x0 + bw - 1, y0))
            pygame.draw.line(s, tuple(max(0, c - 50) for c in rgb), (x0, y0 + h_ - 1), (x0 + bw - 1, y0 + h_ - 1))
            pygame.draw.line(s, tuple(min(255, c + 20) for c in rgb), (x0, y0), (x0, y0 + h_ - 1))
            for _ in range(rng2.randint(1, 3)):
                nx = x0 + rng2.randint(2, max(3, bw - 2))
                ny = y0 + rng2.randint(2, max(3, h_ - 2))
                dark = tuple(max(0, c - rng2.randint(20, 55)) for c in rgb)
                pygame.draw.line(s, dark, (nx, ny), (nx + rng2.randint(1, 5), ny + rng2.randint(0, 2)), 1)
    return s

def make_miniboss_wall_texture(size):
    """Industrial / rusted steel look for Killdozer arena."""
    s = pygame.Surface((size, size))
    s.fill((30, 18, 5))
    rng2 = random.Random(55)
    panel_h = size // 3
    for row in range(3):
        y0 = row * panel_h
        col = [(50, 30, 10), (40, 25, 8), (60, 35, 12)][row % 3]
        pygame.draw.rect(s, col, (0, y0, size, panel_h - 1))
        # Rivets
        for rx2 in [4, size - 4]:
            pygame.draw.circle(s, (90, 60, 20), (rx2, y0 + panel_h // 2), 3)
            pygame.draw.circle(s, (120, 90, 40), (rx2, y0 + panel_h // 2), 2)
        # Rust streaks
        for _ in range(3):
            sx2 = rng2.randint(4, size - 4)
            pygame.draw.line(s, (100, 40, 10), (sx2, y0), (sx2 + rng2.randint(-3, 3), y0 + panel_h), 1)
    # Warning stripes at bottom
    stripe_y = size - 8
    for i in range(0, size, 8):
        col2 = (220, 160, 0) if (i // 8) % 2 == 0 else (20, 10, 0)
        pygame.draw.rect(s, col2, (i, stripe_y, 8, 8))
    return s

def make_boss_wall_texture(size):
    s = pygame.Surface((size, size))
    MORTAR=(20,0,30); A=(50,0,80); B=(40,0,60); C=(70,10,100)
    bh=size//4; mt=max(1,size//32)
    s.fill(MORTAR)
    for row in range(4):
        y0=row*bh+mt; h_=bh-mt; off=(size//4) if row%2 else 0
        for col in range(-1,4):
            x0=col*(size//2)+off+mt; bw=(size//2)-mt
            rgb=[A,B,C][(row*3+col)%3]
            pygame.draw.rect(s,rgb,(x0,y0,bw,h_))
            pygame.draw.line(s,tuple(min(255,c+25) for c in rgb),(x0,y0),(x0+bw-1,y0))
            pygame.draw.line(s,tuple(max(0,c-30) for c in rgb),(x0,y0+h_-1),(x0+bw-1,y0+h_-1))
    rng2 = random.Random(99)
    for _ in range(6):
        rx = rng2.randint(4, size-8)
        ry = rng2.randint(4, size-8)
        pygame.draw.line(s, (180, 0, 255), (rx, ry), (rx+rng2.randint(2,8), ry+rng2.randint(2,8)), 1)
    return s

def make_door_texture(size):
    s=pygame.Surface((size,size)); s.fill((60,0,80))
    for i in range(1,4): pygame.draw.line(s,(120,80,180),(4,size*i//4),(size-4,size*i//4),2)
    pygame.draw.line(s,(120,80,180),(size//2,4),(size//2,size-4),2)
    pygame.draw.rect(s,(200,160,40),(0,0,size,size),3)
    pygame.draw.circle(s,(220,180,50),(size*3//4,size//2),5)
    pygame.draw.circle(s,(255,220,80),(size*3//4,size//2),3)
    return s

def make_exit_door_texture(size):
    s=pygame.Surface((size,size)); s.fill((0,30,60))
    for i in range(1,4): pygame.draw.line(s,(0,200,220),(4,size*i//4),(size-4,size*i//4),2)
    pygame.draw.line(s,(0,200,220),(size//2,4),(size//2,size-4),2)
    pygame.draw.rect(s,(255,200,0),(0,0,size,size),4)
    cx,cy=size//2,size//2
    for a in range(0,360,60):
        r=math.radians(a)
        pygame.draw.line(s,(255,220,0),(cx,cy),(cx+int(math.cos(r)*10),cy+int(math.sin(r)*10)),2)
    pygame.draw.circle(s,(255,255,150),(cx,cy),5)
    return s

def make_wood_texture(size):
    s=pygame.Surface((size,size)); rng=random.Random(42)
    PC=[(200,120,50),(215,130,45),(190,105,40),(225,140,55)]
    GD=(160,80,25); GL=(240,160,75); ph=size//4
    for p in range(4):
        y0=p*ph; bc=PC[p%4]; pygame.draw.rect(s,bc,(0,y0,size,ph-1))
        for _ in range(rng.randint(6,10)):
            gy=y0+rng.randint(1,ph-2); gc=GD if rng.random()<0.6 else GL
            gx=0
            while gx<size:
                sg=rng.randint(4,12); of=rng.randint(-1,1); x2=min(size-1,gx+sg)
                pygame.draw.line(s,gc,(gx,gy+of),(x2,gy+of)); gx=x2+1
        if rng.random()<0.4:
            kx=rng.randint(size//6,size-size//6); ky=y0+ph//2
            for r in range(5,0,-1):
                pygame.draw.circle(s,(max(0,GD[0]-r*5),max(0,GD[1]-r*3),max(0,GD[2])),(kx,ky),r)
        pygame.draw.line(s,(80,45,15),(0,y0+ph-1),(size,y0+ph-1))
    return s

def make_miniboss_floor_texture(size):
    """Concrete / industrial floor for Killdozer arena."""
    s = pygame.Surface((size, size))
    rng = random.Random(77)
    s.fill((35, 30, 25))
    # Grid lines (tile grout)
    for i in range(0, size, size // 4):
        pygame.draw.line(s, (20, 16, 12), (i, 0), (i, size), 1)
        pygame.draw.line(s, (20, 16, 12), (0, i), (size, i), 1)
    # Scuff marks
    for _ in range(12):
        sx = rng.randint(0, size - 1)
        sy = rng.randint(0, size - 1)
        pygame.draw.line(s, (50, 40, 30), (sx, sy), (sx + rng.randint(-6, 6), sy + rng.randint(-6, 6)), 1)
    return s

def make_boss_floor_texture(size):
    s=pygame.Surface((size,size)); rng=random.Random(13)
    s.fill((15,0,25))
    for _ in range(20):
        fx=rng.randint(0,size-1); fy=rng.randint(0,size-1)
        fw=rng.randint(4,16); fh=rng.randint(2,8)
        pygame.draw.rect(s,(25,0,40),(fx,fy,fw,fh))
    for _ in range(4):
        x1=rng.randint(2,size-2); y1=rng.randint(2,size-2)
        x2=rng.randint(2,size-2); y2=rng.randint(2,size-2)
        pygame.draw.line(s,(60,0,100),(x1,y1),(x2,y2),1)
    return s

def make_ceiling_texture(size, level=1):
    t = max(0.0, min(1.0, (level - 1) / 8.0))
    base_r = int(30 - 10*t); base_g = 0; base_b = int(55 + 55*t)
    s=pygame.Surface((size,size)); rng=random.Random(7); s.fill((base_r, base_g, base_b))
    for _ in range(60):
        sx=rng.randint(0,size-1); sy=rng.randint(0,size-1)
        sw=rng.randint(2,8); sh=rng.randint(1,4); sh2=rng.randint(40,80)
        pygame.draw.rect(s,(int(sh2*(1-t*0.5)),sh2//2,int(sh2+40*t)),(sx,sy,sw,sh))
    return s

def make_miniboss_ceiling_texture(size):
    """Dark industrial ceiling for Killdozer arena."""
    s = pygame.Surface((size, size))
    rng = random.Random(33)
    s.fill((18, 14, 8))
    for _ in range(30):
        sx = rng.randint(0, size - 1)
        sy = rng.randint(0, size - 1)
        sw = rng.randint(4, 14)
        sh = rng.randint(2, 6)
        pygame.draw.rect(s, (28, 22, 12), (sx, sy, sw, sh))
    # Hazard strip hint
    for i in range(0, size, 10):
        col = (60, 44, 0) if (i // 10) % 2 == 0 else (18, 14, 8)
        pygame.draw.rect(s, col, (i, size - 6, 10, 6))
    return s

def make_boss_ceiling_texture(size):
    s=pygame.Surface((size,size)); rng=random.Random(77); s.fill((20,0,10))
    for _ in range(80):
        sx=rng.randint(0,size-1); sy=rng.randint(0,size-1)
        sw=rng.randint(2,10); sh=rng.randint(1,5)
        r=rng.randint(60,120); gg=0; b=rng.randint(30,80)
        pygame.draw.rect(s,(r,gg,b),(sx,sy,sw,sh))
    return s

def make_dracula_img(size):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cape_pts = [(size//2, size//8), (size//8, size*7//8), (size*7//8, size*7//8)]
    pygame.draw.polygon(s, (60, 0, 90), cape_pts)
    pygame.draw.polygon(s, (100, 0, 140), cape_pts, 2)
    pygame.draw.rect(s, (30, 0, 50), (size//3, size//3, size//3, size//2))
    pygame.draw.rect(s, (220, 210, 230), (size//2-6, size//3, 12, size//3))
    pygame.draw.ellipse(s, (200, 180, 200), (size//3, size//8-4, size//3, size//4))
    pygame.draw.circle(s, (255, 0, 0), (size//2-7, size//5), 4)
    pygame.draw.circle(s, (255, 0, 0), (size//2+7, size//5), 4)
    pygame.draw.circle(s, (255, 150, 0), (size//2-7, size//5), 2)
    pygame.draw.circle(s, (255, 150, 0), (size//2+7, size//5), 2)
    pygame.draw.polygon(s, (255,255,255), [(size//2-4,size//4+2),(size//2-6,size//4+8),(size//2-2,size//4+2)])
    pygame.draw.polygon(s, (255,255,255), [(size//2+4,size//4+2),(size//2+6,size//4+8),(size//2+2,size//4+2)])
    pygame.draw.polygon(s, (220,210,230), [(size//3,size//3),(size//2-8,size//3+10),(size//2,size//3)])
    pygame.draw.polygon(s, (220,210,230), [(size*2//3,size//3),(size//2+8,size//3+10),(size//2,size//3)])
    for r in range(6,1,-1):
        a = max(0, 40 - r*6)
        glow = pygame.Surface((size,size), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (150, 0, 255, a), (size//2-r*4, size//2-r*4, r*8, r*8))
        s.blit(glow, (0,0))
    return s

def extract_cols(tex, size):
    cols=[]
    for col in range(size):
        c=pygame.Surface((1,size)); c.blit(tex,(0,0),(col,0,1,size)); cols.append(c)
    return cols


# ---------------------------------------------------------------------------
# DDA raycaster
# ---------------------------------------------------------------------------
def dda_cast(px, py, angle, grid, map_w, map_h, door_states=None):
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    if abs(cos_a) < 1e-9: cos_a = 1e-9
    if abs(sin_a) < 1e-9: sin_a = 1e-9

    mx = int(px / TILE_SIZE)
    my = int(py / TILE_SIZE)

    ddx = abs(TILE_SIZE / cos_a)
    ddy = abs(TILE_SIZE / sin_a)

    if cos_a < 0:
        sx=-1; sdx=(px - mx*TILE_SIZE)/abs(cos_a)
    else:
        sx=1; sdx=((mx+1)*TILE_SIZE - px)/abs(cos_a)
    if sin_a < 0:
        sy=-1; sdy=(py - my*TILE_SIZE)/abs(sin_a)
    else:
        sy=1; sdy=((my+1)*TILE_SIZE - py)/abs(sin_a)

    side=0
    for _ in range(MAX_DEPTH):
        if sdx < sdy:
            sdx+=ddx; mx+=sx; side=0
        else:
            sdy+=ddy; my+=sy; side=1
        if mx<0 or mx>=map_w or my<0 or my>=map_h:
            return MAX_DEPTH*TILE_SIZE, CELL_WALL, 0.0, 0
        cell=grid[my][mx]
        if cell in (CELL_WALL, CELL_DOOR, CELL_EXITDOOR):
            if cell == CELL_DOOR and door_states and door_states.get((my, mx), {}).get('open'):
                continue
            if side==0:
                perp=(mx*TILE_SIZE - px + (1-sx)*TILE_SIZE/2)/cos_a
                wx=(py+perp*sin_a)/TILE_SIZE
            else:
                perp=(my*TILE_SIZE - py + (1-sy)*TILE_SIZE/2)/sin_a
                wx=(px+perp*cos_a)/TILE_SIZE
            wx-=math.floor(wx)
            return perp, cell, wx, side

    return MAX_DEPTH*TILE_SIZE, CELL_WALL, 0.0, 0


# ---------------------------------------------------------------------------
# A* Pathfinder
# ---------------------------------------------------------------------------
def astar(grid, map_w, map_h, sx, sy, gx, gy):
    if (sx, sy) == (gx, gy):
        return []

    def passable(x, y):
        if x < 0 or x >= map_w or y < 0 or y >= map_h:
            return False
        return grid[y][x] == CELL_FLOOR

    def h(x, y):
        return math.hypot(x - gx, y - gy)

    open_heap = []
    heapq.heappush(open_heap, (h(sx, sy), 0, sx, sy))
    came_from = {}
    g_score   = {(sx, sy): 0}
    closed    = set()

    DIRS = [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]
    COSTS = [1.0, 1.0, 1.0, 1.0, 1.414, 1.414, 1.414, 1.414]

    while open_heap:
        f, g, cx, cy = heapq.heappop(open_heap)
        if (cx, cy) in closed:
            continue
        closed.add((cx, cy))
        if (cx, cy) == (gx, gy):
            path = []
            node = (gx, gy)
            while node in came_from:
                path.append(node)
                node = came_from[node]
            path.reverse()
            return path
        for (ddx, ddy), cost in zip(DIRS, COSTS):
            nx, ny = cx + ddx, cy + ddy
            if not passable(nx, ny):
                continue
            if ddx != 0 and ddy != 0:
                if not passable(cx + ddx, cy) or not passable(cx, cy + ddy):
                    continue
            ng = g + cost
            if ng < g_score.get((nx, ny), float('inf')):
                g_score[(nx, ny)] = ng
                came_from[(nx, ny)] = (cx, cy)
                heapq.heappush(open_heap, (ng + h(nx, ny), ng, nx, ny))

    return []


# ---------------------------------------------------------------------------
# UI Helper functions
# ---------------------------------------------------------------------------
def draw_gradient_rect(surf, color1, color2, rect, vertical=True, horizontal=None):
    if horizontal is not None:
        vertical = not horizontal
    x, y, w, h = rect
    has_alpha = len(color1) == 4
    if vertical:
        for i in range(h):
            t = i / max(1, h-1)
            r = int(color1[0] + (color2[0]-color1[0])*t)
            g = int(color1[1] + (color2[1]-color1[1])*t)
            b = int(color1[2] + (color2[2]-color1[2])*t)
            col = (r, g, b, int(color1[3] + (color2[3]-color1[3])*t)) if has_alpha else (r, g, b)
            pygame.draw.line(surf, col, (x,y+i), (x+w,y+i))
    else:
        for i in range(w):
            t = i / max(1, w-1)
            r = int(color1[0] + (color2[0]-color1[0])*t)
            g = int(color1[1] + (color2[1]-color1[1])*t)
            b = int(color1[2] + (color2[2]-color1[2])*t)
            col = (r, g, b, int(color1[3] + (color2[3]-color1[3])*t)) if has_alpha else (r, g, b)
            pygame.draw.line(surf, col, (x+i,y), (x+i,y+h))

def draw_glowing_text(surf, text, font, color, x, y, glow_color=None, glow_radius=3, centered=False):
    if glow_color is None:
        glow_color = tuple(min(255, c//2) for c in color)
    if centered:
        base = font.render(text, True, color)
        x = x - base.get_width()//2
    for dx in range(-glow_radius, glow_radius+1):
        for dy in range(-glow_radius, glow_radius+1):
            if dx == 0 and dy == 0: continue
            dist = math.sqrt(dx*dx + dy*dy)
            if dist > glow_radius: continue
            alpha = int(180 * (1 - dist/glow_radius))
            glow_surf = font.render(text, True, glow_color)
            glow_surf.set_alpha(alpha)
            surf.blit(glow_surf, (x+dx, y+dy))
    txt = font.render(text, True, color)
    surf.blit(txt, (x, y))
    return txt.get_width()

def draw_fancy_bar(surf, x, y, cur, mx, bw, bh, fill_color, bg_color=(30,0,50), label=None, font=None, glow=True):
    r = max(0.0, cur / mx)
    pygame.draw.rect(surf, bg_color, (x-1, y-1, bw+2, bh+2), border_radius=bh//2+1)
    pygame.draw.rect(surf, (bg_color[0]//2, bg_color[1]//2, bg_color[2]//2), (x, y, bw, bh), border_radius=bh//2)
    fw = max(0, int(bw * r))
    if fw > 0:
        bright = tuple(min(255, c+60) for c in fill_color)
        draw_gradient_rect(surf, bright, fill_color, (x, y, fw, bh), horizontal=False if True else True)
        pygame.draw.line(surf, tuple(min(255, c+80) for c in fill_color), (x+2, y+1), (x+fw-2, y+1))
    border_col = tuple(min(255, c+100) for c in fill_color) if glow else COL_WHITE
    pygame.draw.rect(surf, border_col, (x, y, bw, bh), 1, border_radius=bh//2)
    if label and font:
        lbl = font.render(label, True, COL_WHITE)
        surf.blit(lbl, (x + bw//2 - lbl.get_width()//2, y + bh//2 - lbl.get_height()//2))


def format_time(seconds):
    mins = int(seconds) // 60
    secs = int(seconds) % 60
    ms = int((seconds - int(seconds)) * 100)
    return f"{mins:02d}:{secs:02d}.{ms:02d}"


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------
class Game:

    def __init__(self, screen, level=1, prev_score=0, load_data=None,
                 carried_health=None, carried_ammo=None,
                 speedrun_start=None, total_kills=0,
                 sound_volume=0.55, sfx_volume=0.75, sfx_mode='normal',
                 mouse_sensitivity=MOUSE_SENSITIVITY,
                 carried_upgrades=None, carried_tokens=0,
                 run_seed=0, demo_mode=False,
                 screen_shake_enabled=True):
        self.screen     = screen
        self.level      = level
        self.run_seed   = run_seed
        self.clock      = pygame.time.Clock()
        self.is_boss_level     = (level == BOSS_LEVEL)
        self.is_miniboss_level = (level == MINI_BOSS_LEVEL)
        self.screen_shake_enabled = screen_shake_enabled

        self.sound_volume = sound_volume
        self.sfx_volume   = sfx_volume
        self.sfx_mode     = sfx_mode
        self.mouse_sensitivity = mouse_sensitivity
        pygame.mixer.music.set_volume(self.sound_volume)

        self.font        = pygame.font.SysFont('Georgia', 26, bold=True)
        self.big_font    = pygame.font.SysFont('Georgia', 44, bold=True)
        self.small_font  = pygame.font.SysFont('Georgia', 16, bold=True)
        self.tiny_font   = pygame.font.SysFont('Georgia', 13)
        self._hint_text   = ""
        self._hint_frames = 0

        if speedrun_start is None:
            self.speedrun_start = time.time()
        else:
            self.speedrun_start = speedrun_start
        self.speedrun_paused_time = 0.0
        self._pause_start = None

        self.total_kills = total_kills
        self.level_kills = 0
        self.demo_mode   = demo_mode

        # Demo AI state
        self._demo_target_angle  = 0.0
        self._demo_strafe_dir    = 1
        self._demo_strafe_timer  = 0
        self._demo_open_door_cd  = 0

        def load_img(name, fb_col, fb_sz):
            full_path = os.path.join(MEDIA_PATH, name)
            try:
                return pygame.image.load(full_path).convert_alpha()
            except Exception as e:
                s = pygame.Surface((fb_sz, fb_sz), pygame.SRCALPHA)
                s.fill(fb_col)
                return s

        self.v1_img    = load_img('vihu.png',   (255,105,180), 64)
        self.v2_img    = load_img('vihu2.png',   (180, 80,220), 64)
        self.rotta_img = load_img('rotta.png',   (255, 80,  0), 48)
        # Item sprites shrunk 20% from original sizes
        self.box_img   = load_img('ammobox.png', (255,215,  0), 38)   # was 48
        self.hp_img    = load_img('hela.png',    (  0,200, 80), 38)   # was 48
        self.boom_img  = load_img('boom.png',    (255,140,  0), 60)
        # Per-weapon gun images (fallback to ase.png if specific file not found)
        raw_pistol     = load_img('pistol.png',  (147,112,219), 150)
        raw_shotgun    = load_img('shotgun.png', (180, 80, 30), 150)
        raw_smg        = load_img('smg.png',     (60, 180,255), 150)
        self.gun_imgs  = {
            WEAPON_PISTOL:  pygame.transform.scale(raw_pistol,  (380, 300)),
            WEAPON_SHOTGUN: pygame.transform.scale(raw_shotgun, (380, 300)),
            WEAPON_SMG:     pygame.transform.scale(raw_smg,     (380, 300)),
        }
        # Backwards-compat alias -- points to current weapon image
        self.gun_img   = self.gun_imgs[WEAPON_PISTOL]
        raw_dracula = load_img('dracula.png', (120, 0, 200), 128)
        self.dracula_img = pygame.transform.scale(raw_dracula, (128, 128))
        raw_miniboss = load_img('miniboss.png', (180, 80, 0), 96)
        self.miniboss_img = pygame.transform.scale(raw_miniboss, (96, 96))

        raw_token = load_img('token.png', (255, 220, 50), 19)
        self.token_img = pygame.transform.scale(raw_token, (19, 19))   # was 24

        self.trap_img = pygame.Surface((26, 26), pygame.SRCALPHA)      # was 32
        pygame.draw.polygon(self.trap_img, (200, 30, 30, 200), [(13,2),(24,24),(2,24)])
        pygame.draw.polygon(self.trap_img, (255,80,80,120), [(13,6),(21,22),(5,22)])

        raw_station = load_img('station.png', (80, 0, 180), 64)
        self.station_img = pygame.transform.scale(raw_station, (64, 64))
        raw_stationbg = load_img('stationbg.png', (20, 5, 40), 128)
        self.stationbg_img = pygame.transform.scale(raw_stationbg, (WIDTH, HEIGHT))

        self.upgrades = carried_upgrades if carried_upgrades is not None else {
            'damage': 0, 'firerate': 0, 'health': 0,
            'stamina': 0, 'stamina_recovery': 0, 'ammo_cap': 0,
            'armor': 0,        # damage reduction (each level: 5%)
            'ricochet': 0,     # chance bullets penetrate to next enemy
            'lifesteal': 0,    # chance to heal on kill
        }
        self.tokens_held       = carried_tokens
        self.MAX_UPGRADES      = 5
        self.base_shooting_timer = 22
        self.base_damage         = 1

        self.art_imgs = []
        for art_name in ['art1.png', 'art2.png', 'art3.png', 'art4.png', 'art5.png']:
            try:
                art_path = os.path.join(MEDIA_PATH, art_name)
                raw_art = pygame.image.load(art_path).convert_alpha()
                self.art_imgs.append(pygame.transform.scale(raw_art, (128, 128)))
            except Exception:
                placeholder = pygame.Surface((128, 128))
                placeholder.fill([(200,50,150),(50,150,200),(150,200,50)][len(self.art_imgs) % 3])
                self.art_imgs.append(placeholder)

        def make_key_img(color_rgb):
            img = pygame.Surface((40, 40), pygame.SRCALPHA)
            pygame.draw.circle(img, color_rgb, (12, 12), 10, 3)
            pygame.draw.rect(img,   color_rgb, (20, 10, 18, 5))
            pygame.draw.rect(img,   color_rgb, (30, 15,  5, 5))
            return img

        self.key_imgs = {
            'red':   make_key_img((255,  60,  60)),
            'blue':  make_key_img(( 60, 140, 255)),
            'green': make_key_img(( 60, 210, 100)),
        }
        self.key_img = self.key_imgs.get(getattr(self, 'keycard_color', 'red'),
                                         self.key_imgs['red'])

        self.face_frames = []
        for fi, fname in enumerate(['antivihu.png', 'antivihu2.png', 'antivihu3.png',
                                     'antivihu4.png', 'antivihu5.png']):
            raw = load_img(fname, (255, 20, 147), 80)
            self.face_frames.append(pygame.transform.scale(raw, (80, 80)))
        raw_face      = self.face_frames[0]
        self.ui_face  = raw_face

        # Music -- miniboss gets its own track if available, else boss.mp3
        if self.is_miniboss_level:
            music_file = 'miniboss.mp3'
            if not os.path.exists(os.path.join(MEDIA_PATH, music_file)):
                music_file = 'boss.mp3'
        elif self.is_boss_level:
            music_file = 'boss.mp3'
        else:
            music_file = 'music.mp3'
        try:
            pygame.mixer.music.load(os.path.join(MEDIA_PATH, music_file))
            pygame.mixer.music.set_volume(self.sound_volume)
            pygame.mixer.music.play(-1)
        except:
            pass

        def load_sfx(name):
            try:
                sfx = pygame.mixer.Sound(os.path.join(MEDIA_PATH, name))
                sfx.set_volume(self.sfx_volume)
                return sfx
            except Exception as e:
                print(f"Could not load sound '{name}': {e}")
                return None

        self.sfx_shot        = load_sfx('shot.wav')
        self.sfx_deaths      = [s for s in (load_sfx(f'death{i}.wav') for i in range(1, 6)) if s]
        self.sfx_boss_deaths = [s for s in (load_sfx(f'death{i}.wav') for i in range(1, 6)) if s]
        self.sfx_deaths_alt  = [s for s in (load_sfx(f'2-death{("" if i==1 else str(i))}.wav')
                                             for i in range(1, 3)) if s]
        self.sfx_win         = load_sfx('win.wav')
        self.sfx_playerdeath = load_sfx('playerdeath.wav')
        # Per-weapon SFX -- fall back to generic shot.wav if specific file absent
        self.sfx_shot_pistol  = load_sfx('shot_pistol.wav') or self.sfx_shot
        self.sfx_shot_shotgun = load_sfx('shot_shotgun.wav') or self.sfx_shot
        self.sfx_shot_smg     = load_sfx('shot_smg.wav')    or self.sfx_shot

        self._player_death_played = False
        self._win_played          = False

        TEX = 128                      # Higher-res wall textures (was 64)
        self.TEX_SIZE  = TEX
        if self.is_boss_level:
            self.wall_tex = make_boss_wall_texture(TEX)
        elif self.is_miniboss_level:
            self.wall_tex = make_miniboss_wall_texture(TEX)
        else:
            self.wall_tex = make_brick_texture(TEX, level)

        self.door_tex  = make_door_texture(TEX)
        self.exit_tex  = make_exit_door_texture(TEX)

        if self.is_boss_level:
            self.wood_tex = make_boss_floor_texture(256)
            self.ceil_tex = make_boss_ceiling_texture(256)
        elif self.is_miniboss_level:
            self.wood_tex = make_miniboss_floor_texture(256)
            self.ceil_tex = make_miniboss_ceiling_texture(256)
        else:
            self.wood_tex = make_wood_texture(256)
            self.ceil_tex = make_ceiling_texture(256, level)

        self._wall_cols = extract_cols(self.wall_tex, TEX)
        self._door_cols = extract_cols(self.door_tex, TEX)
        self._exit_cols = extract_cols(self.exit_tex, TEX)

        self._art_cols = [extract_cols(img, TEX) for img in self.art_imgs]

        try:
            import numpy as np
            self._np = np
            self._wood_arr = pygame.surfarray.array3d(self.wood_tex)
            self._ceil_arr = pygame.surfarray.array3d(self.ceil_tex)
            self._use_numpy = True
        except ImportError:
            self._use_numpy = False

        self.rng = random.Random(level * 9999 + 42)
        (self.grid, player_start, self.exit_pos,
         _key_pos, door_list, self.MAP_W, self.MAP_H,
         art_positions, self.keycard_color, keys_needed_map,
         _key_pos2, _key_pos3,
         self._loot_room_centers, self._secret_walls) = generate_map(self.rng, level, run_seed)

        # Pre-compute reachable tile set for safe item placement
        start_tx = int(player_start[0] / TILE_SIZE)
        start_ty = int(player_start[1] / TILE_SIZE)
        self._reachable_tiles = _flood_fill_reachable(
            self.grid, self.MAP_W, self.MAP_H, start_tx, start_ty)

        # Track loot room centers (no secret walls)
        self._secret_opened = set()  # kept for save-compat, always empty

        self.wall_art = {}
        if art_positions and self.art_imgs:
            art_rng = random.Random(level * 54321)
            for wx, wy, fdx, fdy in art_positions:
                art_idx = art_rng.randint(0, len(self.art_imgs) - 1)
                self.wall_art[(wx, wy)] = art_idx

        self.door_states = {}
        for ry in range(self.MAP_H):
            for rx in range(self.MAP_W):
                c = self.grid[ry][rx]
                if c in (CELL_DOOR, CELL_EXITDOOR):
                    self.door_states[(ry,rx)] = {
                        'open': False,
                        'timer': 0,
                        'locked': (c == CELL_EXITDOOR)
                    }

        self.px, self.py    = float(player_start[0]), float(player_start[1])
        self.angle          = math.pi * 1.5   # face north (toward Killdozer) on miniboss level
        if not self.is_miniboss_level:
            self.angle      = 0.0
        ammo_cap_lvl = self.upgrades.get('ammo_cap', 0)
        # Base max ammo per weapon; ammo_cap upgrade adds 12% per tier (rounded)
        self.base_max_pistol  = 128
        self.base_max_shotgun = 64
        self.base_max_smg     = 256
        cap_mult = 1.0 + ammo_cap_lvl * 0.12
        self.max_ammo_pistol  = int(self.base_max_pistol  * cap_mult)
        self.max_ammo_shotgun = int(self.base_max_shotgun * cap_mult)
        self.max_ammo_smg     = int(self.base_max_smg     * cap_mult)
        # Legacy single field kept for save-compat; not used in gameplay
        self.max_ammo = self.max_ammo_pistol

        if carried_ammo is not None:
            # carried_ammo is a dict {'pistol':n,'shotgun':n,'smg':n} from level transition
            if isinstance(carried_ammo, dict):
                self.ammo_pistol  = max(0, min(carried_ammo.get('pistol',  0), self.max_ammo_pistol))
                self.ammo_shotgun = max(0, min(carried_ammo.get('shotgun', 0), self.max_ammo_shotgun))
                self.ammo_smg     = max(0, min(carried_ammo.get('smg',     0), self.max_ammo_smg))
            else:
                # Old-format integer (load from save that predates split ammo)
                self.ammo_pistol  = min(int(carried_ammo), self.max_ammo_pistol)
                self.ammo_shotgun = 20
                self.ammo_smg     = 60
        else:
            self.ammo_pistol  = 20
            self.ammo_shotgun = 8
            self.ammo_smg     = 40

        # Convenience helpers: get/set ammo for the active weapon
        # (access via self.ammo_pistol / self.ammo_shotgun / self.ammo_smg directly)

        self.max_health  = 50 + self.upgrades.get('health', 0) * 5
        self.max_stamina = 100.0 + self.upgrades.get('stamina', 0) * 20
        self.stamina     = 100.0

        if carried_health is not None:
            self.health = max(1, min(carried_health, self.max_health))
        else:
            self.health = 50
        self.score       = prev_score
        # On miniboss level: 1 key needed (dropped by Killdozer), no pre-placed keys
        self.keys_needed    = keys_needed_map if not self.is_boss_level and not self.is_miniboss_level else (1 if self.is_miniboss_level else 0)
        self.keys_collected = 0
        self.is_exhausted   = False
        self._trap_slow_timer = 0
        self.show_fps       = False

        if load_data:
            self.level      = load_data.get('level', level)
            self.score      = load_data.get('score', prev_score)
            self.health     = load_data.get('health', self.health)
            self.stamina    = load_data.get('stamina', 100.0)
            self.px         = load_data.get('px', self.px)
            self.py         = load_data.get('py', self.py)
            self.angle      = load_data.get('angle', self.angle)
            self.keys_collected = load_data.get('keys_collected', 0)
            saved_elapsed = load_data.get('speedrun_elapsed', 0.0)
            self.speedrun_start = time.time() - saved_elapsed
            self.total_kills = load_data.get('total_kills', 0)
            saved_upgrades = load_data.get('upgrades', None)
            if saved_upgrades is not None:
                self.upgrades = saved_upgrades
            self.tokens_held = load_data.get('tokens_held', self.tokens_held)
            # Restore per-weapon ammo
            saved_ammo = load_data.get('ammo_split', None)
            if saved_ammo:
                self.ammo_pistol  = max(0, min(saved_ammo.get('pistol',  self.ammo_pistol),  self.max_ammo_pistol))
                self.ammo_shotgun = max(0, min(saved_ammo.get('shotgun', self.ammo_shotgun), self.max_ammo_shotgun))
                self.ammo_smg     = max(0, min(saved_ammo.get('smg',     self.ammo_smg),     self.max_ammo_smg))
            elif 'ammo' in load_data:
                # Legacy single-ammo save
                self.ammo_pistol = max(0, min(int(load_data['ammo']), self.max_ammo_pistol))
            # Restore active weapon
            self.weapon = load_data.get('weapon', WEAPON_PISTOL)
            # Recalculate max ammo with saved upgrades applied
            ammo_cap_lvl2 = self.upgrades.get('ammo_cap', 0)
            cap_mult2 = 1.0 + ammo_cap_lvl2 * 0.12
            self.max_ammo_pistol  = int(self.base_max_pistol  * cap_mult2)
            self.max_ammo_shotgun = int(self.base_max_shotgun * cap_mult2)
            self.max_ammo_smg     = int(self.base_max_smg     * cap_mult2)
            self.max_health  = 50 + self.upgrades.get('health', 0) * 5
            self.max_stamina = 100.0 + self.upgrades.get('stamina', 0) * 20
            # Restore streak state
            self._streak_kills = load_data.get('streak_kills', 0)
            self._streak_timer = load_data.get('streak_timer', 0)
            self._streak_tier  = load_data.get('streak_tier',  0)

        self.shooting_timer = 0
        self.walk_cycle     = 0.0
        self.is_moving      = False
        self.pain_flash     = 0
        self.muzzle_flash   = 0
        self._cam_vel       = 0.0   # smoothed camera angular velocity
        self._cut_cam_x     = None  # smoothed cutscene camera x
        self._cut_cam_y     = None  # smoothed cutscene camera y
        self._cut_cam_a     = None  # smoothed cutscene camera angle
        self.BOOM_DURATION  = 40
        self.explosions     = []
        self.boss_flicker_timer = 0
        self.boss_flicker_alpha = 0
        self.z_buffer       = [float('inf')] * WIDTH
        self.level_complete = False
        self.level_fade     = 0
        self.game_won       = False
        self.boss           = None
        self.miniboss       = None
        self.boss_killed    = False
        self.tick_count     = 0

        # -- Screen shake ------------------------------------------------
        self.shake_timer    = 0
        self.shake_intensity= 0
        self._shake_ox      = 0
        self._shake_oy      = 0

        # -- Weapon system -----------------------------------------------
        self.weapon         = WEAPON_PISTOL
        self._weapon_switch_cd = 0
        self._pending_scroll   = 0

        # -- Kill streak / score multiplier --------------------------------
        self._streak_kills   = 0     # kills in current streak window
        self._streak_timer   = 0     # ticks remaining before window expires
        self._streak_tier    = 0     # current multiplier tier (0 = no streak)
        self._streak_display = 0     # frames to show the banner
        self._streak_msg     = ""
        self._streak_col     = COL_GOLD

        # -- Player knockback state ---------------------------------------
        self._knockback_vx  = 0.0
        self._knockback_vy  = 0.0

        # -- Death screen stats -------------------------------------------
        self._death_floor    = self.level
        self._death_time     = 0.0   # captured when player dies

        self.boss_intro_timer = 840 if self.is_boss_level else (840 if self.is_miniboss_level else 0)
        self.boss_warning_alpha = 0

        self.boss_ammo_respawn_timer = 0
        self.BOSS_AMMO_RESPAWN_INTERVAL = 600

        self.pressure_ticks        = 0
        self.pressure_spawn_timer  = 0
        self.PRESSURE_RAMP_TICKS   = 18000
        self.PRESSURE_INTERVAL_MAX = 600
        self.PRESSURE_INTERVAL_MIN = 20
        self._pressure_warned      = False

        self.mouse_captured = True
        pygame.mouse.set_visible(False)
        pygame.event.set_grab(True)
        pygame.mouse.get_rel()

        self.enemies = []
        self._spawn_initial_enemies()
        self.respawn_queue = []
        self.items = []
        if self.level == DEMO_LEVEL:
            # Key placed by generate_demo_arena; enemies & supplies via _spawn_demo_enemies
            key_spr = self.key_imgs.get(self.keycard_color, self.key_imgs['red'])
            self.items.append(SpriteObject(key_pos[0], key_pos[1], key_spr, ITEM_KEY))
            self._spawn_demo_enemies()
        elif not self.is_boss_level and not self.is_miniboss_level:
            self._spawn_items()
        elif self.is_miniboss_level:
            self._spawn_miniboss_items()
        else:
            # Boss level items
            for p in self._free_floors(5):
                self.items.append(SpriteObject(p[0], p[1], self.box_img, ITEM_AMMO))
            for p in self._free_floors(3):
                self.items.append(SpriteObject(p[0], p[1], self.hp_img, ITEM_HEALTH))

        self.sky_surf = self._make_sky()

        self.ui_pulse = 0.0
        self.damage_numbers = []

    # ------------------------------------------------------------------
    # Miniboss level item spawning -- no pre-placed keys, just supplies
    # ------------------------------------------------------------------
    def _spawn_miniboss_items(self):
        """Spawn ammo boxes and health packs in the Killdozer arena.
        Keys are NOT pre-placed -- the boss drops one on death.
        """
        W, H = self.MAP_W, self.MAP_H

        # Ammo in alcoves on the sides
        for p in self._free_floors(8, min_dist=TILE_SIZE * 3):
            self.items.append(SpriteObject(p[0], p[1], self.box_img, ITEM_AMMO))

        # Health packs spread around arena
        for p in self._free_floors(4, min_dist=TILE_SIZE * 4):
            self.items.append(SpriteObject(p[0], p[1], self.hp_img, ITEM_HEALTH))

    # ------------------------------------------------------------------
    # Timer helpers
    # ------------------------------------------------------------------
    def get_speedrun_elapsed(self):
        if self._pause_start is not None:
            return (self._pause_start - self.speedrun_start) - self.speedrun_paused_time
        return (time.time() - self.speedrun_start) - self.speedrun_paused_time

    def _pause_timer(self):
        self._pause_start = time.time()

    def _resume_timer(self):
        if self._pause_start is not None:
            self.speedrun_paused_time += time.time() - self._pause_start
            self._pause_start = None

    def _release_mouse(self):
        self.mouse_captured = False
        pygame.mouse.set_visible(True)
        pygame.event.set_grab(False)

    def _capture_mouse(self):
        self.mouse_captured = True
        pygame.mouse.set_visible(False)
        pygame.event.set_grab(True)
        pygame.mouse.get_rel()

    def _play_death_sfx(self, is_boss=False):
        if self.sfx_mode == 'alt' and self.sfx_deaths_alt:
            pool = self.sfx_deaths_alt
        elif is_boss:
            pool = self.sfx_boss_deaths
        else:
            pool = self.sfx_deaths
        if pool:
            random.choice(pool).play()

    def _set_sfx_volume(self, vol):
        self.sfx_volume = vol
        all_sfx = (self.sfx_deaths + self.sfx_boss_deaths + self.sfx_deaths_alt +
                   [self.sfx_shot, self.sfx_win, self.sfx_playerdeath])
        for sfx in all_sfx:
            if sfx:
                sfx.set_volume(vol)

    def _make_sky(self):
        s = pygame.Surface((WIDTH, HEIGHT//2))
        if self.is_boss_level:
            for y in range(HEIGHT//2):
                t = y / (HEIGHT//2)
                r = int(120 + t * 30)
                g = 0
                b = int(5 + t * 10)
                pygame.draw.line(s, (r, g, b), (0, y), (WIDTH, y))
            rng2 = random.Random(self.level * 7 + 3)
            for _ in range(80):
                br = rng2.randint(150, 220)
                s.set_at((rng2.randint(0, WIDTH-1), rng2.randint(0, HEIGHT//2-1)), (br, 0, 0))
        elif self.is_miniboss_level:
            # Industrial haze -- yellowish smog
            for y in range(HEIGHT//2):
                t = y / (HEIGHT//2)
                pygame.draw.line(s, (int(40+t*20), int(28+t*12), int(10+t*5)), (0, y), (WIDTH, y))
            rng2 = random.Random(55)
            for _ in range(40):
                br = rng2.randint(100, 160)
                s.set_at((rng2.randint(0, WIDTH-1), rng2.randint(0, HEIGHT//2-1)), (br, br//2, 0))
        else:
            for y in range(HEIGHT//2):
                t = y / (HEIGHT//2)
                pygame.draw.line(s, (int(20+t*55), 0, int(60+t*80)), (0, y), (WIDTH, y))
            rng2 = random.Random(self.level * 7 + 3)
            for _ in range(140):
                br = rng2.randint(180, 255)
                s.set_at((rng2.randint(0, WIDTH-1), rng2.randint(0, HEIGHT//2-1)), (br, br, br))
        return s

    def _free_floors(self, count=1, min_dist=0):
        out = []
        for _ in range(count * 120):
            if len(out) >= count:
                break
            rx = self.rng.randint(1, self.MAP_W-2)
            ry = self.rng.randint(1, self.MAP_H-2)
            if self.grid[ry][rx] == CELL_FLOOR:
                wx = rx * TILE_SIZE + TILE_SIZE // 2
                wy = ry * TILE_SIZE + TILE_SIZE // 2
                if min_dist > 0 and math.hypot(wx - self.px, wy - self.py) < min_dist:
                    continue
                out.append((wx, wy))
        return out

    def _post5_mult(self):
        if self.level <= 5:
            return 1.0
        return 1.0 + (self.level - 5) * 0.3

    def _vihu_health(self, level):
        base = max(1, min(10, 1 + (level - 1)))
        return max(1, int(base * self._post5_mult()))

    def _vihu2_health(self, level):
        base = max(3, min(15, 3 + (level - 1) * 1.5))
        return max(3, int(base * self._post5_mult()))

    def _make_vihu(self, x, y):
        speed = (1.3 + self.level * 0.1) * self._post5_mult()
        return Enemy(x, y, self.v1_img, speed, self._vihu_health(self.level), 3)

    def _make_vihu2(self, x, y):
        speed = (0.9 + self.level * 0.05) * self._post5_mult()
        return Enemy(x, y, self.v2_img, speed, int(self._vihu2_health(self.level)), 6, True)

    def _spawn_demo_enemies(self):
        """Spawn enemies at fixed, hand-picked positions in the demo arena.
        All positions are in the centres of the open rooms -- guaranteed clear
        sightlines from the hub and corridors.
        """
        def world(tx, ty):
            return tx * TILE_SIZE + TILE_SIZE // 2, ty * TILE_SIZE + TILE_SIZE // 2

        # West room -- two ground enemies
        wx1, wy1 = world(7, 19)
        wx2, wy2 = world(10, 20)
        self.enemies.append(self._make_vihu(wx1, wy1))
        self.enemies.append(self._make_vihu(wx2, wy2))

        # East room -- one flier + one ground
        ex1, ey1 = world(30, 19)
        ex2, ey2 = world(33, 20)
        self.enemies.append(self._make_vihu2(ex1, ey1))
        self.enemies.append(self._make_vihu(ex2, ey2))

        # North room -- two enemies guarding the key
        nx1, ny1 = world(19,  6)
        nx2, ny2 = world(21,  9)
        self.enemies.append(self._make_vihu(nx1, ny1))
        self.enemies.append(self._make_vihu2(nx2, ny2))

        # South room -- two enemies between hub and exit
        sx1, sy1 = world(19, 29)
        sx2, sy2 = world(21, 32)
        self.enemies.append(self._make_vihu(sx1, sy1))
        self.enemies.append(self._make_vihu(sx2, sy2))

        # Drop some ammo boxes in each room so the AI never runs dry
        ammo_spots = [
            world(8, 19), world(32, 19),
            world(19,  7), world(19, 30),
            world(19, 19),  # hub centre bonus box
        ]
        for ax, ay in ammo_spots:
            self.items.append(SpriteObject(ax, ay, self.box_img, ITEM_AMMO))

        # Health packs in each room
        hp_spots = [world(6, 21), world(33, 18), world(21, 10), world(21, 33)]
        for hx, hy in hp_spots:
            self.items.append(SpriteObject(hx, hy, self.hp_img, ITEM_HEALTH))

    def _spawn_initial_enemies(self):
        SAFE_DIST = TILE_SIZE * 8
        self.miniboss = None

        if self.level == DEMO_LEVEL:
            # Demo arena uses hand-placed enemies via _spawn_demo_enemies
            # (called after items are set up, at the end of __init__)
            return

        if self.is_miniboss_level:
            # Killdozer spawns at arena centre (cleared of obstacles in generate_miniboss_arena)
            mb_cx = (self.MAP_W // 2) * TILE_SIZE + TILE_SIZE // 2
            mb_cy = (self.MAP_H // 2) * TILE_SIZE + TILE_SIZE // 2
            self.miniboss = KilldozerBoss(mb_cx, mb_cy, self.miniboss_img)
            self.enemies.append(self.miniboss)

            # A few support enemies -- ground only, no fliers, limited count
            for p in self._free_floors(4, min_dist=SAFE_DIST):
                self.enemies.append(self._make_vihu(p[0], p[1]))

            self._hint("KILLDOZER APPROACHES! Kill it to get the key!", 220)

        elif self.is_boss_level:
            # Dracula spawns at arena centre (cleared of obstacles in generate_boss_arena)
            boss_cx = (self.MAP_W // 2) * TILE_SIZE + TILE_SIZE // 2
            boss_cy = (self.MAP_H // 2) * TILE_SIZE + TILE_SIZE // 2
            self.boss = DraculaBoss(boss_cx, boss_cy, self.dracula_img)
            self.enemies.append(self.boss)
            for p in self._free_floors(4, min_dist=SAFE_DIST):
                self.enemies.append(self._make_vihu2(p[0], p[1]))
        else:
            ng = 6 + self.level * 2
            nf = 3 + self.level
            nr = (self.level - 4) * 2 if self.level >= 5 else 0
            total = ng + nf + nr

            # Collect floor tiles, weight by distance from player and other spawn points
            candidates = []
            for ry in range(1, self.MAP_H - 1):
                for rx in range(1, self.MAP_W - 1):
                    if self.grid[ry][rx] == CELL_FLOOR:
                        # Only spawn on reachable tiles
                        if hasattr(self, '_reachable_tiles') and (rx, ry) not in self._reachable_tiles:
                            continue
                        wx = rx * TILE_SIZE + TILE_SIZE // 2
                        wy = ry * TILE_SIZE + TILE_SIZE // 2
                        if math.hypot(wx - self.px, wy - self.py) >= SAFE_DIST:
                            candidates.append((wx, wy))
            self.rng.shuffle(candidates)

            # Greedy spread: pick positions at least N tiles apart
            chosen = []
            min_sep = TILE_SIZE * 4
            for wx, wy in candidates:
                if len(chosen) >= total:
                    break
                if all(math.hypot(wx-ox, wy-oy) >= min_sep for ox, oy in chosen):
                    chosen.append((wx, wy))
            # Top up with anything remaining if spread didn't fit them all
            while len(chosen) < total and candidates:
                wx, wy = candidates[len(chosen) % len(candidates)]
                chosen.append((wx, wy))

            for p in chosen[:ng]:
                self.enemies.append(self._make_vihu(p[0], p[1]))
            for p in chosen[ng:ng+nf]:
                self.enemies.append(self._make_vihu2(p[0], p[1]))
            for p in chosen[ng+nf:ng+nf+nr]:
                self.enemies.append(Rotta(p[0], p[1], self.rotta_img, self.level))

    def _spawn_items(self):
        """Spawn all items, seeded per run+level, only on reachable floor tiles."""
        seed = self.run_seed * 1000 + self.level
        item_rng = random.Random(seed)

        def spread_floors(count, min_dist_tiles=6, min_player_dist_tiles=5,
                          must_be_reachable=True):
            """Pick up to `count` reachable floor tiles spread at least
            min_dist_tiles apart and at least min_player_dist_tiles from player."""
            candidates = []
            for ry in range(1, self.MAP_H - 1):
                for rx in range(1, self.MAP_W - 1):
                    if self.grid[ry][rx] != CELL_FLOOR:
                        continue
                    if must_be_reachable and (rx, ry) not in self._reachable_tiles:
                        continue
                    wx = rx * TILE_SIZE + TILE_SIZE // 2
                    wy = ry * TILE_SIZE + TILE_SIZE // 2
                    if math.hypot(wx - self.px, wy - self.py) > min_player_dist_tiles * TILE_SIZE:
                        candidates.append((wx, wy))
            item_rng.shuffle(candidates)
            chosen = []
            for wx, wy in candidates:
                if len(chosen) >= count:
                    break
                too_close = any(math.hypot(wx-ox, wy-oy) < min_dist_tiles * TILE_SIZE
                                for ox, oy in chosen)
                if not too_close:
                    chosen.append((wx, wy))
            return chosen

        # ---- Ammo boxes ------------------------------------------------
        for wx, wy in spread_floors(10 + self.level, min_dist_tiles=5, min_player_dist_tiles=4):
            self.items.append(SpriteObject(wx, wy, self.box_img, ITEM_AMMO))

        # ---- Health packs ----------------------------------------------
        for wx, wy in spread_floors(6, min_dist_tiles=7, min_player_dist_tiles=4):
            self.items.append(SpriteObject(wx, wy, self.hp_img, ITEM_HEALTH))

        # ---- Keys ------------------------------------------------------
        # Keys placed far from player and spread from each other
        key_spr = self.key_imgs.get(self.keycard_color, self.key_imgs['red'])
        if self.keys_needed > 0:
            key_spots = spread_floors(self.keys_needed,
                                      min_dist_tiles=12, min_player_dist_tiles=10)
            # Fallback: relax distance constraints if map is small
            if len(key_spots) < self.keys_needed:
                key_spots = spread_floors(self.keys_needed,
                                          min_dist_tiles=6, min_player_dist_tiles=5)
            for wx, wy in key_spots:
                self.items.append(SpriteObject(wx, wy, key_spr, ITEM_KEY))

        # ---- Tokens ----------------------------------------------------
        # Token budget designed so a player who finds most tokens can buy
        # most upgrades.  9 upgrades, tiered costs: 1+1+2+2+3 = 9 per slot
        # total possible spend ~81 tokens for full kit.  We give 50-60 across
        # a full run so a focused player gets the upgrades they care about.
        #
        # Level  tokens  cumulative
        #   1      5        5
        #   2      5       10
        #   3      6       16   (upgrade station here)
        #   4      6       22
        #   6      7       29   (upgrade station here)
        #   7      7       36
        #   8      8       44
        #   9      8       52   (upgrade station here)
        # Plus loot rooms add 1-2 each, secrets add 1 each -> ~60 total
        token_counts = {1: 5, 2: 5, 3: 6, 4: 6, 6: 7, 7: 7, 8: 8, 9: 8}
        tc = token_counts.get(self.level, 0)
        if tc > 0:
            for wx, wy in spread_floors(tc, min_dist_tiles=6, min_player_dist_tiles=5):
                self.items.append(SpriteObject(wx, wy, self.token_img, ITEM_TOKEN))

        # ---- Traps -----------------------------------------------------
        trap_count = item_rng.randint(4, 8)
        for wx, wy in spread_floors(trap_count, min_dist_tiles=4, min_player_dist_tiles=4):
            self.items.append(SpriteObject(wx, wy, self.trap_img, ITEM_TRAP))

        # ---- Upgrade station on levels 3, 6, 9 -------------------------
        if self.level in (3, 6, 9):
            spots = spread_floors(1, min_dist_tiles=8, min_player_dist_tiles=6)
            if spots:
                wx, wy = spots[0]
                self.items.append(SpriteObject(wx, wy, self.station_img, 'upgrade_station'))

        # ---- Dead-end loot rooms ----------------------------------------
        # Validate each centre is on a reachable floor tile before placing
        for lx, ly in self._loot_room_centers:
            if not (1 <= lx < self.MAP_W-1 and 1 <= ly < self.MAP_H-1):
                continue
            if self.grid[ly][lx] != CELL_FLOOR:
                continue
            if (lx, ly) not in self._reachable_tiles:
                continue
            wx2 = lx * TILE_SIZE + TILE_SIZE // 2
            wy2 = ly * TILE_SIZE + TILE_SIZE // 2
            self.items.append(SpriteObject(wx2, wy2, self.hp_img, ITEM_HEALTH))
            self.items.append(SpriteObject(wx2 + TILE_SIZE, wy2, self.box_img, ITEM_AMMO))
            # Always drop a token in loot rooms (guaranteed reward for exploration)
            self.items.append(SpriteObject(wx2, wy2 + TILE_SIZE, self.token_img, ITEM_TOKEN))

    # ------------------------------------------------------------------
    # Collision
    # ------------------------------------------------------------------
    def _blocked(self, rx, ry):
        if rx < 0 or rx >= self.MAP_W or ry < 0 or ry >= self.MAP_H:
            return True
        c = self.grid[ry][rx]
        if c == CELL_WALL:
            return True
        if c in (CELL_DOOR, CELL_EXITDOOR):
            return not self.door_states.get((ry, rx), {}).get('open', False)
        return False

    def _move(self, dx, dy):
        M = 14
        nx, ny = self.px + dx, self.py + dy
        bx = False
        for my in [int((self.py-M)/TILE_SIZE), int((self.py+M)/TILE_SIZE)]:
            if self._blocked(int((nx + (M if dx > 0 else -M))/TILE_SIZE), my):
                bx = True
        if not bx:
            self.px = nx
        by = False
        for mx2 in [int((self.px-M)/TILE_SIZE), int((self.px+M)/TILE_SIZE)]:
            if self._blocked(mx2, int((ny + (M if dy > 0 else -M))/TILE_SIZE)):
                by = True
        if not by:
            self.py = ny

    # ------------------------------------------------------------------
    # Doors
    # ------------------------------------------------------------------
    def _try_open_door(self):
        for d in range(1, int(TILE_SIZE * 1.6)):
            tx = int((self.px + math.cos(self.angle)*d) / TILE_SIZE)
            ty = int((self.py + math.sin(self.angle)*d) / TILE_SIZE)
            if 0 <= ty < self.MAP_H and 0 <= tx < self.MAP_W:
                c = self.grid[ty][tx]
                if c in (CELL_DOOR, CELL_EXITDOOR):
                    st = self.door_states[(ty, tx)]
                    if st['locked'] and self.keys_collected < self.keys_needed:
                        col_name = self.keycard_color.upper()
                        if self.is_miniboss_level:
                            self._hint("Kill KILLDOZER first to get the key!", 120)
                        elif self.keys_needed > 1:
                            self._hint(f"Need {self.keys_needed} {col_name} keycards! ({self.keys_collected}/{self.keys_needed})", 120)
                        else:
                            self._hint(f"Need the {col_name} keycard!", 120)
                        return
                    if not st['open']:
                        st['open'] = True
                        st['timer'] = 0 if st['locked'] else 400
                        if st['locked']:
                            self.level_complete = True
                    return

    def update_doors(self):
        for st in self.door_states.values():
            if st['open'] and st['timer'] > 0:
                st['timer'] -= 1
                if st['timer'] <= 0:
                    st['open'] = False

    def _hint(self, text, frames=90):
        self._hint_text  = text
        self._hint_frames = frames

    # ------------------------------------------------------------------
    # Killdozer mini-boss AI
    # ------------------------------------------------------------------
    def update_miniboss(self):
        if not self.miniboss or not self.miniboss.alive:
            return
        mb = self.miniboss

        # Phase 2 at 60hp
        if mb.health <= 60 and not mb.phase2_entered:
            mb.phase2_entered = True
            mb.phase          = 2
            mb.speed          = 4.0
            mb.damage         = 22
            mb.charge_cooldown  = 160
            mb.summon_cooldown  = 250
            mb.blitz_cooldown   = 340
            self._hint("KILLDOZER PHASE 2 - IT'S ENRAGED!", 200)

        dist_to_player = math.hypot(self.px - mb.x, self.py - mb.y)
        if dist_to_player < 48 and mb.damage_cooldown == 0:
            self.health = max(0, self.health - mb.damage)
            mb.damage_cooldown = 50
            self.pain_flash = 20

        if mb.damage_cooldown > 0:
            mb.damage_cooldown -= 1

        # --- ATTACK 1: Charge ---
        if mb.charging:
            nx = mb.x + mb.charge_vx
            ny = mb.y + mb.charge_vy
            tx = int(nx / TILE_SIZE)
            ty = int(ny / TILE_SIZE)
            hit_wall = self._blocked(tx, int(mb.y / TILE_SIZE)) or self._blocked(int(mb.x / TILE_SIZE), ty)
            if hit_wall:
                mb.charging = False
                mb.charge_tracking = 0
                count = 12
                for i in range(count):
                    a = (2 * math.pi * i) / count
                    mb.nova_projectiles.append({
                        'x': mb.x, 'y': mb.y,
                        'vx': math.cos(a) * 5.0, 'vy': math.sin(a) * 5.0,
                        'life': 100
                    })
                mb.charge_timer = mb.charge_cooldown
            else:
                mb.x = nx
                mb.y = ny
                if dist_to_player < 52 and mb.damage_cooldown == 0:
                    self.health = max(0, self.health - mb.damage + 6)
                    mb.damage_cooldown = 60
                    self.pain_flash = 25
                    mb.charging = False
                    mb.charge_tracking = 0
                    mb.charge_timer = mb.charge_cooldown
        else:
            mb.charge_timer -= 1
            if mb.charge_timer <= 0:
                if mb.charge_tracking < mb.TRACK_FRAMES:
                    mb.charge_tracking += 1
                    # Continuously update locked aim point during tracking (red beam)
                    mb.charge_lock_x = self.px
                    mb.charge_lock_y = self.py
                    if mb.charge_tracking == 1:
                        self._hint("KILLDOZER IS WINDING UP!", 60)
                else:
                    # Commit to locked target -- player can dodge during track phase
                    dx = mb.charge_lock_x - mb.x
                    dy = mb.charge_lock_y - mb.y
                    d  = math.hypot(dx, dy) or 1
                    spd = 18.0 if mb.phase == 2 else 13.0
                    mb.charge_vx = (dx / d) * spd
                    mb.charge_vy = (dy / d) * spd
                    mb.charging  = True
                    mb.charge_tracking = 0

        # --- ATTACK 2: Summon ---
        mb.summon_timer -= 1
        if mb.summon_timer <= 0:
            mb.summon_timer = mb.summon_cooldown
            count = 2
            spawned = 0
            for _ in range(60):
                if spawned >= count:
                    break
                pos = self._free_floors(1, min_dist=TILE_SIZE * 3)
                if pos:
                    self.enemies.append(self._make_vihu(pos[0][0], pos[0][1]))
                    spawned += 1
            self._hint("KILLDOZER CALLED FOR BACKUP!", 90)

        # --- ATTACK 3: Blitz ---
        if mb.blitz_active:
            mb.blitz_duration -= 1
            dx = self.px - mb.x
            dy = self.py - mb.y
            d  = math.hypot(dx, dy) or 1
            spd = 9.0 if mb.phase == 2 else 6.5
            ORBIT_DIST = TILE_SIZE * 4  # keep this far from the player while orbiting

            if d > ORBIT_DIST:
                # Move toward orbit radius
                move_x = (dx / d) * spd
                move_y = (dy / d) * spd
            else:
                # Orbit: perpendicular movement around the player
                # Alternate orbit direction every blitz using blitz_duration parity
                perp_x = -dy / d
                perp_y =  dx / d
                orbit_dir = 1 if (mb.blitz_duration // 60) % 2 == 0 else -1
                move_x = perp_x * spd * orbit_dir
                move_y = perp_y * spd * orbit_dir

            nx = mb.x + move_x
            ny = mb.y + move_y
            tx = int(nx / TILE_SIZE)
            ty = int(ny / TILE_SIZE)
            if not self._blocked(tx, int(mb.y / TILE_SIZE)):
                mb.x = nx
            if not self._blocked(int(mb.x / TILE_SIZE), ty):
                mb.y = ny
            mb.blitz_shoot_timer -= 1
            if mb.blitz_shoot_timer <= 0:
                mb.blitz_shoot_timer = 15 if mb.phase == 2 else 25
                angle = math.atan2(self.py - mb.y, self.px - mb.x)
                spread = 0.2
                for off in [-spread, 0, spread]:
                    a = angle + off
                    mb.nova_projectiles.append({
                        'x': mb.x, 'y': mb.y,
                        'vx': math.cos(a) * 5.5, 'vy': math.sin(a) * 5.5,
                        'life': 80
                    })
            if mb.blitz_duration <= 0:
                mb.blitz_active = False
                mb.blitz_timer  = mb.blitz_cooldown
        else:
            mb.blitz_timer -= 1
            if mb.blitz_timer <= 0:
                mb.blitz_active   = True
                mb.blitz_duration = 240 if mb.phase == 2 else 180
                mb.blitz_shoot_timer = 0
                self._hint("KILLDOZER IS SPEEDING UP!", 80)

        # Normal chase
        if not mb.charging and not mb.blitz_active:
            dx = self.px - mb.x
            dy = self.py - mb.y
            d  = math.hypot(dx, dy) or 1
            nx = mb.x + (dx / d) * mb.speed
            ny = mb.y + (dy / d) * mb.speed
            tx = int(nx / TILE_SIZE)
            ty = int(ny / TILE_SIZE)
            if not self._blocked(tx, int(mb.y / TILE_SIZE)):
                mb.x = nx
            if not self._blocked(int(mb.x / TILE_SIZE), ty):
                mb.y = ny

        # Update nova_projectiles
        still = []
        for p in mb.nova_projectiles:
            p['x'] += p['vx']; p['y'] += p['vy']; p['life'] -= 1
            tx2 = int(p['x'] / TILE_SIZE); ty2 = int(p['y'] / TILE_SIZE)
            if not (0 < tx2 < self.MAP_W and 0 < ty2 < self.MAP_H):
                continue
            if self.grid[ty2][tx2] == CELL_WALL:
                continue
            if math.hypot(self.px - p['x'], self.py - p['y']) < 24:
                self.health = max(0, self.health - 8)
                self.pain_flash = 15
                continue
            if p['life'] > 0:
                still.append(p)
        mb.nova_projectiles = still

    # ------------------------------------------------------------------
    # Boss AI (Dracula)
    # ------------------------------------------------------------------
    def update_boss(self):
        if not self.boss or not self.boss.alive:
            return

        boss = self.boss
        boss.rage_aura = (boss.rage_aura + 3) % 360

        if boss.health <= boss.max_health // 2 and not boss.phase2_entered:
            boss.phase2_entered = True
            boss.phase = 2
            boss.speed = 2.5
            boss.damage = 14
            boss.summon_cooldown = 280
            boss.dash_cooldown   = 420
            boss.nova_cooldown   = 540

        if not boss.invinc_active and boss.invinc_thresholds:
            next_thresh = boss.invinc_thresholds[-1]
            if boss.health <= next_thresh:
                boss.invinc_thresholds.pop()
                boss.invinc_active = True
                boss.invinc_timer  = boss.INVINC_DURATION
                boss.health        = next_thresh
                self._hint("DRACULA IS INVINCIBLE!", 180)
                self._summon_rotta_wave()

        if boss.invinc_active:
            boss.invinc_timer -= 1
            boss.invinc_pulse  = (boss.invinc_pulse + 1) % 20
            if boss.invinc_timer <= 0:
                boss.invinc_active = False
                self._hint("DRACULA IS VULNERABLE AGAIN!", 120)

        boss.summon_timer += 1
        if boss.summon_timer >= boss.summon_cooldown:
            boss.summon_timer = 0
            self._summon_dracula_minions()

        # --- Dash (with telegraph warning) ---
        if boss.is_dashing:
            boss.x += boss.dash_vx
            boss.y += boss.dash_vy
            boss.dash_duration -= 1
            dist = math.hypot(self.px - boss.x, self.py - boss.y)
            if dist < 50 and boss.damage_cooldown == 0:
                self.health = max(0, self.health - boss.damage + 4)
                boss.damage_cooldown = 60
                self.pain_flash = 25
            if boss.dash_duration <= 0:
                boss.is_dashing = False
        elif boss.dash_telegraph > 0:
            # Telegraph phase: boss winds up, warning shown in draw_sprites
            boss.dash_telegraph -= 1
            if boss.dash_telegraph == 0:
                # Commit the dash
                dx = self.px - boss.x
                dy = self.py - boss.y
                d  = math.hypot(dx, dy) or 1
                spd = 10.0 if boss.phase == 2 else 7.0
                boss.dash_vx = (dx / d) * spd
                boss.dash_vy = (dy / d) * spd
                boss.is_dashing   = True
                boss.dash_duration = 18
        else:
            boss.dash_timer += 1
            if boss.dash_timer >= boss.dash_cooldown:
                boss.dash_timer = 0
                boss.dash_telegraph = 30   # 0.5s warning before dash fires

        # --- Nova (with charge-up glow) ---
        boss.nova_timer += 1
        # Charge-up visual in the 60 frames before nova fires
        if boss.nova_timer >= boss.nova_cooldown - 60:
            boss.nova_charge = min(60, boss.nova_timer - (boss.nova_cooldown - 60))
        else:
            boss.nova_charge = 0

        if boss.nova_timer >= boss.nova_cooldown:
            boss.nova_timer = 0
            boss.nova_charge = 0
            count = 8 if boss.phase == 1 else 12
            for i in range(count):
                a = (2 * math.pi * i) / count
                spd = 3.5
                boss.nova_projectiles.append({
                    'x': boss.x, 'y': boss.y,
                    'vx': math.cos(a) * spd, 'vy': math.sin(a) * spd,
                    'life': 120
                })

        # --- Blood Rain: telegraphed impact zones, then damage pillars ---
        boss.rain_timer += 1
        if boss.rain_timer >= boss.rain_cooldown and not boss.rain_active:
            boss.rain_timer = 0
            boss.rain_active = True
            # Cast warning circles at player + scatter spots
            spots = [(self.px, self.py)]
            for _ in range(3 if boss.phase == 2 else 2):
                ox = self.px + self.rng.uniform(-TILE_SIZE * 2.5, TILE_SIZE * 2.5)
                oy = self.py + self.rng.uniform(-TILE_SIZE * 2.5, TILE_SIZE * 2.5)
                spots.append((ox, oy))
            boss.rain_warnings = [
                {'x': sx, 'y': sy, 'life': 60, 'max_life': 60}
                for sx, sy in spots
            ]
            boss.rain_drops = []

        if boss.rain_active:
            # Count down warnings; when they expire convert to active drops
            still_warnings = []
            for w in boss.rain_warnings:
                w['life'] -= 1
                if w['life'] <= 0:
                    # Warning expired _ spawn the impact drop
                    boss.rain_drops.append({'x': w['x'], 'y': w['y'], 'life': 40})
                else:
                    still_warnings.append(w)
            boss.rain_warnings = still_warnings

            # Process active drops (damage player if nearby)
            still_drops = []
            for dr in boss.rain_drops:
                dr['life'] -= 1
                if math.hypot(self.px - dr['x'], self.py - dr['y']) < 42:
                    if boss.damage_cooldown == 0:
                        dmg = 10 if boss.phase == 1 else 14
                        self.health = max(0, self.health - dmg)
                        boss.damage_cooldown = 30
                        self.pain_flash = 22
                if dr['life'] > 0:
                    still_drops.append(dr)
            boss.rain_drops = still_drops

            # Rain cycle ends when both lists are empty
            if not boss.rain_warnings and not boss.rain_drops:
                boss.rain_active = False

        still = []
        for p in boss.nova_projectiles:
            p['x']    += p['vx']
            p['y']    += p['vy']
            p['life'] -= 1
            tx = int(p['x'] / TILE_SIZE)
            ty = int(p['y'] / TILE_SIZE)
            if not (0 < tx < self.MAP_W and 0 < ty < self.MAP_H):
                continue
            if self.grid[ty][tx] == CELL_WALL:
                p['vx'] *= -1; p['vy'] *= -1
                p['x'] += p['vx'] * 2; p['y'] += p['vy'] * 2
            if math.hypot(self.px - p['x'], self.py - p['y']) < 28:
                self.health = max(0, self.health - 6)
                self.pain_flash = 18
                continue
            if p['life'] > 0:
                still.append(p)
        boss.nova_projectiles = still

        if boss.phase == 2 and not boss.is_dashing:
            boss.strafe_angle += 0.018
            orbit_r = TILE_SIZE * 4
            target_x = self.px + math.cos(boss.strafe_angle) * orbit_r
            target_y = self.py + math.sin(boss.strafe_angle) * orbit_r
            ddx = target_x - boss.x
            ddy = target_y - boss.y
            d2  = math.hypot(ddx, ddy) or 1
            boss.x += (ddx / d2) * boss.speed
            boss.y += (ddy / d2) * boss.speed

        if boss.phase == 2:
            boss.teleport_timer += 1
            if boss.teleport_timer >= 600:
                boss.teleport_timer = 0
                for _ in range(20):
                    angle = self.rng.random() * math.pi * 2
                    dist  = TILE_SIZE * self.rng.uniform(4, 7)
                    tx = self.px + math.cos(angle) * dist
                    ty = self.py + math.sin(angle) * dist
                    ttx = int(tx / TILE_SIZE)
                    tty = int(ty / TILE_SIZE)
                    if 0 < ttx < self.MAP_W and 0 < tty < self.MAP_H and self.grid[tty][ttx] == CELL_FLOOR:
                        boss.x = tx
                        boss.y = ty
                        self.pain_flash = 4
                        break

        self.boss_ammo_respawn_timer += 1
        if self.boss_ammo_respawn_timer >= self.BOSS_AMMO_RESPAWN_INTERVAL:
            self.boss_ammo_respawn_timer = 0
            pos = self._free_floors(1)
            if pos:
                self.items.append(SpriteObject(pos[0][0], pos[0][1], self.box_img, ITEM_AMMO))
    def _summon_rotta_wave(self):
        spawned  = 0
        attempts = 0
        while spawned < 3 and attempts < 100:
            attempts += 1
            rx = self.rng.randint(3, self.MAP_W - 4)
            ry = self.rng.randint(3, self.MAP_H - 4)
            if self.grid[ry][rx] == CELL_FLOOR:
                wx = rx * TILE_SIZE + TILE_SIZE // 2
                wy = ry * TILE_SIZE + TILE_SIZE // 2
                self.enemies.append(Rotta(wx, wy, self.rotta_img, 10))
                spawned += 1

    def _summon_dracula_minions(self):
        count = 1 if self.boss.phase == 1 else 2
        for _ in range(count):
            angle = self.rng.random() * math.pi * 2
            dist  = TILE_SIZE * self.rng.uniform(1.5, 3)
            mx = self.boss.x + math.cos(angle) * dist
            my = self.boss.y + math.sin(angle) * dist
            tmx = int(mx / TILE_SIZE)
            tmy = int(my / TILE_SIZE)
            if 0 < tmx < self.MAP_W and 0 < tmy < self.MAP_H and self.grid[tmy][tmx] == CELL_FLOOR:
                self.enemies.append(Enemy(mx, my, self.v1_img, 2.0, 1, 5))
        self.explosions.append({'x': self.boss.x, 'y': self.boss.y, 'timer': self.BOOM_DURATION})

    # ------------------------------------------------------------------
    # Enemies
    # ------------------------------------------------------------------
    def _get_move_dir(self, e):
        etx = int(e.x / TILE_SIZE)
        ety = int(e.y / TILE_SIZE)
        ptx = int(self.px / TILE_SIZE)
        pty = int(self.py / TILE_SIZE)

        if e.state == 'chase':
            target_tx, target_ty = ptx, pty
        else:
            e.roam_timer -= 1
            if e.roam_timer <= 0 or e.path_target == (etx, ety) or not e.path:
                found = False
                for _ in range(10):
                    rx = etx + self.rng.randint(-5, 5)
                    ry = ety + self.rng.randint(-5, 5)
                    if 0 < rx < self.MAP_W and 0 < ry < self.MAP_H and self.grid[ry][rx] == CELL_FLOOR:
                        e.path_target = (rx, ry)
                        e.roam_timer = self.rng.randint(90, 180)
                        found = True
                        break
                if not found:
                    e.path_target = (etx, ety)
            target_tx, target_ty = e.path_target

        e.path_timer -= 1
        if e.path_timer <= 0 or (e.state == 'chase' and e.path_target != (ptx, pty)
                                  and e.path_timer <= 0):
            if e.state == 'chase':
                e.path_timer  = 60 + int(self.rng.random() * 20)   # slower replan = smoother
            else:
                e.path_timer  = 90
            e.path_target = (target_tx, target_ty)
            e.path = astar(self.grid, self.MAP_W, self.MAP_H, etx, ety, target_tx, target_ty)

        if e.path:
            while e.path:
                wx, wy = e.path[0]
                wc_x = wx * TILE_SIZE + TILE_SIZE // 2
                wc_y = wy * TILE_SIZE + TILE_SIZE // 2
                if math.hypot(e.x - wc_x, e.y - wc_y) < TILE_SIZE * 0.6:
                    e.path.pop(0)
                else:
                    break
            if e.path:
                wx, wy = e.path[0]
                tx = wx * TILE_SIZE + TILE_SIZE // 2
                ty = wy * TILE_SIZE + TILE_SIZE // 2
            else:
                if e.state == 'chase':
                    tx, ty = self.px, self.py
                else:
                    return 0.0, 0.0
        else:
            if e.state == 'chase':
                tx, ty = self.px, self.py
            else:
                return 0.0, 0.0

        ddx = tx - e.x
        ddy = ty - e.y
        d   = math.hypot(ddx, ddy)
        if d < 1:
            return 0.0, 0.0
        return ddx / d, ddy / d

    def move_enemies(self):
        for e in self.enemies:
            if not e.alive:
                continue
            # Skip miniboss -- handled by update_miniboss()
            if getattr(e, 'is_miniboss', False):
                continue

            dx   = self.px - e.x
            dy   = self.py - e.y
            dist = math.hypot(dx, dy)

            # Alert state: pause briefly, flash exclamation, then engage
            if dist < e.detect_range and e.state == 'roam' and e.alerted_timer == 0:
                e.alerted_timer = ENEMY_ALERT_FRAMES
            if e.alerted_timer > 0:
                e.alerted_timer -= 1
                if e.alerted_timer == 0:
                    e.state = 'chase'
                continue   # stand still during alert window

            if dist < e.detect_range:
                e.state = 'chase'

            if e.damage_cooldown > 0:
                e.damage_cooldown -= 1

            is_vihu2 = e.is_flying and not getattr(e, 'is_boss', False) and not isinstance(e, Rotta)
            if is_vihu2 and e.state == 'chase':
                if e.ranged_cooldown > 0:
                    e.ranged_cooldown -= 1
                if dist < e.ranged_range:
                    if e.ranged_cooldown == 0:
                        e.ranged_cooldown = 120
                        angle_to_player = math.atan2(dy, dx)
                        e.ranged_projectiles.append({
                            'x': e.x, 'y': e.y,
                            'vx': math.cos(angle_to_player) * 9.0,
                            'vy': math.sin(angle_to_player) * 9.0,
                            'life': 90
                        })
                    continue

            contact_range = 35 if not getattr(e, 'is_boss', False) else 55
            if dist <= contact_range and e.damage_cooldown == 0:
                armor_lvl  = self.upgrades.get('armor', 0)
                raw_dmg    = e.damage
                reduced    = max(1, int(raw_dmg * (1.0 - armor_lvl * 0.05)))
                self.health        = max(0, self.health - reduced)
                e.damage_cooldown  = 60
                self.pain_flash    = 20
                self._shake(8, 12)
                # Knockback: push player away from enemy
                if dist > 0.1:
                    kb = 6.0
                    self._knockback_vx -= (dx / dist) * kb
                    self._knockback_vy -= (dy / dist) * kb
                if self.health <= 0:
                    self._death_floor = self.level
                    self._death_time  = self.get_speedrun_elapsed()

            if dist > contact_range:
                if getattr(e, 'is_boss', False):
                    if dist > 1:
                        e.x += (dx / dist) * e.speed
                        e.y += (dy / dist) * e.speed
                    continue

                dir_x, dir_y = self._get_move_dir(e)
                speed_mod = 0.5 if e.state == 'roam' else 1.0

                if isinstance(e, Rotta):
                    e.zz_timer += 1
                    if e.zz_timer >= e.zz_period:
                        e.zz_timer  = 0
                        e.zz_side  *= -1
                        e.zz_period = 14 + int(self.rng.random() * 10)
                    perp_x = -dir_y * e.zz_strength * e.zz_side
                    perp_y =  dir_x * e.zz_strength * e.zz_side
                    vx = (dir_x * e.speed + perp_x) * speed_mod
                    vy = (dir_y * e.speed + perp_y) * speed_mod
                else:
                    vx = dir_x * e.speed * speed_mod
                    vy = dir_y * e.speed * speed_mod

                nx = int(e.x / TILE_SIZE)
                ny = int(e.y / TILE_SIZE)
                if not self._blocked(int((e.x + vx) / TILE_SIZE), ny): e.x += vx
                if not self._blocked(nx, int((e.y + vy) / TILE_SIZE)): e.y += vy

        for e in self.enemies:
            if not e.alive or not hasattr(e, 'ranged_projectiles'):
                continue
            still = []
            for p in e.ranged_projectiles:
                p['x'] += p['vx']; p['y'] += p['vy']; p['life'] -= 1
                tx = int(p['x'] / TILE_SIZE); ty = int(p['y'] / TILE_SIZE)
                if not (0 < tx < self.MAP_W and 0 < ty < self.MAP_H):
                    continue
                if self.grid[ty][tx] == CELL_WALL:
                    continue
                if math.hypot(self.px - p['x'], self.py - p['y']) < 22:
                    armor_lvl = self.upgrades.get('armor', 0)
                    raw_pdmg  = e.damage // 2
                    self.health = max(0, self.health - max(1, int(raw_pdmg * (1.0 - armor_lvl * 0.05))))
                    self.pain_flash = 12
                    self._shake(5, 8)
                    # Knockback from projectile direction
                    plen = math.hypot(p['vx'], p['vy']) or 1
                    self._knockback_vx += (p['vx'] / plen) * 4.0
                    self._knockback_vy += (p['vy'] / plen) * 4.0
                    if self.health <= 0:
                        self._death_floor = self.level
                        self._death_time  = self.get_speedrun_elapsed()
                    continue
                if p['life'] > 0:
                    still.append(p)
            e.ranged_projectiles = still

    def update_respawns(self):
        if self.is_boss_level or self.is_miniboss_level:
            return
        still = []
        for (t, etype) in self.respawn_queue:
            t -= 1
            if t <= 0:
                pos = self._free_floors(1)
                if pos and math.hypot(pos[0][0]-self.px, pos[0][1]-self.py) > TILE_SIZE*5:
                    p = pos[0]
                    if etype == 'fly':
                        self.enemies.append(self._make_vihu2(p[0], p[1]))
                    elif etype == 'rotta' and self.level >= 5:
                        self.enemies.append(Rotta(p[0], p[1], self.rotta_img, self.level))
                    else:
                        self.enemies.append(self._make_vihu(p[0], p[1]))
                    continue
            still.append((t, etype))
        self.respawn_queue = still

    def update_pressure_spawner(self):
        if self.is_boss_level or self.is_miniboss_level:
            return

        self.pressure_ticks += 1

        if not self._pressure_warned and self.pressure_ticks >= 10800:
            self._pressure_warned = True
            self._hint("The horde is closing in... GET OUT!", 180)

        t = min(1.0, self.pressure_ticks / self.PRESSURE_RAMP_TICKS)
        interval = int(self.PRESSURE_INTERVAL_MAX +
                       (self.PRESSURE_INTERVAL_MIN - self.PRESSURE_INTERVAL_MAX) * t)

        self.pressure_spawn_timer -= 1
        if self.pressure_spawn_timer <= 0:
            self.pressure_spawn_timer = interval

            pos = self._free_floors(1)
            if pos and math.hypot(pos[0][0] - self.px, pos[0][1] - self.py) > TILE_SIZE * 6:
                p = pos[0]
                roll = self.rng.random()
                fly_chance   = min(0.4, 0.1 + self.level * 0.03)
                rotta_chance = min(0.3, max(0.0, (self.level - 4) * 0.06))
                if roll < rotta_chance and self.level >= 5:
                    self.enemies.append(Rotta(p[0], p[1], self.rotta_img, self.level))
                elif roll < rotta_chance + fly_chance:
                    self.enemies.append(self._make_vihu2(p[0], p[1]))
                else:
                    self.enemies.append(self._make_vihu(p[0], p[1]))

    # ------------------------------------------------------------------
    # Upgrade station menu
    # ------------------------------------------------------------------
    def _show_upgrade_menu(self):
        if self.tokens_held <= 0:
            self._hint("No tokens! Find upgrade tokens in the levels.", 150)
            return
        pygame.mouse.set_visible(True)
        pygame.event.set_grab(False)

        # Station on level 3 caps upgrades at level 3; others allow full 5
        station_cap = 3 if self.level == 3 else self.MAX_UPGRADES

        # (key, label, color, cost_per_level) -- cost scales: tier 1-2 cost 1, tier 3-4 cost 2, tier 5 cost 3
        def upgrade_cost(cur):
            if cur < 2: return 1
            if cur < 4: return 2
            return 3

        options = [
            ('damage',           'Damage x2 per tier',      (255, 120,  50)),
            ('firerate',         'Fire Rate +1',            (255, 220,  50)),
            ('health',           'Max Health +5',           ( 80, 220, 100)),
            ('stamina',          'Max Stamina +20',         ( 80, 180, 255)),
            ('stamina_recovery', 'Stamina Recovery',        (180, 100, 255)),
            ('ammo_cap',         'Max Ammo +12% all',       (255, 180,  60)),
            ('armor',            'Armor +5% Resist',        (120, 200, 255)),
            ('ricochet',         'Ricochet Shot Chance',    (255,  80, 200)),
            ('lifesteal',        'Lifesteal on Kill',       (  0, 255, 120)),
        ]

        COLS = 3
        ROWS = 3
        BTN_W, BTN_H = 270, 58
        GAP = 8
        grid_w = COLS * BTN_W + (COLS - 1) * GAP
        grid_h = ROWS * BTN_H + (ROWS - 1) * GAP
        grid_x = WIDTH//2 - grid_w//2
        grid_y = HEIGHT//2 - grid_h//2 + 20

        btn_rects = []
        for i in range(len(options)):
            col_i = i % COLS
            row_i = i // COLS
            btn_rects.append(pygame.Rect(
                grid_x + col_i * (BTN_W + GAP),
                grid_y + row_i * (BTN_H + GAP),
                BTN_W, BTN_H
            ))
        close_btn = pygame.Rect(WIDTH//2 - 80, grid_y + grid_h + 16, 160, 40)
        clock = pygame.time.Clock()

        while True:
            self.screen.blit(self.stationbg_img, (0, 0))
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            self.screen.blit(overlay, (0, 0))

            title = self.font.render("UPGRADE STATION", True, (200, 100, 255))
            self.screen.blit(title, title.get_rect(center=(WIDTH//2, grid_y - 48)))

            if station_cap < self.MAX_UPGRADES:
                cap_txt = self.small_font.render(f"Station cap: Tier {station_cap}", True, (255, 180, 60))
                self.screen.blit(cap_txt, cap_txt.get_rect(center=(WIDTH//2, grid_y - 24)))

            tok_bg = pygame.Surface((200, 32), pygame.SRCALPHA)
            tok_bg.fill((60, 40, 0, 200))
            self.screen.blit(tok_bg, tok_bg.get_rect(center=(WIDTH//2, grid_y - 68)))
            tok = self.font.render(f"Tokens: {self.tokens_held}", True, (255, 220, 50))
            self.screen.blit(tok, tok.get_rect(center=(WIDTH//2, grid_y - 68)))

            mx, my = pygame.mouse.get_pos()
            for i, (key, label, col) in enumerate(options):
                r = btn_rects[i]
                cur = self.upgrades.get(key, 0)
                cost = upgrade_cost(cur)
                maxed = cur >= station_cap
                can_afford = self.tokens_held >= cost and not maxed
                hov = r.collidepoint(mx, my) and can_afford
                bg = (60, 10, 80) if not maxed else (22, 22, 22)
                if hov: bg = (95, 18, 120)
                pygame.draw.rect(self.screen, bg, r, border_radius=8)
                pygame.draw.rect(self.screen, col if not maxed else (60,60,60), r, 2, border_radius=8)

                # Label
                if cur >= self.MAX_UPGRADES:
                    status = "MAX"
                elif cur >= station_cap:
                    status = f"Capped ({cur}/{station_cap})"
                else:
                    status = f"Tier {cur}/{station_cap}  [{cost} token{'s' if cost>1 else ''}]"
                name_t  = self.small_font.render(label, True, col if not maxed else (80,80,80))
                stat_t  = self.tiny_font.render(status, True, (200,200,200) if not maxed else (60,60,60))
                self.screen.blit(name_t, name_t.get_rect(midleft=(r.x+10, r.centery - 10)))
                self.screen.blit(stat_t, stat_t.get_rect(midleft=(r.x+10, r.centery + 10)))

                # Pip bar showing current level
                for pip in range(self.MAX_UPGRADES):
                    px2 = r.right - 14 - pip * 12
                    py2 = r.centery
                    pip_col = col if pip < cur else (40, 20, 50)
                    pygame.draw.circle(self.screen, pip_col, (px2, py2), 4)

            ch = close_btn.collidepoint(mx, my)
            pygame.draw.rect(self.screen, (70,5,35) if not ch else (110,12,55), close_btn, border_radius=8)
            pygame.draw.rect(self.screen, (200,50,100), close_btn, 2, border_radius=8)
            ct = self.small_font.render("Close  [Esc]", True, (255,255,255))
            self.screen.blit(ct, ct.get_rect(center=close_btn.center))

            pygame.display.flip()
            clock.tick(60)

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit(); import sys; sys.exit()
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    self._capture_mouse(); return
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if close_btn.collidepoint(mx, my):
                        self._capture_mouse(); return
                    for i, (key, label, col) in enumerate(options):
                        if btn_rects[i].collidepoint(mx, my):
                            cur = self.upgrades.get(key, 0)
                            cost = upgrade_cost(cur)
                            if cur < station_cap and self.tokens_held >= cost:
                                self.upgrades[key] = cur + 1
                                self.tokens_held -= cost
                                if key == 'health':
                                    self.max_health += 5
                                    self.health = min(self.health + 5, self.max_health)
                                elif key == 'stamina':
                                    self.max_stamina += 20
                                    self.stamina = min(self.stamina + 20, self.max_stamina)
                                elif key == 'ammo_cap':
                                    cap_mult3 = 1.0 + self.upgrades['ammo_cap'] * 0.12
                                    self.max_ammo_pistol  = int(self.base_max_pistol  * cap_mult3)
                                    self.max_ammo_shotgun = int(self.base_max_shotgun * cap_mult3)
                                    self.max_ammo_smg     = int(self.base_max_smg     * cap_mult3)
                                self._hint(f"Upgraded: {label}!", 120)
                                if self.tokens_held <= 0:
                                    self._capture_mouse(); return

    # ------------------------------------------------------------------
    # Pickups
    # ------------------------------------------------------------------
    def check_pickups(self):
        for item in self.items[:]:
            dist = math.hypot(self.px - item.x, self.py - item.y)
            if item.item_type == ITEM_TRAP:
                if dist < 28 and not getattr(self, '_trap_slow_timer', 0) > 0:
                    self._trap_slow_timer = 180
                    self._hint("TRAP! Slowed!", 60)
                continue
            if dist < 48:
                if item.item_type == ITEM_AMMO:
                    # Give ammo to all weapons proportionally; skip if all full
                    p_gain = min(8,  self.max_ammo_pistol  - self.ammo_pistol)
                    s_gain = min(4,  self.max_ammo_shotgun - self.ammo_shotgun)
                    m_gain = min(16, self.max_ammo_smg     - self.ammo_smg)
                    if p_gain <= 0 and s_gain <= 0 and m_gain <= 0:
                        continue
                    self.ammo_pistol  = min(self.max_ammo_pistol,  self.ammo_pistol  + 8)
                    self.ammo_shotgun = min(self.max_ammo_shotgun, self.ammo_shotgun + 4)
                    self.ammo_smg     = min(self.max_ammo_smg,     self.ammo_smg     + 16)
                    self.damage_numbers.append([int(item.x), int(item.y), "+AMMO", COL_GOLD, 60])
                elif item.item_type == ITEM_HEALTH:
                    if self.health >= self.max_health:
                        continue  # already at full health
                    gained = min(25, self.max_health - self.health)
                    self.health = min(self.max_health, self.health + 25)
                    self.damage_numbers.append([int(item.x), int(item.y), f"+{gained} HP", COL_GREEN, 60])
                elif item.item_type == ITEM_KEY:
                    self.keys_collected = min(self.keys_needed, self.keys_collected + 1)
                    col_name = self.keycard_color.upper()
                    if self.is_miniboss_level:
                        self._hint("KEY COLLECTED! Find the exit - north wall!", 220)
                    elif self.keys_collected < self.keys_needed:
                        remaining = self.keys_needed - self.keys_collected
                        self._hint(f"{col_name} KEYCARD {self.keys_collected}/{self.keys_needed}! Find {remaining} more!", 200)
                    else:
                        self._hint(f"ALL {col_name} KEYCARDS COLLECTED! Find the exit!", 200)
                elif item.item_type == ITEM_TOKEN:
                    self.tokens_held += 1
                    self.damage_numbers.append([int(item.x), int(item.y), "+1 TOKEN", (255,220,50), 90])
                    self._hint(f"Upgrade token! ({self.tokens_held} held)  Use at upgrade station.", 150)
                elif item.item_type == 'upgrade_station':
                    self._show_upgrade_menu()
                    continue
                else:
                    continue
                self.items.remove(item)

    # ------------------------------------------------------------------
    # Draw floor + ceiling
    # ------------------------------------------------------------------
    def draw_floor_and_ceiling(self):
        hh  = HEIGHT // 2
        tw  = self.wood_tex.get_width()
        th  = self.wood_tex.get_height()
        cw  = self.ceil_tex.get_width()
        ch  = self.ceil_tex.get_height()
        rlx = math.cos(self.angle - HALF_FOV)
        rly = math.sin(self.angle - HALF_FOV)
        rrx = math.cos(self.angle + HALF_FOV)
        rry = math.sin(self.angle + HALF_FOV)

        if self._use_numpy:
            np  = self._np
            wa  = self._wood_arr
            ca  = self._ceil_arr
            fs  = pygame.Surface((WIDTH, hh))
            cs  = pygame.Surface((WIDTH, hh))
            fp  = pygame.surfarray.pixels3d(fs)
            cp  = pygame.surfarray.pixels3d(cs)
            ci  = np.arange(WIDTH)
            for y in range(hh):
                p  = y + 1
                rd = (HEIGHT * 0.5 * TILE_SIZE) / p
                sx = rd * (rrx - rlx) / WIDTH
                sy = rd * (rry - rly) / WIDTH
                fx = (np.floor(self.px + rd*rlx + sx*ci)).astype(int) % tw
                fy = (np.floor(self.py + rd*rly + sy*ci)).astype(int) % th
                fx = np.where(fx < 0, fx + tw, fx)
                fy = np.where(fy < 0, fy + th, fy)
                sh  = max(20, min(255, int(210 * TILE_SIZE / (rd + 1))))
                cs2 = max(10, min(180, int(160 * TILE_SIZE / (rd + 1))))
                fp[:, y, :] = wa[fx, fy] * sh // 255
                gx = fx % cw
                gy = fy % ch
                cp[:, hh-1-y, :] = ca[gx, gy] * cs2 // 255
            del fp, cp
            self.screen.blit(cs, (0, 0))
            self.screen.blit(fs, (0, hh))
        else:
            self.screen.blit(self.sky_surf, (0, 0))
            pygame.draw.rect(self.screen, (100,60,25), (0, hh, WIDTH, hh))

    # ------------------------------------------------------------------
    # Cast rays (DDA)
    # ------------------------------------------------------------------
    def cast_rays(self):
        # NUM_RAYS == WIDTH so sw == 1: one ray per pixel column = maximum sharpness
        self.z_buffer = []
        sw   = max(1, WIDTH // NUM_RAYS)
        tick = pygame.time.get_ticks()

        # Fog parameters tuned for wider FOV and longer draw distance
        FOG_START = TILE_SIZE * 3
        FOG_END   = MAX_DEPTH * TILE_SIZE
        if self.is_boss_level:
            fog_rgb = (40, 0, 15)
        elif self.is_miniboss_level:
            fog_rgb = (20, 14, 8)
        else:
            fog_rgb = (8, 0, 18)

        for ray in range(NUM_RAYS):
            ra = (self.angle - HALF_FOV) + ray * (FOV / NUM_RAYS)
            dist, cell, wx, side = dda_cast(self.px, self.py, ra, self.grid, self.MAP_W, self.MAP_H, self.door_states)

            for i in range(sw):
                if ray * sw + i < WIDTH:
                    self.z_buffer.append(dist)

            wall_h = int((TILE_SIZE * HEIGHT * 1.9) / (dist + 0.1))
            wt     = (HEIGHT // 2) - (wall_h // 2)

            # Directional shading: N/S walls slightly darker than E/W
            ss = 0.58 if side == 0 else 1.0
            atten = max(0.04, ss / (1.0 + dist * 0.0012))
            fog_t = max(0.0, min(1.0, (dist - FOG_START) / max(1, FOG_END - FOG_START)))
            sv = int(atten * 255 * (1.0 - fog_t * 0.88))
            sv = max(10, min(255, sv))

            tc = int(wx * self.TEX_SIZE) % self.TEX_SIZE

            cos_a = math.cos(ra)
            sin_a = math.sin(ra)
            if abs(cos_a) < 1e-9: cos_a = 1e-9
            if abs(sin_a) < 1e-9: sin_a = 1e-9
            hit_mx = int((self.px + cos_a * dist) / TILE_SIZE)
            hit_my = int((self.py + sin_a * dist) / TILE_SIZE)
            hit_mx = max(0, min(self.MAP_W - 1, hit_mx))
            hit_my = max(0, min(self.MAP_H - 1, hit_my))

            if cell == CELL_DOOR:
                door_st = self.door_states.get((hit_my, hit_mx), {})
                if door_st.get('open'):
                    continue
                cols = self._door_cols
            elif cell == CELL_EXITDOOR:
                pulse = int(abs(math.sin(tick * 0.003)) * 60)
                sv    = min(255, sv + pulse)
                cols  = self._exit_cols
            elif cell == CELL_WALL and (hit_mx, hit_my) in self.wall_art:
                art_idx = self.wall_art[(hit_mx, hit_my)]
                cols = self._art_cols[art_idx]
            else:
                cols = self._wall_cols

            if wall_h > 0 and 0 <= tc < len(cols):
                col = pygame.transform.scale(cols[tc], (sw + 1, max(1, wall_h)))
                sh = pygame.Surface(col.get_size())
                sh.fill((sv, sv, sv))
                col.blit(sh, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
                if fog_t > 0.05:
                    fv = int(fog_t * 55)
                    fg = pygame.Surface(col.get_size())
                    fg.fill((min(255, fog_rgb[0] + fv),
                              min(255, fog_rgb[1] + fv // 3),
                              min(255, fog_rgb[2] + fv // 2)))
                    fg.set_alpha(int(fog_t * 140))
                    col.blit(fg, (0, 0))
                self.screen.blit(col, (ray * sw, wt))

        while len(self.z_buffer) < WIDTH:
            self.z_buffer.append(float('inf'))

    # ------------------------------------------------------------------
    # Draw sprites
    # ------------------------------------------------------------------
    def draw_sprites(self):
        live = [e for e in self.enemies if e.alive] + list(self.items)
        self.explosions = [b for b in self.explosions if b['timer'] > 0]
        for b in self.explosions:
            b['timer'] -= 1

        R = []
        for s in live:
            dx = s.x - self.px
            dy = s.y - self.py
            euclid = math.hypot(dx, dy)
            # Perpendicular (corrected) distance -- matches z_buffer values from cast_rays
            perp = dx * math.cos(self.angle) + dy * math.sin(self.angle)
            perp = max(0.1, perp)
            R.append((euclid, perp, 's', s))
        for b in self.explosions:
            dx = b['x'] - self.px
            dy = b['y'] - self.py
            euclid = math.hypot(dx, dy)
            perp = dx * math.cos(self.angle) + dy * math.sin(self.angle)
            perp = max(0.1, perp)
            R.append((euclid, perp, 'b', b))
        R.sort(key=lambda r: (-r[0], id(r[3])))

        if not hasattr(self, '_sprite_cache'):
            self._sprite_cache = {}

        def get_scaled(img, size):
            key = (id(img), size)
            if key not in self._sprite_cache:
                self._sprite_cache[key] = pygame.transform.scale(img, (size, size))
                # Keep cache from growing unbounded
                if len(self._sprite_cache) > 512:
                    self._sprite_cache.pop(next(iter(self._sprite_cache)))
            return self._sprite_cache[key]

        def z_visible(xp, sz, dist):
            cx_s = max(0, min(WIDTH - 1, xp + sz // 2))
            return self.z_buffer[cx_s] > dist

        def draw_sprite_clipped(img, xp, yd, sz2, dist, alpha=255):
            """Fast sprite rendering with per-column z-clipping using numpy."""
            if sz2 < 1:
                return
            scaled = get_scaled(img, max(1, sz2))
            sw = scaled.get_width()
            sh = scaled.get_height()

            # Screen X range clipped to viewport
            x0 = max(0, xp)
            x1 = min(WIDTH, xp + sw)
            if x0 >= x1:
                return

            # Build a boolean mask of which columns pass the z-buffer
            screen_cols = range(x0, x1)
            sprite_cols_start = x0 - xp

            # Find contiguous visible runs and blit them as rectangles
            run_start = None
            for i, sx in enumerate(screen_cols):
                visible = self.z_buffer[sx] > dist
                if visible and run_start is None:
                    run_start = i
                elif not visible and run_start is not None:
                    # Blit the run
                    src_x = sprite_cols_start + run_start
                    run_w = i - run_start
                    src_rect = pygame.Rect(src_x, 0, run_w, sh)
                    dst = (x0 + run_start, yd)
                    if alpha < 255:
                        strip = scaled.subsurface(src_rect).copy()
                        strip.set_alpha(alpha)
                        self.screen.blit(strip, dst)
                    else:
                        self.screen.blit(scaled, dst, src_rect)
                    run_start = None
            # Flush final run
            if run_start is not None:
                src_x = sprite_cols_start + run_start
                run_w = len(screen_cols) - run_start
                src_rect = pygame.Rect(src_x, 0, run_w, sh)
                dst = (x0 + run_start, yd)
                if alpha < 255:
                    strip = scaled.subsurface(src_rect).copy()
                    strip.set_alpha(alpha)
                    self.screen.blit(strip, dst)
                else:
                    self.screen.blit(scaled, dst, src_rect)

        for euclid, perp, kind, obj in R:
            ox = obj.x if kind == 's' else obj['x']
            oy = obj.y if kind == 's' else obj['y']
            gamma = math.atan2(oy - self.py, ox - self.px) - self.angle
            while gamma >  math.pi: gamma -= 2*math.pi
            while gamma < -math.pi: gamma += 2*math.pi
            if not (-HALF_FOV < gamma < HALF_FOV):
                continue

            sz  = int((TILE_SIZE * HEIGHT * 1.9) / (perp + 0.1))
            sz  = min(sz, 3500)

            xp  = int((gamma + HALF_FOV) / FOV * WIDTH - sz//2)
            yp  = (HEIGHT // 2) - sz//2
            dist = perp

            if kind == 'b':
                al = int(255 * (obj['timer'] / self.BOOM_DURATION))
                draw_sprite_clipped(self.boom_img, xp, yp, max(1, sz), dist, alpha=al)
            else:
                s   = obj
                yd  = yp
                sz2 = sz
                is_boss_sprite = getattr(s, 'is_boss', False)
                if is_boss_sprite:
                    yd  -= sz // 3
                    sz2  = int(sz * 1.2)
                    if sz2 > 5 and z_visible(xp, sz2, dist):
                        if getattr(s, 'is_miniboss', False):
                            aura_pulse = abs(math.sin(self.tick_count * 0.08)) * 0.3 + 0.7
                            aura_sz = int(sz2 * 1.3 * aura_pulse)
                            aura = pygame.Surface((aura_sz, aura_sz), pygame.SRCALPHA)
                            col = (255, 100, 0, 40) if s.phase == 1 else (255, 50, 50, 55)
                            pygame.draw.ellipse(aura, col, (0, 0, aura_sz, aura_sz))
                            self.screen.blit(aura, (xp + sz2//2 - aura_sz//2, yd + sz2//2 - aura_sz//2))
                        elif self.boss and self.boss.invinc_active:
                            shield_col = (255, 215, 0, 80 + int(abs(math.sin(self.boss.invinc_pulse * 0.3)) * 100))
                            shield_sz  = int(sz2 * 1.5)
                            shield     = pygame.Surface((shield_sz, shield_sz), pygame.SRCALPHA)
                            pygame.draw.ellipse(shield, shield_col, (0, 0, shield_sz, shield_sz))
                            self.screen.blit(shield, (xp + sz2//2 - shield_sz//2, yd + sz2//2 - shield_sz//2))
                        else:
                            aura_pulse = abs(math.sin(math.radians(self.boss.rage_aura))) * 0.3 + 0.7
                            aura_sz = int(sz2 * 1.4 * aura_pulse)
                            aura = pygame.Surface((aura_sz, aura_sz), pygame.SRCALPHA)
                            color = (200, 50, 255, 30) if s.phase == 1 else (255, 50, 50, 40)
                            pygame.draw.ellipse(aura, color, (0, 0, aura_sz, aura_sz))
                            self.screen.blit(aura, (xp + sz2//2 - aura_sz//2, yd + sz2//2 - aura_sz//2))
                elif isinstance(s, Enemy) and s.is_flying:
                    yd -= sz // 2
                elif isinstance(s, Rotta):
                    sz2  = int(sz * 0.45)
                    yd   = (HEIGHT // 2) + sz2 // 2
                elif s.is_item:
                    if s.item_type == ITEM_TRAP:
                        sz2 = max(4, int(sz * 0.5))
                        floor_y = HEIGHT // 2 + HEIGHT // 4
                        yd = floor_y - sz2
                        FADE_NEAR = TILE_SIZE * 0.8
                        FADE_FAR  = TILE_SIZE * 4
                        trap_alpha = int(255 * max(0.0, min(1.0,
                            1.0 - (dist - FADE_NEAR) / (FADE_FAR - FADE_NEAR))))
                        if trap_alpha > 0:
                            draw_sprite_clipped(s.img, xp, yd, max(1, sz2), dist, alpha=trap_alpha)
                        continue
                    yd  += sz // 4
                    sz2  = int(sz * 0.65)

                skip_draw = False
                if is_boss_sprite and not getattr(s, 'is_miniboss', False) and self.boss and self.boss.invinc_active:
                    if (self.boss.invinc_pulse // 3) % 2 == 1:
                        skip_draw = True

                if not skip_draw and sz2 > 0:
                    draw_sprite_clipped(s.img, xp, yd, max(1, sz2), dist)

        # Vihu2 ranged projectile orbs
        for e in self.enemies:
            if not e.alive or not hasattr(e, 'ranged_projectiles'):
                continue
            for p in e.ranged_projectiles:
                dx = p['x'] - self.px; dy = p['y'] - self.py
                perp_p = dx * math.cos(self.angle) + dy * math.sin(self.angle)
                if perp_p < 0.1: continue
                gamma2 = math.atan2(dy, dx) - self.angle
                while gamma2 >  math.pi: gamma2 -= 2*math.pi
                while gamma2 < -math.pi: gamma2 += 2*math.pi
                if not (-HALF_FOV < gamma2 < HALF_FOV): continue
                psz = int((TILE_SIZE * HEIGHT * 0.35) / (perp_p + 0.1))
                psz = max(6, min(80, psz))
                pxp = int((gamma2 + HALF_FOV) / FOV * WIDTH - psz//2)
                pyp = HEIGHT//2 - psz//2
                pcx = max(0, min(WIDTH-1, pxp + psz//2))
                if self.z_buffer[pcx] > perp_p:
                    orb = pygame.Surface((psz*2, psz*2), pygame.SRCALPHA)
                    pygame.draw.circle(orb, (200, 80, 255, 220), (psz, psz), psz)
                    pygame.draw.circle(orb, (255, 200, 255, 200), (psz, psz), psz//2)
                    pygame.draw.circle(orb, (255, 255, 255, 180), (psz, psz), max(2, psz//4))
                    self.screen.blit(orb, (pxp, pyp))

        # Killdozer nova projectiles -- orange orbs
        if self.miniboss and self.miniboss.alive:
            for p in self.miniboss.nova_projectiles:
                dx = p['x'] - self.px; dy = p['y'] - self.py
                perp_p = dx * math.cos(self.angle) + dy * math.sin(self.angle)
                if perp_p < 0.1: continue
                gamma2 = math.atan2(dy, dx) - self.angle
                while gamma2 >  math.pi: gamma2 -= 2*math.pi
                while gamma2 < -math.pi: gamma2 += 2*math.pi
                if not (-HALF_FOV < gamma2 < HALF_FOV): continue
                psz = int((TILE_SIZE * HEIGHT * 0.30) / (perp_p + 0.1))
                psz = max(6, min(70, psz))
                pxp = int((gamma2 + HALF_FOV) / FOV * WIDTH - psz//2)
                pyp = HEIGHT//2 - psz//2
                pcx = max(0, min(WIDTH-1, pxp + psz//2))
                if self.z_buffer[pcx] > perp_p:
                    orb2 = pygame.Surface((psz*2, psz*2), pygame.SRCALPHA)
                    pygame.draw.circle(orb2, (255, 120, 0, 220), (psz, psz), psz)
                    pygame.draw.circle(orb2, (255, 240, 80, 180), (psz, psz), psz//2)
                    pygame.draw.circle(orb2, (255, 255, 200, 180), (psz, psz), max(2, psz//4))
                    self.screen.blit(orb2, (pxp, pyp))

        # ---------------------------------------------------------------
        # DRACULA SPECIAL ATTACK VISUALS
        # ---------------------------------------------------------------
        if self.boss and self.boss.alive:
            boss = self.boss

            # -- Dash telegraph: pulsing magenta ring around boss when winding up --
            if boss.dash_telegraph > 0:
                t_frac = boss.dash_telegraph / 30.0  # 1.0 _ 0.0 as it counts down
                dx = boss.x - self.px; dy = boss.y - self.py
                perp_b = dx * math.cos(self.angle) + dy * math.sin(self.angle)
                if perp_b > 0.1:
                    gamma_b = math.atan2(dy, dx) - self.angle
                    while gamma_b >  math.pi: gamma_b -= 2*math.pi
                    while gamma_b < -math.pi: gamma_b += 2*math.pi
                    if -HALF_FOV < gamma_b < HALF_FOV:
                        tsz = int((TILE_SIZE * HEIGHT * 1.9) / (perp_b + 0.1))
                        tsz = max(20, min(3500, int(tsz * 1.6)))
                        txp = int((gamma_b + HALF_FOV) / FOV * WIDTH)
                        tyd = HEIGHT // 2 - tsz // 3
                        # Pulsing ring: brightens as telegraph expires (urgency cue)
                        pulse = abs(math.sin(boss.dash_telegraph * 0.25))
                        ring_alpha = int(80 + 160 * (1.0 - t_frac) * pulse)
                        ring_surf = pygame.Surface((tsz, tsz), pygame.SRCALPHA)
                        ring_col = (255, 40, 200, ring_alpha)
                        pygame.draw.ellipse(ring_surf, ring_col,
                                            (0, 0, tsz, tsz), max(3, tsz // 18))
                        self.screen.blit(ring_surf, (txp - tsz // 2, tyd))

            # -- Nova charge: boss glows brighter/hotter as nova charges --
            if boss.nova_charge > 0:
                charge_frac = boss.nova_charge / 60.0
                dx = boss.x - self.px; dy = boss.y - self.py
                perp_b = dx * math.cos(self.angle) + dy * math.sin(self.angle)
                if perp_b > 0.1:
                    gamma_b = math.atan2(dy, dx) - self.angle
                    while gamma_b >  math.pi: gamma_b -= 2*math.pi
                    while gamma_b < -math.pi: gamma_b += 2*math.pi
                    if -HALF_FOV < gamma_b < HALF_FOV:
                        csz = int((TILE_SIZE * HEIGHT * 1.9) / (perp_b + 0.1))
                        csz = max(20, min(3500, int(csz * (1.4 + charge_frac * 0.6))))
                        cxp = int((gamma_b + HALF_FOV) / FOV * WIDTH)
                        cyd = HEIGHT // 2 - csz // 3
                        # Expanding hot glow rings, colour shifts white-hot near fire
                        for ri, (rc, ra_base) in enumerate([
                            ((255, 255, 80),  30),
                            ((255, 180, 0),   45),
                            ((255, 80,  255), 20),
                        ]):
                            ring_r = int(csz * (0.55 + ri * 0.15 + charge_frac * 0.25))
                            if ring_r < 4: continue
                            ring_alpha = int(ra_base + 80 * charge_frac *
                                             abs(math.sin(boss.nova_charge * 0.18 + ri)))
                            ring_surf2 = pygame.Surface((ring_r * 2, ring_r * 2), pygame.SRCALPHA)
                            pygame.draw.ellipse(ring_surf2,
                                                (rc[0], rc[1], rc[2], min(255, ring_alpha)),
                                                (0, 0, ring_r * 2, ring_r * 2),
                                                max(2, ring_r // 10))
                            self.screen.blit(ring_surf2, (cxp - ring_r, cyd + csz // 2 - ring_r))

            # -- Blood Rain warnings: red floor circles projected at player's feet --
            for w in boss.rain_warnings:
                wx, wy = w['x'], w['y']
                w_frac = w['life'] / w['max_life']  # 1.0 _ 0.0 shrinks to impact
                dx = wx - self.px; dy = wy - self.py
                perp_w = dx * math.cos(self.angle) + dy * math.sin(self.angle)
                if perp_w < 0.5: continue
                gamma_w = math.atan2(dy, dx) - self.angle
                while gamma_w >  math.pi: gamma_w -= 2*math.pi
                while gamma_w < -math.pi: gamma_w += 2*math.pi
                if not (-HALF_FOV < gamma_w < HALF_FOV): continue
                # Project onto floor plane
                floor_y_screen = int(HEIGHT // 2 + (HEIGHT * 0.5 * TILE_SIZE) / (perp_w + 0.1))
                if floor_y_screen >= HEIGHT: continue
                screen_cx = int((gamma_w + HALF_FOV) / FOV * WIDTH)
                # Ellipse radius inversely proportional to distance, pulse as it tightens
                base_r = max(6, min(120, int(HEIGHT * 0.35 * TILE_SIZE / (perp_w + 0.1))))
                rx_e   = base_r
                ry_e   = max(3, base_r // 4)
                # Urgency: blinks faster and gets more opaque as life runs out
                blink = abs(math.sin(w['life'] * 0.22)) if w_frac > 0.3 else 1.0
                alpha  = int(80 + 160 * (1.0 - w_frac) * blink)
                warn_surf = pygame.Surface((rx_e * 2 + 4, ry_e * 2 + 4), pygame.SRCALPHA)
                warn_cx, warn_cy = rx_e + 2, ry_e + 2
                # Outer danger ring (dark red)
                pygame.draw.ellipse(warn_surf, (180, 0, 0, min(255, alpha)),
                                    (0, 0, rx_e * 2 + 4, ry_e * 2 + 4), max(2, rx_e // 8))
                # Inner fill (brighter red)
                pygame.draw.ellipse(warn_surf, (255, 30, 30, min(180, alpha // 2)),
                                    (rx_e // 2, ry_e // 2, rx_e, ry_e))
                self.screen.blit(warn_surf, (screen_cx - rx_e - 2, floor_y_screen - ry_e - 2))

            # -- Blood Rain drops: crimson pillar splash when impact occurs --
            for dr in boss.rain_drops:
                wx, wy = dr['x'], dr['y']
                life_frac = dr['life'] / 40.0
                dx = wx - self.px; dy = wy - self.py
                perp_d = dx * math.cos(self.angle) + dy * math.sin(self.angle)
                if perp_d < 0.5: continue
                gamma_d = math.atan2(dy, dx) - self.angle
                while gamma_d >  math.pi: gamma_d -= 2*math.pi
                while gamma_d < -math.pi: gamma_d += 2*math.pi
                if not (-HALF_FOV < gamma_d < HALF_FOV): continue
                screen_cx = int((gamma_d + HALF_FOV) / FOV * WIDTH)
                floor_y_screen = int(HEIGHT // 2 + (HEIGHT * 0.5 * TILE_SIZE) / (perp_d + 0.1))
                pillar_h = max(8, min(HEIGHT // 2, int(
                    (HEIGHT * 0.8 * TILE_SIZE / (perp_d + 0.1)) * life_frac)))
                pillar_w = max(4, min(60, int(
                    (HEIGHT * 0.12 * TILE_SIZE / (perp_d + 0.1)))))
                # Only draw if not behind a wall
                pcx_d = max(0, min(WIDTH - 1, screen_cx))
                if perp_d < self.z_buffer[pcx_d]:
                    drop_alpha = int(200 * life_frac)
                    drop_surf = pygame.Surface((pillar_w, pillar_h), pygame.SRCALPHA)
                    for seg in range(3):
                        seg_h = pillar_h // 3
                        seg_y = seg * seg_h
                        seg_r = max(80, 200 - seg * 60)
                        seg_a = max(0, drop_alpha - seg * 50)
                        pygame.draw.rect(drop_surf, (seg_r, 0, 0, seg_a),
                                         (pillar_w // 4, seg_y,
                                          pillar_w // 2, seg_h + 1))
                    # Splash ring at base
                    splash_r = pillar_w
                    pygame.draw.ellipse(drop_surf,
                                        (220, 0, 0, min(255, drop_alpha)),
                                        (0, pillar_h - 4, pillar_w, 4))
                    self.screen.blit(drop_surf,
                                     (screen_cx - pillar_w // 2,
                                      floor_y_screen - pillar_h))

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def draw_ui(self):
        self.tick_count += 1
        self.ui_pulse = math.sin(self.tick_count * 0.05) * 0.5 + 0.5

        # Vignette -- darkens screen edges for cinematic look with wide FOV
        if not hasattr(self, '_vignette'):
            vw, vh = WIDTH, HEIGHT
            self._vignette = pygame.Surface((vw, vh), pygame.SRCALPHA)
            cx2, cy2 = vw // 2, vh // 2
            max_r = math.hypot(cx2, cy2)
            for vy in range(0, vh, 2):
                for vx in range(0, vw, 2):
                    d = math.hypot(vx - cx2, vy - cy2) / max_r
                    a = int(min(200, max(0, (d - 0.45) * 380)))
                    if a > 0:
                        self._vignette.set_at((vx, vy), (0, 0, 0, a))
                        if vx + 1 < vw: self._vignette.set_at((vx+1, vy), (0, 0, 0, a))
                        if vy + 1 < vh: self._vignette.set_at((vx, vy+1), (0, 0, 0, a))
                        if vx + 1 < vw and vy + 1 < vh: self._vignette.set_at((vx+1, vy+1), (0, 0, 0, a))
        self.screen.blit(self._vignette, (0, 0))

        wb_x = math.sin(self.walk_cycle) * 4 if self.is_moving else 0
        wb_y = abs(math.cos(self.walk_cycle)) * 3 if self.is_moving else 0
        if self.is_moving:
            self.walk_cycle += 0.20

        if self.boss_intro_timer == 0:
            cur_gun = self.gun_imgs.get(self.weapon, self.gun_imgs[WEAPON_PISTOL])
            gw, gh = cur_gun.get_size()
            gy = HEIGHT - gh - 35 + wb_y + (10 if self.shooting_timer > 6 else 0)
            # Pistol and SMG sit slightly right of centre; shotgun is centred
            gun_x_offset = 0 if self.weapon == WEAPON_SHOTGUN else 60
            self.screen.blit(cur_gun, (WIDTH//2 - gw//2 + int(wb_x) + gun_x_offset, gy))

            if self.muzzle_flash > 0:
                fr = 45 + self.muzzle_flash * 2
                fs = pygame.Surface((fr*2, fr*2), pygame.SRCALPHA)
                pygame.draw.circle(fs, (255, 220, 80, self.muzzle_flash*14), (fr, fr), fr)
                self.screen.blit(fs, (WIDTH//2 - fr, gy - fr + 15))
                self.muzzle_flash -= 1

        if self.pain_flash > 0:
            pf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pf.fill((220, 0, 0, int(130 * self.pain_flash / 20)))
            self.screen.blit(pf, (0, 0))
            self.pain_flash -= 1

        if self.boss_intro_timer > 0:
            self.boss_intro_timer -= 1
            # Save real player camera
            real_px, real_py, real_angle = self.px, self.py, self.angle
            # Compute cinematic camera position and angle, then render the scene from it
            self._apply_cutscene_camera()
            # Re-cast rays from cutscene camera
            self.cast_rays()
            self.draw_sprites()
            # Restore
            self.px, self.py, self.angle = real_px, real_py, real_angle
            # Reset smooth state once cutscene finishes
            if self.boss_intro_timer == 0:
                self._cut_cam_x = self._cut_cam_y = self._cut_cam_a = None
            # Draw cinematic overlay (portrait, name, etc.) -- no HUD
            self._draw_boss_cutscene(self.boss_intro_timer)
            return  # skip all HUD drawing below

        # _
        # HUD PANEL
        # _
        PANEL_H = 100
        panel_y = HEIGHT - PANEL_H

        # Panel background -- alpha-layered gradient
        panel_surf = pygame.Surface((WIDTH, PANEL_H), pygame.SRCALPHA)
        for yi in range(PANEL_H):
            t = yi / PANEL_H
            r = int(8  + 18 * t); g = int(2 + 4 * t); b = int(18 + 28 * t)
            pygame.draw.line(panel_surf, (r, g, b, 230), (0, yi), (WIDTH, yi))
        self.screen.blit(panel_surf, (0, panel_y))

        # Top border -- pulsing accent line + inner highlight
        pulse_bright = int(180 + self.ui_pulse * 75)
        border_col = (pulse_bright // 2, 0, pulse_bright)
        pygame.draw.line(self.screen, border_col, (0, panel_y), (WIDTH, panel_y), 2)
        pygame.draw.line(self.screen, (40, 10, 60), (0, panel_y + 2), (WIDTH, panel_y + 2), 1)

        # -- Face portrait ---------------------------------------------
        face_sz = 84
        face_x  = WIDTH//2 - face_sz//2
        face_y  = panel_y + (PANEL_H - face_sz) // 2

        face_idx = min(len(self.face_frames) - 1,
                       max(0, (self.max_health - max(1, self.health)) // 10))
        self.ui_face = self.face_frames[face_idx]

        if self.health < self.max_health * 0.3:
            pulse_alpha = int(abs(math.sin(self.tick_count * 0.12)) * 200 + 55)
            danger_frame = pygame.Surface((face_sz + 8, face_sz + 8), pygame.SRCALPHA)
            pygame.draw.rect(danger_frame, (255, 30, 30, pulse_alpha),
                             (0, 0, face_sz + 8, face_sz + 8), 4, border_radius=8)
            self.screen.blit(danger_frame, (face_x - 4, face_y - 4))
        else:
            pygame.draw.rect(self.screen, (80, 20, 100),
                             (face_x - 3, face_y - 3, face_sz + 6, face_sz + 6), 3, border_radius=6)
        pygame.draw.rect(self.screen, (5, 0, 12),
                         (face_x - 1, face_y - 1, face_sz + 2, face_sz + 2), border_radius=5)
        self.screen.blit(pygame.transform.scale(self.ui_face, (face_sz, face_sz)), (face_x, face_y))

        # -- HP + Stamina bars (left of face) -------------------------
        LEFT_W = 210
        left_x = face_x - LEFT_W - 14
        left_cy = panel_y + PANEL_H // 2

        # HP bar
        hp_ratio = max(0.0, self.health / self.max_health)
        hp_col   = (int(220*(1-hp_ratio)+60*hp_ratio), int(60*(1-hp_ratio)+200*hp_ratio), int(60*(1-hp_ratio)+80*hp_ratio))
        hp_bg    = pygame.Rect(left_x, left_cy - 30, LEFT_W, 24)
        pygame.draw.rect(self.screen, (15, 5, 25), hp_bg, border_radius=7)
        pygame.draw.rect(self.screen, (50, 15, 65), hp_bg, 1, border_radius=7)
        if hp_ratio > 0:
            fw = max(4, int(LEFT_W * hp_ratio))
            pygame.draw.rect(self.screen, tuple(max(0,c-70) for c in hp_col),
                             (left_x+1, left_cy-29, fw-2, 22), border_radius=6)
            pygame.draw.rect(self.screen, tuple(min(255,c+70) for c in hp_col),
                             (left_x+1, left_cy-29, fw-2, 5), border_radius=5)
        hp_lbl = self.small_font.render(f"HP  {self.health}/{self.max_health}", True, (230,230,230))
        self.screen.blit(hp_lbl, hp_lbl.get_rect(midleft=(left_x+7, left_cy-18)))

        # Stamina bar
        st_ratio = max(0.0, self.stamina / self.max_stamina)
        st_col   = (30, 130, 220) if not self.is_exhausted else (200, 80, 0)
        st_bg    = pygame.Rect(left_x, left_cy + 4, LEFT_W, 12)
        pygame.draw.rect(self.screen, (10, 5, 20), st_bg, border_radius=4)
        pygame.draw.rect(self.screen, (30, 10, 40), st_bg, 1, border_radius=4)
        if st_ratio > 0:
            sw = max(4, int(LEFT_W * st_ratio))
            pygame.draw.rect(self.screen, tuple(max(0,c-50) for c in st_col),
                             (left_x+1, st_bg.y+1, sw-2, 10), border_radius=3)
            pygame.draw.rect(self.screen, tuple(min(255,c+60) for c in st_col),
                             (left_x+1, st_bg.y+1, sw-2, 3), border_radius=3)
        st_label = "STAMINA" + ("  [EXHAUSTED]" if self.is_exhausted else "")
        st_lbl = self.tiny_font.render(st_label, True,
                                        (200,160,255) if not self.is_exhausted else (255,140,50))
        self.screen.blit(st_lbl, (left_x, left_cy + 18))

        # Key + Token row under bars
        ix = left_x
        if self.keys_collected > 0 or self.keys_needed > 0:
            key_col_map = {'red':(255,80,80),'blue':(80,160,255),'green':(60,210,100)}
            key_col = key_col_map.get(self.keycard_color, COL_GOLD)
            if self.keys_collected >= self.keys_needed:
                key_col = (80, 255, 140)
            kbg = pygame.Rect(ix, left_cy + 34, 90, 18)
            pygame.draw.rect(self.screen, tuple(c//6 for c in key_col), kbg, border_radius=4)
            pygame.draw.rect(self.screen, key_col, kbg, 1, border_radius=4)
            key_label = f"KEY {self.keys_collected}/{self.keys_needed}" if self.keys_needed > 1                         else ("KEY OK" if self.keys_collected > 0 else "KEY")
            kt = self.tiny_font.render(key_label, True, key_col)
            self.screen.blit(kt, kt.get_rect(center=kbg.center))
        if self.tokens_held > 0:
            tok_bg = pygame.Rect(ix + 96, left_cy + 34, 100, 18)
            pygame.draw.rect(self.screen, (40,30,5), tok_bg, border_radius=4)
            pygame.draw.rect(self.screen, (255,200,50), tok_bg, 1, border_radius=4)
            tok_txt = self.tiny_font.render(f"TOKENS  {self.tokens_held}", True, (255,220,80))
            self.screen.blit(tok_txt, tok_txt.get_rect(center=tok_bg.center))

        # -- Ammo + Level/Score (right of face) ------------------------
        RIGHT_W = 200
        right_x = face_x + face_sz + 14
        right_cy = panel_y + PANEL_H // 2

        ammo_now = getattr(self, f'ammo_{self.weapon}', 0)
        ammo_max = getattr(self, f'max_ammo_{self.weapon}', 1)
        ammo_col = COL_GOLD if ammo_now > ammo_max // 4 else (255,120,30) if ammo_now > 0 else (180,30,30)
        ammo_bg  = pygame.Rect(right_x, right_cy - 32, RIGHT_W, 36)
        pygame.draw.rect(self.screen, (20, 15, 5), ammo_bg, border_radius=8)
        pygame.draw.rect(self.screen, ammo_col, ammo_bg, 2, border_radius=8)
        ammo_tag = self.tiny_font.render(f"AMMO  ({self.weapon.upper()})", True, (180, 150, 100))
        ammo_num = self.font.render(f"{ammo_now}/{ammo_max}", True, ammo_col)
        self.screen.blit(ammo_tag, (right_x + 8, right_cy - 30))
        self.screen.blit(ammo_num, ammo_num.get_rect(midright=(right_x + RIGHT_W - 8, right_cy - 14)))

        lv_col = COL_BOSS_BRIGHT if self.is_boss_level else ((255,160,0) if self.is_miniboss_level else (180,120,255))
        lv_str = "FINAL BOSS" if self.is_boss_level else ("KILLDOZER" if self.is_miniboss_level else f"LEVEL  {self.level}")
        lv_txt = self.small_font.render(lv_str, True, lv_col)
        self.screen.blit(lv_txt, (right_x, right_cy + 8))
        sc_txt = self.tiny_font.render(f"SCORE  {self.score:,}", True, (200,180,240))
        self.screen.blit(sc_txt, (right_x, right_cy + 30))

        # Score multiplier indicator
        if self._streak_tier > 0 and self._streak_timer > 0:
            mult_val = 1 + self._streak_tier
            timer_frac = self._streak_timer / STREAK_WINDOW
            mult_col = STREAK_COLORS[min(self._streak_tier - 1, len(STREAK_COLORS)-1)]
            mult_bg = pygame.Rect(right_x, right_cy + 48, RIGHT_W, 16)
            pygame.draw.rect(self.screen, (10,5,0), mult_bg, border_radius=4)
            bar_fill = pygame.Rect(right_x, right_cy + 48, int(RIGHT_W * timer_frac), 16)
            pygame.draw.rect(self.screen, tuple(c//3 for c in mult_col), bar_fill, border_radius=4)
            pygame.draw.rect(self.screen, mult_col, mult_bg, 1, border_radius=4)
            mt = self.tiny_font.render(f"x{mult_val} SCORE MULTIPLIER", True, mult_col)
            self.screen.blit(mt, mt.get_rect(center=mult_bg.center))

        # -- Weapon selector ----------------------------------------------
        weapon_labels = [(WEAPON_PISTOL, '1', 'PISTOL'), (WEAPON_SHOTGUN, '2', 'SHTGN'), (WEAPON_SMG, '3', 'SMG')]
        wx_start = right_x + RIGHT_W + 10
        for i, (wname, wkey, wshort) in enumerate(weapon_labels):
            active = (self.weapon == wname)
            wr = pygame.Rect(wx_start + i * 52, right_cy - 26, 48, 36)
            wbg = (50, 10, 70) if active else (18, 4, 28)
            wborder = (220, 80, 255) if active else (60, 20, 80)
            pygame.draw.rect(self.screen, wbg, wr, border_radius=5)
            pygame.draw.rect(self.screen, wborder, wr, 2 if active else 1, border_radius=5)
            num_t = self.tiny_font.render(wkey, True, (120,80,160) if not active else (255,220,255))
            wname_t = self.tiny_font.render(wshort, True, wborder)
            self.screen.blit(num_t, num_t.get_rect(center=(wr.centerx, wr.y + 9)))
            self.screen.blit(wname_t, wname_t.get_rect(center=(wr.centerx, wr.y + 24)))

        # -- Trap slow overlay -----------------------------------------
        if self._trap_slow_timer > 0:
            ratio = self._trap_slow_timer / 180
            slow_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            slow_surf.fill((60, 0, 160, int(ratio * 35)))
            self.screen.blit(slow_surf, (0, 0))
            for sw2 in range(0, 14, 4):
                pygame.draw.rect(self.screen, (100, 0, 220),
                                 (sw2, sw2, WIDTH - sw2*2, HEIGHT - sw2*2), 3)
            slow_txt = self.font.render("SLOWED", True, (180, 80, 255))
            self.screen.blit(slow_txt, slow_txt.get_rect(center=(WIDTH//2, HEIGHT//2 - 70)))

        # -- Upgrade station prompt -------------------------------------
        for item in self.items:
            if item.item_type == 'upgrade_station':
                if math.hypot(self.px - item.x, self.py - item.y) < TILE_SIZE * 2.5:
                    pb = pygame.Surface((260, 30), pygame.SRCALPHA)
                    pb.fill((0, 0, 0, 150))
                    self.screen.blit(pb, (WIDTH//2 - 130, HEIGHT//2 + 28))
                    prompt = self.small_font.render("[E]  Upgrade Station", True, (200, 100, 255))
                    self.screen.blit(prompt, prompt.get_rect(center=(WIDTH//2, HEIGHT//2 + 43)))

        # -- Speedrun timer + kills -------------------------------------
        elapsed   = self.get_speedrun_elapsed()
        timer_str = format_time(elapsed)
        timer_col = (255,255,80) if not self.is_boss_level else (255,100,255)
        if self.is_miniboss_level: timer_col = (255,180,50)
        timer_bg = pygame.Surface((190, 46), pygame.SRCALPHA)
        timer_bg.fill((0, 0, 0, 150))
        pygame.draw.rect(timer_bg, (60, 20, 80, 120), (0, 0, 190, 46), 1, border_radius=4)
        self.screen.blit(timer_bg, (6, 6))
        draw_glowing_text(self.screen, f"RUN  {timer_str}", self.small_font, timer_col,
                          12, 10, glow_color=(80, 60, 0))
        kills_txt = self.tiny_font.render(f"KILLS  {self.total_kills + self.level_kills}",
                                          True, (200, 180, 255))
        self.screen.blit(kills_txt, (12, 34))

        # FPS
        if self.show_fps:
            fps_val = int(self.clock.get_fps())
            fps_col = (80,255,80) if fps_val>=55 else (255,200,50) if fps_val>=30 else (255,60,60)
            fps_txt = self.tiny_font.render(f"FPS: {fps_val}", True, fps_col)
            self.screen.blit(fps_txt, (8, 54))

        # -- Kill streak banner -----------------------------------------
        if self._streak_display > 0:
            alpha = min(255, self._streak_display * 6)
            scale = 1.0 + 0.3 * (self._streak_display / 100.0)
            streak_font = pygame.font.SysFont('Georgia', int(28 * scale), bold=True)
            stxt = streak_font.render(self._streak_msg, True, self._streak_col)
            stxt.set_alpha(alpha)
            sx = WIDTH//2 - stxt.get_width()//2
            sy = HEIGHT//2 - 100
            # Dark pill behind it
            sbg = pygame.Surface((stxt.get_width()+24, stxt.get_height()+8), pygame.SRCALPHA)
            sbg.fill((0, 0, 0, min(180, alpha)))
            self.screen.blit(sbg, (sx - 12, sy - 4))
            self.screen.blit(stxt, (sx, sy))

        # -- Enemy alert exclamation marks (world-projected) ------------
        for e in self.enemies:
            if not e.alive or e.alerted_timer == 0:
                continue
            dx2 = e.x - self.px; dy2 = e.y - self.py
            perp2 = dx2 * math.cos(self.angle) + dy2 * math.sin(self.angle)
            if perp2 < 0.5:
                continue
            gamma2 = math.atan2(dy2, dx2) - self.angle
            while gamma2 >  math.pi: gamma2 -= 2*math.pi
            while gamma2 < -math.pi: gamma2 += 2*math.pi
            if not (-HALF_FOV < gamma2 < HALF_FOV):
                continue
            sprite_h = int((TILE_SIZE * HEIGHT * 1.9) / (perp2 + 0.1))
            scr_x = int((gamma2 + HALF_FOV) / FOV * WIDTH)
            scr_y = HEIGHT//2 - sprite_h//2 - 20
            frac = e.alerted_timer / ENEMY_ALERT_FRAMES
            if int(self.tick_count * 0.3) % 2 == 0:
                ex_col = (255, 240, 0)
                ex_txt = self.font.render("!", True, ex_col)
                ex_txt.set_alpha(int(255 * frac))
                self.screen.blit(ex_txt, ex_txt.get_rect(center=(scr_x, max(10, scr_y))))

        # -- Crosshair -------------------------------------------------
        cx, cy = WIDTH//2, HEIGHT//2
        shooting = self.shooting_timer > 0
        if self.weapon == WEAPON_SHOTGUN:
            spread   = 16 if shooting else 10
        elif self.weapon == WEAPON_SMG:
            spread   = 11 if shooting else 6
        else:
            spread   = 9 if shooting else 5
        cross_col = (255, 80, 180) if shooting else (240, 240, 240)
        for (dx2, dy2) in [(-1,0),(1,0),(0,-1),(0,1)]:
            s = (cx+dx2*spread, cy+dy2*spread)
            e2= (cx+dx2*(spread+10), cy+dy2*(spread+10))
            pygame.draw.line(self.screen, (0,0,0), (s[0]+1,s[1]+1), (e2[0]+1,e2[1]+1), 2)
            pygame.draw.line(self.screen, cross_col, s, e2, 2)
        pygame.draw.circle(self.screen, (0,0,0), (cx+1,cy+1), 2, 1)
        pygame.draw.circle(self.screen, cross_col, (cx,cy), 2, 1)
        if shooting: self.shooting_timer -= 1

        # -- Hint message ---------------------------------------------
        if self._hint_frames > 0:
            self._hint_frames -= 1
            hw = len(self._hint_text) * 10 + 28
            hint_bg = pygame.Surface((hw, 32), pygame.SRCALPHA)
            hint_bg.fill((0, 0, 0, 150))
            pygame.draw.rect(hint_bg, (80, 40, 0, 120), (0, 0, hw, 32), 1, border_radius=5)
            hx = WIDTH//2 - hw//2; hy = HEIGHT//2 + 48
            self.screen.blit(hint_bg, (hx, hy))
            draw_glowing_text(self.screen, self._hint_text, self.small_font,
                              (255, 230, 90), hx+14, hy+6, glow_color=(120, 80, 0))

        self._draw_door_hint()
        self._draw_minimap()

        if self.is_boss_level and self.boss and self.boss.alive:
            self._draw_boss_bar()
        if self.is_miniboss_level and self.miniboss and self.miniboss.alive:
            self._draw_miniboss_bar()

        if self.is_miniboss_level and self.miniboss and not self.miniboss.alive:
            if self.keys_collected == 0:
                remind = self.small_font.render("Grab the KEY Killdozer dropped!", True, (255,200,50))
                self.screen.blit(remind, remind.get_rect(center=(WIDTH//2, HEIGHT//2 - 55)))
            else:
                remind = self.small_font.render("Find the EXIT - north wall!", True, (80, 255, 150))
                self.screen.blit(remind, remind.get_rect(center=(WIDTH//2, HEIGHT//2 - 55)))


        if self.health <= 0:
            if self.sfx_playerdeath and not self._player_death_played:
                self._player_death_played = True
                self.sfx_playerdeath.play()
                self._death_floor = self.level
                self._death_time  = self.get_speedrun_elapsed()
            go = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            draw_gradient_rect(go, (0,0,0,0), (0,0,0,200), (0,0,WIDTH,HEIGHT))
            self.screen.blit(go, (0, 0))
            draw_glowing_text(self.screen, "YOU DIED", self.big_font,
                              COL_ACCENT, WIDTH//2, HEIGHT//2-70, glow_color=(100,0,50), centered=True)
            # Stat box
            stat_box = pygame.Surface((360, 90), pygame.SRCALPHA)
            stat_box.fill((0, 0, 0, 160))
            pygame.draw.rect(stat_box, (120, 20, 60, 200), (0,0,360,90), 2, border_radius=8)
            self.screen.blit(stat_box, stat_box.get_rect(center=(WIDTH//2, HEIGHT//2 - 8)))
            total_k = self.total_kills + self.level_kills
            stat_lines = [
                (f"Floor {self._death_floor}", (255, 180, 50)),
                (f"Score  {self.score:,}", (200, 160, 255)),
                (f"Kills  {total_k}   Time  {format_time(self._death_time)}", (160, 220, 255)),
            ]
            for i, (sline, scol) in enumerate(stat_lines):
                st = self.small_font.render(sline, True, scol)
                self.screen.blit(st, st.get_rect(center=(WIDTH//2, HEIGHT//2 - 28 + i*24)))
            sub = self.small_font.render("Press R to restart from Level 1", True, (255, 182, 193))
            self.screen.blit(sub, sub.get_rect(center=(WIDTH//2, HEIGHT//2+60)))

        self.damage_numbers = [(x, y, t, c, f-1) for x,y,t,c,f in self.damage_numbers if f > 0]
        for x, y, txt, col, frames in self.damage_numbers:
            alpha = min(255, frames * 8)
            dn = self.small_font.render(txt, True, col)
            dn.set_alpha(alpha)
            screen_x = WIDTH//2 + 40
            screen_y = HEIGHT//2 - 30 - (60 - frames)
            self.screen.blit(dn, (screen_x, screen_y))

    # ------------------------------------------------------------------
    # Boss cutscene helpers
    # ------------------------------------------------------------------
    def _apply_cutscene_camera(self):
        """Sets self.px/py/angle to the smoothed cinematic camera position for this frame."""
        is_mb = self.is_miniboss_level
        TOTAL = 840

        timer    = self.boss_intro_timer
        progress = 1.0 - (timer / TOTAL)   # 0 _ 1

        boss_obj = self.miniboss if is_mb else self.boss
        if boss_obj:
            bx, by = boss_obj.x, boss_obj.y
        else:
            bx = (self.MAP_W // 2) * TILE_SIZE + TILE_SIZE // 2
            by = (self.MAP_H // 2) * TILE_SIZE + TILE_SIZE // 2

        px_start = self.px
        py_start = self.py

        orbit_r  = TILE_SIZE * 9
        arena_cx = bx
        arena_cy = by

        T1, T2, T3, T4 = 0.25, 0.55, 0.80, 1.0

        def lerp(a, b, t): return a + (b - a) * t
        def smooth(t):     return t * t * (3 - 2 * t)

        # Compute the raw target position for this frame
        if progress < T1:
            t      = smooth(progress / T1)
            angle  = math.pi * 2 * t * 0.6 + math.pi
            tx     = arena_cx + math.cos(angle) * orbit_r
            ty_    = arena_cy + math.sin(angle) * orbit_r
            ta     = math.atan2(arena_cy - ty_, arena_cx - tx)

        elif progress < T2:
            t      = smooth((progress - T1) / (T2 - T1))
            orbit_angle = math.pi * 2 * 0.6 + math.pi
            start_x = arena_cx + math.cos(orbit_angle) * orbit_r
            start_y = arena_cy + math.sin(orbit_angle) * orbit_r
            close_dist  = TILE_SIZE * 3.5
            close_angle = math.pi
            end_x  = bx + math.cos(close_angle) * close_dist
            end_y  = by + math.sin(close_angle) * close_dist
            tx     = lerp(start_x, end_x, t)
            ty_    = lerp(start_y, end_y, t)
            ta     = math.atan2(by - ty_, bx - tx)

        elif progress < T3:
            t      = smooth((progress - T2) / (T3 - T2))
            close_dist  = lerp(TILE_SIZE * 3.5, TILE_SIZE * 2.2, t)
            close_angle = math.pi
            tx     = bx + math.cos(close_angle) * close_dist
            ty_    = by + math.sin(close_angle) * close_dist
            ta     = math.atan2(by - ty_, bx - tx)

        else:
            t      = smooth((progress - T3) / (T4 - T3))
            close_dist  = TILE_SIZE * 2.2
            close_angle = math.pi
            start_x = bx + math.cos(close_angle) * close_dist
            start_y = by + math.sin(close_angle) * close_dist
            tx      = lerp(start_x, px_start, t)
            ty_     = lerp(start_y, py_start, t)
            if t < 0.99:
                ta  = math.atan2(by - ty_, bx - tx)
            else:
                ta  = self.angle

        # -- Smooth the camera --
        # Initialise smoothed state on first frame
        if self._cut_cam_x is None:
            self._cut_cam_x = tx
            self._cut_cam_y = ty_
            self._cut_cam_a = ta

        # Lerp factor: higher = snappier, lower = smoother
        SMOOTH = 0.06
        self._cut_cam_x += (tx  - self._cut_cam_x) * SMOOTH
        self._cut_cam_y += (ty_ - self._cut_cam_y) * SMOOTH
        # Angle needs shortest-path lerp
        da = ta - self._cut_cam_a
        while da >  math.pi: da -= 2 * math.pi
        while da < -math.pi: da += 2 * math.pi
        self._cut_cam_a += da * SMOOTH

        # Clamp to floor tiles
        cx, cy = self._cut_cam_x, self._cut_cam_y
        ttx = int(cx / TILE_SIZE); tty = int(cy / TILE_SIZE)
        if not (0 < ttx < self.MAP_W - 1 and 0 < tty < self.MAP_H - 1 and
                self.grid[tty][ttx] == CELL_FLOOR):
            # Keep previous valid position
            cx, cy = self.px, self.py

        self.px, self.py = cx, cy
        self.angle = self._cut_cam_a

    def _draw_boss_cutscene(self, timer):
        """Draws the cinematic overlay (title card, portrait, lore) over the 3D scene."""
        is_mb = self.is_miniboss_level
        TOTAL = 840

        progress = 1.0 - (timer / TOTAL)
        T1, T2, T3, T4 = 0.25, 0.55, 0.80, 1.0

        # -- Letterbox bars --
        bar_h = 60
        pygame.draw.rect(self.screen, (0, 0, 0), (0, 0, WIDTH, bar_h))
        pygame.draw.rect(self.screen, (0, 0, 0), (0, HEIGHT - bar_h, WIDTH, bar_h))

        # -- Phase-dependent vignette --
        vig_alpha = 0
        if progress < T1:
            # Fade in from black
            vig_alpha = int(255 * (1.0 - progress / T1))
        elif progress > T3:
            # Fade out to black
            t = (progress - T3) / (T4 - T3)
            vig_alpha = int(255 * t)

        if vig_alpha > 0:
            vig = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            vig.fill((0, 0, 0, vig_alpha))
            self.screen.blit(vig, (0, 0))

        # -- Boss data --
        if is_mb:
            portrait  = pygame.transform.scale(self.miniboss_img, (220, 220))
            name_str  = "KILLDOZER"
            sub_str   = "Mini-Boss  |  Level 5"
            hp_str    = "100 HP"
            name_col  = (255, 140,   0)
            bar_col   = (255, 100,   0)
            lore_lines = [
                "An unstoppable industrial juggernaut.",
                "It charges. It summons. It never tires.",
                "Survive the Killdozer.",
            ]
        else:
            portrait  = pygame.transform.scale(self.dracula_img, (220, 220))
            name_str  = "DRACULA"
            sub_str   = "Final Boss  |  Level 10"
            hp_str    = "300 HP"
            name_col  = (220,  60, 255)
            bar_col   = (180,   0, 255)
            lore_lines = [
                "The ancient vampire lord of darkness.",
                "Invincible at half health - wait for the moment.",
                "Destroy her before she destroys you.",
            ]

        # -- Title card shown during phases 2-4 --
        def fade_alpha(phase_start, phase_end, fade_in_len=0.06, fade_out_start=T3):
            if progress < phase_start: return 0
            if progress < phase_start + fade_in_len:
                return int(255 * (progress - phase_start) / fade_in_len)
            if progress > fade_out_start:
                t = (progress - fade_out_start) / (T4 - fade_out_start)
                return int(255 * (1.0 - t))
            return 255

        card_alpha = fade_alpha(T2 - 0.05, T4)
        if card_alpha > 0:
            # Dark side panel for portrait
            panel = pygame.Surface((280, 260), pygame.SRCALPHA)
            panel.fill((0, 0, 0, 160))
            panel.set_alpha(card_alpha)
            self.screen.blit(panel, (30, HEIGHT // 2 - 130))

            portrait.set_alpha(card_alpha)
            self.screen.blit(portrait, (40, HEIGHT // 2 - 110))

            # Name
            ns = self.big_font.render(name_str, True, name_col)
            ns.set_alpha(card_alpha)
            self.screen.blit(ns, ns.get_rect(midleft=(330, HEIGHT // 2 - 90)))

            # Subtitle
            ss2 = self.small_font.render(sub_str, True, (200, 200, 200))
            ss2.set_alpha(card_alpha)
            self.screen.blit(ss2, ss2.get_rect(midleft=(330, HEIGHT // 2 - 55)))

            # HP bar
            bw = 280; bh = 12
            bx = 330; bby = HEIGHT // 2 - 30
            bp_surf = pygame.Surface((bw + 4, bh + 4), pygame.SRCALPHA)
            pygame.draw.rect(bp_surf, (30, 8, 0, 180), (0, 0, bw + 4, bh + 4), border_radius=7)
            pygame.draw.rect(bp_surf, bar_col + (card_alpha,), (2, 2, bw, bh), border_radius=6)
            bp_surf.set_alpha(card_alpha)
            self.screen.blit(bp_surf, (bx - 2, bby - 2))
            hp_l = self.small_font.render(hp_str, True, COL_WHITE)
            hp_l.set_alpha(card_alpha)
            self.screen.blit(hp_l, (bx, bby + bh + 6))

            # Lore lines appearing one by one (during phase 3)
            for li, line in enumerate(lore_lines):
                line_t = T2 + 0.04 + li * 0.08
                la = fade_alpha(line_t, T4, fade_in_len=0.05)
                la = min(la, card_alpha)
                if la <= 0:
                    continue
                ls = self.small_font.render(line, True, (180, 180, 200))
                ls.set_alpha(la)
                self.screen.blit(ls, ls.get_rect(midleft=(330, HEIGHT // 2 + 10 + li * 26)))

        # -- Phase label (top bar) --
        if progress > T1 * 0.3 and progress < T4 - 0.05:
            label_alpha = int(min(255, max(0, (progress - T1 * 0.3) / 0.05 * 255)))
            if progress > T4 - 0.12:
                label_alpha = int(255 * (1 - (progress - (T4 - 0.12)) / 0.12))
            phase_lbl = self.tiny_font.render(name_str, True, name_col)
            phase_lbl.set_alpha(label_alpha)
            self.screen.blit(phase_lbl, phase_lbl.get_rect(center=(WIDTH // 2, bar_h // 2)))

        # -- Skip hint --
        if 0.05 < progress < T4 - 0.10:
            skip = self.tiny_font.render("Press any key to skip", True, (120, 120, 120))
            skip.set_alpha(160)
            self.screen.blit(skip, skip.get_rect(center=(WIDTH // 2, HEIGHT - bar_h // 2)))

    def _draw_boss_bar(self):
        bar_h = 28
        bar_pad = 12
        bw = WIDTH - bar_pad*2
        r = max(0.0, self.boss.health / self.boss.max_health)

        bg = pygame.Surface((WIDTH, bar_h + 20), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 180))
        self.screen.blit(bg, (0, 0))

        phase_txt = "PHASE 2" if self.boss.phase == 2 else ""
        invinc_txt = "  INVINCIBLE!" if self.boss.invinc_active else ""
        draw_glowing_text(self.screen, f"DRACULA  {phase_txt}{invinc_txt}", self.font,
                          COL_GOLD if self.boss.invinc_active else COL_BOSS_BRIGHT,
                          WIDTH//2, 2, glow_color=(80,0,140), centered=True)

        pygame.draw.rect(self.screen, (30, 0, 50), (bar_pad, bar_h - 4, bw, 16), border_radius=8)

        fill_w = max(0, int(bw * r))
        if fill_w > 0:
            if self.boss.invinc_active:
                pulse = abs(math.sin(self.tick_count * 0.12))
                col1 = (255, 200, 0)
                col2 = (255, 255, 150)
                fc = tuple(int(col1[i] + (col2[i]-col1[i])*pulse) for i in range(3))
            else:
                col1 = (200, 50, 255) if self.boss.phase == 2 else (120, 0, 200)
                col2 = (255, 100, 100) if self.boss.phase == 2 else (180, 0, 255)
                pulse = abs(math.sin(self.tick_count * 0.07)) if self.boss.phase == 2 else 0
                fc = tuple(int(col1[i] + (col2[i]-col1[i])*pulse) for i in range(3))
            draw_gradient_rect(self.screen, tuple(min(255,c+60) for c in fc), fc,
                               (bar_pad, bar_h-4, fill_w, 16), vertical=False)
            pygame.draw.line(self.screen, tuple(min(255,c+80) for c in fc),
                             (bar_pad+2, bar_h-3), (bar_pad+fill_w-2, bar_h-3))

        for seg in range(1, 4):
            sx = bar_pad + int(bw * seg / 4)
            pygame.draw.line(self.screen, (0,0,0), (sx, bar_h-4), (sx, bar_h+12), 2)

        pygame.draw.rect(self.screen, COL_GOLD if self.boss.invinc_active else COL_BOSS_BRIGHT,
                         (bar_pad, bar_h-4, bw, 16), 1, border_radius=8)

        hp_txt = self.tiny_font.render(f"{self.boss.health}/{self.boss.max_health}", True, COL_WHITE)
        self.screen.blit(hp_txt, hp_txt.get_rect(center=(WIDTH//2, bar_h+4)))

    def _draw_miniboss_bar(self):
        mb = self.miniboss
        bar_h = 28
        bar_pad = 12
        bw = WIDTH - bar_pad * 2
        r = max(0.0, mb.health / mb.max_health)

        bg = pygame.Surface((WIDTH, bar_h + 20), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 180))
        self.screen.blit(bg, (0, 0))

        phase_txt = "  PHASE 2" if mb.phase == 2 else ""
        charge_txt = "  CHARGING!" if mb.charging else ("  BLITZING!" if mb.blitz_active else "")
        draw_glowing_text(self.screen, f"KILLDOZER{phase_txt}{charge_txt}", self.font,
                          (255, 140, 0) if mb.blitz_active else (220, 80, 0),
                          WIDTH//2, 2, glow_color=(120, 40, 0), centered=True)

        pygame.draw.rect(self.screen, (40, 10, 0), (bar_pad, bar_h - 4, bw, 16), border_radius=8)
        fill_w = max(0, int(bw * r))
        if fill_w > 0:
            pulse = abs(math.sin(self.tick_count * 0.09)) if mb.phase == 2 else 0
            col1 = (255, 80,  0)
            col2 = (255, 200, 0)
            fc   = tuple(int(col1[i] + (col2[i]-col1[i])*pulse) for i in range(3))
            draw_gradient_rect(self.screen, tuple(min(255,c+60) for c in fc), fc,
                               (bar_pad, bar_h-4, fill_w, 16), vertical=False)
            pygame.draw.line(self.screen, tuple(min(255,c+80) for c in fc),
                             (bar_pad+2, bar_h-3), (bar_pad+fill_w-2, bar_h-3))
        mx = bar_pad + bw // 2
        pygame.draw.line(self.screen, (255,255,0), (mx, bar_h-4), (mx, bar_h+12), 2)
        pygame.draw.rect(self.screen, (220, 80, 0), (bar_pad, bar_h-4, bw, 16), 1, border_radius=8)
        hp_txt = self.tiny_font.render(f"{int(mb.health)}/{mb.max_health}", True, COL_WHITE)
        self.screen.blit(hp_txt, hp_txt.get_rect(center=(WIDTH//2, bar_h+4)))

    def _draw_door_hint(self):
        for d in range(1, int(TILE_SIZE * 1.6)):
            tx = int((self.px + math.cos(self.angle)*d) / TILE_SIZE)
            ty = int((self.py + math.sin(self.angle)*d) / TILE_SIZE)
            if 0 <= ty < self.MAP_H and 0 <= tx < self.MAP_W:
                c  = self.grid[ty][tx]
                st = self.door_states.get((ty, tx), {})
                if c == CELL_EXITDOOR and not st.get('open'):
                    has_all = self.keys_collected >= self.keys_needed
                    if self.is_miniboss_level and not has_all:
                        lbl = "[E]  Kill KILLDOZER first!"
                        col = (255, 80, 80)
                    elif not has_all:
                        col_name = self.keycard_color.upper()
                        need_str = f" ({self.keys_collected}/{self.keys_needed})" if self.keys_needed > 1 else ""
                        lbl = f"[E]  Need {col_name} keycard{need_str}"
                        col = (255, 80, 80)
                    else:
                        lbl = "[E]  Open Exit"
                        col = (80, 255, 150)
                    bg = pygame.Surface((len(lbl)*9+16, 24), pygame.SRCALPHA)
                    bg.fill((0,0,0,110))
                    hx = WIDTH//2 - bg.get_width()//2
                    self.screen.blit(bg, (hx, HEIGHT//2+30))
                    ht = self.small_font.render(lbl, True, col)
                    self.screen.blit(ht, ht.get_rect(center=(WIDTH//2, HEIGHT//2+42)))
                    return
                elif c == CELL_DOOR and not st.get('open'):
                    ht = self.small_font.render("[E]  Open Door", True, (255,220,80))
                    self.screen.blit(ht, ht.get_rect(center=(WIDTH//2, HEIGHT//2+42)))
                    return

    def _draw_minimap(self):
        pygame.draw.line(self.screen, (60, 10, 80), (WIDTH, 0), (WIDTH, HEIGHT), 2)

        panel = pygame.Surface((MAP_PANEL_W, HEIGHT))
        panel.fill((8, 2, 16))
        self.screen.blit(panel, (WIDTH, 0))

        pad = 8
        avail_w = MAP_PANEL_W - pad * 2
        avail_h = HEIGHT - pad * 2 - 20

        C = min(avail_w // self.MAP_W, avail_h // self.MAP_H)
        C = max(1, C)
        mw = self.MAP_W * C
        mh = self.MAP_H * C

        ox = WIDTH + pad + (avail_w - mw) // 2
        oy = pad + 20

        lbl = self.tiny_font.render("MAP", True, (180, 80, 255))
        self.screen.blit(lbl, lbl.get_rect(center=(WIDTH + MAP_PANEL_W // 2, pad + 6)))

        for ry in range(self.MAP_H):
            for rx in range(self.MAP_W):
                v = self.grid[ry][rx]
                if v == CELL_WALL:
                    col = (50, 8, 80)
                elif v == CELL_EXITDOOR:
                    col = (0, 220, 220)
                elif v == CELL_DOOR:
                    col = (80, 200, 80) if self.door_states.get((ry,rx),{}).get('open') else (200, 160, 40)
                else:
                    col = (18, 6, 30)
                pygame.draw.rect(self.screen, col, (ox + rx*C, oy + ry*C, max(1,C-1), max(1,C-1)))

        if self.boss and self.boss.alive:
            pulse_r = 3 + int(self.ui_pulse * 2)
            col = COL_GOLD if self.boss.invinc_active else COL_BOSS_BRIGHT
            pygame.draw.circle(self.screen, col,
                (ox + int(self.boss.x/TILE_SIZE*C), oy + int(self.boss.y/TILE_SIZE*C)), pulse_r)

        # Miniboss dot -- orange pulsing
        if self.miniboss and self.miniboss.alive:
            pulse_r = 3 + int(self.ui_pulse * 2)
            mb_col = (255, 140, 0) if self.miniboss.phase == 1 else (255, 60, 60)
            pygame.draw.circle(self.screen, mb_col,
                (ox + int(self.miniboss.x/TILE_SIZE*C), oy + int(self.miniboss.y/TILE_SIZE*C)), pulse_r)

        for e in self.enemies:
            if e.alive and not getattr(e, 'is_boss', False):
                col = (255, 130, 0) if isinstance(e, Rotta) else (255, 60, 60)
                pygame.draw.circle(self.screen, col,
                    (ox + int(e.x/TILE_SIZE*C), oy + int(e.y/TILE_SIZE*C)), max(1, C))

        for item in self.items:
            if item.item_type == ITEM_KEY:
                pygame.draw.circle(self.screen, COL_GOLD,
                    (ox + int(item.x/TILE_SIZE*C), oy + int(item.y/TILE_SIZE*C)), max(2, C))
            elif item.item_type == 'upgrade_station':
                sx = ox + int(item.x/TILE_SIZE*C)
                sy = oy + int(item.y/TILE_SIZE*C)
                r = max(3, C + 1)
                pygame.draw.rect(self.screen, (160, 0, 255), (sx - r, sy - r, r*2, r*2))
                pygame.draw.rect(self.screen, (220, 140, 255), (sx - r, sy - r, r*2, r*2), 1)
                u_lbl = self.tiny_font.render("U", True, (255, 255, 255))
                self.screen.blit(u_lbl, u_lbl.get_rect(center=(sx, sy)))

        pmx = ox + int(self.px/TILE_SIZE*C)
        pmy = oy + int(self.py/TILE_SIZE*C)
        pygame.draw.circle(self.screen, COL_WHITE, (pmx, pmy), max(2, C+1))
        pygame.draw.line(self.screen, (255, 255, 100),
            (pmx, pmy),
            (pmx + int(math.cos(self.angle)*9), pmy + int(math.sin(self.angle)*9)), 1)

        border_col = COL_BOSS_BRIGHT if self.is_boss_level else ((255, 140, 0) if self.is_miniboss_level else (100, 20, 160))
        pygame.draw.rect(self.screen, border_col, (ox, oy, mw, mh), 1)

    # ------------------------------------------------------------------
    # Demo AI -- auto-plays the game for presentation mode
    # ------------------------------------------------------------------
    def _demo_has_los(self, tx, ty):
        """Cast a DDA ray from player toward (tx, ty). Returns True if nothing
        solid blocks the path before we reach the target."""
        dx = tx - self.px
        dy = ty - self.py
        dist = math.hypot(dx, dy)
        if dist < 1:
            return True
        angle_to = math.atan2(dy, dx)
        hit_dist, cell, _, _ = dda_cast(
            self.px, self.py, angle_to,
            self.grid, self.MAP_W, self.MAP_H, self.door_states
        )
        return hit_dist >= dist - TILE_SIZE * 0.5

    def _has_los(self, ax, ay, bx, by):
        """Returns True if there is an unobstructed line of sight from (ax,ay)
        to (bx,by) -- i.e. the first wall hit is beyond the target."""
        dx = bx - ax
        dy = by - ay
        dist = math.hypot(dx, dy)
        if dist < 1:
            return True
        angle_to = math.atan2(dy, dx)
        hit_dist, _, _, _ = dda_cast(
            ax, ay, angle_to,
            self.grid, self.MAP_W, self.MAP_H, self.door_states
        )
        return hit_dist >= dist - TILE_SIZE * 0.5

    def handle_demo_ai(self):
        """Scripted trailer-style demo that showcases gameplay in predetermined scenes."""
        # Always invincible
        self.health     = self.max_health
        self.pain_flash = 0
        self.stamina    = self.max_stamina
        self.is_moving  = False

        # Init script state
        if not hasattr(self, '_demo_tick'):
            self._demo_tick        = 0
            self._demo_scene       = -1
            self._demo_waypoint    = None
            self._demo_shoot_cd    = 0
            self._demo_look_target = None
            self._demo_open_door_cd = 0

        self._demo_tick += 1
        T = self._demo_tick

        def world(tx, ty):
            return tx * TILE_SIZE + TILE_SIZE // 2, ty * TILE_SIZE + TILE_SIZE // 2

        # -- Scripted enemy layout per scene ---------------------------
        # Format: {scene_id: [(tx, ty, type), ...]}
        # type: 'v1'=ground, 'v2'=flying
        ENEMY_LAYOUTS = {
            1: [(7, 19, 'v1'), (10, 20, 'v1')],           # west room: 2 ground
            2: [(7, 19, 'v1'), (10, 20, 'v1')],           # same, now shoot them
            3: [(7, 19, 'v1')],                            # one surviving
            4: [(19, 6, 'v2'), (21, 9, 'v1')],            # north room
            5: [(19, 6, 'v2'), (21, 9, 'v1')],            # north, fight
            6: [(30, 19, 'v2'), (33, 20, 'v1')],          # east room
            7: [(30, 19, 'v2'), (33, 20, 'v1')],          # east, fight
            8: [(19, 29, 'v1'), (21, 32, 'v1')],          # south room
            9: [(19, 29, 'v1')],                           # south, moving to exit
            10: [(7, 19, 'v1'), (30, 19, 'v2')],          # dramatic lookback, enemies visible
            11: [(7, 19, 'v1'), (30, 19, 'v2'),
                 (19, 6, 'v1')],                           # hub strafe, multiple targets
        }

        LOOP = 1800
        t = T % LOOP

        # Determine scene from tick
        if   t < 80:   scene = 0
        elif t < 200:  scene = 1
        elif t < 380:  scene = 2
        elif t < 480:  scene = 3
        elif t < 600:  scene = 4
        elif t < 750:  scene = 5
        elif t < 900:  scene = 6
        elif t < 1050: scene = 7
        elif t < 1200: scene = 8
        elif t < 1380: scene = 9
        elif t < 1500: scene = 10
        elif t < 1650: scene = 11
        else:          scene = 0

        # When scene changes, rebuild enemy list from script
        if scene != self._demo_scene:
            self._demo_scene = scene
            self.enemies = []
            layout = ENEMY_LAYOUTS.get(scene, [])
            for tx, ty, etype in layout:
                wx, wy = world(tx, ty)
                if etype == 'v2':
                    e = self._make_vihu2(wx, wy)
                else:
                    e = self._make_vihu(wx, wy)
                # Fix position -- disable AI path
                e.state = 'roam'
                e.path  = []
                self.enemies.append(e)

        # Keep scripted enemies at their fixed positions (frozen in place)
        layout = ENEMY_LAYOUTS.get(scene, [])
        for i, e in enumerate(self.enemies):
            if not e.alive or i >= len(layout):
                continue
            tx, ty, _ = layout[i]
            wx, wy = world(tx, ty)
            e.x     = wx
            e.y     = wy
            e.state = 'roam'
            e.path  = []

        # -- Scene camera/movement script -------------------------------
        if t < 80:
            self._demo_look_target = None
            self.angle += 0.018
            self._demo_waypoint = None
        elif t < 200:
            self._demo_waypoint    = world(14, 19)
            self._demo_look_target = world(7, 19)
        elif t < 380:
            self._demo_waypoint    = None
            self._demo_look_target = world(7, 19)
        elif t < 480:
            self._demo_waypoint    = world(16, 17)
            self._demo_look_target = world(7, 19)
        elif t < 600:
            self._demo_waypoint    = world(19, 8)
            self._demo_look_target = world(19, 6)
        elif t < 750:
            self._demo_waypoint    = None
            self._demo_look_target = world(19, 6)
        elif t < 900:
            self._demo_waypoint    = world(28, 19)
            self._demo_look_target = world(30, 19)
        elif t < 1050:
            self._demo_waypoint    = None
            self._demo_look_target = world(30, 19)
        elif t < 1200:
            self._demo_waypoint    = world(19, 27)
            self._demo_look_target = world(19, 29)
        elif t < 1380:
            self._demo_waypoint    = world(19, 33)
            self._demo_look_target = world(19, 36)
        elif t < 1500:
            self._demo_waypoint    = None
            self._demo_look_target = world(7, 19)
        elif t < 1650:
            self._demo_waypoint    = world(22, 22)
            self._demo_look_target = world(7, 19)
        else:
            self._demo_waypoint    = world(19, 19)
            self._demo_look_target = None
            self.angle += 0.022

        # -- Camera rotation -------------------------------------------
        if self._demo_look_target is not None:
            lx, ly = self._demo_look_target
            aim_angle = math.atan2(ly - self.py, lx - self.px)
            diff = aim_angle - self.angle
            while diff >  math.pi: diff -= 2 * math.pi
            while diff < -math.pi: diff += 2 * math.pi
            TURN_RATE = 0.045
            DEADZONE  = 0.012
            if abs(diff) < DEADZONE:
                self._cam_vel *= 0.5
            else:
                raw_delta = max(-TURN_RATE, min(TURN_RATE, diff))
                self._cam_vel = self._cam_vel * 0.35 + raw_delta * 0.65
            self.angle += self._cam_vel
        else:
            self._cam_vel *= 0.85

        # -- Movement --------------------------------------------------
        SPEED = 4.0
        if self._demo_waypoint is not None:
            wx, wy = self._demo_waypoint
            dist_wp = math.hypot(wx - self.px, wy - self.py)
            if dist_wp > TILE_SIZE * 0.8:
                move_a = math.atan2(wy - self.py, wx - self.px)
                probe_x = self.px + math.cos(move_a) * TILE_SIZE * 0.9
                probe_y = self.py + math.sin(move_a) * TILE_SIZE * 0.9
                if not self._blocked(int(probe_x/TILE_SIZE), int(probe_y/TILE_SIZE)):
                    self._move(math.cos(move_a) * SPEED, math.sin(move_a) * SPEED)
                    self.is_moving = True

        # -- Shooting at scripted enemies -------------------------------
        if self._demo_shoot_cd > 0:
            self._demo_shoot_cd -= 1

        # Only shoot during "fight" scenes
        if scene in (2, 5, 7, 9, 11) and self._demo_shoot_cd == 0 and self.ammo_pistol > 0:
            for e in self.enemies:
                if not e.alive: continue
                d = math.hypot(e.x - self.px, e.y - self.py)
                if d > TILE_SIZE * 14: continue
                aim_ra = math.atan2(e.y - self.py, e.x - self.px) - self.angle
                while aim_ra >  math.pi: aim_ra -= 2 * math.pi
                while aim_ra < -math.pi: aim_ra += 2 * math.pi
                if abs(aim_ra) < 0.25:
                    self.shooting_timer = self.base_shooting_timer
                    self.muzzle_flash   = 7
                    self.ammo_pistol    = max(self.ammo_pistol - 1, 0)
                    if self.sfx_shot: self.sfx_shot.play()
                    self._demo_shoot_cd = self.base_shooting_timer + 10
                    e.health -= (1 + self.upgrades.get('damage', 0)) * 3
                    if e.health <= 0:
                        e.alive = False
                        self._play_death_sfx()
                        self.explosions.append({'x': e.x, 'y': e.y, 'timer': self.BOOM_DURATION})
                    break

        if self.ammo_pistol < 10:
            self.ammo_pistol = min(30, self.max_ammo_pistol)

        self._demo_tick += 1
        T = self._demo_tick

        def world(tx, ty):
            return tx * TILE_SIZE + TILE_SIZE // 2, ty * TILE_SIZE + TILE_SIZE // 2

    def handle_input(self):
        keys = pygame.key.get_pressed()
        self.is_moving = False

        if self.mouse_captured:
            mx_rel, _ = pygame.mouse.get_rel()
            target_delta = mx_rel * self.mouse_sensitivity
            # Smooth: lerp current angular velocity toward the raw input each frame
            self._cam_vel = self._cam_vel * 0.45 + target_delta * 0.55
            self.angle += self._cam_vel

        TURN = 0.052
        if keys[pygame.K_LEFT]:  self.angle -= TURN
        if keys[pygame.K_RIGHT]: self.angle += TURN

        wants_to_sprint = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        wants_to_move   = (keys[pygame.K_w] or keys[pygame.K_s] or
                           keys[pygame.K_UP] or keys[pygame.K_DOWN])

        if self.stamina <= 0:
            self.is_exhausted = True
        if self.is_exhausted and self.stamina >= 30:
            self.is_exhausted = False

        if wants_to_move and wants_to_sprint and not self.is_exhausted:
            current_speed = 7.0
            self.stamina -= 0.9
        else:
            current_speed = 4.0
            if self.stamina < self.max_stamina:
                recover_rate = 0.3 if self.is_exhausted else 0.5
                recover_rate += self.upgrades.get('stamina_recovery', 0) * 0.15
                self.stamina += recover_rate

        if self._trap_slow_timer > 0:
            self._trap_slow_timer -= 1
            current_speed *= 0.35

        self.stamina = max(0.0, min(self.stamina, self.max_stamina))

        dx = dy = 0.0

        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dx += math.cos(self.angle) * current_speed
            dy += math.sin(self.angle) * current_speed
            self.is_moving = True
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dx -= math.cos(self.angle) * current_speed
            dy -= math.sin(self.angle) * current_speed
            self.is_moving = True

        strafe_angle = self.angle + math.pi / 2
        if keys[pygame.K_a]:
            dx -= math.cos(strafe_angle) * current_speed
            dy -= math.sin(strafe_angle) * current_speed
            self.is_moving = True
        if keys[pygame.K_d]:
            dx += math.cos(strafe_angle) * current_speed
            dy += math.sin(strafe_angle) * current_speed
            self.is_moving = True

        # Apply knockback decay
        if abs(self._knockback_vx) > 0.1 or abs(self._knockback_vy) > 0.1:
            self._move(self._knockback_vx, self._knockback_vy)
            self._knockback_vx *= 0.72
            self._knockback_vy *= 0.72
        else:
            self._knockback_vx = self._knockback_vy = 0.0

        if dx or dy:
            self._move(dx, dy)

        # -- Weapon switching ---------------------------------------------
        if self._weapon_switch_cd > 0:
            self._weapon_switch_cd -= 1

        scroll = 0
        if hasattr(self, '_pending_scroll'):
            scroll = self._pending_scroll
            self._pending_scroll = 0

        if self._weapon_switch_cd == 0:
            switch_to = None
            if keys[pygame.K_1]:
                switch_to = WEAPON_PISTOL
            elif keys[pygame.K_2]:
                switch_to = WEAPON_SHOTGUN
            elif keys[pygame.K_3]:
                switch_to = WEAPON_SMG
            elif scroll != 0:
                idx = WEAPON_ORDER.index(self.weapon)
                idx = (idx + scroll) % len(WEAPON_ORDER)
                switch_to = WEAPON_ORDER[idx]
            if switch_to and switch_to != self.weapon:
                self.weapon = switch_to
                self._weapon_switch_cd = 12
                self._hint(f"Weapon: {self.weapon.upper()}", 60)

        mouse_buttons = pygame.mouse.get_pressed()
        shoot_pressed = keys[pygame.K_SPACE] or mouse_buttons[0]

        # -- Weapon fire stats (all damage values scale with 'damage' upgrade) ------
        # damage upgrade: each tier doubles the base damage of every weapon.
        # firerate upgrade: each tier cuts interval by a fixed amount per weapon.
        dmg_base_mult = 1 + self.upgrades.get('damage', 0)  # 1x, 2x, 3x ...
        fr_lvl = self.upgrades.get('firerate', 0)

        if self.weapon == WEAPON_PISTOL:
            fire_interval  = max(6,  22 - fr_lvl * 2)  # 22 -> 6 frames
            ammo_attr      = 'ammo_pistol'
            max_ammo_attr  = 'max_ammo_pistol'
            ammo_per_shot  = 1
            pellets        = 1
            spread_angle   = 0.0
            base_dmg       = 2 * dmg_base_mult          # 2, 4, 6 ...
            muzzle_frames  = 7
        elif self.weapon == WEAPON_SHOTGUN:
            fire_interval  = max(20, 42 - fr_lvl * 3)  # 42 -> 20 frames
            ammo_attr      = 'ammo_shotgun'
            max_ammo_attr  = 'max_ammo_shotgun'
            ammo_per_shot  = 1
            pellets        = 3                          # 3 pellets x 1 dmg = 3 total
            spread_angle   = 0.22
            base_dmg       = 1 * dmg_base_mult          # 1 per pellet -> 3 total, 6, 9 ...
            muzzle_frames  = 12
        else:  # SMG
            fire_interval  = max(3,  12 - fr_lvl * 1)  # 12 -> 3 frames
            ammo_attr      = 'ammo_smg'
            max_ammo_attr  = 'max_ammo_smg'
            ammo_per_shot  = 1
            pellets        = 1
            spread_angle   = 0.07
            base_dmg       = 1 * dmg_base_mult          # 1, 2, 3 ...
            muzzle_frames  = 5

        cur_ammo     = getattr(self, ammo_attr)
        cur_max_ammo = getattr(self, max_ammo_attr)

        if shoot_pressed and self.shooting_timer == 0 and cur_ammo >= ammo_per_shot:
            self.shooting_timer = fire_interval
            self.muzzle_flash   = muzzle_frames
            setattr(self, ammo_attr, cur_ammo - ammo_per_shot)
            sfx_map = {
                WEAPON_PISTOL:  self.sfx_shot_pistol,
                WEAPON_SHOTGUN: self.sfx_shot_shotgun,
                WEAPON_SMG:     self.sfx_shot_smg,
            }
            sfx = sfx_map.get(self.weapon, self.sfx_shot)
            if sfx:
                sfx.play()

            # Apply score multiplier to every kill done during this fire event
            hit_any = False

            for pellet in range(pellets):
                pspread = 0.0
                if pellets > 1:
                    pspread = (pellet / (pellets - 1) - 0.5) * 2 * spread_angle
                elif spread_angle > 0:
                    pspread = (self.rng.random() - 0.5) * 2 * spread_angle

                for e in sorted(
                    [e for e in self.enemies if e.alive],
                    key=lambda e: math.hypot(e.x-self.px, e.y-self.py)
                ):
                    ed = math.hypot(e.x - self.px, e.y - self.py)
                    ra = math.atan2(e.y - self.py, e.x - self.px) - self.angle - pspread
                    while ra >  math.pi: ra -= 2*math.pi
                    while ra < -math.pi: ra += 2*math.pi

                    aim_tolerance = 0.30 if not getattr(e, 'is_boss', False) else 0.45
                    if self.weapon == WEAPON_SHOTGUN:
                        aim_tolerance = 0.50
                    if abs(ra) < aim_tolerance and self.z_buffer[WIDTH//2] > ed:
                        if getattr(e, 'is_boss', False) and not getattr(e, 'is_miniboss', False) and self.boss and self.boss.invinc_active:
                            self._hint("INVINCIBLE! Wait for the shield to drop!", 60)
                            break

                        dmg = max(1, base_dmg)
                        e.health -= dmg
                        e.state = 'chase'
                        hit_any = True
                        if e.health <= 0:
                            e.alive = False
                            self.level_kills += 1
                            self._register_kill()
                            # Lifesteal: chance to heal on kill
                            lifesteal_lvl = self.upgrades.get('lifesteal', 0)
                            if lifesteal_lvl > 0 and self.rng.random() < lifesteal_lvl * 0.12:
                                healed = min(self.max_health - self.health, 3 + lifesteal_lvl)
                                self.health += healed
                                self.damage_numbers.append([int(e.x), int(e.y), f"+{healed} HP", COL_GREEN, 60])
                            if getattr(e, 'is_boss', False):
                                if getattr(e, 'is_miniboss', False):
                                    self._score_kill(3000)
                                    self.explosions.append({'x': e.x, 'y': e.y, 'timer': self.BOOM_DURATION * 3})
                                    self._play_death_sfx(is_boss=True)
                                    self._shake(14, 25)
                                    key_spr = self.key_imgs.get(self.keycard_color, self.key_imgs['red'])
                                    self.items.append(SpriteObject(e.x, e.y, key_spr, ITEM_KEY))
                                    self._hint("KILLDOZER DEFEATED! Grab the key and find the EXIT (north wall)!", 300)
                                else:
                                    self.boss_killed = True
                                    self._score_kill(5000)
                                    self.game_won = True
                                    self.explosions.append({'x': e.x, 'y': e.y, 'timer': self.BOOM_DURATION * 3})
                                    self._play_death_sfx(is_boss=True)
                                    self._shake(18, 40)
                                    if self.sfx_win and not self._win_played:
                                        self._win_played = True
                                        self.sfx_win.play()
                            elif isinstance(e, Rotta):
                                self._score_kill(75)
                                etype = 'rotta'
                                self._play_death_sfx()
                            elif e.is_flying:
                                self._score_kill(100)
                                etype = 'fly'
                                self._play_death_sfx()
                            else:
                                self._score_kill(50)
                                etype = 'ground'
                                self._play_death_sfx()
                            if not getattr(e, 'is_boss', False):
                                self.explosions.append({'x': e.x, 'y': e.y, 'timer': self.BOOM_DURATION})
                                self._shake(5, 8)
                                if not self.is_miniboss_level:
                                    self.respawn_queue.append(
                                        (ENEMY_RESPAWN_TICKS + self.rng.randint(-60, 120), etype)
                                    )
                                if self.rng.random() < 0.25:
                                    self.items.append(SpriteObject(e.x, e.y, self.box_img, ITEM_AMMO))
                        break  # each pellet hits at most one enemy; ricochet handled below

            # Ricochet: after a kill, bullet can chain to the nearest other enemy
            ricochet_lvl = self.upgrades.get('ricochet', 0)
            if hit_any and ricochet_lvl > 0 and self.rng.random() < ricochet_lvl * 0.15:
                for e2 in sorted(
                    [e for e in self.enemies if e.alive],
                    key=lambda e: math.hypot(e.x-self.px, e.y-self.py)
                ):
                    ed2 = math.hypot(e2.x - self.px, e2.y - self.py)
                    if ed2 > TILE_SIZE * 12:
                        break
                    ra2 = math.atan2(e2.y - self.py, e2.x - self.px) - self.angle
                    while ra2 >  math.pi: ra2 -= 2*math.pi
                    while ra2 < -math.pi: ra2 += 2*math.pi
                    # Must be roughly in front of player, within z-buffer range,
                    # AND have unobstructed LOS (no wall between player and target)
                    if abs(ra2) < 0.8 and self.z_buffer[WIDTH//2] > ed2 and \
                            self._has_los(self.px, self.py, e2.x, e2.y):
                        chain_dmg = max(1, int(2 * (1 + self.upgrades.get('damage', 0)) * 0.5))
                        e2.health -= chain_dmg
                        e2.state = 'chase'
                        self.damage_numbers.append([int(e2.x), int(e2.y), f"RICOCHET -{chain_dmg}", (255,80,200), 50])
                        if e2.health <= 0:
                            e2.alive = False
                            self.level_kills += 1
                            self._register_kill()
                            self._score_kill(30)
                            self._play_death_sfx()
                            self.explosions.append({'x': e2.x, 'y': e2.y, 'timer': self.BOOM_DURATION})
                        break

    # -- Shake helpers ----------------------------------------------------
    def _shake(self, intensity, duration):
        if not self.screen_shake_enabled:
            return
        if intensity > self.shake_intensity:
            self.shake_intensity = intensity
            self.shake_timer     = duration

    def _tick_shake(self):
        if self.shake_timer > 0:
            self.shake_timer -= 1
            frac = self.shake_timer / max(1, self.shake_intensity)
            mag  = self.shake_intensity * frac
            self._shake_ox = int((self.rng.random() - 0.5) * 2 * mag)
            self._shake_oy = int((self.rng.random() - 0.5) * 2 * mag)
        else:
            self.shake_intensity = 0
            self._shake_ox = self._shake_oy = 0

    # -- Score multiplier / streak tracker --------------------------------
    def _register_kill(self):
        """Every kill refreshes the streak timer. More kills = higher multiplier."""
        now = self.tick_count
        # Reset window: every kill resets the 3-second (180-tick) timer
        self._streak_timer = STREAK_WINDOW   # frames until multiplier expires
        self._streak_kills += 1

        # Determine multiplier tier based on total kills in current streak
        n = self._streak_kills
        new_tier = 0
        for i, threshold in enumerate(STREAK_THRESHOLDS):
            if n >= threshold:
                new_tier = i + 1

        if new_tier > self._streak_tier:
            self._streak_tier    = new_tier
            self._streak_msg     = STREAK_NAMES[new_tier - 1]
            self._streak_col     = STREAK_COLORS[new_tier - 1]
            self._streak_display = 120

    def _tick_streak(self):
        """Decay the streak timer each frame; reset kills+tier when it expires."""
        if self._streak_timer > 0:
            self._streak_timer -= 1
        if self._streak_timer == 0 and self._streak_kills > 0:
            self._streak_kills = 0
            self._streak_tier  = 0
            self._streak_display = 0

        if self._streak_display > 0:
            self._streak_display -= 1

    def _score_kill(self, base_pts):
        """Award base_pts scaled by the current streak multiplier."""
        mult = 1 + self._streak_tier   # 1x, 2x, 3x, 4x, 5x
        self.score += base_pts * mult

    def _update_boss_flicker(self):
        self.boss_flicker_timer -= 1
        if self.boss_flicker_timer <= 0:
            self.boss_flicker_timer = self.rng.randint(120, 300)
            self.boss_flicker_alpha = self.rng.randint(235, 255)

        if self.boss_flicker_alpha > 0:
            self.boss_flicker_alpha = max(0, self.boss_flicker_alpha - 0.8)

    # ------------------------------------------------------------------
    # Tick
    # ------------------------------------------------------------------
    def tick(self, events):
        for ev in events:
            if ev.type == pygame.MOUSEWHEEL:
                self._pending_scroll = -ev.y  # scroll down = next weapon
            if ev.type == pygame.KEYDOWN:
                if self.demo_mode:
                    # Any key press during demo exits back to menu
                    self._release_mouse()
                    return 'demo_exit'
                # Skip boss cutscene on any key (except escape)
                if self.boss_intro_timer > 60 and ev.key != pygame.K_ESCAPE:
                    self.boss_intro_timer = 60
                    self._cut_cam_x = self._cut_cam_y = self._cut_cam_a = None
                    continue
                if ev.key == pygame.K_ESCAPE:
                    self._release_mouse()
                    self._pause_timer()
                    return 'pause'
                if ev.key == pygame.K_l:
                    self.show_fps = not self.show_fps
                if ev.key == pygame.K_r and self.health <= 0:
                    self._release_mouse()
                    return 'restart'
                if ev.key == pygame.K_e and self.health > 0:
                    used_station = False
                    for item in self.items:
                        if item.item_type == 'upgrade_station':
                            if math.hypot(self.px - item.x, self.py - item.y) < TILE_SIZE * 2.5:
                                self._show_upgrade_menu()
                                used_station = True
                                break
                    if not used_station:
                        self._try_open_door()
            if ev.type == pygame.MOUSEBUTTONDOWN and self.demo_mode:
                self._release_mouse()
                return 'demo_exit'

        # Streak timer + display decay
        self._tick_streak()

        # Screen shake
        self._tick_shake()

        if self.health > 0 and not self.level_complete and not self.game_won:
            if self.boss_intro_timer <= 60:
                if self.demo_mode:
                    self.handle_demo_ai()
                    self.check_pickups()
                    self.update_doors()
                else:
                    self.handle_input()
                    self.move_enemies()
                    self.update_respawns()
                    self.update_pressure_spawner()
                    self.check_pickups()
                    self.update_doors()
                    if self.is_boss_level:
                        self.update_boss()
                    if self.is_miniboss_level:
                        self.update_miniboss()

        if self.level_complete:
            self.level_fade += 4
            if self.level_fade >= 255:
                self._release_mouse()
                return 'next_level'

        if self.game_won:
            self.level_fade += 2
            if self.level_fade >= 255:
                self._release_mouse()
                return 'game_won'

        self.screen.fill((0, 0, 0))
        # Apply screen shake offset via a subsurface offset blit
        ox, oy = self._shake_ox, self._shake_oy
        if ox or oy:
            # Render to a temporary surface offset by shake
            render_surf = pygame.Surface((WIDTH + abs(ox)*2, HEIGHT + abs(oy)*2))
            render_surf.fill((0, 0, 0))
            old_screen = self.screen
            self.screen = render_surf
            if self.boss_intro_timer == 0:
                self.draw_floor_and_ceiling()
                self.cast_rays()
                self.draw_sprites()
            else:
                self.draw_floor_and_ceiling()
            self.screen = old_screen
            self.screen.blit(render_surf, (ox, oy))
        else:
            if self.boss_intro_timer == 0:
                self.draw_floor_and_ceiling()
                self.cast_rays()
                self.draw_sprites()
            else:
                self.draw_floor_and_ceiling()

        if self.is_boss_level:
            self._update_boss_flicker()
            if self.boss_flicker_alpha > 0:
                flicker_surf = pygame.Surface((WIDTH, HEIGHT))
                flicker_surf.fill((0, 0, 0))
                flicker_surf.set_alpha(self.boss_flicker_alpha)
                self.screen.blit(flicker_surf, (0, 0))

        self.draw_ui()

        if self.level_complete:
            fade = pygame.Surface((WIDTH, HEIGHT))
            fade.fill((0, 0, 0))
            fade.set_alpha(min(255, self.level_fade))
            self.screen.blit(fade, (0, 0))
            msg = self.big_font.render(f"LEVEL {self.level} COMPLETE", True, COL_GOLD)
            self.screen.blit(msg, msg.get_rect(center=(WIDTH//2, HEIGHT//2)))

        if self.game_won:
            fade = pygame.Surface((WIDTH, HEIGHT))
            fade.fill((0, 0, 0))
            fade.set_alpha(min(200, self.level_fade))
            self.screen.blit(fade, (0, 0))
            draw_glowing_text(self.screen, "DRACULA IS SLAIN!", self.big_font,
                              COL_BOSS_BRIGHT, WIDTH//2, HEIGHT//2-20, centered=True)
            draw_glowing_text(self.screen, "She crumbles to dust...", self.font,
                              COL_GOLD, WIDTH//2, HEIGHT//2+30, centered=True)

        if self.show_fps:
            fps_val = int(self.clock.get_fps())
            fps_col = (80, 255, 80) if fps_val >= 55 else (255, 200, 50) if fps_val >= 30 else (255, 60, 60)
            fps_txt = self.small_font.render(f"FPS: {fps_val}", True, fps_col)
            self.screen.blit(fps_txt, (8, 8))

        if self.demo_mode:
            # Pulsing "DEMO MODE" banner
            pulse_a = int(abs(math.sin(self.tick_count * 0.04)) * 80 + 140)
            banner = pygame.Surface((WIDTH, 36), pygame.SRCALPHA)
            banner.fill((0, 0, 0, 180))
            self.screen.blit(banner, (0, HEIGHT - 36))
            demo_col = (255, 20, 147)
            draw_glowing_text(self.screen, "DEMO MODE  -  Press any key to return to menu",
                              self.small_font, demo_col, WIDTH // 2, HEIGHT - 28,
                              glow_color=(100, 0, 50), centered=True)
            # Top badge
            top_badge = pygame.Surface((160, 28), pygame.SRCALPHA)
            top_badge.fill((0, 0, 0, 160))
            self.screen.blit(top_badge, (WIDTH // 2 - 80, 0))
            draw_glowing_text(self.screen, "[ DEMO ]", self.small_font,
                              (255, 215, 0), WIDTH // 2, 4,
                              glow_color=(120, 80, 0), centered=True)

        return None


HIGHSCORE_FILE = os.path.join(BASE_PATH, "highscores.json")

def load_settings():
    """Load persistent settings from disk, returning defaults for missing keys."""
    defaults = {
        'sound_volume': 0.55,
        'sfx_volume': 0.75,
        'sfx_mode': 'normal',
        'mouse_sensitivity': MOUSE_SENSITIVITY,
        'screen_shake_enabled': True,
    }
    try:
        with open(SETTINGS_FILE, 'r') as f:
            saved = json.load(f)
        # Merge: saved values override defaults, unknown keys are ignored
        for k in defaults:
            if k in saved:
                defaults[k] = saved[k]
    except Exception:
        pass
    return defaults

def save_settings(settings):
    """Persist current settings to disk."""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass

def load_highscores():
    """Return {'by_score': [...], 'by_time': [...]} -- each up to 10 entries.
    Each entry: {'score': int, 'time': float, 'kills': int}.
    Migrates legacy flat-list format automatically."""
    try:
        with open(HIGHSCORE_FILE, "r") as f:
            raw = json.load(f)
        if isinstance(raw, list):
            # Migrate old flat list
            by_score = sorted(raw, key=lambda s: s['score'], reverse=True)[:10]
            by_time  = sorted([e for e in raw if e.get('time', 0) > 0],
                              key=lambda s: s['time'])[:10]
            return {'by_score': by_score, 'by_time': by_time}
        return {
            'by_score': raw.get('by_score', [])[:10],
            'by_time':  raw.get('by_time',  [])[:10],
        }
    except Exception:
        return {'by_score': [], 'by_time': []}


def save_highscore(score, time_secs, kills):
    """Insert run into both tables and persist. Returns (tables, score_record, time_record)."""
    tables = load_highscores()
    entry  = {'score': score, 'time': round(time_secs, 2), 'kills': kills}

    by_score = sorted(tables['by_score'] + [entry], key=lambda s: s['score'], reverse=True)[:10]
    by_time  = sorted(tables['by_time']  + [entry], key=lambda s: s['time'])[:10]

    new_tables = {'by_score': by_score, 'by_time': by_time}
    try:
        with open(HIGHSCORE_FILE, "w") as f:
            json.dump(new_tables, f, indent=2)
    except Exception:
        pass

    score_record = len(by_score) > 0 and by_score[0]['score'] == score and by_score[0]['kills'] == kills
    time_record  = len(by_time)  > 0 and by_time[0]['time']  == entry['time'] and by_time[0]['kills'] == kills
    return new_tables, score_record, time_record


# ---------------------------------------------------------------------------
# Win Screen
# ---------------------------------------------------------------------------
def show_win_screen(screen, font, big_font, small_font, score, speedrun_time, total_kills):
    clock  = pygame.time.Clock()
    t      = 0
    tab    = 'score'   # 'score' or 'time'
    particles = [
        (random.randint(0, WIDTH), random.randint(0, HEIGHT),
         random.uniform(-2, 2), random.uniform(-3, -0.5),
         random.choice([COL_ACCENT, COL_GOLD, COL_BOSS_BRIGHT, (255,255,255)]))
        for _ in range(80)
    ]

    tables, score_record, time_record = save_highscore(score, speedrun_time, total_kills)

    # Tab button rects -- defined once outside the loop so click-handling works
    hs_x, hs_y, hs_w = WIDTH//2 + 60, 148, 330
    tab_w = (hs_w - 12) // 2
    tab_score_rect = pygame.Rect(hs_x + 4,             hs_y + 4, tab_w, 26)
    tab_time_rect  = pygame.Rect(hs_x + tab_w + 8,     hs_y + 4, tab_w, 26)

    while True:
        t += 1
        mx, my = pygame.mouse.get_pos()

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_TAB:
                    tab = 'time' if tab == 'score' else 'score'
                else:
                    return
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                if tab_score_rect.collidepoint(mx, my):
                    tab = 'score'
                elif tab_time_rect.collidepoint(mx, my):
                    tab = 'time'
                else:
                    return

        # ---- background ----
        screen.fill(COL_DARK)
        for i in range(20):
            angle = math.radians(t * 0.5 + i * 18)
            r  = 200 + math.sin(t * 0.02 + i) * 30
            x  = int(WIDTH//2 + math.cos(angle) * r)
            y  = int(HEIGHT//2 + math.sin(angle) * r * 0.5)
            pygame.draw.circle(screen, (30,0,60), (x, y),
                               2 + int(abs(math.sin(t*0.03+i)) * 4))

        new_p = []
        for px2, py2, vx, vy, col in particles:
            px2 += vx; py2 += vy; vy += 0.08
            if py2 < HEIGHT:
                pygame.draw.circle(screen, col, (int(px2), int(py2)), 3)
                new_p.append((px2, py2, vx, vy, col))
            else:
                new_p.append((random.randint(0, WIDTH), -10,
                               random.uniform(-2, 2), random.uniform(-3, -0.5), col))
        particles = new_p

        pulse     = abs(math.sin(t * 0.05))
        title_col = tuple(int(COL_BOSS_BRIGHT[i]*pulse + COL_GOLD[i]*(1-pulse)) for i in range(3))
        draw_glowing_text(screen, "VICTORY!", big_font, title_col,
                          WIDTH//2, 58, glow_color=(80,0,120), centered=True)

        # record banner
        if score_record and time_record:   banner = "*** NEW SCORE + TIME RECORD ***"
        elif score_record:                 banner = "*** NEW HIGH SCORE ***"
        elif time_record:                  banner = "*** NEW FASTEST TIME ***"
        else:                              banner = "DRACULA HAS BEEN DESTROYED"
        b_col = COL_GOLD if (score_record or time_record) else (180, 160, 255)
        if not (score_record or time_record) or t % 60 < 40:
            draw_glowing_text(screen, banner, font, b_col,
                              WIDTH//2, 104, glow_color=(80,60,0), centered=True)

        # ---- run stats box (left) ----
        bx, by, bw, bh = WIDTH//2 - 460, 148, 390, 178
        draw_gradient_rect(screen, (20,5,35), (35,10,55), (bx, by, bw, bh))
        pygame.draw.rect(screen, COL_ACCENT, (bx, by, bw, bh), 2, border_radius=10)

        draw_glowing_text(screen, "FINAL SCORE", font, (200,150,255),
                          bx+bw//2, by+14, centered=True)
        sc2 = tuple(int(COL_GOLD[i]*pulse + 255*(1-pulse)) for i in range(3))
        draw_glowing_text(screen, f"{score:,}", big_font, sc2,
                          bx+bw//2, by+42, glow_color=(100,80,0), centered=True)
        pygame.draw.line(screen, COL_ACCENT2, (bx+16, by+90), (bx+bw-16, by+90), 1)

        tl = small_font.render("RUN TIME", True, (180,160,220))
        screen.blit(tl, tl.get_rect(center=(bx+bw//4, by+106)))
        tv_col = (255,255,80) if speedrun_time < 600 else COL_WHITE
        draw_glowing_text(screen, format_time(speedrun_time), font, tv_col,
                          bx+bw//4, by+125, glow_color=(80,80,0), centered=True)
        pygame.draw.line(screen, COL_ACCENT2, (bx+bw//2, by+96), (bx+bw//2, by+168), 1)

        kl = small_font.render("TOTAL KILLS", True, (180,160,220))
        screen.blit(kl, kl.get_rect(center=(bx+bw*3//4, by+106)))
        draw_glowing_text(screen, str(total_kills), font, (255,100,100),
                          bx+bw*3//4, by+125, glow_color=(100,0,0), centered=True)
        fl = small_font.render("You are the ultimate goon.", True, (180,140,220))
        screen.blit(fl, fl.get_rect(center=(bx+bw//2, by+160)))

        # ---- leaderboard panel (right) ----
        hs_h = 355
        draw_gradient_rect(screen, (10,3,25), (22,8,40), (hs_x, hs_y, hs_w, hs_h))
        pygame.draw.rect(screen, (80,20,120), (hs_x, hs_y, hs_w, hs_h), 2, border_radius=10)

        # Tab buttons
        for rect, label, tid in [(tab_score_rect,'BY SCORE','score'),
                                  (tab_time_rect, 'BY TIME', 'time')]:
            active = (tab == tid)
            hov    = rect.collidepoint(mx, my)
            bg     = (90,22,140) if active else ((40,12,60) if hov else (20,6,35))
            border = (220,90,255) if active else (90,35,120)
            pygame.draw.rect(screen, bg,     rect, border_radius=5)
            pygame.draw.rect(screen, border, rect, 1, border_radius=5)
            lt = small_font.render(label, True, (255,230,255) if active else (150,100,190))
            screen.blit(lt, lt.get_rect(center=rect.center))

        # Column headers
        hy = hs_y + 36
        for hdr, hx2 in [("#", hs_x+8), ("SCORE", hs_x+36),
                          ("TIME",  hs_x+168), ("KILLS", hs_x+262)]:
            ht2 = small_font.render(hdr, True, (140,100,200))
            screen.blit(ht2, (hx2, hy))
        pygame.draw.line(screen, (80,30,120), (hs_x+5, hy+18), (hs_x+hs_w-5, hy+18), 1)

        rows = tables['by_score'] if tab == 'score' else tables['by_time']
        for ri, entry in enumerate(rows[:10]):
            ry2     = hs_y + 58 + ri * 29
            is_this = (entry['score'] == score and
                       abs(entry.get('time', 0) - speedrun_time) < 1.0 and
                       entry.get('kills', -1) == total_kills)
            rc      = COL_GOLD if ri == 0 else (160,130,210)
            if is_this:
                hi = pygame.Surface((hs_w-8, 24), pygame.SRCALPHA)
                hi.fill((80,40,0,110))
                screen.blit(hi, (hs_x+4, ry2-2))
                rc = COL_GOLD

            screen.blit(small_font.render(f"#{ri+1}",                  True, rc),
                        (hs_x+8,   ry2))
            screen.blit(small_font.render(f"{entry['score']:,}",        True, rc),
                        (hs_x+36,  ry2))
            screen.blit(small_font.render(format_time(entry.get('time',0)), True, (160,220,160)),
                        (hs_x+168, ry2))
            screen.blit(small_font.render(str(entry.get('kills',0)),    True, (180,140,180)),
                        (hs_x+270, ry2))

        # footer hint
        if t % 80 < 55:
            hint = small_font.render("[TAB] switch sort  |  any other key to exit",
                                     True, (100,80,140))
            screen.blit(hint, hint.get_rect(center=(WIDTH//2, HEIGHT - 22)))

        pygame.display.flip()
        clock.tick(FPS)


# ---------------------------------------------------------------------------
# Menus
# ---------------------------------------------------------------------------
def show_main_menu(screen, font, small_font):
    pygame.mouse.set_visible(True)
    pygame.event.set_grab(False)

    bg_img = None
    bg_x = bg_y = 0
    try:
        raw = pygame.image.load(os.path.join(MEDIA_PATH, 'load.png')).convert_alpha()
        iw, ih = raw.get_size()
        scale = max(WIDTH / iw, HEIGHT / ih)
        sw, sh = int(iw * scale), int(ih * scale)
        scaled = pygame.transform.scale(raw, (sw, sh))
        bg_img = scaled
        bg_x = (WIDTH - sw) // 2
        bg_y = (HEIGHT - sh) // 2
    except Exception as e:
        pass

    btn_width, btn_height = 260, 56
    start_y = HEIGHT//2 - 10
    btns = [
        {"text": "NEW GAME", "action": "new",  "rect": pygame.Rect(WIDTH//2 - btn_width//2, start_y,       btn_width, btn_height)},
        {"text": "LOAD GAME","action": "load", "rect": pygame.Rect(WIDTH//2 - btn_width//2, start_y + 76,  btn_width, btn_height)},
        {"text": "[ DEMO ]", "action": "demo", "rect": pygame.Rect(WIDTH//2 - btn_width//2, start_y + 152, btn_width, btn_height)},
        {"text": "EXIT",     "action": "exit", "rect": pygame.Rect(WIDTH//2 - btn_width//2, start_y + 228, btn_width, btn_height)},
    ]

    clock = pygame.time.Clock()
    msg = ""
    msg_timer = 0
    t = 0
    menu_tab = 'score'   # leaderboard sidebar tab

    while True:
        t += 1
        screen.fill(COL_DARK)
        if bg_img:
            screen.blit(bg_img, (bg_x, bg_y))
        else:
            for i in range(12):
                angle = math.radians(t * 0.3 + i * 30)
                x = int(WIDTH//2 + math.cos(angle) * (180 + i*10))
                y = int(HEIGHT//3 + math.sin(angle*2) * 40)
                pygame.draw.circle(screen, (20,0,40), (x,y), 15)

        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        draw_gradient_rect(ov, (0,0,0,0), (0,0,0,180), (0,HEIGHT//2,WIDTH,HEIGHT//2))
        screen.blit(ov, (0,0))

        pulse = abs(math.sin(t * 0.04))
        title_col = (255, int(20 + pulse*40), int(100 + pulse*47))
        draw_glowing_text(screen, "GOON ETERNAL", font, title_col,
                          WIDTH//2, HEIGHT//2-120, glow_color=(100,0,50), centered=True)

        mx, my = pygame.mouse.get_pos()
        click = False

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                click = True

        for b in btns:
            hovered = b["rect"].collidepoint((mx, my))
            is_demo = b["action"] == "demo"
            if hovered:
                if is_demo:
                    draw_gradient_rect(screen, (180, 140, 0), (120, 90, 0), tuple(b["rect"]))
                else:
                    draw_gradient_rect(screen, (180, 20, 100), (140, 10, 80), tuple(b["rect"]))
            else:
                if is_demo:
                    draw_gradient_rect(screen, (80, 60, 0), (50, 35, 0), tuple(b["rect"]))
                else:
                    draw_gradient_rect(screen, (100, 10, 60), (60, 5, 40), tuple(b["rect"]))
            border_col = (255, 220, 80) if is_demo else ((255,150,200) if hovered else (255, 105, 180))
            pygame.draw.rect(screen, border_col, b["rect"], 2, border_radius=8)

            txt_col = (255, 220, 80) if is_demo else COL_WHITE
            txt = font.render(b["text"], True, txt_col)
            screen.blit(txt, txt.get_rect(center=b["rect"].center))

            if click and hovered:
                if b["action"] == "load":
                    if not os.path.exists(SAVE_FILE):
                        msg = "No save file found!"
                        msg_timer = 90
                    else:
                        return "load"
                elif b["action"] == "exit":
                    pygame.quit()
                    sys.exit()
                else:
                    return b["action"]

        if msg_timer > 0:
            mtxt = small_font.render(msg, True, (255, 80, 80))
            screen.blit(mtxt, mtxt.get_rect(center=(WIDTH//2, start_y + 240)))
            msg_timer -= 1

        # -- Highscore sidebar ------------------------------------------
        hs_data = load_highscores()
        by_score = hs_data.get('by_score', [])
        by_time  = hs_data.get('by_time',  [])
        if by_score or by_time:
            hs_x = WIDTH//2 + 155
            hs_y = start_y - 10
            hs_w = 220
            rows_to_show = min(5, max(len(by_score), len(by_time)))
            hs_h = 64 + rows_to_show * 24

            hsbg = pygame.Surface((hs_w, hs_h), pygame.SRCALPHA)
            hsbg.fill((0, 0, 0, 170))
            screen.blit(hsbg, (hs_x, hs_y))
            pygame.draw.rect(screen, (80, 20, 120), (hs_x, hs_y, hs_w, hs_h), 1, border_radius=6)

            # Mini tab buttons
            mtab_w = (hs_w - 10) // 2
            mtab_score = pygame.Rect(hs_x + 4,          hs_y + 4, mtab_w, 20)
            mtab_time  = pygame.Rect(hs_x + mtab_w + 6, hs_y + 4, mtab_w, 20)

            for ev2 in pygame.event.get(pygame.MOUSEBUTTONDOWN):
                if mtab_score.collidepoint(ev2.pos):
                    menu_tab = 'score'
                elif mtab_time.collidepoint(ev2.pos):
                    menu_tab = 'time'
                else:
                    pygame.event.post(ev2)  # put it back for button handling

            for rect2, lbl2, tid2 in [(mtab_score,'SCORE','score'),(mtab_time,'TIME','time')]:
                active2 = (menu_tab == tid2)
                pygame.draw.rect(screen, (70,18,110) if active2 else (18,5,28), rect2, border_radius=4)
                pygame.draw.rect(screen, (200,80,255) if active2 else (70,25,90), rect2, 1, border_radius=4)
                lt2 = small_font.render(lbl2, True, (240,220,255) if active2 else (120,80,160))
                screen.blit(lt2, lt2.get_rect(center=rect2.center))

            rows2 = by_score if menu_tab == 'score' else by_time
            col_lbl = small_font.render("SCORE" if menu_tab == 'score' else "TIME",
                                        True, (140,100,200))
            screen.blit(col_lbl, (hs_x + 44, hs_y + 28))

            for ri2, entry2 in enumerate(rows2[:5]):
                ry2 = hs_y + 44 + ri2 * 24
                rc2 = COL_GOLD if ri2 == 0 else (160,140,200)
                rk  = small_font.render(f"#{ri2+1}", True, rc2)
                if menu_tab == 'score':
                    val = small_font.render(f"{entry2['score']:,}", True, rc2)
                else:
                    val = small_font.render(format_time(entry2.get('time', 0)), True, (160,220,160))
                screen.blit(rk,  (hs_x + 8,  ry2))
                screen.blit(val, (hs_x + 44, ry2))

        pygame.display.flip()
        clock.tick(FPS)


def show_settings_menu(screen, font, small_font, tiny_font, game):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 200))
    bg = screen.copy()

    clock = pygame.time.Clock()

    sound_vol   = game.sound_volume
    sfx_vol     = game.sfx_volume
    sfx_mode    = game.sfx_mode
    sensitivity = game.mouse_sensitivity
    shake_on    = game.screen_shake_enabled

    slider_w = 280
    slider_h = 12
    sliders = {
        'sound': pygame.Rect(WIDTH//2 - slider_w//2, HEIGHT//2 - 120, slider_w, slider_h),
        'sfx':   pygame.Rect(WIDTH//2 - slider_w//2, HEIGHT//2 -  30, slider_w, slider_h),
        'sens':  pygame.Rect(WIDTH//2 - slider_w//2, HEIGHT//2 +  60, slider_w, slider_h),
    }

    back_btn    = pygame.Rect(WIDTH//2 - 120, HEIGHT//2 + 230, 240, 50)
    mode_btn    = pygame.Rect(WIDTH//2 - 120, HEIGHT//2 + 110, 240, 40)
    shake_btn   = pygame.Rect(WIDTH//2 - 120, HEIGHT//2 + 158, 240, 40)

    dragging = None

    while True:
        screen.blit(bg, (0, 0))
        screen.blit(overlay, (0, 0))

        draw_glowing_text(screen, "SETTINGS", font, COL_ACCENT, WIDTH//2, HEIGHT//2 - 220,
                          glow_color=(100,0,50), centered=True)

        mx, my = pygame.mouse.get_pos()
        click = False
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                click = True
                if sliders['sound'].inflate(0, 20).collidepoint(mx, my):
                    dragging = 'sound'
                elif sliders['sfx'].inflate(0, 20).collidepoint(mx, my):
                    dragging = 'sfx'
                elif sliders['sens'].inflate(0, 20).collidepoint(mx, my):
                    dragging = 'sens'
                elif mode_btn.collidepoint(mx, my):
                    sfx_mode = 'alt' if sfx_mode == 'normal' else 'normal'
                    game.sfx_mode = sfx_mode
                elif shake_btn.collidepoint(mx, my):
                    shake_on = not shake_on
                    game.screen_shake_enabled = shake_on
            if ev.type == pygame.MOUSEBUTTONUP:
                dragging = None
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return
            if ev.type == pygame.MOUSEMOTION and dragging:
                r = sliders[dragging]
                t = max(0.0, min(1.0, (mx - r.x) / r.width))
                if dragging == 'sound':
                    sound_vol = t
                    game.sound_volume = sound_vol
                    pygame.mixer.music.set_volume(sound_vol)
                elif dragging == 'sfx':
                    sfx_vol = t
                    game._set_sfx_volume(sfx_vol)
                elif dragging == 'sens':
                    sensitivity = 0.0005 + t * 0.006
                    game.mouse_sensitivity = sensitivity

        sv_lbl = font.render("Music Volume", True, (220, 180, 255))
        screen.blit(sv_lbl, sv_lbl.get_rect(center=(WIDTH//2, HEIGHT//2 - 150)))
        _draw_slider(screen, sliders['sound'], sound_vol, (200, 80, 255), (60, 200, 120))
        sv_pct = small_font.render(f"{int(sound_vol * 100)}%", True, COL_WHITE)
        screen.blit(sv_pct, (sliders['sound'].right + 12, sliders['sound'].y - 2))

        sfx_lbl = font.render("SFX Volume", True, (220, 180, 255))
        screen.blit(sfx_lbl, sfx_lbl.get_rect(center=(WIDTH//2, HEIGHT//2 - 60)))
        _draw_slider(screen, sliders['sfx'], sfx_vol, (255, 80, 180), (255, 200, 60))
        sfx_pct = small_font.render(f"{int(sfx_vol * 100)}%", True, COL_WHITE)
        screen.blit(sfx_pct, (sliders['sfx'].right + 12, sliders['sfx'].y - 2))

        sens_lbl = font.render("Mouse Sensitivity", True, (220, 180, 255))
        screen.blit(sens_lbl, sens_lbl.get_rect(center=(WIDTH//2, HEIGHT//2 + 30)))
        sens_t = (sensitivity - 0.0005) / 0.006
        _draw_slider(screen, sliders['sens'], sens_t, (255, 140, 60), (60, 180, 255))
        sens_txt = small_font.render(f"{sensitivity:.4f}", True, COL_WHITE)
        screen.blit(sens_txt, (sliders['sens'].right + 12, sliders['sens'].y - 2))

        mode_hov = mode_btn.collidepoint(mx, my)
        if mode_hov:
            draw_gradient_rect(screen, (80,10,80), (50,0,60), tuple(mode_btn))
        else:
            draw_gradient_rect(screen, (30,5,40), (20,0,30), tuple(mode_btn))
        pygame.draw.rect(screen, (200,80,255) if mode_hov else (120,40,160),
                         mode_btn, 2, border_radius=8)
        mode_lbl_txt = "Death SFX: NORMAL" if sfx_mode == 'normal' else "Death SFX: ALT"
        mode_col = (180,255,180) if sfx_mode == 'alt' else (255,200,255)
        mtxt = small_font.render(mode_lbl_txt, True, mode_col)
        screen.blit(mtxt, mtxt.get_rect(center=mode_btn.center))

        # Screen shake toggle
        shake_hov = shake_btn.collidepoint(mx, my)
        sbg_col = (30,50,30) if shake_on else (50,20,20)
        if shake_hov: sbg_col = tuple(min(255,c+30) for c in sbg_col)
        pygame.draw.rect(screen, sbg_col, shake_btn, border_radius=8)
        sborder = (100,255,100) if shake_on else (255,80,80)
        pygame.draw.rect(screen, sborder, shake_btn, 2, border_radius=8)
        shake_lbl_txt = "Screen Shake: ON" if shake_on else "Screen Shake: OFF"
        shake_col = (160,255,160) if shake_on else (255,140,140)
        stxt = small_font.render(shake_lbl_txt, True, shake_col)
        screen.blit(stxt, stxt.get_rect(center=shake_btn.center))

        hovered = back_btn.collidepoint(mx, my)
        if hovered:
            draw_gradient_rect(screen, (120,10,70), (80,0,50), tuple(back_btn))
        else:
            draw_gradient_rect(screen, (40,5,30), (25,0,20), tuple(back_btn))
        pygame.draw.rect(screen, (255,100,180) if hovered else COL_ACCENT, back_btn, 2, border_radius=8)
        btxt = font.render("Back", True, COL_WHITE)
        screen.blit(btxt, btxt.get_rect(center=back_btn.center))
        if click and hovered:
            return

        pygame.display.flip()
        clock.tick(FPS)


def _draw_slider(screen, rect, value, track_col, fill_col):
    pygame.draw.rect(screen, (40, 20, 60), rect, border_radius=6)
    fill_w = int(rect.width * max(0.0, min(1.0, value)))
    if fill_w > 0:
        fill_rect = pygame.Rect(rect.x, rect.y, fill_w, rect.height)
        pygame.draw.rect(screen, fill_col, fill_rect, border_radius=6)
    pygame.draw.rect(screen, track_col, rect, 2, border_radius=6)
    handle_x = rect.x + int(rect.width * max(0.0, min(1.0, value)))
    pygame.draw.circle(screen, COL_WHITE, (handle_x, rect.centery), 8)
    pygame.draw.circle(screen, track_col, (handle_x, rect.centery), 6)


def show_pause_menu(screen, font, small_font, tiny_font, game):
    pygame.mouse.set_visible(True)
    pygame.event.set_grab(False)
    pygame.mouse.get_rel()

    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))

    btn_width, btn_height = 290, 52
    start_y = HEIGHT//2 - 170

    btns = [
        {"text": "Continue", "action": "continue",
         "rect": pygame.Rect(WIDTH//2 - btn_width//2, start_y, btn_width, btn_height)},
        {"text": "Save Game", "action": "save",
         "rect": pygame.Rect(WIDTH//2 - btn_width//2, start_y + 68, btn_width, btn_height)},
        {"text": "Settings", "action": "settings",
         "rect": pygame.Rect(WIDTH//2 - btn_width//2, start_y + 136, btn_width, btn_height)},
        {"text": "Quit to Menu", "action": "menu",
         "rect": pygame.Rect(WIDTH//2 - btn_width//2, start_y + 204, btn_width, btn_height)},
        {"text": "Exit Game", "action": "exit",
         "rect": pygame.Rect(WIDTH//2 - btn_width//2, start_y + 272, btn_width, btn_height)},
    ]

    clock = pygame.time.Clock()
    bg = screen.copy()
    message = ""
    msg_timer = 0

    while True:
        screen.blit(bg, (0, 0))
        screen.blit(overlay, (0, 0))

        draw_glowing_text(screen, "PAUSED", font, COL_ACCENT, WIDTH//2, start_y - 56,
                          glow_color=(100,0,50), centered=True)

        elapsed = game.get_speedrun_elapsed()
        timer_line = small_font.render(f"Run Time: {format_time(elapsed)}", True, (255, 255, 100))
        screen.blit(timer_line, timer_line.get_rect(center=(WIDTH//2, start_y - 24)))
        kills_line = small_font.render(f"Total Kills: {game.total_kills + game.level_kills}", True, (200, 160, 255))
        screen.blit(kills_line, kills_line.get_rect(center=(WIDTH//2, start_y - 4)))

        mx, my = pygame.mouse.get_pos()
        click = False

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                click = True
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                game._capture_mouse()
                game._resume_timer()
                return 'continue'

        for b in btns:
            hovered = b["rect"].collidepoint((mx, my))
            if hovered:
                draw_gradient_rect(screen, (120,10,70), (80,0,50), tuple(b["rect"]))
            else:
                draw_gradient_rect(screen, (40,5,30), (25,0,20), tuple(b["rect"]))
            pygame.draw.rect(screen, (255,100,180) if hovered else COL_ACCENT, b["rect"], 2, border_radius=8)
            txt = font.render(b["text"], True, COL_WHITE)
            screen.blit(txt, txt.get_rect(center=b["rect"].center))

            if click and hovered:
                if b["action"] == "save":
                    elapsed_save = game.get_speedrun_elapsed()
                    state = {
                        'level': game.level, 'score': game.score,
                        'health': game.health, 'stamina': game.stamina,
                        'ammo_split': {
                            'pistol':  game.ammo_pistol,
                            'shotgun': game.ammo_shotgun,
                            'smg':     game.ammo_smg,
                        },
                        'weapon': game.weapon,
                        'px': game.px, 'py': game.py,
                        'angle': game.angle, 'keys_collected': game.keys_collected,
                        'speedrun_elapsed': elapsed_save,
                        'total_kills': game.total_kills + game.level_kills,
                        'upgrades': game.upgrades,
                        'tokens_held': game.tokens_held,
                        'max_health': game.max_health,
                        'max_stamina': game.max_stamina,
                        'run_seed': game.run_seed,
                        # streak state
                        'streak_kills': game._streak_kills,
                        'streak_timer': game._streak_timer,
                        'streak_tier':  game._streak_tier,
                    }
                    try:
                        with open(SAVE_FILE, "w") as f:
                            json.dump(state, f)
                        message = "Game Saved!"
                        msg_timer = 90
                    except Exception as e:
                        message = "Save failed!"
                        msg_timer = 90
                elif b["action"] == "settings":
                    show_settings_menu(screen, font, small_font, tiny_font, game)
                    bg = screen.copy()
                elif b["action"] == "continue":
                    game._capture_mouse()
                    game._resume_timer()
                    return 'continue'
                else:
                    return b["action"]

        if msg_timer > 0:
            c = COL_GREEN if "Saved" in message else COL_RED
            mtxt = small_font.render(message, True, c)
            screen.blit(mtxt, mtxt.get_rect(center=(WIDTH//2, start_y + 342)))
            msg_timer -= 1

        pygame.display.flip()
        clock.tick(FPS)


def show_loading_screen(screen, font, small_font, level):
    pygame.mouse.set_visible(True)
    pygame.event.set_grab(False)

    is_boss     = (level == BOSS_LEVEL)
    is_miniboss = (level == MINI_BOSS_LEVEL)
    is_demo     = (level == DEMO_LEVEL)
    screen.fill(COL_DARK if not is_boss else (5, 0, 10))
    load_img_surf = None
    lw2 = lh2 = 0
    try:
        raw  = pygame.image.load(os.path.join(MEDIA_PATH, 'load.png')).convert_alpha()
        lw, lh = raw.get_size()
        scale = min(WIDTH / lw, (HEIGHT - 140) / lh)
        lw2, lh2 = int(lw * scale), int(lh * scale)
        load_img_surf = pygame.transform.scale(raw, (lw2, lh2))
    except:
        pass

    if is_boss:
        lv_txt  = font.render("ENTERING THE BOSS CHAMBER...", True, COL_BOSS_BRIGHT)
        tip_txt = small_font.render("DRACULA has 300 HP. She goes invincible at 150 HP!", True, (200,100,255))
    elif is_miniboss:
        lv_txt  = font.render("THE KILLDOZER AWAITS...", True, (255, 140, 0))
        tip_txt = small_font.render("Kill KILLDOZER to drop the key - then find the exit (north wall)!", True, (255,200,100))
    elif is_demo:
        lv_txt  = font.render("DEMO - Combat Showcase Arena", True, (255, 215, 0))
        tip_txt = small_font.render("Watch the action unfold! Press any key to return to menu.", True, (200, 200, 100))
    else:
        lv_txt  = font.render(f"Loading Level {level}...", True, (255,182,193))
        tip_txt = small_font.render(random.choice([
            "Tip: Press E to open doors!",
            "Tip: Find the KEY before the exit!",
            "Tip: Dead enemies respawn - keep moving!",
            "Tip: Flying enemies deal double damage!",
            "Tip: The cyan door is the exit!",
            "Tip: Hold SHIFT to sprint away from Rottas!",
            "Tip: Your HP and ammo carry over between levels!",
            "Tip: Your max HP is 50 - healing items are vital!",
            "Tip: A/D strafes! Left click or SPACE to shoot.",
            f"Tip: Level 10 is the final boss - Dracula!",
            "Tip: Check walls for art! (or don't, it's fine)",
        ]), True, (180, 130, 200))

    bar_w = 400
    bar_x = WIDTH//2 - bar_w//2
    bar_y = HEIGHT - 18

    start = time.time()
    while True:
        elapsed  = time.time() - start
        progress = min(1.0, elapsed / 1.5)
        if is_miniboss:
            screen.fill((12, 8, 3))
        elif is_boss:
            screen.fill((5, 0, 10))
        else:
            screen.fill(COL_DARK)

        if load_img_surf:
            screen.blit(load_img_surf, (WIDTH//2 - lw2//2, HEIGHT//2 - lh2//2 - 30))
        else:
            draw_glowing_text(screen, "GOON ETERNAL", font, COL_ACCENT,
                              WIDTH//2, HEIGHT//2-40, centered=True)

        if is_boss:
            ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            ov.fill((60, 0, 0, 40))
            screen.blit(ov, (0,0))
        elif is_miniboss:
            ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            ov.fill((60, 30, 0, 30))
            screen.blit(ov, (0,0))

        screen.blit(lv_txt,  lv_txt.get_rect(center=(WIDTH//2, HEIGHT-70)))
        screen.blit(tip_txt, tip_txt.get_rect(center=(WIDTH//2, HEIGHT-45)))

        bar_col = COL_BOSS_BRIGHT if is_boss else ((255, 140, 0) if is_miniboss else COL_ACCENT)
        pygame.draw.rect(screen, (30,0,50), (bar_x, bar_y, bar_w, 12), border_radius=6)
        pygame.draw.rect(screen, bar_col, (bar_x, bar_y, int(bar_w*progress), 12), border_radius=6)

        pygame.display.flip()
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
        if progress >= 1.0:
            break
        pygame.time.delay(16)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    pygame.init()
    pygame.mixer.init()
    screen = pygame.display.set_mode((TOTAL_WIDTH, HEIGHT))
    pygame.display.set_caption("GOON ETERNAL")
    font       = pygame.font.SysFont('Georgia', 26, bold=True)
    big_font   = pygame.font.SysFont('Georgia', 44, bold=True)
    small_font = pygame.font.SysFont('Georgia', 18, bold=True)
    tiny_font  = pygame.font.SysFont('Georgia', 13)

    settings = load_settings()

    while True:
        pygame.mixer.music.stop()
        menu_action = show_main_menu(screen, font, small_font)

        level = 1
        prev_score = 0
        load_data = None
        carried_health = None
        carried_ammo   = None
        speedrun_start = None
        total_kills    = 0
        run_seed       = random.randint(0, 2**31)   # fresh random seed every new game

        if menu_action == 'load':
            try:
                with open(SAVE_FILE, "r") as f:
                    load_data = json.load(f)
                level = load_data.get('level', 1)
                prev_score = load_data.get('score', 0)
                saved_elapsed = load_data.get('speedrun_elapsed', 0.0)
                speedrun_start = time.time() - saved_elapsed
                total_kills = load_data.get('total_kills', 0)
                run_seed = load_data.get('run_seed', run_seed)  # preserve seed from save
            except Exception as e:
                print(f"Failed to load save: {e}")

        # ---- Demo mode ----
        if menu_action == 'demo':
            demo_running = True
            while demo_running:
                pygame.mixer.music.stop()
                show_loading_screen(screen, font, small_font, DEMO_LEVEL)
                demo_game = Game(
                    screen, level=DEMO_LEVEL, prev_score=0,
                    carried_health=50, carried_ammo=99,
                    speedrun_start=time.time(), total_kills=0,
                    sound_volume=settings['sound_volume'],
                    sfx_volume=settings['sfx_volume'],
                    sfx_mode=settings['sfx_mode'],
                    mouse_sensitivity=settings['mouse_sensitivity'],
                    carried_upgrades={'damage': 2, 'firerate': 2, 'health': 0,
                                      'stamina': 0, 'stamina_recovery': 0, 'ammo_cap': 0},
                    carried_tokens=0,
                    run_seed=random.randint(0, 2**31),
                    demo_mode=True,
                )
                pygame.mouse.set_visible(True)
                pygame.event.set_grab(False)

                demo_clock = pygame.time.Clock()
                while demo_running:
                    events = pygame.event.get()
                    for ev in events:
                        if ev.type == pygame.QUIT:
                            pygame.quit()
                            sys.exit()
                        # Any key/click ends the demo and returns to menu
                        if ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                            demo_running = False
                            break

                    if not demo_running:
                        break

                    result = demo_game.tick(events)
                    pygame.display.flip()
                    demo_clock.tick(FPS)

                    if result == 'demo_exit':
                        demo_running = False
                        break

            continue  # Return to main menu loop
        # ---- End demo mode ----

        carried_upgrades = None
        carried_tokens   = 0
        in_game = True

        while in_game:
            update_discord(level, prev_score)
            show_loading_screen(screen, font, small_font, level)
            game = Game(
                screen, level=level, prev_score=prev_score, load_data=load_data,
                carried_health=carried_health, carried_ammo=carried_ammo,
                speedrun_start=speedrun_start, total_kills=total_kills,
                sound_volume=settings['sound_volume'],
                sfx_volume=settings['sfx_volume'],
                sfx_mode=settings['sfx_mode'],
                mouse_sensitivity=settings['mouse_sensitivity'],
                carried_upgrades=carried_upgrades,
                carried_tokens=carried_tokens,
                run_seed=run_seed,
                screen_shake_enabled=settings['screen_shake_enabled'],
            )
            load_data = None
            if speedrun_start is None:
                speedrun_start = game.speedrun_start

            clock = pygame.time.Clock()

            while in_game:
                events = pygame.event.get()
                for ev in events:
                    if ev.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit()

                result = game.tick(events)

                if result == 'pause':
                    pause_action = show_pause_menu(screen, font, small_font, tiny_font, game)
                    settings['sound_volume'] = game.sound_volume
                    settings['sfx_volume']   = game.sfx_volume
                    settings['sfx_mode']     = game.sfx_mode
                    settings['mouse_sensitivity'] = game.mouse_sensitivity
                    settings['screen_shake_enabled'] = game.screen_shake_enabled
                    save_settings(settings)
                    if pause_action == 'menu':
                        in_game = False
                        break
                    elif pause_action == 'exit':
                        pygame.quit()
                        sys.exit()

                pygame.display.flip()
                game.clock.tick(FPS)

                if result == 'game_won':
                    final_time = game.get_speedrun_elapsed()
                    final_kills = game.total_kills + game.level_kills
                    show_win_screen(screen, font, big_font, small_font,
                                    game.score, final_time, final_kills)
                    in_game = False
                    break
                elif result == 'next_level':
                    prev_score     = game.score
                    carried_health = game.health
                    carried_ammo   = {
                        'pistol':  game.ammo_pistol,
                        'shotgun': game.ammo_shotgun,
                        'smg':     game.ammo_smg,
                    }
                    carried_upgrades = game.upgrades
                    carried_tokens   = game.tokens_held
                    run_seed       = game.run_seed
                    speedrun_start = game.speedrun_start
                    total_kills    = game.total_kills + game.level_kills
                    settings['sound_volume'] = game.sound_volume
                    settings['sfx_volume']   = game.sfx_volume
                    settings['sfx_mode']     = game.sfx_mode
                    settings['mouse_sensitivity'] = game.mouse_sensitivity
                    settings['screen_shake_enabled'] = game.screen_shake_enabled
                    save_settings(settings)
                    level += 1
                    break
                elif result == 'restart':
                    level            = 1
                    prev_score       = 0
                    carried_health   = None
                    carried_ammo     = None
                    carried_upgrades = None
                    carried_tokens   = 0
                    speedrun_start   = None
                    total_kills      = 0
                    break


if __name__ == "__main__":
    main()
