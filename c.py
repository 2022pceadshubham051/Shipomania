import logging
import asyncio
import random
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from telegram.error import TelegramError, Forbidden, BadRequest
from collections import defaultdict
import json

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ======================== CONFIGURATION ========================
BOT_TOKEN = '8318859222:AAHQAINsicVy2I6Glu6Hj_d57pIIghGUnUU'
ADMIN_IDS = [7460266461, 7379484662, 8049934625]
SUPPORTIVE_GROUP_ID = -1002707382739

# ======================== DATABASE SETUP ========================
def init_database():
    """Initialize SQLite database for persistent data."""
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS players (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        total_games INTEGER DEFAULT 0,
        wins INTEGER DEFAULT 0,
        kills INTEGER DEFAULT 0,
        deaths INTEGER DEFAULT 0,
        damage_dealt INTEGER DEFAULT 0,
        damage_taken INTEGER DEFAULT 0,
        heals_done INTEGER DEFAULT 0,
        loots_collected INTEGER DEFAULT 0,
        win_streak INTEGER DEFAULT 0,
        best_streak INTEGER DEFAULT 0,
        last_played TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS game_history (
        game_id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        winner_id INTEGER,
        winner_name TEXT,
        total_players INTEGER,
        total_rounds INTEGER,
        start_time TEXT,
        end_time TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS group_settings (
        chat_id INTEGER PRIMARY KEY,
        join_time INTEGER DEFAULT 120,
        operation_time INTEGER DEFAULT 120,
        min_players INTEGER DEFAULT 2,
        max_players INTEGER DEFAULT 20,
        allow_spectators INTEGER DEFAULT 1
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS player_achievements (
        user_id INTEGER,
        achievement TEXT,
        unlocked_at TEXT,
        PRIMARY KEY (user_id, achievement)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS banned_players (
        chat_id INTEGER,
        user_id INTEGER,
        PRIMARY KEY (chat_id, user_id)
    )''')
    
    conn.commit()
    conn.close()

init_database()

# ======================== GIF COLLECTIONS ========================
GIFS = {
    'joining': [
        'https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExMDM1YXJoY3hldW9lbGc3bzF1NXh0a3R3eWFxeHY5anNyNTM4ZGcwdSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/fbweTsoLncIri6UZQ7/giphy.gif',
        'https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExeThsZ2ExOHZjN2t4ZzZndTVtY3llZHBqczZhaWF3Ymo2Ynhzb293cCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/kEVjWx3z32V8MW6K4M/giphy.gif',
        'https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExbDdqdWxwNTd2emV6dG1tanNkZmwwdjBiNmp6ZXFlNXd2N2w3ZWR5dCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/5BzeAQ175PkadFk8lZ/giphy.gif'
    ],
    'start': [
        'https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExZ3NqczloM295OHM3MG5rdTF1dXFlMWswMnE4b2V1NnJoNzNwcGRveSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/JTbY3urUF1sSV6O8u2/giphy.gif',
        'https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExbXk5Z3ozY3R1OXI0a2hjcWN5dnBpdHJnZDd1NHFrZjE3bzY0dDNvayZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/lnDHpizt0ebLdFLaqd/giphy.gif',
        'https://media.giphy.com/media/3o7TKPATxjC5VJhPKo/giphy.gif'
    ],
    'operation': [
        'https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3a3NseTlkaWppM3lpZGpuejBrb29rbG84ZXR6OXNiYXVvcGNpMDR4ZCZlcD12MV9naWZzX3JlbGF0ZWQmY3Q9Zw/0tHC1XOhyAoK9KPMkz/giphy.gif',
        'https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExNGEwZDVyazZhOTJhb2lsNG0xdjllc3hrcDNpemVlb2M1ZHV6dmMyciZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/GGEmK9eMz3PVgxHjD3/giphy.gif',
'https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExbGliNGxidWNmczkyaGQ3cGpjeWt5em43YnA0aGVwZmF4Y3RubXJwdiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/rFxIAqcOpfzcXQEgrw/giphy.gif'
    ],
    'day_summary': [
        'https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExaXdxd2NsMjV4ZGF1NDhycXJiMmlybjZ5YmdjbWFlcTk3N3dqOGxiMyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/c41Vg6E0tqOuxk32rH/giphy.gif',
        'https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExODl6NG96eTV1c3pvZGU3dWUzaGk0bWMwaDhibWN3MXhyNG5ubW9qeCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/BYcWkvGqvvFqRgQ2Vm/giphy.gif',
'https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExb3Z0eWd3c2llaWNtbnp3d3F4bDBlbTl3ZnBjNmtieXBkMjluNTZnYyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/BIyzgq3lnNmhxYWv32/giphy.gif',
'https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExbmc3Y3lncXU4azd5bW1uN2owMGtwNHhuNnphMW9sMjI4YXNuaWU1cSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/zPpo787qbLEJ1S4Z0C/giphy.gif',
'https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExeWZ1dDZxeGhra2QweHZsYWlia2g2a3MzNzNzcXE0ZGpmZ3lqZTZzdCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/fUeFfa117JhyRLpVyV/giphy.gif',
'https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExYWJxbW9nN3UycWp6NzBpYWQ0dnVncDgxaHRxOWt2OXY0Yzd6M2VqZSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/k31lneLEJCRPT7lHHA/giphy.gif',
'https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExcHY5YnprM3J3MWQwNHZnZTlwcXludTVqOHQ4MWltNXo4OWFnN3Y5ZCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/m93WvfVRJqyTF0YW1u/giphy.gif'
    ],
    'victory': [
        'https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExbnhhNGUwdTE3ajc5M2w5bTZiY3I2ZjB3d3lra2dkd3Bid2VzN3JheCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/LS9LaplvNW3pdgfotU/giphy.gif',
        'https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExdXE2djB1dmc2cDJwZm5vbjhlMnZzbnNpOG0wZHpxY2V5OGp3dDZucSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/Q5vYhbuKoqZZpnVjLB/giphy.gif',
        'https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExaTlhNDBlY3JudXl6enhqdHBpcHA3dmlsM3g2aW03MnZucWg5Nm40bSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/EeTwHqk6WROjXPwAuv/giphy.gif',
'https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExZHRvMjZjZGd0eGwybDllNmxoejVwZ3gxZW5tZXp4b3V5NW1ia2h5ayZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/KCjWgrlSD75yhobhfa/giphy.gif'
    ],
    'eliminated': [
        'https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExd2V4cDU2cmNud2Y4YmhjMWR6c3lzaWFiZnZ6c3Vja3AxOXNxczhueSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/CplBQMJQvucceS53Dx/giphy.gif',
        'https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExand5dW1ua2VxejlndXNlMnF0cGtrZzQ0MmE4cHh2MDExeTd4a3ZsMyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/JzUf8zxxOmm2Byt60A/giphy.gif',
'https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExZnN5Z2I1Njd3eHU4N2FubGJzY2k1cjRtOXQ2N2w1dGJoY2ZmdXlnciZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/w5o2yikw2bK60zsnPR/giphy.gif'
    ],
    'extend': [
        'https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExNnY5YmtrcnZnMGl3NnRoZXlqbXBmYnVoZnJ5aWQ4bmZqZnh3Z2Q5ZSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/dYmF4olecsBFf6tHD5/giphy.gif'
    ],
    'rules': 'https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExZjIxYTRndTgxd3Z4Y3Vsd3hudmU3NXVuemlpODhuNGR6ZXdjdjc2dCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/S5WkrHtbicZXPc5tay/giphy.gif',
    'event': 'https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExYmw4M3o5M21zaHF2eXZ6ejRkNmZtYnlsaTJpa3Nocmo3cHc3bzV6biZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/be2r19iT40ytEpiGAH/giphy.gif',
    'meteor': 'https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExcXcxczg3M3ByMGI1MzFvYW4zZ3E2dzI0ZDJvYmx0a2xzdGM0OHNzcSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/dD114a2D1TwEUscuMs/giphy.gif',
    'boost': 'https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExd3N4YWdkdmRoazNtczNpamY2cnRrMHdwYTBncHBta2oyYmR6cDMzaCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/v532chtg1u147AIixq/giphy.gif'
}

# ======================== GAME CONSTANTS ========================
HP_START = 100
ATTACK_DAMAGE = (20, 25)
HEAL_AMOUNT = (8, 16)
LOOT_HP = (1,4 )
DEFEND_REDUCTION = 0.5
CRIT_CHANCE = 0.20
CRIT_MULTIPLIER = 1.5
AFK_TURNS_LIMIT = 3
MAP_SIZE = 5
ATTACK_RANGE = 2

LOOT_ITEMS = {
    'laser_gun': {'type': 'weapon', 'bonus': 20, 'rarity': 'rare', 'emoji': '🔫'},
    'plasma_cannon': {'type': 'weapon', 'bonus': 35, 'rarity': 'epic', 'emoji': '💥'},
    'health_kit': {'type': 'potion', 'bonus': 30, 'rarity': 'common', 'emoji': '💊'},
    'mega_potion': {'type': 'potion', 'bonus': 60, 'rarity': 'rare', 'emoji': '🧪'},
    'shield_gen': {'type': 'shield', 'bonus': 0.3, 'rarity': 'rare', 'emoji': '🛡️'},
    'fortress_shield': {'type': 'shield', 'bonus': 0.5, 'rarity': 'epic', 'emoji': '🏰'},
    'energy_core': {'type': 'energy', 'bonus': 15, 'rarity': 'common', 'emoji': '⚡'},
    'quantum_core': {'type': 'energy', 'bonus': 30, 'rarity': 'epic', 'emoji': '✨'}
}

RARITY_WEIGHTS = {'common': 50, 'rare': 30, 'epic': 15, 'legendary': 5}

# ======================== COSMIC EVENTS ========================
COSMIC_EVENTS = {
    'meteor_storm': {
        'name': '☄️ Meteor Storm',
        'desc': 'Cosmic debris damages all ships!',
        'effect': 'damage_all',
        'value': (15, 30),
        'emoji': '☄️'
    },
    'solar_boost': {
        'name': '🌟 Solar Boost',
        'desc': 'Solar energy heals all ships!',
        'effect': 'heal_all',
        'value': (20, 35),
        'emoji': '🌟'
    },
    'wormhole': {
        'name': '🌀 Wormhole Teleport',
        'desc': 'Random ships teleport to new positions!',
        'effect': 'teleport',
        'value': None,
        'emoji': '🌀'
    },
    'energy_surge': {
        'name': '⚡ Energy Surge',
        'desc': 'Next attacks deal bonus damage!',
        'effect': 'damage_boost',
        'value': 1.5,
        'emoji': '⚡'
    },
    'pirate_ambush': {
        'name': '🏴‍☠️ Pirate Ambush',
        'desc': 'Space pirates attack random ships!',
        'effect': 'random_damage',
        'value': (20, 40),
        'emoji': '🏴‍☠️'
    },
    'asteroid_field': {
        'name': '🪨 Asteroid Field',
        'desc': 'Navigation hazard - all take light damage!',
        'effect': 'damage_all',
        'value': (10, 20),
        'emoji': '🪨'
    },
    'nebula_shield': {
        'name': '🌌 Nebula Shield',
        'desc': 'Cosmic nebula provides temporary shields!',
        'effect': 'shield_all',
        'value': 0.3,
        'emoji': '🌌'
    }
}

# ======================== ACHIEVEMENTS ========================
ACHIEVEMENTS = {
    'first_blood': {'name': 'First Blood', 'desc': 'Get your first kill', 'emoji': '🩸'},
    'killer': {'name': 'Killer', 'desc': 'Get 5 kills in a single game', 'emoji': '💀'},
    'survivor': {'name': 'Survivor', 'desc': 'Win your first game', 'emoji': '🏆'},
    'champion': {'name': 'Champion', 'desc': 'Win 10 games', 'emoji': '👑'},
    'collector': {'name': 'Collector', 'desc': 'Collect 50 items', 'emoji': '📦'},
    'healer': {'name': 'Medic', 'desc': 'Heal 1000 HP total', 'emoji': '💉'},
    'damage_dealer': {'name': 'Destroyer', 'desc': 'Deal 5000 damage total', 'emoji': '⚡'},
    'streak_3': {'name': '3-Win Streak', 'desc': 'Win 3 games in a row', 'emoji': '🔥'},
    'team_player': {'name': 'Team Player', 'desc': 'Win a team game', 'emoji': '🤝'},
    'explorer': {'name': 'Space Explorer', 'desc': 'Move 50 times on the map', 'emoji': '🧭'}
}

# ======================== GAME CLASS ========================
class Game:
    def __init__(self, chat_id, creator_id, creator_name):
        self.game_id = None
        self.chat_id = chat_id
        self.creator_id = creator_id
        self.creator_name = creator_name
        self.mode = None
        self.players = {}
        self.spectators = set()
        self.day = 0
        self.joining_message_id = None
        self.is_joining = False
        self.is_active = False
        self.join_end_time = None
        self.operation_end_time = None
        self.settings = self.load_settings()
        self.start_time = datetime.now()
        self.total_damage = 0
        self.total_heals = 0
        self.operations_log = []
        self.active_event = None
        self.event_effect = None
        self.map_grid = [[[] for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
        self.teams = {'alpha': set(), 'beta': set()}
        
    def load_settings(self):
        """Load group settings."""
        conn = sqlite3.connect('ship_battle.db')
        c = conn.cursor()
        c.execute('SELECT * FROM group_settings WHERE chat_id = ?', (self.chat_id,))
        settings = c.fetchone()
        conn.close()
        
        if settings:
            return {
                'join_time': settings[1],
                'operation_time': settings[2],
                'min_players': settings[3],
                'max_players': settings[4],
                'allow_spectators': settings[5]
            }
        return {
            'join_time': 120,
            'operation_time': 120,
            'min_players': 2,
            'max_players': 15,
            'allow_spectators': 1
        }
    
    def add_player(self, user_id, username, first_name, team=None):
        """Add player with detailed stats."""
        if len(self.players) >= self.settings['max_players']:
            return False, "🚫 Fleet at max capacity!"
        
        if user_id not in self.players:
            # Random starting position
            x, y = random.randint(0, MAP_SIZE-1), random.randint(0, MAP_SIZE-1)
            self.map_grid[x][y].append(user_id)
            
            self.players[user_id] = {
                'user_id': user_id,
                'username': username or first_name,
                'first_name': first_name,
                'hp': HP_START,
                'max_hp': HP_START,
                'inventory': [],
                'operation': None,
                'target': None,
                'position': (x, y),
                'team': team,
                'afk_turns': 0,
                'stats': {
                    'kills': 0,
                    'damage_dealt': 0,
                    'damage_taken': 0,
                    'heals_done': 0,
                    'loots': 0,
                    'moves': 0
                },
                'alive': True,
                'last_action_time': None
            }
            
            if team:
                self.teams[team].add(user_id)
            
            return True, "✅ Joined successfully!"
        return False, "⚠️ Already joined!"
    
    def get_alive_players(self):
        """Get list of alive player IDs."""
        return [uid for uid, data in self.players.items() if data['alive']]
    
    def get_alive_team_players(self, team):
        """Get alive players from a specific team."""
        return [uid for uid in self.teams[team] if self.players[uid]['alive']]
    
    def get_players_in_range(self, user_id, attack_range=ATTACK_RANGE):
        """Get players within attack range."""
        if user_id not in self.players:
            return []
        
        player = self.players[user_id]
        px, py = player['position']
        targets = []
        
        for target_id, target in self.players.items():
            if target_id == user_id or not target['alive']:
                continue
            
            # Team mode: can't attack teammates
            if self.mode == 'team' and player['team'] == target['team']:
                continue
            
            tx, ty = target['position']
            distance = abs(px - tx) + abs(py - ty)  # Manhattan distance
            
            if distance <= attack_range:
                targets.append(target_id)
        
        return targets
    
    def move_player(self, user_id, direction):
        """Move player on the map."""
        if user_id not in self.players:
            return False
        
        player = self.players[user_id]
        x, y = player['position']
        
        # Remove from old position
        self.map_grid[x][y].remove(user_id)
        
        # Calculate new position
        if direction == 'up' and x > 0:
            x -= 1
        elif direction == 'down' and x < MAP_SIZE - 1:
            x += 1
        elif direction == 'left' and y > 0:
            y -= 1
        elif direction == 'right' and y < MAP_SIZE - 1:
            y += 1
        
        # Update position
        player['position'] = (x, y)
        self.map_grid[x][y].append(user_id)
        player['stats']['moves'] += 1
        
        return True
    
    def get_map_display(self):
        """Generate map visualization."""
        map_str = "🗺️ **Battle Map** (5x5)\n\n----x----x----x----\n"
        
        for i in range(MAP_SIZE):
            row = ""
            for j in range(MAP_SIZE):
                cell_players = self.map_grid[i][j]
                if not cell_players:
                    row += "⬜"
                else:
                    alive_count = sum(1 for uid in cell_players if self.players[uid]['alive'])
                    if alive_count == 0:
                        row += "⬜"
                    elif alive_count == 1:
                        row += "🟦"
                    else:
                        row += "🟥"
                row += " "
            map_str += row + "\n"
        
        map_str += "\n⬜ Empty | 🟦 1 Ship | 🟥 Multiple Ships"
        return map_str
    
    def get_player_rank(self, user_id):
        """Get player's current rank."""
        alive = self.get_alive_players()
        return len(alive) - alive.index(user_id) + 1 if user_id in alive else len(self.players) + 1

# ======================== DATABASE HELPERS ========================
def update_player_stats(user_id, username, stats_update):
    """Update player statistics."""
    try:
        conn = sqlite3.connect('ship_battle.db')
        c = conn.cursor()
        
        c.execute('SELECT user_id FROM players WHERE user_id = ?', (user_id,))
        if not c.fetchone():
            c.execute('''INSERT INTO players (user_id, username) VALUES (?, ?)''',
                     (user_id, username))
        
        update_fields = []
        values = []
        for key, value in stats_update.items():
            update_fields.append(f"{key} = {key} + ?")
            values.append(value)
        
        values.append(datetime.now().isoformat())
        values.append(user_id)
        
        query = f"UPDATE players SET {', '.join(update_fields)}, last_played = ? WHERE user_id = ?"
        c.execute(query, values)
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error updating stats: {e}")

def unlock_achievement(user_id, achievement_key):
    """Unlock achievement for player."""
    try:
        conn = sqlite3.connect('ship_battle.db')
        c = conn.cursor()
        c.execute('''INSERT OR IGNORE INTO player_achievements (user_id, achievement, unlocked_at)
                     VALUES (?, ?, ?)''', (user_id, achievement_key, datetime.now().isoformat()))
        rows = c.rowcount
        conn.commit()
        conn.close()
        return rows > 0
    except Exception as e:
        logger.error(f"Error unlocking achievement: {e}")
        return False

def get_player_achievements(user_id):
    """Get player's achievements."""
    try:
        conn = sqlite3.connect('ship_battle.db')
        c = conn.cursor()
        c.execute('SELECT achievement FROM player_achievements WHERE user_id = ?', (user_id,))
        achievements = [row[0] for row in c.fetchall()]
        conn.close()
        return achievements
    except:
        return []

def save_game_history(game, winner_id, winner_name):
    """Save game to history."""
    try:
        conn = sqlite3.connect('ship_battle.db')
        c = conn.cursor()
        c.execute('''INSERT INTO game_history 
                     (chat_id, winner_id, winner_name, total_players, total_rounds, start_time, end_time)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                 (game.chat_id, winner_id, winner_name, len(game.players),
                  game.day, game.start_time.isoformat(), datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error saving game: {e}")

def get_leaderboard(limit=10):
    """Get top players."""
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    c.execute('''SELECT username, wins, total_games, kills, damage_dealt 
                 FROM players 
                 ORDER BY wins DESC, kills DESC 
                 LIMIT ?''', (limit,))
    results = c.fetchall()
    conn.close()
    return results

def get_player_stats(user_id):
    """Get player statistics."""
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    c.execute('SELECT * FROM players WHERE user_id = ?', (user_id,))
    stats = c.fetchone()
    conn.close()
    return stats

# ======================== UTILITY FUNCTIONS ========================
def get_random_gif(category):
    """Get random GIF from category."""
    if category in GIFS and isinstance(GIFS[category], list):
        return random.choice(GIFS[category])
    return GIFS.get(category, GIFS['joining'][0])

def get_progress_bar(current, maximum, length=10):
    """Generate progress bar."""
    filled = int((current / maximum) * length)
    bar = '█' * filled + '░' * (length - filled)
    percentage = int((current / maximum) * 100)
    return f"{bar} {percentage}%"

def format_time(seconds):
    """Format seconds to MM:SS."""
    mins, secs = divmod(max(0, int(seconds)), 60)
    return f"{mins:02d}:{secs:02d}"

def get_rarity_color(rarity):
    """Get color emoji for rarity."""
    colors = {
        'common': '⚪',
        'rare': '🔵',
        'epic': '🟣',
        'legendary': '🟠'
    }
    return colors.get(rarity, '⚪')

def get_hp_indicator(hp, max_hp):
    """Get HP color indicator."""
    ratio = hp / max_hp
    if ratio > 0.75:
        return "🟢"
    elif ratio > 0.25:
        return "🟡"
    else:
        return "🔴"

async def safe_send(context, chat_id, text, **kwargs):
    """Safely send message with error handling."""
    try:
        return await context.bot.send_message(chat_id, text, **kwargs)
    except Forbidden:
        logger.warning(f"Bot blocked by user {chat_id}")
    except BadRequest as e:
        logger.error(f"Bad request: {e}")
    except Exception as e:
        logger.error(f"Send error: {e}")
    return None

async def safe_send_animation(context, chat_id, animation, caption, **kwargs):
    """Safely send animation."""
    try:
        return await context.bot.send_animation(chat_id, animation, caption=caption, **kwargs)
    except Exception as e:
        logger.error(f"Animation send error: {e}")
        return await safe_send(context, chat_id, caption, **kwargs)

async def is_admin(context, chat_id, user_id):
    """Check if user is admin."""
    if user_id in ADMIN_IDS:
        return True
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except:
        return False

def trigger_cosmic_event():
    """Randomly trigger a cosmic event."""
    if random.random() < 0.3:  # 30% chance
        event_key = random.choice(list(COSMIC_EVENTS.keys()))
        return event_key, COSMIC_EVENTS[event_key]
    return None, None

async def apply_cosmic_event(context, game, event_key, event_data):
    """Apply cosmic event effects."""
    effect_type = event_data['effect']
    value = event_data['value']
    
    event_log = []
    
    if effect_type == 'damage_all':
        damage = random.randint(*value)
        for user_id, player in game.players.items():
            if player['alive']:
                player['hp'] -= damage
                player['stats']['damage_taken'] += damage
                event_log.append(f"• {player['first_name']}: -{damage} HP")
    
    elif effect_type == 'heal_all':
        heal = random.randint(*value)
        for user_id, player in game.players.items():
            if player['alive']:
                old_hp = player['hp']
                player['hp'] = min(player['max_hp'], player['hp'] + heal)
                actual_heal = player['hp'] - old_hp
                player['stats']['heals_done'] += actual_heal
                event_log.append(f"• {player['first_name']}: +{actual_heal} HP")
    
    elif effect_type == 'teleport':
        teleported = random.sample(game.get_alive_players(), min(3, len(game.get_alive_players())))
        for user_id in teleported:
            player = game.players[user_id]
            old_x, old_y = player['position']
            game.map_grid[old_x][old_y].remove(user_id)
            
            new_x, new_y = random.randint(0, MAP_SIZE-1), random.randint(0, MAP_SIZE-1)
            player['position'] = (new_x, new_y)
            game.map_grid[new_x][new_y].append(user_id)
            
            event_log.append(f"• {player['first_name']} teleported to ({new_x}, {new_y})")
    
    elif effect_type == 'damage_boost':
        game.event_effect = {'type': 'damage_boost', 'value': value}
        event_log.append(f"• All attacks deal {int((value-1)*100)}% bonus damage next turn!")
    
    elif effect_type == 'shield_all':
        game.event_effect = {'type': 'shield', 'value': value}
        event_log.append(f"• All ships gain {int(value*100)}% damage reduction next turn!")
    
    elif effect_type == 'random_damage':
        targets = random.sample(game.get_alive_players(), min(2, len(game.get_alive_players())))
        for user_id in targets:
            player = game.players[user_id]
            damage = random.randint(*value)
            player['hp'] -= damage
            player['stats']['damage_taken'] += damage
            event_log.append(f"• {player['first_name']}: -{damage} HP from pirates!")
    
    return event_log

# ======================== GLOBAL STATE ========================
games = {}

# ======================== COMMAND HANDLERS ========================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message."""
    user = update.effective_user
    welcome_text = f"""
🚀 **Welcome Aboard, Captain {user.first_name}!**  
*Conquer the Stars in Ship Battle Royale* 🌌  

**Quick Start**  
• /creategame - Launch a new battle  
• /help - View all commands  
• /rules - Learn game mechanics  
• /stats - Check your statistics  

**Epic Features**  
• Solo & Team Battles  
• 5x5 Grid Combat Map  
• Cosmic Events & Power-Ups  
• AFK Auto-Elimination System  
• Real-Time Strategy Combat  
• Global Leaderboards & Achievements  

*Ready to dominate the galaxy?* ✨  
"""
    
    keyboard = [
        [InlineKeyboardButton("📖 Game Rules", callback_data="show_rules")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="show_leaderboard")],
        [InlineKeyboardButton("📊 My Stats", callback_data="show_mystats")],
        [InlineKeyboardButton("🏅 Achievements", callback_data="show_achievements")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all commands."""
    help_text = """
🚀 **Ship Battle Royale - Command Center**  

🎮 **Game Commands**  
• /creategame - Start new battle  
• /join - Join ongoing game  
• /leave - Leave before game starts  
• /cancel - Cancel your participation  
• /spectate - Watch game as spectator  
• /map - View battle map  
• /move - Move your ship (in DM)  

📊 **Information Commands**  
• /stats - View game statistics  
• /myhp - Check your ship's HP  
• /inventory - View your items  
• /ranking - Current game ranking  
• /history - Recent game history  
• /achievements - View achievements  
• /compare @user - Compare stats  
• /position - Check your map position  

⚙️ **Admin Commands**  
• /endgame - Force end current game  
• /extend - Add 30s to joining phase  
• /settings - Configure game settings  
• /ban @user - Ban player  
• /unban @user - Unban player  

🏆 **Global Commands**  
• /leaderboard - Top 10 players  
• /mystats - Your global statistics  
• /rules - Game mechanics guide  
• /top_killers - Most kills  
• /top_survivors - Best survival rate  
• /tips - Random strategy tip  

💡 *Pro Tip*: Stay active or face auto-elimination!  
"""
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detailed game rules."""
    rules_text = """
📖 **Ship Battle Royale - Complete Guide**  

🎯 **Objective**: Be the last ship standing!  

-----x-----x-----x-----x-----
->1️⃣ Joining Phase (2 min) 
 
• Min 2, Max 15 players  
• Choose Solo or Team mode  
• Admins can extend (+30s)  

->2️⃣ Combat System  

• 🗡️ **Attack**: 25-45 DMG +15% Crit (Range: 2 cells)  
• 🛡️ **Defend**: 50% damage reduction  
• 💊 **Heal**: 30-50 HP restore  
• 💰 **Loot**: 15-25 HP + random item  
• 🧭 **Move**: Navigate 5x5 grid map  

->3️⃣ Map System 

• 5x5 grid battlefield  
• Move up/down/left/right  
• Attack range: 2 cells (Manhattan distance)  
• Strategic positioning matters!  

->4️⃣ AFK System ⚠️  

• Miss 3 turns = Auto-Elimination  
• "AFK Captain - Ship Lost in Space!"  
• Stay active or lose your ship!  

->5️⃣ Cosmic Events 🌌  

• ☄️ Meteor Storm - Damage all  
• 🌟 Solar Boost - Heal all  
• 🌀 Wormhole - Random teleports  
• ⚡ Energy Surge - Damage boost  
• 🏴‍☠️ Pirate Ambush - Random attacks  
• 🪨 Asteroid Field - Light damage  
• 🌌 Nebula Shield - Temporary shields  

->6️⃣ Team Mode 🤝  

• Alpha vs Beta teams  
• Can't attack teammates  
• Team coordination wins!  
• Eliminate all opponents to win  

->7️⃣ Items & Rarities
 
• ⚪ Common (50%): Basic boosts  
• 🔵 Rare (30%): Enhanced effects  
• 🟣 Epic (15%): Powerful upgrades  
• 🟠 Legendary (5%): Ultimate items  

->8️⃣ Strategy Tips

• ✅ Stay active - avoid AFK elimination  
• ✅ Use map positioning tactically  
• ✅ Coordinate with team (team mode)  
• ✅ Adapt to cosmic events  
• ✅ Balance aggression and healing  

-----x-----x-----x-----x-----

*Good luck, Captain! Conquer the stars!* ✨  
"""
    
    gif_url = GIFS['rules']
    await safe_send_animation(
        context, update.effective_chat.id, gif_url,
        caption=rules_text, parse_mode=ParseMode.MARKDOWN
    )

async def creategame_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create new game."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if update.effective_chat.type == 'private':
        await update.message.reply_text("This command works only in groups!")
        return
    
    if chat_id in games:
        if games[chat_id].is_active:
            await update.message.reply_text(
                "**Battle in progress!** ⚔️\nWait for current game to end or use /spectate to watch!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        else:
            del games[chat_id]
    
    user_name = update.effective_user.first_name
    game = Game(chat_id, user_id, user_name)
    games[chat_id] = game
    
    keyboard = [
        [InlineKeyboardButton("⚔️ Solo Mode - Battle Royale", callback_data=f"mode_solo_{chat_id}")],
        [InlineKeyboardButton("🤝 Team Mode - Alpha vs Beta", callback_data=f"mode_team_{chat_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    caption = """
🚀 Ship Battle Royale
*Choose your battle mode!* 🌌  

**Solo Mode**: Every captain for themselves!  
**Team Mode**: Alpha 🔵 vs Beta 🔴 warfare!  
"""
    
    gif_url = get_random_gif('joining')
    await safe_send_animation(
        context, chat_id, gif_url,
        caption=caption,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        await context.bot.send_message(
            SUPPORTIVE_GROUP_ID,
            f"New game created!\n**Group:** {update.effective_chat.title}\n**Creator:** {user_name}",
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        pass

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all inline button callbacks."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data.startswith('mode_'):
        await handle_mode_selection(query, context)
    elif data.startswith('join_') or data.startswith('leave_'):
        await handle_join_leave(query, context)
    elif data.startswith('team_join_'):
        await handle_team_join(query, context)
    elif data.startswith('operation_'):
        await handle_operation_selection(query, context)
    elif data.startswith('target_'):
        await handle_target_selection(query, context)
    elif data.startswith('move_'):
        await handle_move_selection(query, context)
    elif data.startswith('show_'):
        await handle_show_info(query, context)
    elif data == 'back_to_modes':
        await handle_back_to_modes(query, context)

async def handle_mode_selection(query, context):
    """Handle game mode selection."""
    data = query.data
    chat_id = query.message.chat_id
    
    if chat_id not in games:
        await query.edit_message_caption("Game session expired!")
        return
    
    game = games[chat_id]
    mode = data.split('_')[1]
    
    if mode == 'solo':
        await start_solo_mode(query, context, game)
    elif mode == 'team':
        await start_team_mode(query, context, game)

async def start_solo_mode(query, context, game):
    """Initialize solo mode joining phase."""
    game.mode = 'solo'
    game.is_joining = True
    game.join_end_time = datetime.now() + timedelta(seconds=game.settings['join_time'])
    
    success, msg = game.add_player(
        game.creator_id,
        game.creator_name,
        game.creator_name
    )
    
    if not success:
        await query.edit_message_caption(f"❌ {msg}")
        return
    
    await display_joining_phase(query.message, context, game, edit=True)
    
    await safe_send(
        context, game.chat_id,
        f"**{game.creator_name}** has rallied the fleet! 🚀\n*Solo Battle Royale Mode activated!*",
        parse_mode=ParseMode.MARKDOWN
    )
    
    asyncio.create_task(joining_countdown(context, game))

async def start_team_mode(query, context, game):
    """Initialize team mode joining phase."""
    game.mode = 'team'
    game.is_joining = True
    game.join_end_time = datetime.now() + timedelta(seconds=game.settings['join_time'])
    
    await display_team_joining_phase(query.message, context, game, edit=True)
    
    await safe_send(
        context, game.chat_id,
        f"**{game.creator_name}** initiated Team Battle! 🤝\n*Alpha 🔵 vs Beta 🔴 - Choose your side!*",
        parse_mode=ParseMode.MARKDOWN
    )
    
    asyncio.create_task(joining_countdown(context, game))

async def display_team_joining_phase(message, context, game, edit=False):
    """Display/update team joining phase message."""
    remaining = max(0, int((game.join_end_time - datetime.now()).total_seconds()))
    time_str = format_time(remaining)
    
    alpha_list = ""
    beta_list = ""
    
    alpha_count = 0
    beta_count = 0
    
    for user_id, data in game.players.items():
        name = data['first_name']
        if data['team'] == 'alpha':
            alpha_count += 1
            alpha_list += f"{alpha_count}. 🔵 {name}\n"
        elif data['team'] == 'beta':
            beta_count += 1
            beta_list += f"{beta_count}. 🔴 {name}\n"
    
    if not alpha_list:
        alpha_list = "Awaiting warriors...\n"
    if not beta_list:
        beta_list = "Awaiting warriors...\n"
    
    caption = f"""

🚀 Team Battle - Alpha vs Beta**  
⏱️ Joining Phase : {time_str}  
👥 Players: {len(game.players)}/{game.settings['max_players']}  

->🔵 Team Alpha ({alpha_count})**  
{alpha_list}  

->🔴 Team Beta ({beta_count})**  
{beta_list}  

*Choose your team and fight together!*  
Min {game.settings['min_players']} players (balanced teams preferred)  
"""
    
    if remaining <= 30 and remaining > 0:
        caption += f"⚠️ *HURRY! Only {remaining}s left!*\n"
    
    keyboard = [
        [
            InlineKeyboardButton("🔵 Join Alpha", callback_data=f"team_join_alpha_{game.chat_id}"),
            InlineKeyboardButton("🔴 Join Beta", callback_data=f"team_join_beta_{game.chat_id}")
        ],
        [InlineKeyboardButton("❌ Leave Team", callback_data=f"leave_game_{game.chat_id}")],
        [InlineKeyboardButton("👁️ Spectate", callback_data=f"spectate_{game.chat_id}")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if edit and game.joining_message_id:
            await context.bot.edit_message_caption(
                chat_id=game.chat_id,
                message_id=game.joining_message_id,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            gif_url = get_random_gif('joining')
            new_msg = await safe_send_animation(
                context, game.chat_id, gif_url,
                caption=caption, reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            if new_msg:
                game.joining_message_id = new_msg.message_id
    except BadRequest:
        pass

async def handle_team_join(query, context):
    """Handle team join actions."""
    data = query.data
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    
    if chat_id not in games:
        await query.answer("No active game!", show_alert=True)
        return
    
    game = games[chat_id]
    
    if not game.is_joining:
        await query.answer("Game already started!", show_alert=True)
        return
    
    team = data.split('_')[2]
    username = query.from_user.username
    first_name = query.from_user.first_name
    
    # Check if already in game
    if user_id in game.players:
        old_team = game.players[user_id]['team']
        if old_team == team:
            await query.answer(f"Already in Team {team.title()}!", show_alert=True)
            return
        # Switch teams
        game.teams[old_team].remove(user_id)
        game.teams[team].add(user_id)
        game.players[user_id]['team'] = team
        
        await safe_send(
            context, game.chat_id,
            f"🔄 **{first_name}** switched to Team {team.title()}! {'🔵' if team == 'alpha' else '🔴'}",
            parse_mode=ParseMode.MARKDOWN
        )
        await query.answer(f"Switched to Team {team.title()}!")
    else:
        success, msg = game.add_player(user_id, username, first_name, team=team)
        if success:
            await safe_send(
                context, game.chat_id,
                f"✅ **{first_name}** joined Team {team.title()}! {'🔵' if team == 'alpha' else '🔴'}",
                parse_mode=ParseMode.MARKDOWN
            )
            await query.answer(f"Welcome to Team {team.title()}! 🚀")
        else:
            await query.answer(msg, show_alert=True)
    
    await display_team_joining_phase(query.message, context, game, edit=True)

async def display_joining_phase(message, context, game, edit=False):
    """Display/update joining phase message."""
    remaining = max(0, int((game.join_end_time - datetime.now()).total_seconds()))
    time_str = format_time(remaining)
    
    player_list = ""
    for i, (uid, data) in enumerate(game.players.items(), 1):
        name = data['first_name']
        player_list += f"{i}. 🚢 {name}\n"
    
    if not player_list:
        player_list = "Awaiting brave souls...\n"
    
    caption = f"""
🚀 **Ship Battle Royale - Solo Mode**  
⏱️ **Joining Phase**: {time_str}  
👥 **Players**: {len(game.players)}/{game.settings['max_players']}  

**Fleet Roster**  
{player_list}  

*Join the ultimate space battle!*  
Min {game.settings['min_players']} players required  
⚠️ **AFK Warning**: 3 missed turns = Auto-Elimination!  
"""
    
    if remaining <= 30 and remaining > 0:
        caption += f"⚠️ *HURRY! {remaining}s left!*\n"
    
    keyboard = [
        [InlineKeyboardButton("🚀 Join Battle", callback_data=f"join_game_{game.chat_id}")],
        [InlineKeyboardButton("❌ Leave Fleet", callback_data=f"leave_game_{game.chat_id}")],
        [InlineKeyboardButton("👁️ Spectate", callback_data=f"spectate_{game.chat_id}")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if edit and game.joining_message_id:
            await context.bot.edit_message_caption(
                chat_id=game.chat_id,
                message_id=game.joining_message_id,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            gif_url = get_random_gif('joining')
            new_msg = await safe_send_animation(
                context, game.chat_id, gif_url,
                caption=caption, reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            if new_msg:
                game.joining_message_id = new_msg.message_id
    except BadRequest:
        pass

async def joining_countdown(context, game):
    """Countdown timer for joining phase."""
    try:
        while game.is_joining:
            remaining = int((game.join_end_time - datetime.now()).total_seconds())
            
            if remaining <= 0:
                break
            
            if remaining % 15 == 0 or remaining <= 10:
                try:
                    fake_message = type('obj', (object,), {
                        'message_id': game.joining_message_id,
                        'chat_id': game.chat_id
                    })
                    if game.mode == 'team':
                        await display_team_joining_phase(fake_message, context, game, edit=True)
                    else:
                        await display_joining_phase(fake_message, context, game, edit=True)
                except:
                    pass
            
            if remaining in [60, 30, 10]:
                await safe_send(
                    context, game.chat_id,
                    f"⏰ {remaining} seconds remaining to join! 🚀",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            await asyncio.sleep(1)
        
        if game.is_joining:
            game.is_joining = False
            await start_game_phase(context, game)
            
    except Exception as e:
        logger.error(f"Countdown error: {e}")

async def handle_join_leave(query, context):
    """Handle join/leave actions."""
    data = query.data
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    
    if chat_id not in games:
        await query.answer("No active game!", show_alert=True)
        return
    
    game = games[chat_id]
    
    if not game.is_joining:
        await query.answer("Game already started!", show_alert=True)
        return
    
    username = query.from_user.username
    first_name = query.from_user.first_name
    
    if data.startswith('join_'):
        if game.mode == 'team':
            await query.answer("Use team buttons to join!", show_alert=True)
            return
        
        success, msg = game.add_player(user_id, username, first_name)
        if success:
            await safe_send(
                context, game.chat_id,
                f"✅ **{first_name}** has joined the armada! 💥",
                parse_mode=ParseMode.MARKDOWN
            )
            await query.answer("Welcome aboard, Captain! 🚀")
        else:
            await query.answer(msg, show_alert=True)
    
    elif data.startswith('leave_'):
        if user_id in game.players:
            team = game.players[user_id].get('team')
            if team:
                game.teams[team].remove(user_id)
            del game.players[user_id]
            await safe_send(
                context, game.chat_id,
                f"❌ **{first_name}** has abandoned ship! ⚠️",
                parse_mode=ParseMode.MARKDOWN
            )
            await query.answer("You've left the game!")
        else:
            await query.answer("You're not in the game!", show_alert=True)
    
    if game.mode == 'team':
        await display_team_joining_phase(query.message, context, game, edit=True)
    else:
        await display_joining_phase(query.message, context, game, edit=True)

async def start_game_phase(context, game):
    """Start the actual game."""
    if len(game.players) < game.settings['min_players']:
        caption = f"""
❌ **Insufficient Crew!**  
*Min {game.settings['min_players']} players required*  
Game cancelled. Try again with `/creategame`!  
"""
        await safe_send_animation(
            context, game.chat_id,
            get_random_gif('joining'),
            caption=caption,
            parse_mode=ParseMode.MARKDOWN
        )
        del games[game.chat_id]
        return
    
    # Team mode balance check
    if game.mode == 'team':
        alpha_count = len(game.teams['alpha'])
        beta_count = len(game.teams['beta'])
        
        if alpha_count == 0 or beta_count == 0:
            await safe_send(
                context, game.chat_id,
                "❌ **Both teams need players!** Game cancelled.",
                parse_mode=ParseMode.MARKDOWN
            )
            del games[game.chat_id]
            return
    
    game.is_active = True
    game.day = 1
    
    mode_text = "Solo Battle Royale" if game.mode == 'solo' else f"Team Battle - Alpha 🔵 vs Beta 🔴"
    
    caption = f"""
⚔️ **Battle Commencing!**  
*Day {game.day} - The Hunt Begins!*  

🎮 **Mode**: {mode_text}  
🚢 **{len(game.players)} Ships Entered**  

**Combat Parameters**  
• Starting HP: 200/ship  
• Map: 5x5 Grid Battlefield  
• Attack Range: 2 cells  
• Operation Time: {format_time(game.settings['operation_time'])}  
• ⚠️ AFK Limit: 3 missed turns  

*May the best Captain win!* 🏆  
"""
    
    gif_url = get_random_gif('start')
    await safe_send_animation(
        context, game.chat_id, gif_url,
        caption=caption,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Show initial map
    map_display = game.get_map_display()
    await safe_send(context, game.chat_id, map_display, parse_mode=ParseMode.MARKDOWN)
    
    for user_id in game.players:
        await send_operation_dm(context, game, user_id)
    
    game.operation_end_time = datetime.now() + timedelta(seconds=game.settings['operation_time'])
    asyncio.create_task(operation_countdown(context, game))

async def send_operation_dm(context, game, user_id):
    """Send operation selection to player via DM."""
    player = game.players[user_id]
    hp = player['hp']
    hp_bar = get_progress_bar(hp, player['max_hp'])
    hp_ind = get_hp_indicator(hp, player['max_hp'])
    px, py = player['position']
    
    inventory_text = ""
    if player['inventory']:
        inventory_text = ""
        for item_key in player['inventory']:
            item = LOOT_ITEMS[item_key]
            rarity_emoji = get_rarity_color(item['rarity'])
            inventory_text += f"{rarity_emoji} {item['emoji']} {item_key.replace('_', ' ').title()}\n"
    else:
        inventory_text = "Empty - Loot for power-ups! 📦"
    
    team_text = ""
    if game.mode == 'team':
        team_emoji = "🔵" if player['team'] == 'alpha' else "🔴"
        team_text = f"**Team**: {team_emoji} {player['team'].title()}\n"
    
    text = f"""
🚢 **Your Flagship Status - Day {game.day}**  
{hp_ind} **HP**: {hp}/{player['max_hp']} {hp_bar}  
📍 **Position**: ({px}, {py})  
{team_text}
**Battle Info**  
• AFK Count: {player['afk_turns']}/3 ⚠️  
• Time: {format_time(game.settings['operation_time'])}  

**Your Arsenal**  
{inventory_text}  

*Choose your operation wisely!* ⚔️  
"""
    
    keyboard = [
        [InlineKeyboardButton("🗡️ Attack Enemy", callback_data=f"operation_attack_{user_id}")],
        [InlineKeyboardButton("🛡️ Raise Shields", callback_data=f"operation_defend_{user_id}"),
        InlineKeyboardButton("💊 Repair Hull", callback_data=f"operation_heal_{user_id}")],
        [InlineKeyboardButton("💰 Scavenge Loot", callback_data=f"operation_loot_{user_id}"),
        InlineKeyboardButton("🧭 Move Ship", callback_data=f"operation_move_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    gif_url = get_random_gif('operation')
    await safe_send_animation(
        context, user_id, gif_url,
        caption=text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def operation_countdown(context, game):
    """Countdown for operation selection with early end and updates."""
    try:
        last_update_time = datetime.now()
        while game.is_active and game.operation_end_time:
            remaining = int((game.operation_end_time - datetime.now()).total_seconds())
            
            if remaining <= 0:
                break
            
            # Check if all ready
            alive_players = game.get_alive_players()
            ready_count = sum(1 for uid in alive_players if game.players[uid]['operation'] is not None)
            all_ready = ready_count == len(alive_players)
            
            if all_ready:
                await safe_send(
                    context, game.chat_id,
                    f"🚀 **ALL CAPTAINS READY!** Processing Day {game.day} operations immediately! ⚡",
                    parse_mode=ParseMode.MARKDOWN
                )
                break
            
            # Periodic updates every 20s
            if (datetime.now() - last_update_time).total_seconds() >= 20:
                pending_players = [game.players[uid]['first_name'] for uid in alive_players if game.players[uid]['operation'] is None]
                pending_names = ", ".join(pending_players[:3])
                if len(pending_players) > 3:
                    pending_names += f" +{len(pending_players)-3} more"
                
                update_text = f"""
⏱️ **Operation Status - Day {game.day}**  
• Time Remaining: {format_time(remaining)}  
• ✅ Ready: {ready_count}/{len(alive_players)}  
• ⏳ Pending: {pending_names}  

*Choose fast or auto-defend!* ⚠️  
"""
                await safe_send(
                    context, game.chat_id,
                    update_text,
                    parse_mode=ParseMode.MARKDOWN
                )
                last_update_time = datetime.now()
            
            # Warnings
            if remaining in [60, 30, 15]:
                for uid in alive_players:
                    if game.players[uid]['operation'] is None:
                        await safe_send(
                            context, uid,
                            f"⏰ {remaining}s left! Choose or auto-defend! ⚠️",
                            parse_mode=ParseMode.MARKDOWN
                        )
            
            await asyncio.sleep(1)
        
        if game.is_active:
            await process_day_operations(context, game)
            
    except Exception as e:
        logger.error(f"Operation countdown error: {e}")

async def handle_operation_selection(query, context):
    """Handle operation button press."""
    data = query.data
    parts = data.split('_')
    operation = parts[1]
    user_id = int(parts[2])
    
    game = None
    for g in games.values():
        if user_id in g.players:
            game = g
            break
    
    if not game:
        await query.answer("Game not found!", show_alert=True)
        return
    
    if not game.is_active:
        await query.answer("Game not active!", show_alert=True)
        return
    
    player = game.players[user_id]
    
    if not player['alive']:
        await query.answer("You've been eliminated!", show_alert=True)
        return
    
    if player['operation']:
        await query.answer("Operation already selected!", show_alert=True)
        return
    
    if operation == 'attack':
        await show_target_selection(query, context, game, user_id)
    elif operation == 'move':
        await show_move_selection(query, context, game, user_id)
    else:
        await set_operation(query, context, game, user_id, operation, None)

async def show_target_selection(query, context, game, user_id):
    """Show available targets for attack."""
    targets_in_range = game.get_players_in_range(user_id)
    
    if not targets_in_range:
        await query.answer("No enemies in range! Move closer or choose another action.", show_alert=True)
        return
    
    keyboard = []
    
    for target_id in targets_in_range:
        target = game.players[target_id]
        name = target['first_name']
        hp = target['hp']
        hp_ind = get_hp_indicator(hp, target['max_hp'])
        tx, ty = target['position']
        
        team_emoji = ""
        if game.mode == 'team':
            team_emoji = "🔵" if target['team'] == 'alpha' else "🔴"
        
        keyboard.append([
            InlineKeyboardButton(
                f"{team_emoji} {hp_ind} {name} ({hp} HP) @ ({tx},{ty})",
                callback_data=f"target_{target_id}_{user_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("◀️ Back", callback_data=f"operation_defend_{user_id}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = """
🗡️ **Target Selection**  

*Choose your target wisely!*  

**HP Indicators**  
• 🟢 High (150+) - Tough  
• 🟡 Medium (75-150) - Fair  
• 🔴 Low (<75) - Weak  

*Tip*: Strike the wounded!  
"""
    
    try:
        await query.edit_message_caption(caption=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    except BadRequest:
        try:
            await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        except:
            pass

async def show_move_selection(query, context, game, user_id):
    """Show movement options."""
    player = game.players[user_id]
    px, py = player['position']
    
    keyboard = []
    
    if px > 0:
        keyboard.append([InlineKeyboardButton("⬆️ Move Up", callback_data=f"move_up_{user_id}")])
    if px < MAP_SIZE - 1:
        keyboard.append([InlineKeyboardButton("⬇️ Move Down", callback_data=f"move_down_{user_id}")])
    if py > 0:
        keyboard.append([InlineKeyboardButton("⬅️ Move Left", callback_data=f"move_left_{user_id}")])
    if py < MAP_SIZE - 1:
        keyboard.append([InlineKeyboardButton("➡️ Move Right", callback_data=f"move_right_{user_id}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Back", callback_data=f"operation_defend_{user_id}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Show mini map around player
    mini_map = f"📍 **Your Position**: ({px}, {py})\n\n"
    
    for i in range(max(0, px-1), min(MAP_SIZE, px+2)):
        row = ""
        for j in range(max(0, py-1), min(MAP_SIZE, py+2)):
            if i == px and j == py:
                row += "🟢 "  # Your position
            elif game.map_grid[i][j]:
                alive_count = sum(1 for uid in game.map_grid[i][j] if game.players[uid]['alive'])
                if alive_count > 0:
                    row += "🔴 "
                else:
                    row += "⬜ "
            else:
                row += "⬜ "
        mini_map += row + "\n"
    
    text = f"""
🧭 **Ship Navigation**  

{mini_map}

*Strategic positioning is key!*  
• Attack range: 2 cells  
• Move to engage or evade  

Choose your direction:  
"""
    
    try:
        await query.edit_message_caption(caption=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    except BadRequest:
        try:
            await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        except:
            pass

async def handle_move_selection(query, context):
    """Handle movement direction selection."""
    data = query.data
    parts = data.split('_')
    direction = parts[1]
    user_id = int(parts[2])
    
    game = None
    for g in games.values():
        if user_id in g.players:
            game = g
            break
    
    if not game:
        await query.answer("Game not found!", show_alert=True)
        return
    
    player = game.players[user_id]
    old_pos = player['position']
    
    game.move_player(user_id, direction)
    new_pos = player['position']
    
    await set_operation(query, context, game, user_id, 'move', None)
    await query.answer(f"Moved from {old_pos} to {new_pos}! ✅")

async def handle_target_selection(query, context):
    """Handle target selection for attack."""
    data = query.data
    parts = data.split('_')
    target_id = int(parts[1])
    user_id = int(parts[2])
    
    game = None
    for g in games.values():
        if user_id in g.players:
            game = g
            break
    
    if not game:
        await query.answer("Game not found!", show_alert=True)
        return
    
    await set_operation(query, context, game, user_id, 'attack', target_id)

async def set_operation(query, context, game, user_id, operation, target_id):
    """Set player's operation with enhanced confirmation."""
    player = game.players[user_id]
    player['operation'] = operation
    player['target'] = target_id
    player['last_action_time'] = datetime.now()
    player['afk_turns'] = 0  # Reset AFK counter
    
    op_names = {
        'attack': '🗡️ Attack',
        'defend': '🛡️ Defend',
        'heal': '💊 Heal',
        'loot': '💰 Loot',
        'move': '🧭 Move'
    }
    
    op_descriptions = {
        'attack': 'Unleash fury on your target!',
        'defend': 'Shields up! Reduce damage by 50%',
        'heal': 'Repair systems and restore HP',
        'loot': 'Scavenge for HP and rare items',
        'move': 'Navigate to strategic position'
    }
    
    alive_players = game.get_alive_players()
    ready_count = sum(1 for uid in alive_players if game.players[uid]['operation'] is not None)
    
    text = f"""
✅ **Operation Confirmed: {op_names[operation]}**  

{op_descriptions[operation]}  
"""
    
    if target_id:
        target_name = game.players[target_id]['first_name']
        text += f"**Target**: {target_name}\n"
    
    remaining = int((game.operation_end_time - datetime.now()).total_seconds())
    text += f"""
**Status**  
• Ready: {ready_count}/{len(alive_players)}  
• Time: {format_time(remaining)}  

*Locked in. Stars favor you!* ✨  
"""
    
    reply_markup = InlineKeyboardMarkup([])
    
    try:
        await query.edit_message_caption(
            caption=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    except BadRequest:
        try:
            await query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
    
    confirmation_text = f"✅ **You have chosen {op_names[operation]}!**"
    if target_id:
        target_name = game.players[target_id]['first_name']
        confirmation_text += f"\n**Target**: {target_name}"
    confirmation_text += "\n*Prepare for battle!* ⚡"
    
    await safe_send(
        context, user_id,
        confirmation_text,
        parse_mode=ParseMode.MARKDOWN
    )
    
    await query.answer(f"{op_names[operation]} confirmed! ⚡")

async def process_day_operations(context, game):
    """Process all operations for the day."""
    await safe_send(
        context, game.chat_id,
        f"🔄 **Processing Day {game.day} Operations...** Stand by! ⚡",
        parse_mode=ParseMode.MARKDOWN
    )
    
    await asyncio.sleep(2)
    
    # Check for cosmic event
    event_key, event_data = trigger_cosmic_event()
    event_log = []
    
    if event_key and event_data:
        game.active_event = event_key
        gif_url = GIFS.get('event', get_random_gif('operation'))
        
        await safe_send_animation(
            context, game.chat_id, gif_url,
            caption=f"""
🌌 **COSMIC EVENT!**  
{event_data['emoji']} **{event_data['name']}**  

*{event_data['desc']}*  

Processing effects...  
""",
            parse_mode=ParseMode.MARKDOWN
        )
        
        await asyncio.sleep(2)
        event_log = await apply_cosmic_event(context, game, event_key, event_data)
    
    # Handle AFK players - Auto defend or eliminate
    for user_id, player in game.players.items():
        if player['alive'] and not player['operation']:
            player['afk_turns'] += 1
            if player['afk_turns'] >= AFK_TURNS_LIMIT:
                player['alive'] = False
                player['hp'] = 0
                await safe_send_animation(
                    context, user_id,
                    get_random_gif('eliminated'),
                    caption=f"""
⚠️ **AFK Captain - Ship Lost in Space!**  

You were eliminated for inactivity!  
*Missed {AFK_TURNS_LIMIT} consecutive turns*  

Stay active next time! 🚀  
""",
                    parse_mode=ParseMode.MARKDOWN
                )
                await safe_send(
                    context, game.chat_id,
                    f"⚠️ **{player['first_name']}** was eliminated for being AFK! ({AFK_TURNS_LIMIT} missed turns)",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                player['operation'] = 'defend'
                await safe_send(
                    context, user_id,
                    f"⚠️ **Auto-Defend activated!** (AFK: {player['afk_turns']}/{AFK_TURNS_LIMIT})\n*Choose next turn or face elimination!*",
                    parse_mode=ParseMode.MARKDOWN
                )
    
    base_attack = random.randint(*ATTACK_DAMAGE)
    base_heal = random.randint(*HEAL_AMOUNT)
    base_loot_hp = random.randint(*LOOT_HP)
    
    # Apply event boost if active
    if game.event_effect and game.event_effect['type'] == 'damage_boost':
        base_attack = int(base_attack * game.event_effect['value'])
    
    attacks = defaultdict(list)
    defenders = set()
    healers = set()
    looters = set()
    movers = []
    
    for user_id, player in game.players.items():
        if not player['alive']:
            continue
        
        op = player['operation']
        if op == 'attack' and player['target']:
            # Verify target still in range
            if player['target'] in game.get_players_in_range(user_id):
                attacks[player['target']].append(user_id)
        elif op == 'defend':
            defenders.add(user_id)
        elif op == 'heal':
            healers.add(user_id)
        elif op == 'loot':
            looters.add(user_id)
        elif op == 'move':
            movers.append(user_id)
    
    # Process attacks
    damage_log = []
    for target_id, attackers in attacks.items():
        if target_id not in game.players or not game.players[target_id]['alive']:
            continue
        
        target = game.players[target_id]
        total_damage = 0
        crit_hit = False
        
        for attacker_id in attackers:
            attacker = game.players[attacker_id]
            damage = base_attack
            
            weapon_bonus = 0
            for item_key in attacker['inventory'][:]:
                item = LOOT_ITEMS[item_key]
                if item['type'] == 'weapon':
                    weapon_bonus += item['bonus']
                    attacker['inventory'].remove(item_key)
                    break
            
            damage += weapon_bonus
            
            if random.random() < CRIT_CHANCE:
                damage = int(damage * CRIT_MULTIPLIER)
                crit_hit = True
            
            total_damage += damage
            attacker['stats']['damage_dealt'] += damage
        
        defense_reduction = DEFEND_REDUCTION if target_id in defenders else 0
        
        # Apply event shield if active
        if game.event_effect and game.event_effect['type'] == 'shield':
            defense_reduction += game.event_effect['value']
        
        for item_key in target['inventory'][:]:
            item = LOOT_ITEMS[item_key]
            if item['type'] == 'shield':
                defense_reduction += item['bonus']
                target['inventory'].remove(item_key)
                break
        
        defense_reduction = min(0.8, defense_reduction)
        final_damage = int(total_damage * (1 - defense_reduction))
        
        target['hp'] -= final_damage
        target['stats']['damage_taken'] += final_damage
        
        attacker_names = ", ".join([game.players[a]['first_name'] for a in attackers])
        crit_text = " 💥CRIT!" if crit_hit else ""
        defend_text = f" (🛡️{int(defense_reduction*100)}% blocked)" if defense_reduction > 0 else ""
        hp_ind = get_hp_indicator(max(0, target['hp']), target['max_hp'])
        
        damage_log.append(
            f"{attacker_names} → {hp_ind} {target['first_name']}: {final_damage} DMG{crit_text}{defend_text}"
        )
    
    # Process heals
    heal_log = []
    for user_id in healers:
        player = game.players[user_id]
        heal_amount = base_heal
        
        for item_key in player['inventory'][:]:
            item = LOOT_ITEMS[item_key]
            if item['type'] == 'potion':
                heal_amount += item['bonus']
                player['inventory'].remove(item_key)
                break
        
        old_hp = player['hp']
        player['hp'] = min(player['max_hp'], player['hp'] + heal_amount)
        actual_heal = player['hp'] - old_hp
        player['stats']['heals_done'] += actual_heal
        
        hp_ind = get_hp_indicator(player['hp'], player['max_hp'])
        heal_log.append(
            f"{hp_ind} {player['first_name']} repaired: +{actual_heal} HP"
        )
    
    # Process loots
    loot_log = []
    for user_id in looters:
        player = game.players[user_id]
        loot_hp = base_loot_hp
        
        for item_key in player['inventory'][:]:
            item = LOOT_ITEMS[item_key]
            if item['type'] == 'energy':
                loot_hp += item['bonus']
                player['inventory'].remove(item_key)
                break
        
        player['hp'] = min(player['max_hp'], player['hp'] + loot_hp)
        player['stats']['loots'] += 1
        
        rarity_pool = []
        for item_key, item in LOOT_ITEMS.items():
            rarity_pool.extend([item_key] * RARITY_WEIGHTS[item['rarity']])
        
        new_item = random.choice(rarity_pool)
        player['inventory'].append(new_item)
        
        item_data = LOOT_ITEMS[new_item]
        rarity_emoji = get_rarity_color(item_data['rarity'])
        hp_ind = get_hp_indicator(player['hp'], player['max_hp'])
        
        loot_log.append(
            f"{hp_ind} {player['first_name']} looted: +{loot_hp} HP & {rarity_emoji} {item_data['emoji']} {new_item.replace('_', ' ').title()}"
        )
    
    # Process moves
    move_log = []
    for user_id in movers:
        player = game.players[user_id]
        px, py = player['position']
        move_log.append(f"🧭 {player['first_name']} navigated to ({px}, {py})")
    
    # Check eliminations
    eliminated = []
    for user_id, player in list(game.players.items()):
        if player['alive'] and player['hp'] <= 0:
            player['alive'] = False
            player['hp'] = 0
            eliminated.append((user_id, player['first_name']))
            
            # Award kills
            if user_id in attacks:
                for attacker_id in attacks[user_id]:
                    game.players[attacker_id]['stats']['kills'] += 1
                    
                    # Check first blood achievement
                    if game.players[attacker_id]['stats']['kills'] == 1:
                        if unlock_achievement(attacker_id, 'first_blood'):
                            await safe_send(
                                context, attacker_id,
                                "🏆 **Achievement Unlocked!**\n🩸 First Blood",
                                parse_mode=ParseMode.MARKDOWN
                            )
            
            await safe_send_animation(
                context, user_id,
                get_random_gif('eliminated'),
                caption=f"""
💀 **Eliminated!**  
Your ship was destroyed on Day {game.day}!  
*Final HP: 0*  

*Better luck next time!* ⚡  
""",
                parse_mode=ParseMode.MARKDOWN
            )
    
    # Build summary
    summary_lines = [f"📊 **Day {game.day} Summary**"]
    summary_lines.append("")
    
    if event_log:
        summary_lines.append(f"🌌 **Cosmic Event: {event_data['name']}**")
        for line in event_log:
            summary_lines.append(line)
        summary_lines.append("")
    
    if damage_log:
        summary_lines.append("🗡️ **Attacks**")
        for line in damage_log:
            summary_lines.append(f"• {line}")
        summary_lines.append("")
    
    if heal_log:
        summary_lines.append("💊 **Repairs**")
        for line in heal_log:
            summary_lines.append(f"• {line}")
        summary_lines.append("")
    
    if loot_log:
        summary_lines.append("💰 **Scavenging**")
        for line in loot_log:
            summary_lines.append(f"• {line}")
        summary_lines.append("")
    
    if move_log:
        summary_lines.append("🧭 **Navigation**")
        for line in move_log:
            summary_lines.append(f"• {line}")
        summary_lines.append("")
    
    if eliminated:
        summary_lines.append("💀 **Eliminated**")
        for _, name in eliminated:
            summary_lines.append(f"• {name}")
        summary_lines.append("")
    
    alive_players = game.get_alive_players()
    
    if game.mode == 'solo':
        summary_lines.append(f"🚢 **Survivors ({len(alive_players)})**")
        for user_id in alive_players:
            player = game.players[user_id]
            hp_bar = get_progress_bar(player['hp'], player['max_hp'], 5)
            hp_ind = get_hp_indicator(player['hp'], player['max_hp'])
            px, py = player['position']
            summary_lines.append(f"• {hp_ind} {player['first_name']} - {player['hp']} HP {hp_bar} @ ({px},{py})")
    else:
        alpha_alive = game.get_alive_team_players('alpha')
        beta_alive = game.get_alive_team_players('beta')
        
        summary_lines.append(f"🔵 **Team Alpha ({len(alpha_alive)} alive)**")
        for user_id in alpha_alive:
            player = game.players[user_id]
            hp_ind = get_hp_indicator(player['hp'], player['max_hp'])
            summary_lines.append(f"• {hp_ind} {player['first_name']} - {player['hp']} HP")
        
        summary_lines.append("")
        summary_lines.append(f"🔴 **Team Beta ({len(beta_alive)} alive)**")
        for user_id in beta_alive:
            player = game.players[user_id]
            hp_ind = get_hp_indicator(player['hp'], player['max_hp'])
            summary_lines.append(f"• {hp_ind} {player['first_name']} - {player['hp']} HP")
    
    summary_text = "\n".join(summary_lines)
    
    gif_url = get_random_gif('day_summary')
    await safe_send_animation(
        context, game.chat_id, gif_url,
        caption=summary_text,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Clear event effect
    game.event_effect = None
    
    # Check win condition
    if game.mode == 'solo':
        if len(alive_players) <= 1:
            await end_game(context, game, alive_players)
        else:
            await continue_next_day(context, game)
    else:
        alpha_alive = game.get_alive_team_players('alpha')
        beta_alive = game.get_alive_team_players('beta')
        
        if len(alpha_alive) == 0 or len(beta_alive) == 0:
            await end_team_game(context, game, alpha_alive, beta_alive)
        else:
            await continue_next_day(context, game)

async def continue_next_day(context, game):
    """Start next day of battle."""
    game.day += 1
    
    await asyncio.sleep(3)
    
    caption = f"""
⚔️ **Day {game.day} Begins!**  
*Survivors, choose your operations!*  

Current status updated. Fight smart, Captains! 🚢  
"""
    
    await safe_send(
        context, game.chat_id,
        caption,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Show updated map
    map_display = game.get_map_display()
    await safe_send(context, game.chat_id, map_display, parse_mode=ParseMode.MARKDOWN)
    
    for user_id, player in game.players.items():
        player['operation'] = None
        player['target'] = None
        
        if player['alive']:
            await send_operation_dm(context, game, user_id)
    
    game.operation_end_time = datetime.now() + timedelta(seconds=game.settings['operation_time'])
    asyncio.create_task(operation_countdown(context, game))

async def end_game(context, game, alive_players):
    """End solo game and declare winner."""
    game.is_active = False
    game.is_joining = False
    game.operation_end_time = None
    
    if alive_players:
        winner_id = alive_players[0]
        winner = game.players[winner_id]
        
        update_player_stats(winner_id, winner['username'], {
            'total_games': 1,
            'wins': 1,
            'kills': winner['stats']['kills'],
            'damage_dealt': winner['stats']['damage_dealt'],
            'damage_taken': winner['stats']['damage_taken'],
            'heals_done': winner['stats']['heals_done'],
            'loots_collected': winner['stats']['loots']
        })
        
        save_game_history(game, winner_id, winner['first_name'])
        
        unlock_achievement(winner_id, 'survivor')
        
        if winner['stats']['kills'] >= 5:
            if unlock_achievement(winner_id, 'killer'):
                await safe_send(
                    context, winner_id,
                    "🏆 **Achievement Unlocked!**\n💀 Killer - 5 kills in one game!",
                    parse_mode=ParseMode.MARKDOWN
                )
        
        if winner['stats']['moves'] >= 50:
            if unlock_achievement(winner_id, 'explorer'):
                await safe_send(
                    context, winner_id,
                    "🏆 **Achievement Unlocked!**\n🧭 Space Explorer - 50 moves!",
                    parse_mode=ParseMode.MARKDOWN
                )
        
        victory_text = f"""
🏆 **Victory Royale!**  
**{winner['first_name']}** conquers! 👑  

**Final Stats**  
• HP Left: {winner['hp']}/{winner['max_hp']}  
• Position: {winner['position']}  
• Eliminations: {winner['stats']['kills']}  
• Damage Dealt: {winner['stats']['damage_dealt']}  
• HP Healed: {winner['stats']['heals_done']}  
• Moves: {winner['stats']['moves']}  
• Days Survived: {game.day}  

*Epic battle! GG everyone!* ⚡  
Play again: `/creategame`  
"""
        
        gif_url = get_random_gif('victory')
        await safe_send_animation(
            context, game.chat_id, gif_url,
            caption=victory_text,
            parse_mode=ParseMode.MARKDOWN
        )
        
        await safe_send(
            context, winner_id,
            f"""
🏆 **Congratulations!**  
You are the ultimate champion! 👑  
*Victory recorded in the legends!*  
""",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await safe_send(
            context, game.chat_id,
            f"""
💥 **Mutual Destruction!**  
*All ships eliminated!*  

It's a draw! Try again with `/creategame`.  
""",
            parse_mode=ParseMode.MARKDOWN
        )
    
    for user_id, player in game.players.items():
        if user_id != (alive_players[0] if alive_players else None):
            update_player_stats(user_id, player['username'], {
                'total_games': 1,
                'deaths': 1,
                'kills': player['stats']['kills'],
                'damage_dealt': player['stats']['damage_dealt'],
                'damage_taken': player['stats']['damage_taken'],
                'heals_done': player['stats']['heals_done'],
                'loots_collected': player['stats']['loots']
            })
    
    del games[game.chat_id]

async def end_team_game(context, game, alpha_alive, beta_alive):
    """End team game and declare winning team."""
    game.is_active = False
    game.is_joining = False
    game.operation_end_time = None
    
    if len(alpha_alive) > 0 and len(beta_alive) == 0:
        winning_team = 'alpha'
        winning_emoji = '🔵'
        winners = alpha_alive
    elif len(beta_alive) > 0 and len(alpha_alive) == 0:
        winning_team = 'beta'
        winning_emoji = '🔴'
        winners = beta_alive
    else:
        await safe_send(
            context, game.chat_id,
            "💥 **Both Teams Eliminated!** It's a draw!",
            parse_mode=ParseMode.MARKDOWN
        )
        del games[game.chat_id]
        return
    
    winner_names = []
    for user_id in winners:
        player = game.players[user_id]
        winner_names.append(player['first_name'])
        
        update_player_stats(user_id, player['username'], {
            'total_games': 1,
            'wins': 1,
            'kills': player['stats']['kills'],
            'damage_dealt': player['stats']['damage_dealt'],
            'damage_taken': player['stats']['damage_taken'],
            'heals_done': player['stats']['heals_done'],
            'loots_collected': player['stats']['loots']
        })
        
        if unlock_achievement(user_id, 'team_player'):
            await safe_send(
                context, user_id,
                "🏆 **Achievement Unlocked!**\n🤝 Team Player - Won a team game!",
                parse_mode=ParseMode.MARKDOWN
            )
    
    # Save game history (first winner)
    if winners:
        save_game_history(game, winners[0], game.players[winners[0]]['first_name'])
    
    victory_text = f"""
🏆 **TEAM VICTORY!**  
{winning_emoji} **Team {winning_team.title()} Wins!** 👑  

**Champions**  
{', '.join(winner_names)}  

**Game Stats**  
• Days Survived: {game.day}  
• Total Players: {len(game.players)}  

*Teamwork makes the dream work!* 🤝  
Play again: `/creategame`  
"""
    
    gif_url = get_random_gif('victory')
    await safe_send_animation(
        context, game.chat_id, gif_url,
        caption=victory_text,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Update losing team stats
    losing_team = 'beta' if winning_team == 'alpha' else 'alpha'
    for user_id in game.teams[losing_team]:
        player = game.players[user_id]
        update_player_stats(user_id, player['username'], {
            'total_games': 1,
            'deaths': 1,
            'kills': player['stats']['kills'],
            'damage_dealt': player['stats']['damage_dealt'],
            'damage_taken': player['stats']['damage_taken'],
            'heals_done': player['stats']['heals_done'],
            'loots_collected': player['stats']['loots']
        })
    
    del games[game.chat_id]

# ======================== ADDITIONAL COMMANDS ========================

async def map_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the battle map."""
    chat_id = update.effective_chat.id
    
    if chat_id not in games:
        await update.message.reply_text("No active game!")
        return
    
    game = games[chat_id]
    
    if not game.is_active:
        await update.message.reply_text("Game hasn't started yet!")
        return
    
    map_display = game.get_map_display()
    await update.message.reply_text(map_display, parse_mode=ParseMode.MARKDOWN)

async def position_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check your position on the map."""
    user_id = update.effective_user.id
    
    game = None
    for g in games.values():
        if user_id in g.players:
            game = g
            break
    
    if not game:
        await update.message.reply_text("You're not in any active game!")
        return
    
    if not game.is_active:
        await update.message.reply_text("Game hasn't started yet!")
        return
    
    player = game.players[user_id]
    
    if not player['alive']:
        await update.message.reply_text("You've been eliminated!")
        return
    
    px, py = player['position']
    targets_in_range = game.get_players_in_range(user_id)
    
    text = f"""
📍 **Your Position**: ({px}, {py})  

**Targets in Range ({len(targets_in_range)})**  
"""
    
    if targets_in_range:
        for target_id in targets_in_range:
            target = game.players[target_id]
            tx, ty = target['position']
            hp_ind = get_hp_indicator(target['hp'], target['max_hp'])
            text += f"• {hp_ind} {target['first_name']} @ ({tx}, {ty})\n"
    else:
        text += "No enemies in attack range!\n"
    
    text += f"\n*Attack range: {ATTACK_RANGE} cells*"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def achievements_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show player achievements."""
    user_id = update.effective_user.id
    achievements = get_player_achievements(user_id)
    stats = get_player_stats(user_id)
    
    text = f"""
🏅 **Your Achievements**  
*Unlocked: {len(achievements)}/{len(ACHIEVEMENTS)}*  

"""
    if not achievements:
        text += "No achievements yet! Play to unlock! 🚀\n"
    else:
        for ach_key, ach_data in ACHIEVEMENTS.items():
            status = "✅" if ach_key in achievements else "🔒"
            text += f"{status} {ach_data['emoji']} **{ach_data['name']}** - {ach_data['desc']}\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def top_killers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top killers."""
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    c.execute('''SELECT username, kills, total_games 
                 FROM players 
                 ORDER BY kills DESC 
                 LIMIT 10''')
    results = c.fetchall()
    conn.close()
    
    if not results:
        await update.message.reply_text("No data yet! Be the first to dominate!")
        return
    
    text = "💀 **Top Killers** \n\n"
    medals = ["🥇", "🥈", "🥉"]
    
    for i, (username, kills, games) in enumerate(results, 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        text += f"{medal} **{username}** - {kills} kills\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def top_survivors_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top survivors by win rate."""
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    c.execute('''SELECT username, wins, total_games 
                 FROM players 
                 WHERE total_games >= 5
                 ORDER BY (wins * 100.0 / total_games) DESC 
                 LIMIT 10''')
    results = c.fetchall()
    conn.close()
    
    if not results:
        await update.message.reply_text("Not enough data yet! Keep surviving!")
        return
    
    text = "🏆 **Top Survivors** \n\n"
    medals = ["🥇", "🥈", "🥉"]
    
    for i, (username, wins, games) in enumerate(results, 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        wr = int((wins / games) * 100)
        text += f"{medal} **{username}** - {wr}% win rate\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def compare_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Compare stats with another player."""
    user_id = update.effective_user.id
    stats1 = get_player_stats(user_id)
    
    if not stats1:
        await update.message.reply_text("You have no stats yet! Play a game first.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /compare @username")
        return
    
    username = context.args[0].replace('@', '')
    
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    c.execute('SELECT * FROM players WHERE username = ?', (username,))
    stats2 = c.fetchone()
    conn.close()
    
    if not stats2:
        await update.message.reply_text(f"Player {username} not found!")
        return
    
    _, u1, g1, w1, k1, d1, dmg1, _, h1, _, _, _, _ = stats1
    _, u2, g2, w2, k2, d2, dmg2, _, h2, _, _, _, _ = stats2
    
    def compare_val(v1, v2):
        if v1 > v2:
            return "🟢"
        elif v1 < v2:
            return "🔴"
        return "⚪"
    
    text = f"""
📊 **Comparison: {u1} vs {u2}**  

• **Games**: {compare_val(g1, g2)} {g1} vs {g2}  
• **Wins**: {compare_val(w1, w2)} {w1} vs {w2}  
• **Kills**: {compare_val(k1, k2)} {k1} vs {k2}  
• **Deaths**: {compare_val(d2, d1)} {d1} vs {d2}  
• **Damage**: {compare_val(dmg1, dmg2)} {dmg1} vs {dmg2}  
• **Healed**: {compare_val(h1, h2)} {h1} vs {h2}  

*🟢 You're ahead | 🔴 Opponent leads*  
"""
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def tips_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show game tips."""
    tips = [
        "💡 **Defense Tip**: Defend when your HP drops below 50 to stay in the fight!",
        "💡 **Attack Tip**: Target low-HP enemies to secure quick eliminations.",
        "💡 **Heal Tip**: Save potions for critical moments when you need big heals.",
        "💡 **Loot Tip**: Loot early to build a strong arsenal before battles.",
        "💡 **Strategy**: Mix your actions to keep opponents guessing!",
        "💡 **Timing**: Use shields when under attack, not after damage is done.",
        "💡 **Risk**: High risk = high reward. Attack when you have the surprise.",
        "💡 **Map Tip**: Position yourself strategically - corner enemies or flee to safety!",
        "💡 **AFK Warning**: Stay active! 3 missed turns = instant elimination!",
        "💡 **Team Tip**: Coordinate with teammates - focus fire on single targets!",
        "💡 **Range Tip**: Keep enemies at exactly 2 cells for safe attacks!",
        "💡 **Event Tip**: Adapt your strategy when cosmic events trigger!",
    ]
    
    tip = random.choice(tips)
    text = f"""
💡 **Strategy Tip**  
{tip}  
"""
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current game stats."""
    chat_id = update.effective_chat.id
    
    if chat_id not in games:
        await update.message.reply_text("No active game!")
        return
    
    game = games[chat_id]
    
    if not game.is_active:
        await update.message.reply_text("Game hasn't started yet!")
        return
    
    alive = game.get_alive_players()
    
    if game.mode == 'solo':
        sorted_players = sorted(
            [(uid, p) for uid, p in game.players.items() if p['alive']],
            key=lambda x: x[1]['hp'],
            reverse=True
        )
        
        text = f"""
📊 **Game Statistics - Day {game.day}**  

🚢 **Survivors**: {len(alive)}/{len(game.players)}  

"""
        for i, (uid, player) in enumerate(sorted_players, 1):
            hp_bar = get_progress_bar(player['hp'], player['max_hp'], 5)
            hp_ind = get_hp_indicator(player['hp'], player['max_hp'])
            px, py = player['position']
            text += f"{i}. {hp_ind} **{player['first_name']}** - HP: {player['hp']}/{player['max_hp']} {hp_bar}\n"
            text += f"   📍 ({px},{py}) | 💀 Kills: {player['stats']['kills']} | ⚔️ Damage: {player['stats']['damage_dealt']}\n"
    
    else:  # Team mode
        alpha_alive = game.get_alive_team_players('alpha')
        beta_alive = game.get_alive_team_players('beta')
        
        text = f"""
📊 **Team Game Statistics - Day {game.day}**  

🔵 **Team Alpha**: {len(alpha_alive)} alive  
🔴 **Team Beta**: {len(beta_alive)} alive  

"""
        text += "**🔵 Alpha Team**\n"
        for user_id in alpha_alive:
            player = game.players[user_id]
            hp_ind = get_hp_indicator(player['hp'], player['max_hp'])
            text += f"• {hp_ind} {player['first_name']} - {player['hp']} HP | 💀 {player['stats']['kills']}\n"
        
        text += "\n**🔴 Beta Team**\n"
        for user_id in beta_alive:
            player = game.players[user_id]
            hp_ind = get_hp_indicator(player['hp'], player['max_hp'])
            text += f"• {hp_ind} {player['first_name']} - {player['hp']} HP | 💀 {player['stats']['kills']}\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def extend_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Extend joining time (admin only)."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if chat_id not in games:
        await update.message.reply_text("No active game!")
        return
    
    game = games[chat_id]
    
    if not game.is_joining:
        await update.message.reply_text("Can only extend during joining phase!")
        return
    
    if not await is_admin(context, chat_id, user_id):
        await update.message.reply_text("Only admins can use this command!")
        return
    
    game.join_end_time += timedelta(seconds=30)
    
    caption = """
⏱️ **Time Extended!**  
*+30 seconds added to joining phase!*  
"""
    
    gif_url = get_random_gif('extend')
    await safe_send_animation(
        context, chat_id, gif_url,
        caption=caption,
        parse_mode=ParseMode.MARKDOWN
    )

async def endgame_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force end game (admin only)."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if chat_id not in games:
        await update.message.reply_text("No active game!")
        return
    
    if not await is_admin(context, chat_id, user_id):
        await update.message.reply_text("Only admins can use this command!")
        return
    
    game = games[chat_id]
    game.is_active = False
    game.is_joining = False
    game.operation_end_time = None
    
    await safe_send(
        context, chat_id,
        """
❌ **Game Terminated!**  
*Admin force-ended the game.*  

*Better luck next time!*  
""",
        parse_mode=ParseMode.MARKDOWN
    )
    
    del games[chat_id]

async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show global leaderboard."""
    leaders = get_leaderboard(10)
    
    if not leaders:
        await update.message.reply_text("🏆 **Leaderboard Empty!**\nBe the first legend!")
        return
    
    text = "🏆 **Global Leaderboard** \n\n"
    medals = ["🥇", "🥈", "🥉"]
    
    for i, (username, wins, games, kills, damage) in enumerate(leaders, 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        win_rate = int((wins/games)*100) if games > 0 else 0
        text += f"{medal} **{username}** - {wins} Wins ({win_rate}%)\n"
        text += f"   Kills: {kills} | Damage: {damage}\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def mystats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show personal statistics."""
    user_id = update.effective_user.id
    stats = get_player_stats(user_id)
    
    if not stats:
        await update.message.reply_text(" *No Statistics Yet!**\nPlay your first game to start tracking!")
        return
    
    # stats is (user_id, username, total_games, wins, kills, deaths, damage_dealt, damage_taken, heals_done, loots_collected, win_streak, best_streak, last_played)
    _, username, games, wins, kills, deaths, dmg_dealt, dmg_taken, heals, loots = stats[1:11]
    
    win_rate = int((wins/games)*100) if games > 0 else 0
    kd_ratio = round(kills/deaths, 2) if deaths > 0 else kills
    
    text = f"""
ðŸ"Š *Your Statistics*
*Captain: {username}*  

**Performance**  
â€¢ Games: {games}  
â€¢ Wins: {wins} ({win_rate}%)  
â€¢ K/D: {kd_ratio}  
â€¢ Kills: {kills} | Deaths: {deaths}  

**Combat Totals**  
â€¢ Damage Dealt: {dmg_dealt}  
â€¢ Damage Taken: {dmg_taken}  
â€¢ Healed: {heals}  
â€¢ Loots: {loots}  

*Keep conquering!* ðŸš€  
"""
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def myhp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check personal HP in current game."""
    user_id = update.effective_user.id
    
    game = None
    for g in games.values():
        if user_id in g.players:
            game = g
            break
    
    if not game:
        await update.message.reply_text("You're not in any active game!")
        return
    
    if not game.is_active:
        await update.message.reply_text("Game hasn't started yet!")
        return
    
    player = game.players[user_id]
    
    if not player['alive']:
        await update.message.reply_text("You've been eliminated!")
        return
    
    hp_bar = get_progress_bar(player['hp'], player['max_hp'])
    hp_ind = get_hp_indicator(player['hp'], player['max_hp'])
    rank = game.get_player_rank(user_id)
    px, py = player['position']
    
    text = f"""
🚢 **Your Flagship Status**  
{hp_ind} **HP**: {player['hp']}/{player['max_hp']} {hp_bar}  

**Battle Info**  
• Day: {game.day}  
• Position: ({px}, {py})  
• Rank: #{rank}  
• Kills: {player['stats']['kills']}  
• AFK Count: {player['afk_turns']}/3  

**Stats**  
• Damage Dealt: {player['stats']['damage_dealt']}  
• Damage Taken: {player['stats']['damage_taken']}  
• Healed: {player['stats']['heals_done']}  
• Moves: {player['stats']['moves']}  

*Stay alive, Captain!* ⚔️  
"""
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def inventory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show player's inventory."""
    user_id = update.effective_user.id
    
    game = None
    for g in games.values():
        if user_id in g.players:
            game = g
            break
    
    if not game:
        await update.message.reply_text("You're not in any active game!")
        return
    
    player = game.players[user_id]
    
    if not player['inventory']:
        text = """
📦 **Your Inventory**  
*Empty!*  

Loot to collect items!  
"""
    else:
        text = "📦 **Your Inventory** \n\n"
        
        for item_key in player['inventory']:
            item = LOOT_ITEMS[item_key]
            rarity_emoji = get_rarity_color(item['rarity'])
            
            if item['type'] == 'weapon':
                desc = f"+{item['bonus']} attack DMG"
            elif item['type'] == 'potion':
                desc = f"+{item['bonus']} healing"
            elif item['type'] == 'shield':
                desc = f"+{int(item['bonus']*100)}% reduction"
            elif item['type'] == 'energy':
                desc = f"+{item['bonus']} loot HP"
            else:
                desc = "Special bonus"
            
            text += f"{rarity_emoji} {item['emoji']} **{item_key.replace('_', ' ').title()}** ({item['rarity'].title()}) - {desc}\n"
        
        text += "\n*Items auto-used in next operation!*"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def ranking_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current game ranking."""
    chat_id = update.effective_chat.id
    
    if chat_id not in games:
        await update.message.reply_text("No active game!")
        return
    
    game = games[chat_id]
    
    if not game.is_active:
        await update.message.reply_text("Game hasn't started yet!")
        return
    
    sorted_players = sorted(
        game.players.items(),
        key=lambda x: (x[1]['alive'], x[1]['hp'], x[1]['stats']['kills']),
        reverse=True
    )
    
    text = f"🏅 **Current Rankings - Day {game.day}** \n\n"
    
    for i, (uid, player) in enumerate(sorted_players, 1):
        status = "🚢" if player['alive'] else "💀"
        hp_ind = get_hp_indicator(player['hp'], player['max_hp']) if player['alive'] else "💀"
        px, py = player['position']
        
        team_emoji = ""
        if game.mode == 'team' and player['team']:
            team_emoji = f" {'🔵' if player['team'] == 'alpha' else '🔴'}"
        
        text += f"{i}. {status} {hp_ind} **{player['first_name']}**{team_emoji}\n"
        text += f"   HP: {player['hp']}/{player['max_hp']} | Kills: {player['stats']['kills']} | Pos: ({px},{py})\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent game history."""
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    c.execute('''SELECT winner_name, total_players, total_rounds, end_time 
                 FROM game_history 
                 ORDER BY game_id DESC 
                 LIMIT 5''')
    results = c.fetchall()
    conn.close()
    
    if not results:
        await update.message.reply_text("No game history yet!")
        return
    
    text = "📜 **Recent Battles** \n\n"
    
    for winner, players, rounds, end_time in results:
        date = datetime.fromisoformat(end_time).strftime("%Y-%m-%d %H:%M")
        text += f"🏆 **{winner}** (Winner)\n"
        text += f"   Players: {players} | Days: {rounds}\n"
        text += f"   {date}\n\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Configure game settings (admin only)."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if not await is_admin(context, chat_id, user_id):
        await update.message.reply_text("Only admins can configure settings!")
        return
    
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    c.execute('SELECT * FROM group_settings WHERE chat_id = ?', (chat_id,))
    settings = c.fetchone()
    
    if not settings:
        c.execute('''INSERT INTO group_settings (chat_id) VALUES (?)''', (chat_id,))
        conn.commit()
        settings = (chat_id, 120, 120, 2, 10, 1)
    
    conn.close()
    
    text = f"""
⚙️ **Game Settings**  

• **Join Time**: {settings[1]}s  
• **Operation Time**: {settings[2]}s  
• **Min Players**: {settings[3]}  
• **Max Players**: {settings[4]}  
• **Spectators**: {"Yes" if settings[5] else "No"}  

*Change with*:  
• `/setjointime <seconds>`  
• `/setoptime <seconds>`  
"""
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel participation during joining."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if chat_id not in games:
        await update.message.reply_text("No active game!")
        return
    
    game = games[chat_id]
    
    if not game.is_joining:
        await update.message.reply_text("Can only cancel during joining phase!")
        return
    
    if user_id not in game.players:
        await update.message.reply_text("You're not in the game!")
        return
    
    team = game.players[user_id].get('team')
    if team:
        game.teams[team].remove(user_id)
    
    del game.players[user_id]
    
    await update.message.reply_text("""
❌ **Cancelled**  
*Removed from the game!*  
""")
    
    fake_message = type('obj', (object,), {
        'message_id': game.joining_message_id,
        'chat_id': chat_id
    })
    
    if game.mode == 'team':
        await display_team_joining_phase(fake_message, context, game, edit=True)
    else:
        await display_joining_phase(fake_message, context, game, edit=True)

async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Join an ongoing game."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    
    if chat_id not in games:
        await update.message.reply_text("No active game to join!")
        return
    
    game = games[chat_id]
    
    if not game.is_joining:
        await update.message.reply_text("Game has already started! Use /spectate to watch.")
        return
    
    # Check if banned
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM banned_players WHERE chat_id = ? AND user_id = ?', (chat_id, user_id))
    if c.fetchone():
        await update.message.reply_text("You are banned from games in this group!")
        conn.close()
        return
    conn.close()
    
    if game.mode == 'team':
        await update.message.reply_text("Use the inline buttons to join a team!")
        return
    
    success, msg = game.add_player(user_id, username, first_name)
    if success:
        await safe_send(
            context, chat_id,
            f"✅ **{first_name}** has joined the armada! 💥",
            parse_mode=ParseMode.MARKDOWN
        )
        await update.message.reply_text("Welcome aboard, Captain! 🚀")
        
        fake_message = type('obj', (object,), {
            'message_id': game.joining_message_id,
            'chat_id': chat_id
        })
        await display_joining_phase(fake_message, context, game, edit=True)
    else:
        await update.message.reply_text(msg)

async def leave_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Leave a game during joining phase."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    
    if chat_id not in games:
        await update.message.reply_text("No active game!")
        return
    
    game = games[chat_id]
    
    if not game.is_joining:
        await update.message.reply_text("Can only leave during joining phase!")
        return
    
    if user_id not in game.players:
        await update.message.reply_text("You're not in the game!")
        return
    
    team = game.players[user_id].get('team')
    if team:
        game.teams[team].remove(user_id)
    
    del game.players[user_id]
    await safe_send(
        context, chat_id,
        f"❌ **{first_name}** has abandoned ship! ⚠️",
        parse_mode=ParseMode.MARKDOWN
    )
    
    fake_message = type('obj', (object,), {
        'message_id': game.joining_message_id,
        'chat_id': chat_id
    })
    
    if game.mode == 'team':
        await display_team_joining_phase(fake_message, context, game, edit=True)
    else:
        await display_joining_phase(fake_message, context, game, edit=True)
    
    await update.message.reply_text("You've left the game!")

async def spectate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Spectate an ongoing game."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    
    if chat_id not in games:
        await update.message.reply_text("No active game to spectate!")
        return
    
    game = games[chat_id]
    
    if not game.settings['allow_spectators']:
        await update.message.reply_text("Spectators are not allowed in this game!")
        return
    
    if user_id in game.players:
        await update.message.reply_text("You can't spectate while playing!")
        return
    
    game.spectators.add(user_id)
    await update.message.reply_text(
        f"👁️ **{first_name}** is now spectating the game!",
        parse_mode=ParseMode.MARKDOWN
    )

async def setjointime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set joining phase time (admin only)."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if not await is_admin(context, chat_id, user_id):
        await update.message.reply_text("Only admins can use this command!")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /setjointime <seconds>")
        return
    
    seconds = int(context.args[0])
    if seconds < 30 or seconds > 600:
        await update.message.reply_text("Join time must be between 30 and 600 seconds!")
        return
    
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO group_settings (chat_id, join_time) VALUES (?, ?)', (chat_id, seconds))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"✅ Join time set to {seconds} seconds!",
        parse_mode=ParseMode.MARKDOWN
    )

async def setoptime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set operation phase time (admin only)."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if not await is_admin(context, chat_id, user_id):
        await update.message.reply_text("Only admins can use this command!")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /setoptime <seconds>")
        return
    
    seconds = int(context.args[0])
    if seconds < 30 or seconds > 600:
        await update.message.reply_text("Operation time must be between 30 and 600 seconds!")
        return
    
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO group_settings (chat_id, operation_time) VALUES (?, ?)', (chat_id, seconds))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"✅ Operation time set to {seconds} seconds!",
        parse_mode=ParseMode.MARKDOWN
    )

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a player from participating (admin only)."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if not await is_admin(context, chat_id, user_id):
        await update.message.reply_text("Only admins can use this command!")
        return
    
    if not context.args or not context.args[0].startswith('@'):
        await update.message.reply_text("Usage: /ban @username")
        return
    
    username = context.args[0].replace('@', '')
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM players WHERE username = ?', (username,))
    result = c.fetchone()
    
    if not result:
        await update.message.reply_text(f"Player @{username} not found!")
        conn.close()
        return
    
    banned_user_id = result[0]
    c.execute('INSERT OR IGNORE INTO banned_players (chat_id, user_id) VALUES (?, ?)', (chat_id, banned_user_id))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"🚫 **@{username}** has been banned from games in this group!",
        parse_mode=ParseMode.MARKDOWN
    )

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a player (admin only)."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if not await is_admin(context, chat_id, user_id):
        await update.message.reply_text("Only admins can use this command!")
        return
    
    if not context.args or not context.args[0].startswith('@'):
        await update.message.reply_text("Usage: /unban @username")
        return
    
    username = context.args[0].replace('@', '')
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM players WHERE username = ?', (username,))
    result = c.fetchone()
    
    if not result:
        await update.message.reply_text(f"Player @{username} not found!")
        conn.close()
        return
    
    banned_user_id = result[0]
    c.execute('DELETE FROM banned_players WHERE chat_id = ? AND user_id = ?', (chat_id, banned_user_id))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"✅ **@{username}** has been unbanned!",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_show_info(query, context):
    """Handle show info buttons."""
    data = query.data
    user_id = query.from_user.id
    
    if data == "show_rules":
        await query.answer()
        await query.message.reply_text(
            "📖 **Game Rules** available via `/rules` command",
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "show_leaderboard":
        await query.answer()
        leaders = get_leaderboard(5)
        
        if not leaders:
            text = "🏆 **Leaderboard Empty!**\nBe the first legend!"
        else:
            text = "🏆 **Top Players** \n\n"
            medals = ["🥇", "🥈", "🥉"]
            for i, (username, wins, games, kills, damage) in enumerate(leaders, 1):
                medal = medals[i-1] if i <= 3 else f"{i}."
                text += f"{medal} **{username}** - {wins} wins\n"
        
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    elif data == "show_mystats":
        await query.answer()
        stats = get_player_stats(user_id)
        
        if not stats:
            text = "📊 **No Stats Yet!**\nPlay your first game!"
        else:
            username, games, wins, kills, deaths, dmg, _, heals, loots, _, _, _ = stats[1:]
            win_rate = int((wins/games)*100) if games > 0 else 0
            text = f"""
📊 **Your Stats**  

• Games: {games}  
• Wins: {wins} ({win_rate}%)  
• Kills: {kills}  
• Damage: {dmg}  
• Healed: {heals}  
"""
        
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    elif data == "show_achievements":
        await query.answer()
        achievements = get_player_achievements(user_id)
        
        text = f"🏅 **Your Achievements** \n*Unlocked: {len(achievements)}/{len(ACHIEVEMENTS)}* \n\n"
        
        for ach_key, ach_data in ACHIEVEMENTS.items():
            status = "✅" if ach_key in achievements else "🔒"
            text += f"{status} {ach_data['emoji']} **{ach_data['name']}** \n"
        
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def handle_back_to_modes(query, context):
    """Handle back to mode selection."""
    chat_id = query.message.chat_id
    
    if chat_id not in games:
        await query.edit_message_caption("Game session expired!")
        return
    
    game = games[chat_id]
    
    keyboard = [
        [InlineKeyboardButton("⚔️ Solo Mode - Battle Royale", callback_data=f"mode_solo_{chat_id}")],
        [InlineKeyboardButton("🤝 Team Mode - Alpha vs Beta", callback_data=f"mode_team_{chat_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    caption = """
🚀 **Ship Battle Royale**  
*Choose your battle mode!* 🌌  

**Solo Mode**: Every captain for themselves!  
**Team Mode**: Alpha 🔵 vs Beta 🔴 warfare!  
"""
    
    try:
        await query.edit_message_caption(
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    except BadRequest:
        await query.edit_message_text(
            text=caption,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

def main():
    """Start the bot."""
    try:
        # Initialize the Application with the bot token
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Register command handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("rules", rules_command))
        application.add_handler(CommandHandler("creategame", creategame_command))
        application.add_handler(CommandHandler("join", join_command))
        application.add_handler(CommandHandler("leave", leave_command))
        application.add_handler(CommandHandler("spectate", spectate_command))
        application.add_handler(CommandHandler("achievements", achievements_command))
        application.add_handler(CommandHandler("top_killers", top_killers_command))
        application.add_handler(CommandHandler("top_survivors", top_survivors_command))
        application.add_handler(CommandHandler("compare", compare_command))
        application.add_handler(CommandHandler("tips", tips_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("map", map_command))
        application.add_handler(CommandHandler("position", position_command))
        application.add_handler(CommandHandler("extend", extend_command))
        application.add_handler(CommandHandler("endgame", endgame_command))
        application.add_handler(CommandHandler("leaderboard", leaderboard_command))
        application.add_handler(CommandHandler("mystats", mystats_command))
        application.add_handler(CommandHandler("myhp", myhp_command))
        application.add_handler(CommandHandler("inventory", inventory_command))
        application.add_handler(CommandHandler("ranking", ranking_command))
        application.add_handler(CommandHandler("history", history_command))
        application.add_handler(CommandHandler("settings", settings_command))
        application.add_handler(CommandHandler("cancel", cancel_command))
        application.add_handler(CommandHandler("setjointime", setjointime_command))
        application.add_handler(CommandHandler("setoptime", setoptime_command))
        application.add_handler(CommandHandler("ban", ban_command))
        application.add_handler(CommandHandler("unban", unban_command))
        
        # Register callback query handler for inline buttons
        application.add_handler(CallbackQueryHandler(button_handler))
        
        # Start the bot
        logger.info("🚀 Ship Battle Royale Bot Starting...")
        logger.info("✨ Features: AFK System, Map Grid, Cosmic Events, Team Mode")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Bot startup error: {e}")

if __name__ == '__main__':

    main()
