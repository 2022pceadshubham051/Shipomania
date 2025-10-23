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
import os # For backup

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
SUPPORTIVE_GROUP1_ID = -1003162937388
DEVELOPER_ID = 7460266461  # Your Telegram ID

# Anti-spam configuration
SPAM_COOLDOWN = {}
SPAM_LIMIT = 3  # commands per timeframe
SPAM_TIMEFRAME = 10  # seconds

# Coin system
DAILY_COIN_AMOUNT = 50
WIN_COIN_BONUS = 150
LAST_DAILY_CLAIM = {}


# ======================== LEVEL & XP SYSTEM ========================
XP_PER_WIN = 100
XP_PER_KILL = 25
XP_PER_GAME = 10

# Define player levels and their requirements
LEVELS = {
    1: {'xp': 0, 'name': 'Recruit', 'emoji': '🔰'},
    2: {'xp': 500, 'name': 'Soldier', 'emoji': '⭐'},
    3: {'xp': 1200, 'name': 'Commander', 'emoji': '⭐⭐'},
    4: {'xp': 2500, 'name': 'Captain', 'emoji': '⭐⭐⭐'},
    5: {'xp': 4500, 'name': 'Admiral', 'emoji': '🌟'},
    6: {'xp': 7000, 'name': 'Fleet Admiral', 'emoji': '🌟🌟'},
    7: {'xp': 10000, 'name': 'Grand Admiral', 'emoji': '👑'},
    8: {'xp': 15000, 'name': 'Legendary Hero', 'emoji': '💎'},
}

def get_player_level(total_xp):
    """Get player's current level based on total XP."""
    current_level = 1
    for level in sorted(LEVELS.keys(), reverse=True):
        if total_xp >= LEVELS[level]['xp']:
            current_level = level
            break
    return current_level

def get_xp_for_next_level(current_level):
    """Get XP required for next level."""
    if current_level + 1 in LEVELS:
        return LEVELS[current_level + 1]['xp']
    # Max level - no next level
    return LEVELS[current_level]['xp'] + 10000

def get_level_info(level):
    """Get level info by level number."""
    return LEVELS.get(level, LEVELS[1])

def calculate_xp_progress(current_level, total_xp):
    """Calculate XP progress percentage to next level."""
    current_level_xp = LEVELS[current_level]['xp']
    next_level_xp = get_xp_for_next_level(current_level)
    
    if current_level == 8:  # Max level
        return 100
    
    progress = ((total_xp - current_level_xp) / (next_level_xp - current_level_xp)) * 100
    return min(100, max(0, progress))

# ======================== BOT USERNAME ========================
# Replace with your actual bot username (without @)
BOT_USERNAME = "shipbattlebot"  # Change this to your bot's username

# ======================== MISSING COMMAND HANDLERS ========================
async def challenges_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show daily challenges and rewards."""
    user_id = update.effective_user.id
    
    challenges = {
        'first_kill': {
            'name': 'First Blood',
            'desc': 'Get your first kill in a game',
            'reward': 50,
            'emoji': '🩸'
        },
        'triple_kill': {
            'name': 'Triple Threat',
            'desc': 'Get 3 kills in one game',
            'reward': 150,
            'emoji': '🔥'
        },
        'survivor': {
            'name': 'Last One Standing',
            'desc': 'Win a solo game',
            'reward': 200,
            'emoji': '🏆'
        },
        'collector': {
            'name': 'Item Collector',
            'desc': 'Collect 10 items in one game',
            'reward': 100,
            'emoji': '📦'
        },
        'healer': {
            'name': 'Support Role',
            'desc': 'Heal 200 HP in one game',
            'reward': 75,
            'emoji': '💊'
        },
    }
    
    text = """
┌─────────────────────────────────────
   🎯 DAILY CHALLENGES
└─────────────────────────────────────

Complete challenges to earn bonus coins!

"""
    
    for key, challenge in challenges.items():
        text += f"{challenge['emoji']} **{challenge['name']}**\n"
        text += f"   {challenge['desc']}\n"
        text += f"   Reward: +{challenge['reward']} 🪙\n\n"
    
    text += "*Challenges reset daily!* ⏰"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def cosmetics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available cosmetic items and skins."""
    user_id = update.effective_user.id
    stats = get_player_stats(user_id)
    
    if not stats:
        await update.message.reply_text("❌ No stats yet! Play first.")
        return
    
    # FIX: Handle coins safely - ensure it's an int
    try:
        coins = int(stats[16]) if stats and len(stats) > 16 else 0
    except (ValueError, TypeError):
        coins = 0
    
    cosmetics = {
        'ship_skin_red': {
            'name': '🔴 Red Fury',
            'desc': 'Aggressive red spaceship',
            'cost': 500,
            'rarity': 'rare'
        },
        'ship_skin_blue': {
            'name': '🔵 Frost Rider',
            'desc': 'Cool blue icy ship',
            'cost': 500,
            'rarity': 'rare'
        },
        'ship_skin_gold': {
            'name': '🟡 Golden Legend',
            'desc': 'Legendary golden vessel',
            'cost': 2000,
            'rarity': 'legendary'
        },
        'trail_fire': {
            'name': '🔥 Fire Trail',
            'desc': 'Leave burning trails',
            'cost': 750,
            'rarity': 'epic'
        },
        'trail_ice': {
            'name': '❄️ Frost Trail',
            'desc': 'Leave icy trails',
            'cost': 750,
            'rarity': 'epic'
        },
    }
    
    text = f"""
┌──────────────────────────────────────────
   🎨 COSMETICS SHOP
└──────────────────────────────────────────

💰 Your Balance: {coins} 🪙

**Available Cosmetics:**

"""
    
    for key, cosmetic in cosmetics.items():
        affordable = "✅" if coins >= cosmetic['cost'] else "❌"
        rarity_color = get_rarity_color(cosmetic['rarity'])
        text += f"{affordable} {cosmetic['name']}\n"
        text += f"   {cosmetic['desc']}\n"
        text += f"   {rarity_color} Cost: {cosmetic['cost']} 🪙\n\n"
    
    text += "*More cosmetics coming soon!* ✨"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ======================== SHOP & TITLES ========================
PLAYER_TITLES = {
    'novice_captain': {'name': '⭐ Novice Captain', 'cost': 0, 'emoji': '⭐'},
    'space_pirate': {'name': '🏴‍☠️ Space Pirate', 'cost': 500, 'emoji': '🏴‍☠️'},
    'star_admiral': {'name': '🔱 Star Admiral', 'cost': 1500, 'emoji': '🔱'},
    'void_wanderer': {'name': '🌀 Void Wanderer', 'cost': 3000, 'emoji': '🌀'},
    'galaxy_conqueror': {'name': '👑 Galaxy Conqueror', 'cost': 5000, 'emoji': '👑'},
    'immortal_god': {'name': '✨ Immortal God', 'cost': 10000, 'emoji': '✨'}
}

# ======================== DATABASE SETUP ========================
def init_database():
    """Initialize SQLite database for persistent data."""
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    
    # 1. CREATE the players table IF IT DOES NOT EXIST (First run)
    c.execute('''CREATE TABLE IF NOT EXISTS players (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        total_games INTEGER DEFAULT 0,
        wins INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0,
        kills INTEGER DEFAULT 0,
        deaths INTEGER DEFAULT 0,
        damage_dealt INTEGER DEFAULT 0,
        damage_taken INTEGER DEFAULT 0,
        heals_done INTEGER DEFAULT 0,
        loots_collected INTEGER DEFAULT 0,
        win_streak INTEGER DEFAULT 0,
        best_streak INTEGER DEFAULT 0,
        total_score INTEGER DEFAULT 0,
        betrayals INTEGER DEFAULT 0,
        alliances_formed INTEGER DEFAULT 0,
        last_played TEXT,
        coins INTEGER DEFAULT 0,
        title TEXT DEFAULT 'novice_captain'
    )''')
    
    # 2. Add other tables (These were okay, but keep them for completeness)
    c.execute('''CREATE TABLE IF NOT EXISTS game_history (
        game_id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        winner_id INTEGER,
        winner_name TEXT,
        total_players INTEGER,
        total_rounds INTEGER,
        map_name TEXT,
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
    
    # 3. Handle older versions by checking columns (Now safe, but only necessary
    # if you were migrating from a version without coins/title columns)
    # Since the full CREATE TABLE IF NOT EXISTS command above includes all columns, 
    # this dynamic check is now redundant for new databases, but harmless.
    # We will remove the dynamic check for simplicity, as the full CREATE statement handles it.
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    c.execute('UPDATE players SET coins = 0 WHERE coins IS NULL OR typeof(coins) != "integer"')
    conn.commit()
    conn.close()

# init_database() # Call it here if outside a function

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
    'meteor': 'https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExcXcxczg4M3ByMGI1MzFvYW4zZ3E2dzI0ZDJvYmx0a2xzdGM0OHNzcSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/dD114a2D1TwEUscuMs/giphy.gif',
    'boost': 'https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExd3N4YWdkdmRoazNtczNpamY2cnRrMHdwYTBncHBta2oyYmR6cDMzaCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/v532chtg1u147AIixq/giphy.gif'
}

# ======================== GAME CONSTANTS ========================
HP_START = 100
ATTACK_DAMAGE = (20, 25)
HEAL_AMOUNT = (8, 16)
DEFEND_REDUCTION = 0.5
CRIT_CHANCE = 0.20
CRIT_MULTIPLIER = 1.5
AFK_TURNS_LIMIT = 3
ATTACK_RANGE = 2
ALLIANCE_DURATION = 2  # turns
BETRAYAL_DAMAGE_BONUS = 1.5

# ======================== MAP SYSTEMS ========================
MAPS = {
    'classic': {
        'name': '🗺️ Classic Arena',
        'size': 5,
        'emoji': '⬜',
        'description': 'Standard 5x5 battlefield'
    },
    'volcano': {
        'name': '🌋 Volcanic Wasteland',
        'size': 6,
        'emoji': '🟥',
        'description': '6x6 dangerous terrain with hazards'
    },
    'ice': {
        'name': '❄️ Frozen Tundra',
        'size': 5,
        'emoji': '🟦',
        'description': '5x5 slippery ice field'
    },
    'urban': {
        'name': '🏙️ Urban Warfare',
        'size': 7,
        'emoji': '⬛',
        'description': '7x7 city combat zone'
    },
    'space': {
        'name': '🌌 Deep Space',
        'size': 8,
        'emoji': '🟪',
        'description': '8x8 infinite void battlefield'
    }
}

LOOT_ITEMS = {
    # Weapons
    'laser_gun': {'type': 'weapon', 'bonus': 20, 'rarity': 'rare', 'emoji': '🔫', 'desc': '+20 DMG for one attack'},
    'plasma_cannon': {'type': 'weapon', 'bonus': 35, 'rarity': 'epic', 'emoji': '💥', 'desc': '+35 DMG for one attack'},
    'nova_blaster': {'type': 'weapon', 'bonus': 50, 'rarity': 'legendary', 'emoji': '🌟', 'desc': '+50 DMG for one attack'},
    'pulse_rifle': {'type': 'weapon', 'bonus': 28, 'rarity': 'epic', 'emoji': '⚡', 'desc': '+28 DMG & ignore shields'},
    
    # Shields
    'shield_gen': {'type': 'shield', 'bonus': 0.3, 'rarity': 'rare', 'emoji': '🛡️', 'desc': '30% reduction for 1 turn'},
    'fortress_shield': {'type': 'shield', 'bonus': 0.5, 'rarity': 'epic', 'emoji': '🏰', 'desc': '50% reduction for 1 turn'},
    'quantum_shield': {'type': 'shield', 'bonus': 0.7, 'rarity': 'legendary', 'emoji': '✨', 'desc': '70% reduction for 1 turn'},
    'reflective_shield': {'type': 'shield', 'bonus': 0.4, 'rarity': 'rare', 'emoji': '🪞', 'desc': '40% reduction & reflect 20% DMG'},
    
    # Energy/Healing
    'energy_core': {'type': 'energy', 'bonus': 15, 'rarity': 'common', 'emoji': '⚡', 'desc': 'Restore 15 HP on pickup'},
    'quantum_core': {'type': 'energy', 'bonus': 30, 'rarity': 'epic', 'emoji': '✨', 'desc': 'Restore 30 HP on pickup'},
    'life_essence': {'type': 'energy', 'bonus': 50, 'rarity': 'legendary', 'emoji': '💚', 'desc': 'Restore 50 HP on pickup'},
    'medkit': {'type': 'energy', 'bonus': 25, 'rarity': 'rare', 'emoji': '🏥', 'desc': 'Restore 25 HP + cure AFK'},
    
    # Utility
    'stealth_device': {'type': 'utility', 'bonus': 0, 'rarity': 'legendary', 'emoji': '👻', 'desc': 'Hide from map 1 turn'},
    'emp_grenade': {'type': 'utility', 'bonus': 0, 'rarity': 'rare', 'emoji': '💣', 'desc': 'Reduce next attack by 50%'},
    'teleport_beacon': {'type': 'utility', 'bonus': 0, 'rarity': 'epic', 'emoji': '🌀', 'desc': 'Teleport to random location'},
    'radar_jammer': {'type': 'utility', 'bonus': 0, 'rarity': 'rare', 'emoji': '📡', 'desc': 'Hide position for 1 turn'},
    'speed_boost': {'type': 'utility', 'bonus': 0, 'rarity': 'rare', 'emoji': '💨', 'desc': 'Move 2 cells instead of 1'},
}

RARITY_WEIGHTS = {'common': 40, 'rare': 35, 'epic': 20, 'legendary': 5}

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
    },
        'double_damage_round': {
        'name': '⚡ Double Damage Round',
        'desc': 'All attacks deal 2x damage this round!',
        'trigger': 'round_start',
        'effect': 'damage_multiplier',
        'value': 2.0
    },
    'healing_surge': {
        'name': '💚 Healing Surge',
        'desc': 'All heals restore 50% extra HP!',
        'trigger': 'round_start',
        'effect': 'heal_multiplier',
        'value': 1.5
    },
    'treasure_chest': {
        'name': '💰 Treasure Chest',
        'desc': 'Random players gain bonus coins!',
        'trigger': 'round_end',
        'effect': 'coin_reward',
        'value': 100
    },
    'item_rain': {
        'name': '🎁 Item Rain',
        'desc': 'All players receive free items!',
        'trigger': 'round_start',
        'effect': 'free_item',
        'value': 1
    },
    'shield_dome': {
        'name': '🛡️ Shield Dome',
        'desc': 'All players gain temporary shields!',
        'trigger': 'round_start',
        'effect': 'shield_all',
        'value': 0.4
    },
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
    'explorer': {'name': 'Space Explorer', 'desc': 'Move 50 times on the map', 'emoji': '🧭'},
    'betrayer': {'name': 'Traitor', 'desc': 'Betray an ally', 'emoji': '😈'},
    'diplomat': {'name': 'Diplomat', 'desc': 'Form 10 alliances', 'emoji': '🤝'}
}

# ======================== ANTI-SPAM SYSTEM ========================
def check_spam(user_id):
    """Check if user is spamming commands."""
    current_time = datetime.now()
    
    if user_id not in SPAM_COOLDOWN:
        SPAM_COOLDOWN[user_id] = {'count': 1, 'first_time': current_time}
        return False
    
    user_data = SPAM_COOLDOWN[user_id]
    time_diff = (current_time - user_data['first_time']).total_seconds()
    
    if time_diff > SPAM_TIMEFRAME:
        SPAM_COOLDOWN[user_id] = {'count': 1, 'first_time': current_time}
        return False
    
    user_data['count'] += 1
    
    if user_data['count'] > SPAM_LIMIT:
        return True
    
    return False

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
        self.map_type = 'classic'
        self.map_size = 5
        self.map_grid = [[[] for _ in range(5)] for _ in range(5)]
        self.teams = {'alpha': set(), 'beta': set()}
        self.map_votes = {}
        self.map_voting = False
        self.map_vote_end_time = None
        self.alliances = {}  # {user_id: {'ally': other_user_id, 'turns_left': 2}}
        self._operation_countdown_running = False # New flag to prevent duplicate countdowns
        
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
            'max_players': 20,
            'allow_spectators': 1
        }
    
    def set_map(self, map_type):
        """Set the game map."""
        self.map_type = map_type
        self.map_size = MAPS[map_type]['size']
        self.map_grid = [[[] for _ in range(self.map_size)] for _ in range(self.map_size)]
    
    def add_player(self, user_id, username, first_name, team=None):
        """Add player with detailed stats."""
        if len(self.players) >= self.settings['max_players']:
            return False, "🚫 Fleet at max capacity!"
        
        if user_id not in self.players:
            x, y = random.randint(0, self.map_size-1), random.randint(0, self.map_size-1)
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
            
            # Check alliance
            if user_id in self.alliances and self.alliances[user_id]['ally'] == target_id:
                continue
            
            # Team mode: can't attack teammates
            if self.mode == 'team' and player['team'] == target['team']:
                continue
            
            tx, ty = target['position']
            distance = abs(px - tx) + abs(py - ty)
            
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
        new_x, new_y = x, y
        if direction == 'up' and x > 0:
            new_x -= 1
        elif direction == 'down' and x < self.map_size - 1:
            new_x += 1
        elif direction == 'left' and y > 0:
            new_y -= 1
        elif direction == 'right' and y < self.map_size - 1:
            new_y += 1
        
        player['position'] = (new_x, new_y)
        self.map_grid[new_x][new_y].append(user_id)
        player['stats']['moves'] += 1
        
        return True
    
    def get_map_display(self):
        """Minimalist grid map with box layout, no numbering."""
        map_data = MAPS.get(self.map_type, MAPS['classic'])
        n = self.map_size

        header = (
            f"🗺️ **{map_data['name']}** – {n}x{n}\n"
            f"*{map_data.get('description', '')}*\n\n"
        )

        lines = []
        horizontal = "   +" + "---+" * n  # border for top/mid/bottom
 
        lines.append("```")
        lines.append(horizontal)
        for i in range(n):
            row_cells = []
            for j in range(n):
                cell_players = self.map_grid[i][j]

                # decide emoji for each cell
                if not cell_players:
                    symbol = map_data['emoji']
                else:
                    alive_count = sum(
                        1 for uid in cell_players if self.players.get(uid, {}).get('alive', False)
                    )
                    if alive_count == 0:
                        symbol = "👻"
                    elif alive_count == 1:
                        uid = next(
                            (uid for uid in cell_players if self.players[uid]['alive']),
                            None
                        )
                        if uid and self.mode == 'team':
                            symbol = "🔵" if self.players[uid]['team'] == 'alpha' else "🔴"
                        else:
                            symbol = "🟢"
                    elif alive_count == 2:
                        symbol = "🟡"
                    else:
                        symbol = "🔴"
                row_cells.append(f" {symbol} ")

            # one clean row
            row_line = "   |" + "|".join(row_cells) + "|"
            lines.append(row_line)
            lines.append(horizontal)
        lines.append("```")

    # legend
        legend = (
            f"\n**Legend:** {map_data['emoji']} Empty | 🟢 1 | 🟡 2 | 🔴 3+ | 👻 Dead"
        )
        if self.mode == 'team':
            legend += "\n**Teams:** 🔵 Alpha | 🔴 Beta"

    
        return header + "\n".join(lines) + legend


    
    def get_player_rank(self, user_id):
        """Get player's current rank."""
        alive = self.get_alive_players()
        # Ensure the player is still alive before calculating rank based on the alive list order
        if user_id in alive:
            # Sort players by HP and then Kills to determine dynamic rank
            sorted_alive = sorted(
                [(uid, self.players[uid]) for uid in alive],
                key=lambda x: (x[1]['hp'], x[1]['stats']['kills']),
                reverse=True
            )
            # Find the index of the player in the sorted list
            for i, (uid, _) in enumerate(sorted_alive, 1):
                if uid == user_id:
                    return i
        return len(self.players) + 1 # Dead or not found
    
    def form_alliance(self, user_id1, user_id2):
        """Form alliance between two players."""
        self.alliances[user_id1] = {'ally': user_id2, 'turns_left': ALLIANCE_DURATION}
        self.alliances[user_id2] = {'ally': user_id1, 'turns_left': ALLIANCE_DURATION}
    
    def break_alliance(self, user_id):
        """Break an alliance (betrayal)."""
        if user_id in self.alliances:
            ally_id = self.alliances[user_id]['ally']
            del self.alliances[user_id]
            if ally_id in self.alliances:
                del self.alliances[ally_id]
            return ally_id
        return None
    
    def update_alliances(self):
        """Update alliance durations."""
        to_remove = []
        # Create a copy of keys to iterate over while modifying the dict
        for user_id in list(self.alliances.keys()):
            if user_id in self.alliances: # Check again in case it was deleted by the ally
                data = self.alliances[user_id]
                data['turns_left'] -= 1
                if data['turns_left'] <= 0:
                    to_remove.append(user_id)
        
        for user_id in to_remove:
            if user_id in self.alliances:
                ally_id = self.alliances[user_id]['ally']
                del self.alliances[user_id]
                if ally_id in self.alliances:
                    del self.alliances[ally_id]

# ======================== DATABASE HELPERS ========================
def update_player_stats(user_id, username, stats_update):
    """Update player statistics."""
    try:
        conn = sqlite3.connect('ship_battle.db')
        c = conn.cursor()
        
        # Sanitize username for safety
        safe_username = username if username else str(user_id)
        
        c.execute('SELECT user_id FROM players WHERE user_id = ?', (user_id,))
        if not c.fetchone():
            # Initial insert with default title and coins
            c.execute('''INSERT INTO players (user_id, username, coins, title) VALUES (?, ?, ?, ?)''',
                     (user_id, safe_username, 0, 'novice_captain'))
        
        update_fields = []
        values = []
        for key, value in stats_update.items():
            if key in ['wins', 'losses', 'kills', 'deaths', 'damage_dealt', 'damage_taken', 'heals_done', 'loots_collected', 'total_games', 'total_score', 'betrayals', 'alliances_formed', 'coins']:
                 update_fields.append(f"{key} = {key} + ?")
                 values.append(value)
            elif key == 'title': # Special handling for title update
                 update_fields.append(f"{key} = ?")
                 values.append(value)
        
        # Always update username in case it changed
        update_fields.append("username = ?")
        values.append(safe_username)

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
                     (chat_id, winner_id, winner_name, total_players, total_rounds, map_name, start_time, end_time)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                 (game.chat_id, winner_id, winner_name, len(game.players),
                  game.day, game.map_type, game.start_time.isoformat(), datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error saving game: {e}")

def get_leaderboard(limit=10):
    """Get top players."""
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    c.execute('''SELECT username, wins, total_games, kills, damage_dealt, total_score, title 
                 FROM players 
                 ORDER BY total_score DESC, wins DESC, kills DESC 
                 LIMIT ?''', (limit,))
    results = c.fetchall()
    conn.close()
    return results

def get_player_stats(user_id):
    """Get player statistics with safety validation."""
    try:
        conn = sqlite3.connect('ship_battle.db')
        c = conn.cursor()
        c.execute('SELECT * FROM players WHERE user_id = ?', (user_id,))
        stats = c.fetchone()
        conn.close()
        
        if not stats:
            return None
        
        # Validate stats length
        if len(stats) < 18:
            logger.warning(f"Incomplete stats for user {user_id}")
            return None
        
        # === CRITICAL FIX: Ensure Coins (index 16) is a valid integer ===
        coins_index = 16
        try:
            # Try to convert the value to an integer
            _ = int(stats[coins_index])
        except (ValueError, TypeError):
            # If conversion fails (i.e., it's a timestamp), fix the DB entry
            logger.warning(f"Fixing corrupted coin value for user {user_id}: {stats[coins_index]} -> 0")
            
            # Update DB to set coins to 0
            conn_fix = sqlite3.connect('ship_battle.db')
            c_fix = conn_fix.cursor()
            c_fix.execute('UPDATE players SET coins = ? WHERE user_id = ?', (0, user_id))
            conn_fix.commit()
            conn_fix.close()
            
            # Recreate stats tuple with fixed coin value for current execution
            stats = list(stats)
            stats[coins_index] = 0
            stats = tuple(stats)
        # =============================================================
        
        # Validate and fix title if needed
        title_key = stats[17]
        if not title_key or title_key not in PLAYER_TITLES:
            # Fix corrupted title
            logger.info(f"Fixing corrupted title for user {user_id}: {title_key} -> novice_captain")
            update_player_stats(user_id, stats[1], {'title': 'novice_captain'})
            # Reconstruct tuple with corrected title
            stats = stats[:17] + ('novice_captain',)
        
        return stats
        
    except Exception as e:
        logger.error(f"Error fetching player stats for {user_id}: {e}")
        return None

def get_player_stats_by_username(username):
    """Get player statistics by username (case-insensitive, underscore-friendly lookup)."""
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    # Using GLOB for case-insensitive/approximate matching might be tricky. The best approach is to store a normalized username (lowercase, no underscores) if we rely heavily on lookup, but since we are limited to modifying this file, we will try to match exactly.
    c.execute('SELECT * FROM players WHERE username = ? COLLATE NOCASE', (username,))
    stats = c.fetchone()
    
    # Try another common case if no exact match (like user first_name is stored as username)
    if not stats:
        c.execute('SELECT * FROM players WHERE username LIKE ? COLLATE NOCASE', (f'%{username}%',))
        stats = c.fetchone()
        
    conn.close()
    return stats

def calculate_score(wins, kills, damage_dealt):
    """Calculate player score."""
    return (wins * 100) + (kills * 10) + (damage_dealt // 10)

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

def format_user_stats(stats):
    """Format user statistics in attractive UI."""
    if not stats:
        return "📊 **No Statistics Yet!**\n*Play your first game to start tracking!*"
    
    _, username, games, wins, losses, kills, deaths, dmg_dealt, dmg_taken, heals, loots, win_streak, best_streak, score, betrayals, alliances, coins, title_key = stats[:18]

    # SAFETY CHECK: Ensure title exists
    if not title_key or title_key not in PLAYER_TITLES:
        title_key = 'novice_captain'

    # ESCAPE username
    safe_username = escape_markdown_value(username)
    title_data = PLAYER_TITLES.get(title_key, PLAYER_TITLES['novice_captain'])
    
    win_rate = int((wins/games)*100) if games > 0 else 0
    kd_ratio = round(kills/deaths, 2) if deaths > 0 else kills
    title_data = PLAYER_TITLES.get(title_key, PLAYER_TITLES['novice_captain'])
    
    # === FIX: Safely display coins (should be fixed by get_player_stats now, but keep this for safety) ===
    try:
        coins_display = int(coins)
    except (ValueError, TypeError):
        coins_display = 0
    # =======================================================================================================
    
    return f"""
┌──────────────┐
   📊 PLAYER STATS    
└──────────────┘

👤 **Captain:** {safe_username}
{title_data['emoji']} **Title:** {title_data['name']}
📌 **Your Rank:** #{get_user_rank(stats[0])}

┌──────────────┐
  💰 **ECONOMY**
┣───────────────┫
   🪙 Coins: {coins_display} 🪙
└───────────────┘

┌───────────────┐
  🎮 **GAME RECORD**
┣────────────────┫
   🎯 Games: {games}
   ⚔️ Win%: {win_rate}%
   🏆 Wins: {wins} | ❌ Lost: {losses}
   ⭐ Score: {score}
└────────────────┘

┌────────────────┐
  ⚡ COMBAT STATS
┣────────────────┫
   👁️ Kills: {kills} | 🪦 Deaths: {deaths}
   📈 K/D Ratio: {kd_ratio}
   ⚔️ Damage: {dmg_dealt}
   🛡️ Taken: {dmg_taken}
└────────────────┘

┌────────────────┐
  🎯 SPECIAL STATS
┣────────────────┫
   💊 Healed: {heals} HP
   📦 Loots: {loots}
   🔥 Win Streak: {win_streak}
   🏅 Best Streak: {best_streak}
   🤝 Alliances: {alliances}
   😈 Betrayals: {betrayals}
└────────────────┘

*Keep dominating the battlefield!* 🚀
"""

def escape_markdown_value(text):
    """Escape markdown special characters safely.
    Prevents 'Can't parse entities' Telegram errors."""
    if not text or not isinstance(text, str):
        return str(text) if text else ""
    
    # Characters that break Markdown parsing in Telegram
    escape_chars = {
        '_': '\\_',
        '*': '\\*',
        '[': '\\[',
        ']': '\\]',
        '(': '\\(',
        ')': '\\)',
        '~': '\\~',
        '`': '\\`',
        '>': '\\>',
        '#': '\\#',
        '+': '\\+',
        '-': '\\-',
        '=': '\\=',
        '|': '\\|',
        '{': '\\{',
        '}': '\\}',
        '.': '\\.',
        '!': '\\!'
    }
    
    for char, escaped in escape_chars.items():
        text = text.replace(char, escaped)
    
    return text

def get_user_rank(user_id):
    """Get user's global rank."""
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    c.execute('''SELECT user_id FROM players ORDER BY total_score DESC, wins DESC, kills DESC''')
    results = c.fetchall()
    conn.close()
    
    for i, (uid,) in enumerate(results, 1):
        if uid == user_id:
            return i
    return 0

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

async def is_admin_or_owner(context, chat_id, user_id):
    """Check if user is admin or owner."""
    if user_id == DEVELOPER_ID:
        return True
    if user_id in ADMIN_IDS:
        return True
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except:
        return False

async def is_owner(user_id):
    """Check if user is the developer/owner."""
    return user_id == DEVELOPER_ID

async def pin_message(context, chat_id, message_id):
    """Pin a message in the chat."""
    try:
        await context.bot.pin_chat_message(chat_id, message_id, disable_notification=True)
    except Exception as e:
        logger.error(f"Failed to pin message: {e}")

def trigger_cosmic_event():
    """Randomly trigger a cosmic event."""
    if random.random() < 0.3:
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
            
            new_x, new_y = random.randint(0, game.map_size-1), random.randint(0, game.map_size-1)
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
    """Welcome message with enhanced UI."""
    user = update.effective_user
    
    if check_spam(user.id):
        await update.message.reply_text("⚠️ Slow down! Please wait before using commands again.")
        return
    
    # Ensure player is in DB on start
    update_player_stats(user.id, user.username, {})
    
    welcome_text = f"""
╔══════════════════════╗
      🚀 SHIP BATTLE ROYALE  
╚══════════════════════╝

👋 **Welcome, Captain {user.first_name}!**
*Conquer the Stars in Epic Space Combat* 🌌

┏━━━━━━━━━━━━━━━━━━━━━━┓
┃  🎮 QUICK START
┣━━━━━━━━━━━━━━━━━━━━━━┫
   /creategame - Launch Battle
   /help - All Commands
   /rules - Game Guide
   /mystats - Your Statistics
━━━━━━━━━━━━━━━━━━━━━━━

┏━━━━━━━━━━━━━━━━━━━━━━┓
┃  ⚡ EPIC FEATURES
┣━━━━━━━━━━━━━━━━━━━━━━┫
   ✅ Solo & Team Battles
   ✅ 5 Unique Battle Maps
   ✅ Alliance & Betrayal System
   ✅ Cosmic Events & Power-Ups
   ✅ AFK Auto-Elimination
   ✅ Real-Time Combat Strategy
   ✅ Global Leaderboards
   ✅ Achievement System
   ✅ Buyable Titles/Coins
━━━━━━━━━━━━━━━━━━━━━━━

*Ready to dominate the galaxy?* ✨
"""
    
    keyboard = [
        [
            InlineKeyboardButton("💬 Support Group", url=f"https://t.me/c/{str(SUPPORTIVE_GROUP1_ID)[4:]}/1"),
            InlineKeyboardButton("👨‍💻 Developer", url=f"tg://user?id={DEVELOPER_ID}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help categorized by buttons."""
    if check_spam(update.effective_user.id):
        await update.message.reply_text("⚠️ **Slow down!** Please wait before using commands again.")
        return
    
    help_text = """
╔══════════════════════╗
     📚 COMMAND CENTER    
╚══════════════════════╝

*Select a category to view commands:*
"""
    
    keyboard = [
        [InlineKeyboardButton("🎮 Game Commands", callback_data="help_game")],
        [InlineKeyboardButton("📊 Info Commands", callback_data="help_info")],
        [InlineKeyboardButton("🏆 Global Commands", callback_data="help_global")],
        [InlineKeyboardButton("⚙️ Settings/Admin", callback_data="help_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def help_callback_handler(query, context, category):
    """Handle help category button clicks."""
    if category == "help_game":
        text = """
╔══════════════════════╗
  🎮 GAME COMMANDS (Group Only)
┣━━━━━━━━━━━━━━━━━━━━━━┫
   /creategame - Start battle
   /join - Join game
   /leave - Leave before start
   /spectate - Watch as spectator
   /map - View battle map
   /ally @user - Form alliance (Solo)
   /betray - Break alliance (Solo)
   /cancel - Leave/Cancel joining
━━━━━━━━━━━━━━━━━━━━━━━
"""
    elif category == "help_info":
        text = """
╔══════════════════════╗
  📊 INFO COMMANDS
┣━━━━━━━━━━━━━━━━━━━━━━┫
   /stats - Game statistics (Group)
   /myhp - Your ship HP
   /inventory - Your items
   /ranking - Current ranking (Group)
   /position - Map position
   /history - Game history
   /rules - Game Guide
━━━━━━━━━━━━━━━━━━━━━━━
"""
    elif category == "help_global":
        text = """
╔══════════════════════╗
      🏆 GLOBAL COMMANDS
┣━━━━━━━━━━━━━━━━━━━━━━┫
   /mystats - Your Global Stats
   /leaderboard - Top players
   /achievements - Your badges
   /compare @user - Compare stats
   /tips - Strategy tips
   /daily - Claim daily coins 💰
   /shop - Buy player titles
━━━━━━━━━━━━━━━━━━━━━━━
"""
    elif category == "help_settings":
        text = """
╔══════════════════════╗
  ⚙️ SETTINGS & ADMIN
┣━━━━━━━━━━━━━━━━━━━━━━┫
   /settings - View Group Settings (Admin)
   /setjointime <sec> - Set join time (Admin)
   /setoptime <sec> - Set operation time (Admin)
   /extend - Extend joining time (Admin)
   /endgame - Force end game (Admin)
   
   *Owner Only Commands:*
   /broadcast <msg>
   /backup
   /ban @user
   /unban @user
━━━━━━━━━━━━━━━━━━━━━━━
"""
    else:
        text = "Invalid help category."
        
    keyboard = [[InlineKeyboardButton("◀️ Back to Categories", callback_data="help_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    except BadRequest:
        # If it's the main menu again, just re-send the main help.
        if category != "help_main":
             await query.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def help_main_handler(query, context):
    """Go back to the main help menu."""
    await query.answer()
    await help_command(query.message, context) # Re-use the existing start logic

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detailed game rules with enhanced UI, including Loot explanation."""
    if check_spam(update.effective_user.id):
        await update.message.reply_text("⚠️ **Slow down!** Please wait before using commands again.")
        return
    
    loot_desc = ""
    for item_key, item_data in LOOT_ITEMS.items():
        rarity = item_data['rarity'].title()
        emoji = item_data['emoji']
        name = item_key.replace('_', ' ').title()
        desc = item_data['desc']
        loot_desc += f"   {emoji} **{name}** ({rarity}): {desc}\n"
    
    rules_text = f"""
╔══════════════════════╗
      📖 GAME RULES GUIDE   
╚══════════════════════╝

🎯 **Objective:** Be the last ship standing!

━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ COMBAT & ACTIONS
   🗡️ Attack: 20-25 DMG + 20% Crit (Range: 2 cells)
   🛡️ Defend: 50% damage reduction
   💊 Heal: 8-16 HP restore
   📦 Loot: Collect random rare items
   🧭 Move: Navigate tactical map
   
   ⚠️ **AFK:** Miss 3 turns = Auto-Elimination!

━━━━━━━━━━━━━━━━━━━━━━━━━━

2️⃣ ALLIANCE SYSTEM (Solo Mode)
   • `/ally @user`: Form alliance (2 turns)
   • `/betray`: Break alliance (😈 150% damage bonus!)

━━━━━━━━━━━━━━━━━━━━━━━━━━

3️⃣ LOOT ITEMS
{loot_desc}━━━━━━━━━━━━━━━━━━━━━━━━━━

4️⃣ MAPS & EVENTS
   • 5 Unique Battlefields (5x5 to 8x8)
   • Cosmic Events: Meteor Storm, Solar Boost, etc.

━━━━━━━━━━━━━━━━━━━━━━━━━━

5️⃣ TITLES & COINS 💰
   • `/daily`: Claim daily coins
   • Game Win: +{WIN_COIN_BONUS} Coins
   • `/shop`: Buy unique titles to display on your stats!

*Good luck, Captain! Conquer the stars!* ✨
"""
    
    gif_url = GIFS['rules']
    await safe_send_animation(
        context, update.effective_chat.id, gif_url,
        caption=rules_text, parse_mode=ParseMode.MARKDOWN
    )

async def creategame_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create new game - GROUP ONLY."""
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ This command works only in groups!")
        return
    
    if check_spam(update.effective_user.id):
        await update.message.reply_text("⚠️ Slow down!Please wait before using commands again.")
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if chat_id in games:
        if games[chat_id].is_active:
            await update.message.reply_text(
                "⚔️ Battle in progress!\nWait for current game to end or use /spectate!",
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
╔══════════════════════╗
      🚀 SHIP BATTLE ROYALE  
╚══════════════════════╝

*Choose your battle mode!* 🌌

**⚔️ Solo Mode**
Every captain for themselves!
Last ship standing wins! 💀

**🤝 Team Mode**
Alpha 🔵 vs Beta 🔴 warfare!
Coordinate with your team! 🎯

*Select mode to begin!* ✨
"""
    
    gif_url = get_random_gif('joining')
    sent_msg = await safe_send_animation(
        context, chat_id, gif_url,
        caption=caption,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        await context.bot.send_message(
            SUPPORTIVE_GROUP_ID,
            f"🎮 **New Game Created!**\n**Group:** {update.effective_chat.title}\n**Creator:** {user_name}",
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
        # Pass the original DM message ID to allow 'Back' to return to DM menu
        await handle_operation_selection(query, context)
    elif data.startswith('target_'):
        await handle_target_selection(query, context)
    elif data.startswith('move_'):
        await handle_move_selection(query, context)
    elif data.startswith('show_'):
        await handle_show_info(query, context)
    elif data.startswith('map_vote_'):
        await handle_map_vote(query, context)
    elif data.startswith('help_'):
        if data == 'help_main':
            # Re-send main help command to avoid infinite loop
             await help_main_handler(query, context)
        else:
            await help_callback_handler(query, context, data)
    elif data.startswith('shop_'):
        await handle_shop_selection(query, context)

async def handle_mode_selection(query, context):
    """Handle game mode selection."""
    data = query.data
    chat_id = query.message.chat_id
    
    if chat_id not in games:
        await query.edit_message_caption("❌ Game session expired!")
        return
    
    game = games[chat_id]
    mode = data.split('_')[1]
    
    if mode == 'solo':
        await start_map_voting(query, context, game, 'solo')
    elif mode == 'team':
        await start_map_voting(query, context, game, 'team')

async def start_map_voting(query, context, game, mode):
    """Start map voting phase."""
    game.mode = mode
    game.map_voting = True
    game.map_vote_end_time = datetime.now() + timedelta(seconds=30)
    
    # Add creator to game
    success, msg = game.add_player(
        game.creator_id,
        query.from_user.username,
        game.creator_name
    )
    
    caption = f"""
╔══════════════════════╗
  🗺️ MAP SELECTION     
╚══════════════════════╝

*Vote for your battlefield!* 🎯
**Time:** 30 seconds

**Available Maps:**

🗺️ **Classic Arena** (5x5)
   Standard balanced battlefield

🌋 **Volcanic Wasteland** (6x6)
   Dangerous terrain with hazards

❄️ **Frozen Tundra** (5x5)
   Slippery ice field

🏙️ **Urban Warfare** (7x7)
   Large city combat zone

🌌 **Deep Space** (8x8)
   Massive void battlefield

*Vote now or admins will select!* ⏰
"""
    
    keyboard = [
        [InlineKeyboardButton("🌋 Volcanic Wasteland", callback_data=f"map_vote_volcano"),
        InlineKeyboardButton("❄️ Frozen Tundra", callback_data=f"map_vote_ice")],
        [InlineKeyboardButton("🏙️ Urban Warfare", callback_data=f"map_vote_urban"),
        InlineKeyboardButton("🌌 Deep Space", callback_data=f"map_vote_space")],
        [InlineKeyboardButton("🗺️ Classic Arena", callback_data=f"map_vote_classic")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_caption(
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        game.joining_message_id = query.message.message_id
    except BadRequest:
        pass
    
    await safe_send(
        context, game.chat_id,
        f"🗺️ **Map Voting Started!** Vote for your battlefield in 30 seconds!",
        parse_mode=ParseMode.MARKDOWN
    )
    
    asyncio.create_task(map_voting_countdown(context, game))

async def handle_map_vote(query, context):
    """Handle map voting."""
    data = query.data
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    
    if chat_id not in games:
        await query.answer("No active game!", show_alert=True)
        return
    
    game = games[chat_id]
    
    if not game.map_voting:
        await query.answer("Voting ended!", show_alert=True)
        return
    
    map_type = data.split('_')[2]
    game.map_votes[user_id] = map_type
    
    await query.answer(f"✅ Voted for {MAPS[map_type]['name']}!")
    
    # Update vote counts
    vote_counts = {}
    for voted_map in game.map_votes.values():
        vote_counts[voted_map] = vote_counts.get(voted_map, 0) + 1
    
    votes_text = "\n".join([f"{MAPS[m]['emoji']} {MAPS[m]['name']}: {c} votes" for m, c in vote_counts.items()])
    
    await safe_send(
        context, game.chat_id,
        f"🗳️ **{query.from_user.first_name}** voted for {MAPS[map_type]['name']}!\n\n**Current Votes:**\n{votes_text}",
        parse_mode=ParseMode.MARKDOWN
    )

async def map_voting_countdown(context, game):
    """Countdown for map voting."""
    try:
        await asyncio.sleep(30)
        
        game.map_voting = False
        
        # Count votes
        if game.map_votes:
            vote_counts = {}
            for voted_map in game.map_votes.values():
                vote_counts[voted_map] = vote_counts.get(voted_map, 0) + 1
            
            # Get winning map
            winning_map = max(vote_counts, key=vote_counts.get)
            game.set_map(winning_map)
            
            await safe_send(
                context, game.chat_id,
                f"🎯 **Map Selected: {MAPS[winning_map]['name']}**\n*{vote_counts[winning_map]} votes*",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            # Default to classic
            game.set_map('classic')
            await safe_send(
                context, game.chat_id,
                f"🎯 **Default Map: {MAPS['classic']['name']}**",
                parse_mode=ParseMode.MARKDOWN
            )
        
        # Start joining phase
        if game.mode == 'solo':
            await start_solo_mode_after_voting(context, game)
        else:
            await start_team_mode_after_voting(context, game)
            
    except Exception as e:
        logger.error(f"Map voting error: {e}")

async def start_solo_mode_after_voting(context, game):
    """Start solo mode after map selection."""
    game.is_joining = True
    game.join_end_time = datetime.now() + timedelta(seconds=game.settings['join_time'])
    
    fake_message = type('obj', (object,), {
        'message_id': game.joining_message_id,
        'chat_id': game.chat_id
    })
    
    await display_joining_phase(fake_message, context, game, edit=True)
    
    # Pin the joining message
    await pin_message(context, game.chat_id, game.joining_message_id)
    
    await safe_send(
        context, game.chat_id,
        f"🚀 **{game.creator_name}** rallied the fleet!\n*Solo Battle Royale - {MAPS[game.map_type]['name']}*",
        parse_mode=ParseMode.MARKDOWN
    )
    
    asyncio.create_task(joining_countdown(context, game))

async def start_team_mode_after_voting(context, game):
    """Start team mode after map selection."""
    game.is_joining = True
    game.join_end_time = datetime.now() + timedelta(seconds=game.settings['join_time'])
    
    fake_message = type('obj', (object,), {
        'message_id': game.joining_message_id,
        'chat_id': game.chat_id
    })
    
    await display_team_joining_phase(fake_message, context, game, edit=True)
    
    # Pin the joining message
    await pin_message(context, game.chat_id, game.joining_message_id)
    
    await safe_send(
        context, game.chat_id,
        f"🤝 **{game.creator_name}** initiated Team Battle!\n*Alpha 🔵 vs Beta 🔴 - {MAPS[game.map_type]['name']}*",
        parse_mode=ParseMode.MARKDOWN
    )
    
    asyncio.create_task(joining_countdown(context, game))

async def display_team_joining_phase(message, context, game, edit=False):
    """Display/update team joining phase message with enhanced UI."""
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
            alpha_list += f"   {alpha_count}. 🔵 {name}\n"
        elif data['team'] == 'beta':
            beta_count += 1
            beta_list += f"   {beta_count}. 🔴 {name}\n"
    
    if not alpha_list:
        alpha_list = "   *Awaiting warriors...*\n"
    if not beta_list:
        beta_list = "   *Awaiting warriors...*\n"
    
    caption = f"""
╔══════════════════════╗
      🤝 TEAM BATTLE        
╚══════════════════════╝

🗺️ **Map:** {MAPS[game.map_type]['name']}
⏱️ **Time:** {time_str}
👥 **Players:** {len(game.players)}/{game.settings['max_players']}

┏━━━━━━━━━━━━━━━━━━━━━━┓
  🔵 TEAM ALPHA ({alpha_count})
┣━━━━━━━━━━━━━━━━━━━━━━┫
{alpha_list}━━━━━━━━━━━━━━━━━━━━━━━

┏━━━━━━━━━━━━━━━━━━━━━━┓
      🔴 TEAM BETA ({beta_count})
┣━━━━━━━━━━━━━━━━━━━━━━┫
{beta_list}━━━━━━━━━━━━━━━━━━━━━━━

*Choose your team and fight together!*
Min {game.settings['min_players']} players required
"""
    
    if remaining <= 30 and remaining > 0:
        caption += f"\n⚠️ **HURRY! {remaining}s left!**"
    
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
    
    if user_id in game.players:
        old_team = game.players[user_id].get('team')
        if old_team == team:
            await query.answer(f"Already in Team {team.title()}!", show_alert=True)
            return
        
        if old_team:
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
            stats = get_player_stats(user_id)
            title_key = stats[17] if stats and len(stats) > 17 else 'novice_captain'
            if not title_key or title_key not in PLAYER_TITLES:
                title_key = 'novice_captain'
            title_emoji = PLAYER_TITLES[title_key]['emoji']

            team_emoji = '🔵' if team == 'alpha' else '🔴'
            await safe_send(
                context, game.chat_id,
                f"✨ {title_emoji} **{first_name}** has entered the battlefield! {team_emoji} Team {team.title()}",
                parse_mode=ParseMode.MARKDOWN
)
            await query.answer(f"Welcome to Team {team.title()}! 🚀")
        else:
            await query.answer(msg, show_alert=True)
    
    await display_team_joining_phase(query.message, context, game, edit=True)

async def display_joining_phase(message, context, game, edit=False):
    """Display/update joining phase message with enhanced UI."""
    remaining = max(0, int((game.join_end_time - datetime.now()).total_seconds()))
    time_str = format_time(remaining)
    
    player_list = ""
    for i, (uid, data) in enumerate(game.players.items(), 1):
        # Use player's set title in the list
        stats = get_player_stats(uid)
        title_key = stats[17] if stats else 'novice_captain'
        title_data = PLAYER_TITLES.get(title_key, PLAYER_TITLES['novice_captain'])
        name = data['first_name']
        player_list += f"   {i}. 🚢 {title_data['emoji']} {name}\n"
    
    if not player_list:
        player_list = "   *Awaiting brave souls...*\n"
    
    caption = f"""
╔══════════════════════╗
  ⚔️ SOLO BATTLE ROYALE 
╚══════════════════════╝

🗺️ **Map:** {MAPS[game.map_type]['name']}
⏱️ **Time:** {time_str}
👥 **Players:** {len(game.players)}/{game.settings['max_players']}

┏━━━━━━━━━━━━━━━━━━━━━━┓
      🚢 FLEET ROSTER
┣━━━━━━━━━━━━━━━━━━━━━━┫
{player_list}━━━━━━━━━━━━━━━━━━━━━━━

*Join the ultimate space battle!*
Min {game.settings['min_players']} players required

⚠️ **AFK Warning:** 3 missed turns = Auto-Elimination!
"""
    
    if remaining <= 30 and remaining > 0:
        caption += f"\n⚠️ **HURRY! {remaining}s left!**"
    
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
                    f"⏰ **{remaining} seconds** remaining to join! 🚀",
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
                f"✅ **{first_name}** joined the armada! 💥",
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
                f"❌ **{first_name}** abandoned ship! ⚠️",
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
    """Start the actual game with enhanced UI."""
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
    
    # --- Integration of Map and Day Start Message ---
    map_display = game.get_map_display()
    
    caption = f"""
╔══════════════════════╗
      ⚔️ BATTLE COMMENCING!  
╚══════════════════════╝

🎮 Mode: {mode_text}
🗺️ Map: {MAPS[game.map_type]['name']}
🚢 Ships: {len(game.players)}

┏━━━━━━━━━━━━━━━━━━━━━━┓
  ⚡ COMBAT PARAMETERS
┣━━━━━━━━━━━━━━━━━━━━━━┫
   ❤️ Starting HP: 100
   🎯 Attack Range: 2 cells
   ⏱️ Operation Time: {format_time(game.settings['operation_time'])}
   ⚠️ AFK Limit: 3 turns
━━━━━━━━━━━━━━━━━━━━━━━

*Day {game.day} - The Hunt Begins!*
*May the best Captain win!* 🏆

{map_display}
"""
    # ---------------------------------------------
    
    gif_url = get_random_gif('start')
    await safe_send_animation(
        context, game.chat_id, gif_url,
        caption=caption,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Send operation DMs with inline button
    for user_id in game.players:
        await send_operation_choice_button(context, game, user_id)
    
    game.operation_end_time = datetime.now() + timedelta(seconds=game.settings['operation_time'])
    asyncio.create_task(operation_countdown(context, game))

async def send_operation_choice_button(context, game, user_id):
    """Send button to open bot DM for operations - ONLY TO USER DM."""
    player = game.players[user_id]
    hp = player['hp']
    hp_bar = get_progress_bar(hp, player['max_hp'])
    hp_ind = get_hp_indicator(hp, player['max_hp'])
    
    text = f"""
╔═════════════════════════════════╗
     🚢 DAY {game.day} OPERATIONS
╚═════════════════════════════════╝

{hp_ind} **HP:** {hp}/{player['max_hp']}
{hp_bar}

⚠️ **AFK:** {player['afk_turns']}/3
⏱️ **Time:** {format_time(game.settings['operation_time'])}

*Click below to choose your operation in DM!* ⚡
"""
    
    # FIXED: Use actual bot username from context
    bot_username = context.bot.username or "shipomania_bot"  # Fallback
    keyboard = [[InlineKeyboardButton("⚔️ Choose Operation in DM", url=f"https://t.me/{bot_username}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # SEND ONLY TO USER'S DM - NOT TO GROUP
    await safe_send(context, user_id, text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    # Then send detailed DM with actual buttons
    await send_operation_dm(context, game, user_id)

async def send_operation_dm(context, game, user_id):
    """Send operation selection to player via DM with enhanced UI - ONLY IN DM."""
    player = game.players[user_id]
    hp = player['hp']
    hp_bar = get_progress_bar(hp, player['max_hp'])
    hp_ind = get_hp_indicator(hp, player['max_hp'])
    px, py = player['position']
    
    inventory_text = ""
    if player['inventory']:
        for item_key in player['inventory']:
            item = LOOT_ITEMS[item_key]
            rarity_emoji = get_rarity_color(item['rarity'])
            inventory_text += f"   {rarity_emoji} {item['emoji']} {item_key.replace('_', ' ').title()}\n"
    else:
        inventory_text = "   *Empty - Loot for power-ups!* 📦\n"
    
    team_text = ""
    if game.mode == 'team':
        team_emoji = "🔵" if player['team'] == 'alpha' else "🔴"
        team_text = f"**Team:** {team_emoji} {player['team'].title()}\n"
    
    alliance_text = ""
    if user_id in game.alliances:
        ally_id = game.alliances[user_id]['ally']
        ally_name = game.players[ally_id]['first_name']
        turns_left = game.alliances[user_id]['turns_left']
        alliance_text = f"🤝 **Ally:** {ally_name} ({turns_left} turns left)\n"
    
    # Get Title
    stats = get_player_stats(user_id)
    title_key = stats[17] if stats and len(stats) > 17 else 'novice_captain'
    if not title_key or title_key not in PLAYER_TITLES:
        title_key = 'novice_captain'
    title_data = PLAYER_TITLES.get(title_key, PLAYER_TITLES['novice_captain'])
    
    text = f"""
╔═════════════════════════════════╗
      🚢 YOUR FLAGSHIP     
╚═════════════════════════════════╝

**Day {game.day}** | {MAPS[game.map_type]['name']}
{title_data['emoji']} **Title:** {title_data['name']}

{hp_ind} **HP:** {hp}/{player['max_hp']}
{hp_bar}

📍 **Position:** ({px}, {py})
{team_text}{alliance_text}
┌─────────────────────────────────┐
      ⚡ BATTLE INFO
├─────────────────────────────────┤
   ⚠️ AFK Count: {player['afk_turns']}/3
   ⏱️ Time: {format_time(game.settings['operation_time'])}
   👁️ Kills: {player['stats']['kills']}
└─────────────────────────────────┘

┌─────────────────────────────────┐
      🎖️ YOUR ARSENAL
├─────────────────────────────────┤
{inventory_text}└─────────────────────────────────┘

*Choose your operation wisely!* ⚔️
"""
    
    keyboard = [
        [InlineKeyboardButton("🗡️ Attack Enemy", callback_data=f"operation_attack_{user_id}_{game.chat_id}")],
        [
            InlineKeyboardButton("🛡️ Raise Shields", callback_data=f"operation_defend_{user_id}_{game.chat_id}"),
            InlineKeyboardButton("💊 Repair Hull", callback_data=f"operation_heal_{user_id}_{game.chat_id}")
        ],
        [
            InlineKeyboardButton("📦 Scavenge Loot", callback_data=f"operation_loot_{user_id}_{game.chat_id}"),
            InlineKeyboardButton("🧭 Move Ship", callback_data=f"operation_move_{user_id}_{game.chat_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    gif_url = get_random_gif('operation')
    await safe_send_animation(
        context, user_id, gif_url,
        caption=text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def stats_detailed_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed stats with level and XP."""
    user_id = update.effective_user.id
    stats = get_player_stats(user_id)
    
    if not stats:
        await update.message.reply_text("❌ No stats yet! Play a game first.")
        return
    
    # Extract stats
    username = escape_markdown_value(stats[1])
    games = stats[2]
    wins = stats[3]
    kills = stats[5]
    damage = stats[7]
    coins = stats[16]
    title_key = stats[17]
    
    # Calculate total XP (simplified: wins * 100 + kills * 25)
    total_xp = (wins * XP_PER_WIN) + (kills * XP_PER_KILL)
    current_level = get_player_level(total_xp)
    next_level_xp = get_xp_for_next_level(current_level)
    xp_progress = ((total_xp - LEVELS[current_level]['xp']) / 
                   (next_level_xp - LEVELS[current_level]['xp'])) * 100
    
    if title_key not in PLAYER_TITLES:
        title_key = 'novice_captain'
    
    title_data = PLAYER_TITLES[title_key]
    
    text = f"""
┌──────────────────────────────┐
    📊 DETAILED STATS    
└──────────────────────────────┘

👤 **{username}**
{title_data['emoji']} {title_data['name']}

┌──────────────────────────────┐
  ⭐ LEVEL {current_level}
┣──────────────────────────────┫
   XP: {total_xp}
   Progress: {int(xp_progress)}%
   Next: {next_level_xp} XP
└──────────────────────────────┘

┌──────────────────────────────┐
  💰 ECONOMY
┣──────────────────────────────┫
   Coins: {coins} 🪙
   Win Rate: {int((wins/games)*100) if games > 0 else 0}%
└──────────────────────────────┘

┌──────────────────────────────┐
  ⚔️ COMBAT
┣──────────────────────────────┫
   Games: {games}
   Wins: {wins}
   Kills: {kills}
   Damage: {damage}
└──────────────────────────────┘

*Keep playing to unlock perks!* 🚀
"""
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def operation_countdown(context, game):
    """Consolidated countdown for operation selection."""
    try:
        if game._operation_countdown_running:
            return
        game._operation_countdown_running = True

        last_update_time = datetime.now()
        last_reminder_times = {}
        
        while game.is_active and game.operation_end_time:
            remaining = int((game.operation_end_time - datetime.now()).total_seconds())
            
            if remaining <= 0:
                break

            alive_players = game.get_alive_players()
            ready_count = sum(1 for uid in alive_players if game.players[uid]['operation'] is not None)
            all_ready = (ready_count == len(alive_players))

            if all_ready:
                await safe_send(
                    context, game.chat_id,
                    f"🚀 **ALL READY!** Processing Day {game.day} immediately!",
                    parse_mode=ParseMode.MARKDOWN
                )
                break

            # Status update ONLY every 20 seconds (not spam)
            current_time = datetime.now()
            if (current_time - last_update_time).total_seconds() >= 20:
                pending_players = [
                    game.players[uid]['first_name'] 
                    for uid in alive_players 
                    if game.players[uid]['operation'] is None
                ]
                
                if pending_players:
                    pending_names = ", ".join(pending_players[:3])
                    if len(pending_players) > 3:
                        pending_names += f" +{len(pending_players)-3} more"

                    update_text = f"""
⏱️ **Day {game.day} Operations** - {format_time(remaining)} remaining
✅ Ready: {ready_count}/{len(alive_players)}
⏳ Waiting for: {pending_names}
"""
                    await safe_send(
                        context, game.chat_id,
                        update_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                
                last_update_time = current_time

            # DM reminders ONLY at critical times
            if remaining in [60, 30, 15, 10]:
                for uid in alive_players:
                    player = game.players[uid]
                    
                    if uid not in last_reminder_times or last_reminder_times[uid] != remaining:
                        if player['operation'] is None:
                            await safe_send(
                                context, uid,
                                f"⏰ **{remaining}s left!** Choose operation or auto-defend!",
                                parse_mode=ParseMode.MARKDOWN
                            )
                            last_reminder_times[uid] = remaining

            await asyncio.sleep(1)

        if game.is_active:
            await process_day_operations(context, game)

    except Exception as e:
        logger.error(f"Countdown error: {e}")
    finally:
        game._operation_countdown_running = False

async def handle_operation_selection(query, context):
    """Handle operation button press."""
    data = query.data
    parts = data.split('_')
    operation = parts[1]
    user_id = int(parts[2])
    # The last part is chat_id, use it for generating the back button URL
    chat_id = int(parts[3]) 
    
    game = None
    for g in games.values():
        if user_id in g.players:
            game = g
            break
    
    if not game:
        await query.answer("Game not found!", show_alert=True)
        # Attempt to clean up message if possible
        await query.edit_message_caption("❌ Game not found or session expired!")
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
        await show_target_selection(query, context, game, user_id, chat_id)
    elif operation == 'move':
        await show_move_selection(query, context, game, user_id, chat_id)
    elif operation == 'back':
        # Re-send the main operation DM
        await send_operation_dm(context, game, user_id)
    else:
        # For defend, heal, loot, the target is implicitly 'None'
        await set_operation(query, context, game, user_id, operation, None, chat_id)

# c.py (Changes in show_target_selection)

async def show_target_selection(query, context, game, user_id, chat_id):
    """Show available targets for attack with enhanced UI."""
    targets_in_range = game.get_players_in_range(user_id)
    
    if not targets_in_range:
        await query.answer("No enemies in range! Move closer or choose another action.", show_alert=True)
        # Re-send the main operation menu since attack is not possible
        await send_operation_dm(context, game, user_id)
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
            team_emoji = f" {'🔵' if target['team'] == 'alpha' else '🔴'}"
        
        keyboard.append([
            InlineKeyboardButton(
                f"{team_emoji} {hp_ind} {name} ({hp} HP) @ ({tx},{ty})",
                callback_data=f"target_{target_id}_{user_id}_{chat_id}"
            )
        ])
    
    # Back button that goes back to the main operation menu
    keyboard.append([InlineKeyboardButton("◀️ Back to Operations", callback_data=f"operation_back_{user_id}_{chat_id}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = """
╔══════════════════════╗
      🗡️ TARGET SELECTION   
╚══════════════════════╝

*Choose your target wisely!*

**HP Indicators**
🟢 High (75+) - Tough
🟡 Medium (25-75) - Fair
🔴 Low (<25) - Weak

*Tip: Strike the wounded!* ⚔️
"""
    
    try:
        # 1. Try to edit as a GIF message caption
        await query.edit_message_caption(caption=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    except BadRequest:
        try:
            # 2. If it fails (e.g., message was already edited to plain text), try to edit as text
            await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        except BadRequest as e:
            if 'message is not modified' not in str(e):
                 logger.error(f"Failed to edit DM message in show_target_selection: {e}")
            await query.answer("Cannot update message content.", show_alert=True)


async def show_move_selection(query, context, game, user_id, chat_id):
    """Show movement options with enhanced map."""
    player = game.players[user_id]
    px, py = player['position']
    
    keyboard = []
    
    # Check boundaries and add movement options
    if px > 0:
        keyboard.append([InlineKeyboardButton("⬆️ Move Up", callback_data=f"move_up_{user_id}_{chat_id}")])
    if px < game.map_size - 1:
        keyboard.append([InlineKeyboardButton("⬇️ Move Down", callback_data=f"move_down_{user_id}_{chat_id}")])
    if py > 0:
        keyboard.append([InlineKeyboardButton("⬅️ Move Left", callback_data=f"move_left_{user_id}_{chat_id}")])
    if py < game.map_size - 1:
        keyboard.append([InlineKeyboardButton("➡️ Move Right", callback_data=f"move_right_{user_id}_{chat_id}")])
    
    # Back button that goes back to the main operation menu
    keyboard.append([InlineKeyboardButton("◀️ Back to Operations", callback_data=f"operation_back_{user_id}_{chat_id}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Show enhanced mini map (3x3 grid around player)
    mini_map = f"📍 **Your Position:** ({px}, {py})\n\n"
    map_size = game.map_size
    
    # Generate Coordinates header
    coord_header = "   " + " ".join([f"{j}" for j in range(max(0, py-1), min(map_size, py+2))])
    mini_map += f"```{coord_header}```\n"

    for i in range(max(0, px-1), min(map_size, px+2)):
        row = f"```{i} "
        for j in range(max(0, py-1), min(map_size, py+2)):
            cell_emoji = "⬜" # Default empty cell
            if i == px and j == py:
                cell_emoji = "🚢" # Player's position
            elif game.map_grid[i][j]:
                alive_count = sum(1 for uid in game.map_grid[i][j] if game.players.get(uid,{}).get('alive', False))
                if alive_count > 0:
                    cell_emoji = "🔴" # Enemy near
            row += cell_emoji + " "
        mini_map += row.strip() + "```\n"
        
    
    text = f"""
╔══════════════════════╗
      🧭 SHIP NAVIGATION    
╚══════════════════════╝

{mini_map}

Legend: 🚢 You | 🔴 Enemy Ship | ⬜ Empty Space

*Strategic positioning is key!*
- Attack range: 2 cells
- Move to engage or evade

Choose your direction: ⚡
"""
    
    try:
        await query.edit_message_caption(caption=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    except BadRequest:
        try:
            await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        except:
            await query.answer("Cannot update message content.", show_alert=True)

async def handle_move_selection(query, context):
    """Handle movement direction selection."""
    data = query.data
    parts = data.split('_')
    direction = parts[1]
    user_id = int(parts[2])
    chat_id = int(parts[3])
    
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
    
    await set_operation(query, context, game, user_id, 'move', None, chat_id)
    await query.answer(f"Moved from {old_pos} to {new_pos}! ✅")

async def handle_target_selection(query, context):
    """Handle target selection for attack."""
    data = query.data
    parts = data.split('_')
    target_id = int(parts[1])
    user_id = int(parts[2])
    chat_id = int(parts[3])
    
    game = None
    for g in games.values():
        if user_id in g.players:
            game = g
            break
    
    if not game:
        await query.answer("Game not found!", show_alert=True)
        return
    
    await set_operation(query, context, game, user_id, 'attack', target_id, chat_id)

# c.py (Changes in set_operation)

async def set_operation(query, context, game, user_id, operation, target_id, chat_id):
    """Set player's operation with enhanced confirmation."""
    player = game.players[user_id]
    player['operation'] = operation
    player['target'] = target_id
    player['last_action_time'] = datetime.now()
    player['afk_turns'] = 0
    
    op_names = {
        'attack': '🗡️ Attack',
        'defend': '🛡️ Defend',
        'heal': '💊 Heal',
        'loot': '📦 Loot',
        'move': '🧭 Move'
    }
    
    op_descriptions = {
        'attack': 'Unleash fury on your target!',
        'defend': 'Shields up! Reduce damage by 50%',
        'heal': 'Repair systems and restore HP',
        'loot': 'Scavenge for rare items',
        'move': 'Navigate to strategic position'
    }
    
    alive_players = game.get_alive_players()
    ready_count = sum(1 for uid in alive_players if game.players[uid]['operation'] is not None)
    
    text = f"""
╔══════════════════════╗
      ✅ OPERATION CONFIRMED 
╚══════════════════════╝

⚡ **{op_names[operation]}**
*{op_descriptions[operation]}*
"""
    
    if target_id:
        target_name = game.players[target_id]['first_name']
        text += f"\n🎯 **Target:** {target_name}\n"
    
    remaining = int((game.operation_end_time - datetime.now()).total_seconds()) if game.operation_end_time else 0
    text += f"""
┏━━━━━━━━━━━━━━━━━━━━━━┓
      📊 **STATUS**
┣━━━━━━━━━━━━━━━━━━━━━━┫
   ✅ Ready: {ready_count}/{len(alive_players)}
   ⏱️ Time: {format_time(remaining)}
━━━━━━━━━━━━━━━━━━━━━━━

*Locked in. Stars favor you!* ✨
"""
    
    # Simple button - just go back to group
    # Convert chat_id to group link format
    if str(chat_id).startswith('-100'):
        # Private group format
        group_id = str(chat_id)[4:]  # Remove "-100"
        group_link = f"https://t.me/c/{group_id}"
    else:
        # Channel format (Assuming a public channel/group for the link)
        group_link = f"https://t.me/{abs(chat_id)}"

    keyboard = [[InlineKeyboardButton("📲 Back to Battle", url=group_link)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        # 1. Try to edit as a GIF message caption (most common case after initial DM)
        await query.edit_message_caption(
            caption=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    except BadRequest as e:
        # 2. If it fails (e.g., message was already edited to plain text), try to edit as text
        if 'message is not modified' in str(e):
            # Harmless error, ignore
            pass
        else:
            try:
                await query.edit_message_text(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            except BadRequest as e2:
                # 3. Handle other errors like a message being too old to edit
                logger.error(f"Failed to edit DM message in set_operation after multiple tries: {e2}")
                await query.answer("Operation confirmed, but could not update DM message.", show_alert=False)

    
    await query.answer(f"{op_names[operation]} confirmed! ⚡")

async def process_day_operations(context, game):
    """Process all operations for the day with enhanced UI."""
    await safe_send(
        context, game.chat_id,
        f"🔄 **Processing Day {game.day} Operations...** Stand by! ⚡",
        parse_mode=ParseMode.MARKDOWN
    )
    
    await asyncio.sleep(2)
    
    # Update alliances
    game.update_alliances()
    
    # Check for cosmic event
    event_key, event_data = trigger_cosmic_event()
    event_log = []
    
    if event_key and event_data:
        game.active_event = event_key
        gif_url = GIFS.get('event', get_random_gif('operation'))
        
        await safe_send_animation(
            context, game.chat_id, gif_url,
            caption=f"""
╔══════════════════════╗
      🌌 COSMIC EVENT!     
╚══════════════════════╝

{event_data['emoji']} **{event_data['name']}**

*{event_data['desc']}*

Processing effects... ⚡
""",
            parse_mode=ParseMode.MARKDOWN
        )
        
        await asyncio.sleep(2)
        event_log = await apply_cosmic_event(context, game, event_key, event_data)
    
    # Handle AFK players
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
╔══════════════════════╗
      ⚠️ AFK ELIMINATION   
╚══════════════════════╝

*Ship lost in space!*

You were eliminated for inactivity!
Missed {AFK_TURNS_LIMIT} consecutive turns

Stay active next time! 🚀
""",
                    parse_mode=ParseMode.MARKDOWN
                )
                await safe_send(
                    context, game.chat_id,
                    f"⚠️ **{player['first_name']}** eliminated for being AFK! ({AFK_TURNS_LIMIT} missed turns)",
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
    
    # Apply event boost
    if game.event_effect and game.event_effect['type'] == 'damage_boost':
        base_attack = int(base_attack * game.event_effect['value'])
    
    attacks = defaultdict(list)
    defenders = set()
    healers = set()
    looters = set()
    movers = []
    betrayals = {}
    
    for user_id, player in game.players.items():
        if not player['alive']:
            continue
        
        op = player['operation']
        if op == 'attack' and player['target']:
            # Check for betrayal
            if user_id in game.alliances and game.alliances[user_id]['ally'] == player['target']:
                betrayals[user_id] = player['target']
                game.break_alliance(user_id)
            
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
    
    # Pre-check for EMP Grenade utility
    emp_targets = defaultdict(list)
    for target_id in attacks:
        target = game.players.get(target_id)
        if target and target['alive']:
            if 'EMP_grenade' in target['inventory']:
                emp_targets[target_id].append('EMP_grenade')
                target['inventory'].remove('EMP_grenade')
                
    for target_id, attackers in attacks.items():
        if target_id not in game.players or not game.players[target_id]['alive']:
            continue
        
        target = game.players[target_id]
        total_damage = 0
        crit_hit = False
        betrayal_hit = False
        
        for attacker_id in attackers:
            attacker = game.players[attacker_id]
        
            # Check for speed boost (can attack twice)
            if 'speed_boost' in attacker['inventory']:
                attacker['inventory'].remove('speed_boost')
                # Allow second attack
                if random.random() < 0.6:  # 60% chance to land second attack
                    bonus_damage = random.randint(*ATTACK_DAMAGE)
                    total_damage += bonus_damage
                    game.players[attacker_id]['stats']['damage_dealt'] += bonus_damage
            
            weapon_bonus = 0
            # Only use one weapon per attack turn
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
        
        # Apply EMP grenade reduction (applies to total incoming damage)
        emp_text = ""
        if target_id in emp_targets:
            total_damage = int(total_damage * 0.5)
            emp_text = " (💣 EMP Reduced!)"
        
        # Apply event shield
        if game.event_effect and game.event_effect['type'] == 'shield':
            defense_reduction += game.event_effect['value']
        
        # Apply shield item reduction (only one shield is consumed)
        shield_text = ""
        for item_key in target['inventory'][:]:
            item = LOOT_ITEMS[item_key]
            if item['type'] == 'shield':
                defense_reduction += item['bonus']
                target['inventory'].remove(item_key)
                shield_text = " (🛡️ Item Used)"
                break
        
        defense_reduction = min(0.8, defense_reduction)
        final_damage = int(total_damage * (1 - defense_reduction))
        
        target['hp'] -= final_damage
        target['stats']['damage_taken'] += final_damage
        
        attacker_names = ", ".join([game.players[a]['first_name'] for a in attackers])
        crit_text = " 💥CRIT!" if crit_hit else ""
        betrayal_text = " 😈BETRAYAL!" if betrayal_hit else ""
        defend_text = f" (🛡️{int(defense_reduction*100)}% blocked){shield_text}" if defense_reduction > 0 else shield_text
        hp_ind = get_hp_indicator(max(0, target['hp']), target['max_hp'])
        
        damage_log.append(
            f"{attacker_names} → {hp_ind} {target['first_name']}: {final_damage} DMG{crit_text}{betrayal_text}{defend_text}{emp_text}"
        )
    
    # Process heals
    heal_log = []
    for user_id in healers:
        player = game.players[user_id]
        heal_amount = base_heal
        
        # Energy core items do not stack with heal action (they auto-trigger on loot)
        
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
        player['stats']['loots'] += 1
        
        rarity_pool = []
        for item_key, item in LOOT_ITEMS.items():
            rarity_pool.extend([item_key] * RARITY_WEIGHTS[item['rarity']])
        
        new_item = random.choice(rarity_pool)
        item_data = LOOT_ITEMS[new_item]
        rarity_emoji = get_rarity_color(item_data['rarity'])
        
        # Special handling for energy cores (auto-heal)
        if item_data['type'] == 'energy':
            heal_amount = item_data['bonus']
            player['hp'] += heal_amount # Allow to exceed max HP temporarily (if design allows, currently it is hard limit)
            player['stats']['heals_done'] += heal_amount
            loot_log.append(
                f"📦 {player['first_name']} looted: {rarity_emoji} {item_data['emoji']} {new_item.replace('_', ' ').title()} (+{heal_amount} HP!)"
            )
        else:
            player['inventory'].append(new_item)
            loot_log.append(
                f"📦 {player['first_name']} looted: {rarity_emoji} {item_data['emoji']} {new_item.replace('_', ' ').title()}"
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
            # Find who attacked this player in this turn
            attackers_of_this_player = [att_id for target_id, att_list in attacks.items() if target_id == user_id for att_id in att_list]
            if attackers_of_this_player:
                # Award kill to the last person who dealt damage, or randomly/to all (simple approach: to all attackers)
                for attacker_id in set(attackers_of_this_player):
                    game.players[attacker_id]['stats']['kills'] += 1
                    
                    # Check achievements
                    if game.players[attacker_id]['stats']['kills'] == 1:
                        if unlock_achievement(attacker_id, 'first_blood'):
                            await safe_send(
                                context, attacker_id,
                                "🏆 **Achievement Unlocked!**\n🩸 First Blood",
                                parse_mode=ParseMode.MARKDOWN
                            )
                    
                    # Betrayal achievement (if betrayal led to elimination)
                    if attacker_id in betrayals and betrayals[attacker_id] == user_id:
                        if unlock_achievement(attacker_id, 'betrayer'):
                            await safe_send(
                                context, attacker_id,
                                "🏆 **Achievement Unlocked!**\n😈 Traitor - First Betrayal!",
                                parse_mode=ParseMode.MARKDOWN
                            )
            
            await safe_send_animation(
                context, user_id,
                get_random_gif('eliminated'),
                caption=f"""
╔══════════════════════╗
      💀 ELIMINATED!       
╚══════════════════════╝

Your ship was destroyed on Day {game.day}!
*Final HP: 0*

**Your Stats:**
💀 Kills: {player['stats']['kills']}
⚔️ Damage: {player['stats']['damage_dealt']}
🛡️ Taken: {player['stats']['damage_taken']}

*Better luck next time!* ⚡
""",
                parse_mode=ParseMode.MARKDOWN
            )
    
    # Build enhanced summary
    summary_lines = [f"╔══════════════════════╗"]
    summary_lines.append(f"    📊 DAY {game.day} SUMMARY  ")
    summary_lines.append(f"╚══════════════════════╝\n")
    
    if event_log:
        summary_lines.append(f"🌌 **Cosmic Event: {event_data['name']}**")
        for line in event_log:
            summary_lines.append(line)
        summary_lines.append("")
    
    if damage_log:
        summary_lines.append("┏━━━━━━━━━━━━━━━━━━━━━━┓")
        summary_lines.append("      🗡️ ATTACKS")
        summary_lines.append("┗━━━━━━━━━━━━━━━━━━━━━━┛")
        for line in damage_log:
            summary_lines.append(f"• {line}")
        summary_lines.append("")
    
    if heal_log:
        summary_lines.append("┏━━━━━━━━━━━━━━━━━━━━━━┓")
        summary_lines.append("      💊 REPAIRS")
        summary_lines.append("┗━━━━━━━━━━━━━━━━━━━━━━┛")
        for line in heal_log:
            summary_lines.append(f"• {line}")
        summary_lines.append("")
    
    if loot_log:
        summary_lines.append("┏━━━━━━━━━━━━━━━━━━━━━━┓")
        summary_lines.append("      📦 SCAVENGING")
        summary_lines.append("┗━━━━━━━━━━━━━━━━━━━━━━┛")
        for line in loot_log:
            summary_lines.append(f"• {line}")
        summary_lines.append("")
    
    if move_log:
        summary_lines.append("┏━━━━━━━━━━━━━━━━━━━━━━┓")
        summary_lines.append("      🧭 NAVIGATION")
        summary_lines.append("┗━━━━━━━━━━━━━━━━━━━━━━┛")
        for line in move_log:
            summary_lines.append(f"• {line}")
        summary_lines.append("")
    
    if eliminated:
        summary_lines.append("┏━━━━━━━━━━━━━━━━━━━━━━┓")
        summary_lines.append("      💀 ELIMINATED")
        summary_lines.append("┗━━━━━━━━━━━━━━━━━━━━━━┛")
        for _, name in eliminated:
            summary_lines.append(f"• {name}")
        summary_lines.append("")
    
    alive_players = game.get_alive_players()
    
    if game.mode == 'solo':
        # Re-sort for most current ranking in summary
        sorted_players = sorted(
            [(uid, p) for uid, p in game.players.items() if p['alive']],
            key=lambda x: (x[1]['hp'], x[1]['stats']['kills']),
            reverse=True
        )
        
        summary_lines.append(f"┏━━━━━━━━━━━━━━━━━━━━━━┓")
        summary_lines.append(f"      🚢 SURVIVORS ({len(alive_players)})")
        summary_lines.append(f"┗━━━━━━━━━━━━━━━━━━━━━━┛")
        
        for i, (user_id, player) in enumerate(sorted_players, 1):
            hp_bar = get_progress_bar(player['hp'], player['max_hp'], 5)
            hp_ind = get_hp_indicator(player['hp'], player['max_hp'])
            px, py = player['position']
            summary_lines.append(f"{i}. {hp_ind} {player['first_name']} - {player['hp']} HP {hp_bar} @ ({px},{py})")
            
    else:
        alpha_alive = game.get_alive_team_players('alpha')
        beta_alive = game.get_alive_team_players('beta')
        
        summary_lines.append(f"┏━━━━━━━━━━━━━━━━━━━━━━┓")
        summary_lines.append(f"      🔵 TEAM ALPHA ({len(alpha_alive)} alive)")
        summary_lines.append(f"┗━━━━━━━━━━━━━━━━━━━━━━┛")
        for user_id in alpha_alive:
            player = game.players[user_id]
            hp_ind = get_hp_indicator(player['hp'], player['max_hp'])
            summary_lines.append(f"• {hp_ind} {player['first_name']} - {player['hp']} HP")
        
        summary_lines.append("")
        summary_lines.append(f"┏━━━━━━━━━━━━━━━━━━━━━━┓")
        summary_lines.append(f"      🔴 TEAM BETA ({len(beta_alive)} alive)")
        summary_lines.append(f"┗━━━━━━━━━━━━━━━━━━━━━━┛")
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
    
    # --- Integration of Map and Day Start Message ---
    map_display = game.get_map_display()
    
    caption = f"""
╔══════════════════════╗
      ⚔️ DAY {game.day} BEGINS! 
╚══════════════════════╝

*Survivors, choose your operations!*

{map_display}
"""
    # ---------------------------------------------
    
    await safe_send(
        context, game.chat_id,
        caption,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Show updated map (already done in combined message above)
    # await safe_send(context, game.chat_id, map_display, parse_mode=ParseMode.MARKDOWN)
    
    for user_id, player in game.players.items():
        player['operation'] = None
        player['target'] = None
        
        if player['alive']:
            # Send both the button in group and the detailed DM.
            await send_operation_choice_button(context, game, user_id)
    
    game.operation_end_time = datetime.now() + timedelta(seconds=game.settings['operation_time'])
    asyncio.create_task(operation_countdown(context, game))

async def end_game(context, game,alive_players):
    """End solo game and declare winner with enhanced UI."""
    game.is_active = False
    game.is_joining = False
    game.operation_end_time = None
    
    if alive_players:
        winner_id = alive_players[0]
        winner = game.players[winner_id]
        
        # Calculate score and give coins
        score = calculate_score(1, winner['stats']['kills'], winner['stats']['damage_dealt'])
        coins_earned = WIN_COIN_BONUS
        
        update_player_stats(winner_id, winner['username'], {
            'total_games': 1,
            'wins': 1,
            'kills': winner['stats']['kills'],
            'damage_dealt': winner['stats']['damage_dealt'],
            'damage_taken': winner['stats']['damage_taken'],
            'heals_done': winner['stats']['heals_done'],
            'loots_collected': winner['stats']['loots'],
            'total_score': score,
            'coins': coins_earned
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
╔════════════════════╗
      🏆 VICTORY ROYALE!    
╚════════════════════╝

👑 **Champion: {winner['first_name']}**
🗺️ **Map:** {MAPS[game.map_type]['name']}

┏━━━━━━━━━━━━━━━━━━━━━━┓
      📊 FINAL STATS
┣━━━━━━━━━━━━━━━━━━━━━━┫
   ❤️ HP Left: {winner['hp']}/{winner['max_hp']}
   📍 Position: {winner['position']}
   💀 Eliminations: {winner['stats']['kills']}
   ⚔️ Damage: {winner['stats']['damage_dealt']}
   💊 Healed: {winner['stats']['heals_done']}
   🧭 Moves: {winner['stats']['moves']}
   📅 Days: {game.day}
   ⭐ Score: +{score}
   💰 Coins Earned: +{coins_earned}
━━━━━━━━━━━━━━━━━━━━━━━

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
╔══════════════════════╗
      🏆 CONGRATULATIONS!   
╚══════════════════════╝

You are the ultimate champion! 👑
*Victory recorded in the legends!*

**Score Earned:** +{score} ⭐
**Coins Earned:** +{coins_earned} 💰
**Global Rank:** #{get_user_rank(winner_id)}
""",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await safe_send(
            context, game.chat_id,
            f"""
╔════════════════════════╗
      💥 MUTUAL DESTRUCTION 
╚════════════════════════╝

*All ships eliminated!*

It's a draw! Try again with `/creategame`.
""",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Update stats for all players
    for user_id, player in game.players.items():
        if user_id != (alive_players[0] if alive_players else None):
            score = calculate_score(0, player['stats']['kills'], player['stats']['damage_dealt'])
            # Losers get a smaller coin amount (e.g., 20)
            update_player_stats(user_id, player['username'], {
                'total_games': 1,
                'losses': 1,
                'deaths': 1,
                'kills': player['stats']['kills'],
                'damage_dealt': player['stats']['damage_dealt'],
                'damage_taken': player['stats']['damage_taken'],
                'heals_done': player['stats']['heals_done'],
                'loots_collected': player['stats']['loots'],
                'total_score': score,
                'coins': 20 # Loser coin bonus
            })
    
    del games[game.chat_id]

async def end_team_game(context, game, alpha_alive, beta_alive):
    """End team game and declare winning team with enhanced UI."""
    game.is_active = False
    game.is_joining = False
    game.operation_end_time = None
    
    winning_team = None
    winning_emoji = None
    winners = []
    
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
        
        score = calculate_score(1, player['stats']['kills'], player['stats']['damage_dealt'])
        coins_earned = WIN_COIN_BONUS // 2 # Team win gives half of solo win
        
        update_player_stats(user_id, player['username'], {
            'total_games': 1,
            'wins': 1,
            'kills': player['stats']['kills'],
            'damage_dealt': player['stats']['damage_dealt'],
            'damage_taken': player['stats']['damage_taken'],
            'heals_done': player['stats']['heals_done'],
            'loots_collected': player['stats']['loots'],
            'total_score': score,
            'coins': coins_earned
        })
        
        if unlock_achievement(user_id, 'team_player'):
            await safe_send(
                context, user_id,
                "🏆 **Achievement Unlocked!**\n🤝 Team Player - Won a team game!",
                parse_mode=ParseMode.MARKDOWN
            )
    
    if winners:
        save_game_history(game, winners[0], game.players[winners[0]]['first_name'])
    
    victory_text = f"""
╔════════════════════════╗
      🏆 TEAM VICTORY!      
╚════════════════════════╝

{winning_emoji} **Team {winning_team.title()} Wins!** 👑
🗺️ **Map:** {MAPS[game.map_type]['name']}

┏━━━━━━━━━━━━━━━━━━━━━━┓
      🎖️ CHAMPIONS
┣━━━━━━━━━━━━━━━━━━━━━━┫
"""
    
    for name in winner_names:
        victory_text += f"   {winning_emoji} {name}\n"
    
    victory_text += f"""━━━━━━━━━━━━━━━━━━━━━━━

┏━━━━━━━━━━━━━━━━━━━━━━┓
      📊 GAME STATS
┣━━━━━━━━━━━━━━━━━━━━━━┫
   📅 Days: {game.day}
   👥 Players: {len(game.players)}
━━━━━━━━━━━━━━━━━━━━━━━

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
        score = calculate_score(0, player['stats']['kills'], player['stats']['damage_dealt'])
        update_player_stats(user_id, player['username'], {
            'total_games': 1,
            'losses': 1,
            'deaths': 1,
            'kills': player['stats']['kills'],
            'damage_dealt': player['stats']['damage_dealt'],
            'damage_taken': player['stats']['damage_taken'],
            'heals_done': player['stats']['heals_done'],
            'loots_collected': player['stats']['loots'],
            'total_score': score,
            'coins': 20 # Loser coin bonus
        })
    
    del games[game.chat_id]

# ======================== ALLIANCE COMMANDS ========================
async def ally_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Form alliance with another player - GROUP ONLY."""
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ **This command works only in groups!**")
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if chat_id not in games:
        await update.message.reply_text("❌ No active game!")
        return
    
    game = games[chat_id]
    
    if game.mode != 'solo':
        await update.message.reply_text("❌ Alliances only available in Solo Mode!")
        return
    
    if not game.is_active:
        await update.message.reply_text("❌ Game not started yet!")
        return
    
    if user_id not in game.players or not game.players[user_id]['alive']:
        await update.message.reply_text("❌ You're not in the game or eliminated!")
        return
    
    if user_id in game.alliances:
        ally_name = game.players[game.alliances[user_id]['ally']]['first_name']
        await update.message.reply_text(f"❌ Already allied with {ally_name}!")
        return
    
    target_id = None
    target_name = None
    
    # Try to get target from reply first
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        target_name = update.message.reply_to_message.from_user.first_name
    
    # If not from reply, try to get from arguments (username)
    elif context.args:
        username = context.args[0].replace('@', '')
        
        # Simple iteration to find player by username in current game
        found = False
        for uid, player_data in game.players.items():
            if player_data['username'] and player_data['username'].lower() == username.lower() and player_data['alive']:
                target_id = uid
                target_name = player_data['first_name']
                found = True
                break
        
        if not found:
            await update.message.reply_text(f"❌ Target player @{username} not found in this game!")
            return
            
    if not target_id:
        await update.message.reply_text("❌ Reply to a player's message with `/ally` or use `/ally @username`")
        return
    
    if target_id not in game.players or not game.players[target_id]['alive']:
        await update.message.reply_text("❌ Target player not in game or eliminated!")
        return
    
    if target_id in game.alliances:
        await update.message.reply_text("❌ That player is already in an alliance!")
        return
    
    if target_id == user_id:
        await update.message.reply_text("❌ You can't ally with yourself!")
        return
    
    # Form alliance
    game.form_alliance(user_id, target_id)
    
    player_name = update.effective_user.first_name
    
    # Update stats
    game.players[user_id]['stats']['alliances_formed'] = game.players[user_id]['stats'].get('alliances_formed', 0) + 1
    game.players[target_id]['stats']['alliances_formed'] = game.players[target_id]['stats'].get('alliances_formed', 0) + 1
    
    await safe_send(
        context, chat_id,
        f"""
╔══════════════════════╗
  🤝 ALLIANCE FORMED!   
╚══════════════════════╝

**{player_name}** ⚔️ **{target_name}**

*Duration:* {ALLIANCE_DURATION} turns
*Cannot attack each other*

⚠️ *Betrayal gives damage bonus!* 😈
""",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Send DM notification to ally
    await safe_send(
        context, target_id,
        f"🤝 **{player_name}** has formed an alliance with you for {ALLIANCE_DURATION} turns in the group!",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Check achievement
    if game.players[user_id]['stats']['alliances_formed'] >= 10:
        if unlock_achievement(user_id, 'diplomat'):
            await safe_send(
                context, user_id,
                "🏆 **Achievement Unlocked!**\n🤝 Diplomat - 10 alliances formed!",
                parse_mode=ParseMode.MARKDOWN
            )

async def betray_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Betray your ally - GROUP ONLY."""
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ **This command works only in groups!**")
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if chat_id not in games:
        await update.message.reply_text("❌ No active game!")
        return
    
    game = games[chat_id]
    
    if not game.is_active:
        await update.message.reply_text("❌ Game not started yet!")
        return
    
    if user_id not in game.alliances:
        await update.message.reply_text("❌ You have no alliance to betray!")
        return
    
    ally_id = game.alliances[user_id]['ally']
    ally_name = game.players[ally_id]['first_name']
    
    game.break_alliance(user_id)
    
    await safe_send(
        context, chat_id,
        f"""
╔══════════════════════╗
      😈 BETRAYAL!          
╚══════════════════════╝

**{update.effective_user.first_name}** betrayed **{ally_name}**!

*Next attack deals {int(BETRAYAL_DAMAGE_BONUS * 100)}% damage!* 💥

⚠️ *Choose your enemies wisely...*
""",
        parse_mode=ParseMode.MARKDOWN
    )
    
    await safe_send(
        context, ally_id,
        f"😈 **Your ally {update.effective_user.first_name} has betrayed you!**\n*Watch your back!* ⚠️",
        parse_mode=ParseMode.MARKDOWN
    )

# ======================== COINS AND SHOP ========================

async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Claim daily coins with streak system."""
    user = update.effective_user
    user_id = user.id
    
    # Ensure player is in DB
    update_player_stats(user_id, user.username, {})

    now = datetime.now()
    if user_id in LAST_DAILY_CLAIM:
        last_claim = LAST_DAILY_CLAIM[user_id]
        if (now - last_claim).total_seconds() < 24 * 3600:
            next_claim_time = last_claim + timedelta(hours=24)
            remaining_time = next_claim_time - now
            mins, secs = divmod(remaining_time.seconds, 60)
            hours, mins = divmod(mins, 60)
            await update.message.reply_text(
                f"❌ **Daily Reward Already Claimed!**\nCome back in **{hours}h {mins}m {secs}s** ⏱️",
                parse_mode=ParseMode.MARKDOWN
            )
            return

    # Grant coins with streak bonus
    coins_to_add = DAILY_COIN_AMOUNT
    
    # Get current stats to check streak
    stats = get_player_stats(user_id)
    if stats:
        win_streak = stats[11]
        # Streak bonus: +10 coins per win streak
        streak_bonus = min(win_streak * 10, 100)  # Max 100 bonus
        coins_to_add += streak_bonus
    
    update_player_stats(user_id, user.username, {'coins': coins_to_add})
    LAST_DAILY_CLAIM[user_id] = now
    
    bonus_text = f"\n🔥 **Streak Bonus:** +{streak_bonus} coins!" if stats and stats[11] > 0 else ""
    
    await update.message.reply_text(
        f"✅ **Daily Reward Claimed!**\nYou received **{coins_to_add} 🪙** coins!{bonus_text}\n\nUse `/shop` to buy titles!",
        parse_mode=ParseMode.MARKDOWN
    )

async def shop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the in-game shop for titles."""
    user = update.effective_user
    user_id = user.id
    stats = get_player_stats(user_id)
    
    if not stats:
        await update.message.reply_text("❌ **No Statistics Yet!** Play first.")
        return
    
    # FIX: Safely extract coins as integer to prevent ValueError/TypeError if DB value is NULL/None
    try:
        coins = int(stats[16]) if stats[16] is not None else 0
    except (ValueError, TypeError):
        coins = 0
        logger.warning(f"Coin value in DB is invalid for user {user_id}: {stats[16]}")
    
    current_title_key = stats[17] if len(stats) > 17 else 'novice_captain'
    
    # SAFETY: Ensure title exists
    if not current_title_key or current_title_key not in PLAYER_TITLES:
        current_title_key = 'novice_captain'
    
    title_data = PLAYER_TITLES[current_title_key]
    
    text = f"""
╔═══════════════════════════════════════╗
      🛍️ TITLE SHOP        
╚═══════════════════════════════════════╝

💰 **Your Balance:** {coins} 🪙
✨ **Current Title:** {title_data['name']}

╔═══════════════════════════════════════╗
      ⭐ AVAILABLE TITLES
╠═══════════════════════════════════════╣
"""
    keyboard = []
    
    for key, data in PLAYER_TITLES.items():
        if key == 'novice_captain':
            continue
        
        cost = int(data['cost']) if data['cost'] else 0
        
        # Determine button status
        if key == current_title_key:
            status = "✅ EQUIPPED"
            action = "shop_none"
        elif coins >= cost:
            status = "🛒 BUY"
            action = f"shop_buy_{key}"
        else:
            status = "🔒 TOO EXPENSIVE"
            action = "shop_none"
        
        text += f"{data['emoji']} **{data['name']}**\n"
        text += f"   *Cost: {cost} 🪙 - {status}*\n\n"
        
        # The button should allow 'equip' if the title has already been purchased, 
        # but your current purchase logic immediately sets the title, so we keep 
        # the buy/none logic simple.
        if action != "shop_none":
            keyboard.append([InlineKeyboardButton(
                f"{data['emoji']} {data['name']} - {cost} 🪙", 
                callback_data=action
            )])
        else:
            keyboard.append([InlineKeyboardButton(
                f"{data['emoji']} {data['name']} ({status})", 
                callback_data="shop_none"
            )])

    text += "╚═══════════════════════════════════════╝"
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def handle_shop_selection(query, context):
    """Handle shop buy/equip buttons."""
    data = query.data
    user_id = query.from_user.id
    parts = data.split('_')
    action = parts[1]
    title_key = parts[2] if len(parts) > 2 else None
    
    if action == 'none':
        await query.answer("Already equipped or unavailable!", show_alert=False)
        return
    
    stats = get_player_stats(user_id)
    if not stats:
        await query.answer("Error fetching stats.", show_alert=True)
        return
    
    coins = stats[16]
    current_title_key = stats[17]
    title_data = PLAYER_TITLES.get(title_key)
    
    if not title_data:
        await query.answer("Invalid title.", show_alert=True)
        return
    
    if action == 'buy':
        cost = title_data['cost']
        if coins < cost:
            await query.answer(f"❌ Not enough coins! Need {cost} 🪙", show_alert=True)
            return
        
        # Deduct coins and set title (save as STRING KEY)
        update_player_stats(user_id, query.from_user.username, {
            'coins': -cost
        })
        
        # Update title separately ensuring it's stored as string
        conn = sqlite3.connect('ship_battle.db')
        c = conn.cursor()
        c.execute('UPDATE players SET title = ? WHERE user_id = ?', (title_key, user_id))
        conn.commit()
        conn.close()
        
        await query.answer(f"✅ Purchased and equipped {title_data['name']}!", show_alert=True)
        
        # Refresh shop display
        await shop_command(query.message, context)
    
    elif action == 'equip':
        # Switch to this title
        conn = sqlite3.connect('ship_battle.db')
        c = conn.cursor()
        c.execute('UPDATE players SET title = ? WHERE user_id = ?', (title_key, user_id))
        conn.commit()
        conn.close()
        
        await query.answer(f"✅ Equipped {title_data['name']}!", show_alert=True)
        await shop_command(query.message, context)


# ======================== ADDITIONAL COMMANDS ========================

async def map_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the battle map - GROUP ONLY."""
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ **This command works only in groups!**")
        return
    
    chat_id = update.effective_chat.id
    
    if chat_id not in games:
        await update.message.reply_text("❌ No active game!")
        return
    
    game = games[chat_id]
    
    if not game.is_active:
        await update.message.reply_text("❌ Game hasn't started yet!")
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
        await update.message.reply_text("❌ You're not in any active game!")
        return
    
    if not game.is_active:
        await update.message.reply_text("❌ Game hasn't started yet!")
        return
    
    player = game.players[user_id]
    
    if not player['alive']:
        await update.message.reply_text("❌ You've been eliminated!")
        return
    
    px, py = player['position']
    targets_in_range = game.get_players_in_range(user_id)
    
    text = f"""
╔══════════════════════╗
      📍 YOUR POSITION      
╚══════════════════════╝

📍 **Coordinates:** ({px}, {py})
🗺️ **Map:** {MAPS[game.map_type]['name']}

┏━━━━━━━━━━━━━━━━━━━━━━━┓
      🎯 TARGETS IN RANGE ({len(targets_in_range)})
┣━━━━━━━━━━━━━━━━━━━━━━━┫
"""
    
    if targets_in_range:
        for target_id in targets_in_range:
            target = game.players[target_id]
            tx, ty = target['position']
            hp_ind = get_hp_indicator(target['hp'], target['max_hp'])
            text += f"   • {hp_ind} {target['first_name']} @ ({tx}, {ty})\n"
    else:
        text += "   *No enemies in attack range!*\n"
    
    text += f"""━━━━━━━━━━━━━━━━━━━━━━━━

*Attack range: {ATTACK_RANGE} cells* ⚔️
"""
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def mystats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show personal statistics with enhanced UI."""
    if check_spam(update.effective_user.id):
        await update.message.reply_text("⚠️ **Slow down!** Please wait before using commands again.")
        return
    
    user_id = update.effective_user.id
    stats = get_player_stats(user_id)
    
    # Ensure player has an entry, even if new
    if not stats:
        update_player_stats(user_id, update.effective_user.username, {})
        stats = get_player_stats(user_id)
    
    # Safety check on stats
    if not stats:
        await update.message.reply_text("❌ Error loading stats. Try again later.")
        return
        
    formatted_stats = format_user_stats(stats)
    await update.message.reply_text(formatted_stats, parse_mode=ParseMode.MARKDOWN)

async def achievements_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show player achievements with enhanced UI."""
    if check_spam(update.effective_user.id):
        await update.message.reply_text("⚠️ **Slow down!** Please wait before using commands again.")
        return
    
    user_id = update.effective_user.id
    achievements = get_player_achievements(user_id)
    
    text = f"""
╔══════════════════════╗
      🏅 YOUR ACHIEVEMENTS   
╚══════════════════════╝

*Unlocked: {len(achievements)}/{len(ACHIEVEMENTS)}*

"""
    
    if not achievements:
        text += "No achievements yet! Play to unlock! 🚀\n"
    else:
        for ach_key, ach_data in ACHIEVEMENTS.items():
            status = "✅" if ach_key in achievements else "🔒"
            text += f"{status} {ach_data['emoji']} **{ach_data['name']}**\n   *{ach_data['desc']}*\n\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show global leaderboard with enhanced UI."""
    if check_spam(update.effective_user.id):
        await update.message.reply_text("⚠️ **Slow down!** Please wait before using commands again.")
        return
    
    leaders = get_leaderboard(10)
    
    if not leaders:
        await update.message.reply_text("🏆 **Leaderboard Empty!**\nBe the first legend!")
        return
    
    text = """
╔═════════════════════════════════╗
      🏆 GLOBAL LEADERBOARD 
╚═════════════════════════════════╝

"""
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7  # Enough for top 10
    
    for i, (username, wins, games, kills, damage, score, title_key) in enumerate(leaders, 1):
        # SAFETY CHECKS FIRST
        if title_key not in PLAYER_TITLES:
            title_key = 'novice_captain'
        
        title_data = PLAYER_TITLES.get(title_key, PLAYER_TITLES['novice_captain'])
        
        # ESCAPE username BEFORE use
        safe_username = escape_markdown_value(username)
        
        # NOW use safe_username
        medal = medals[i-1] if i <= len(medals) else "🏅"
        win_rate = int((wins/games)*100) if games > 0 else 0
        
        text += f"{medal} **{safe_username}** {title_data['emoji']}\n"
        text += f"   ⭐ Score: {score} | 🏆 Wins: {wins} ({win_rate}%)\n"
        text += f"   🎯 Kills: {kills} | ⚔️ Damage: {damage}\n\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast message to all players and send to group - OWNER ONLY."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not await is_owner(user_id):
        await update.message.reply_text("❌ **Owner Only Command!**")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: `/broadcast <message>`")
        return
    
    message = " ".join(context.args)
    
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    # Select all distinct users who have interacted with the bot
    c.execute('SELECT DISTINCT user_id FROM players')
    users = c.fetchall()
    conn.close()
    
    broadcast_text = f"""
╔══════════════════════╗
 📢 HOPE YOU ARE DOING GREAT   
╚══════════════════════╝

{message}

*- Ship Battle Royale Team* 🚀
"""
    
    # 1. Send to all users (DMs)
    success_count = 0
    for (uid,) in users:
        result = await safe_send(context, uid, broadcast_text, parse_mode=ParseMode.MARKDOWN)
        if result:
            success_count += 1
        await asyncio.sleep(0.05)  # Rate limiting
    
    # 2. Send to the group (original chat)
    await safe_send(
        context, chat_id,
        f"**Owner Broadcast to Group:**\n{broadcast_text}",
        parse_mode=ParseMode.MARKDOWN
    )
    
    await update.message.reply_text(
        f"✅ **Broadcast Complete!**\n*Sent to {success_count}/{len(users)} users (DM)*\n*Sent to current group*",
        parse_mode=ParseMode.MARKDOWN
    )

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Backup the database file - OWNER ONLY."""
    user_id = update.effective_user.id
    
    if not await is_owner(user_id):
        await update.message.reply_text("❌ **Owner Only Command!**")
        return

    db_path = 'ship_battle.db'
    backup_file_name = f"ship_battle_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    
    try:
        if not os.path.exists(db_path):
            await update.message.reply_text("❌ Database file not found!")
            return

        # Simple file copy for backup
        import shutil
        shutil.copyfile(db_path, backup_file_name)
        
        # Send the file
        await context.bot.send_document(
            chat_id=user_id,
            document=open(backup_file_name, 'rb'),
            caption="✅ **Database Backup Complete!**"
        )
        
        # Clean up local backup file
        os.remove(backup_file_name)
        
        await update.message.reply_text("✅ **Backup sent to your DM!**")
        
    except Exception as e:
        logger.error(f"Backup error: {e}")
        await update.message.reply_text(f"❌ **Backup failed!** Error: {e}")


async def selectmap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually select map - ADMIN ONLY, GROUP ONLY."""
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ **This command works only in groups!**")
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if not await is_admin_or_owner(context, chat_id, user_id):
        await update.message.reply_text("❌ **Admin Only Command!**")
        return
    
    if chat_id not in games:
        await update.message.reply_text("❌ No active game!")
        return
    
    game = games[chat_id]
    
    if not game.map_voting:
        await update.message.reply_text("❌ Map voting not active!")
        return
    
    if not context.args:
        maps_list = "\n".join([f"• `{key}` - {data['name']}" for key, data in MAPS.items()])
        await update.message.reply_text(
            f"❌ Usage: `/selectmap <map_name>`\n\n**Available Maps:**\n{maps_list}",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    map_name = context.args[0].lower()
    
    if map_name not in MAPS:
        await update.message.reply_text(f"❌ Invalid map! Use: {', '.join(MAPS.keys())}")
        return
    
    game.set_map(map_name)
    game.map_voting = False
    
    await safe_send(
        context, chat_id,
        f"🎯 **Admin Selected Map: {MAPS[map_name]['name']}**",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Continue to joining phase
    if game.mode == 'solo':
        await start_solo_mode_after_voting(context, game)
    else:
        await start_team_mode_after_voting(context, game)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current game stats - GROUP ONLY."""
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ **This command works only in groups!**")
        return
    
    chat_id = update.effective_chat.id
    
    if chat_id not in games:
        await update.message.reply_text("❌ No active game!")
        return
    
    game = games[chat_id]
    
    if not game.is_active:
        await update.message.reply_text("❌ Game hasn't started yet!")
        return
    
    alive = game.get_alive_players()
    
    if game.mode == 'solo':
        # Use the dynamic ranking logic
        sorted_players = sorted(
            [(uid, p) for uid, p in game.players.items() if p['alive']],
            key=lambda x: (x[1]['hp'], x[1]['stats']['kills']),
            reverse=True
        )
        
        text = f"""
╔══════════════════════╗
      📊 GAME STATISTICS   
╚══════════════════════╝

📅 **Day {game.day}** | 🗺️ {MAPS[game.map_type]['name']}
🚢 **Survivors:** {len(alive)}/{len(game.players)}

┏━━━━━━━━━━━━━━━━━━━━━━┓
      🏆 RANKINGS
┣━━━━━━━━━━━━━━━━━━━━━━┫
"""
        
        for i, (uid, player) in enumerate(sorted_players, 1):
            hp_bar = get_progress_bar(player['hp'], player['max_hp'], 5)
            hp_ind = get_hp_indicator(player['hp'], player['max_hp'])
            px, py = player['position']
            text += f"{i}. {hp_ind} **{player['first_name']}**\n"
            text += f"   HP: {player['hp']}/{player['max_hp']} {hp_bar}\n"
            text += f"   📍 ({px},{py}) | 💀 Kills: {player['stats']['kills']} | ⚔️ DMG: {player['stats']['damage_dealt']}\n\n"
        
        text += "━━━━━━━━━━━━━━━━━━━━━━━"
    
    else:  # Team mode
        alpha_alive = game.get_alive_team_players('alpha')
        beta_alive = game.get_alive_team_players('beta')
        
        text = f"""
╔══════════════════════╗
      📊 TEAM STATISTICS    
╚══════════════════════╝

📅 **Day {game.day}** | 🗺️ {MAPS[game.map_type]['name']}

🔵 **Team Alpha:** {len(alpha_alive)} alive
🔴 **Team Beta:** {len(beta_alive)} alive

┏━━━━━━━━━━━━━━━━━━━━━━━┓
      🔵 ALPHA TEAM
┣━━━━━━━━━━━━━━━━━━━━━━━┫
"""
        for user_id in alpha_alive:
            player = game.players[user_id]
            hp_ind = get_hp_indicator(player['hp'], player['max_hp'])
            text += f"• {hp_ind} {player['first_name']} - {player['hp']} HP | 💀 {player['stats']['kills']}\n"
        
        text += """━━━━━━━━━━━━━━━━━━━━━━━

┏━━━━━━━━━━━━━━━━━━━━━━┓
      🔴 BETA TEAM
┣━━━━━━━━━━━━━━━━━━━━━━┫
"""
        for user_id in beta_alive:
            player = game.players[user_id]
            hp_ind = get_hp_indicator(player['hp'], player['max_hp'])
            text += f"• {hp_ind} {player['first_name']} - {player['hp']} HP | 💀 {player['stats']['kills']}\n"
        
        text += "━━━━━━━━━━━━━━━━━━━━━━━"
    
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
        await update.message.reply_text("❌ You're not in any active game!")
        return
    
    if not game.is_active:
        await update.message.reply_text("❌ Game hasn't started yet!")
        return
    
    player = game.players[user_id]
    
    if not player['alive']:
        await update.message.reply_text("❌ You've been eliminated!")
        return
    
    hp_bar = get_progress_bar(player['hp'], player['max_hp'])
    hp_ind = get_hp_indicator(player['hp'], player['max_hp'])
    rank = game.get_player_rank(user_id)
    px, py = player['position']
    
    # Get Title
    stats_data = get_player_stats(user_id)
    title_key = stats_data[17] if stats_data and len(stats_data) > 17 else 'novice_captain'
    title_data = PLAYER_TITLES.get(title_key, PLAYER_TITLES['novice_captain'])
    
    text = f"""
╔═══════════════════════╗
      🚢 YOUR FLAGSHIP      
╚═══════════════════════╝
{title_data['emoji']} **Title:** {title_data['name']}

{hp_ind} **HP:** {player['hp']}/{player['max_hp']}
{hp_bar}

┏━━━━━━━━━━━━━━━━━━━━━━━┓
      ⚡ **BATTLE INFO**
┣━━━━━━━━━━━━━━━━━━━━━━━┫
   📅 Day: {game.day}
   📍 Position: ({px}, {py})
   🏆 Rank: #{rank}
   💀 Kills: {player['stats']['kills']}
   ⚠️ AFK: {player['afk_turns']}/3
━━━━━━━━━━━━━━━━━━━━━━━

┏━━━━━━━━━━━━━━━━━━━━━━┓
      📊 **COMBAT STATS**
┣━━━━━━━━━━━━━━━━━━━━━━┫
   ⚔️ Damage Dealt: {player['stats']['damage_dealt']}
   🛡️ Damage Taken: {player['stats']['damage_taken']}
   💊 HP Healed: {player['stats']['heals_done']}
   🧭 Moves: {player['stats']['moves']}
━━━━━━━━━━━━━━━━━━━━━━━

*Stay alive, Captain!* ⚔️
"""
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def inventory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show player's inventory with enhanced UI."""
    user_id = update.effective_user.id
    
    game = None
    for g in games.values():
        if user_id in g.players:
            game = g
            break
    
    if not game:
        await update.message.reply_text("❌ You're not in any active game!")
        return
    
    player = game.players[user_id]
    
    text = f"""
╔══════════════════════╗
  🎒 YOUR INVENTORY     
╚══════════════════════╝

"""
    
    if not player['inventory']:
        text += "*Empty!*\n\nLoot to collect items! 📦"
    else:
        text += f"*Items: {len(player['inventory'])}*\n\n"
        
        # Consolidate items for cleaner look
        item_counts = defaultdict(int)
        for item_key in player['inventory']:
            item_counts[item_key] += 1
            
        for item_key, count in item_counts.items():
            item = LOOT_ITEMS[item_key]
            rarity_emoji = get_rarity_color(item['rarity'])
            
            desc = item['desc']
            
            text += f"{rarity_emoji} {item['emoji']} **{item_key.replace('_', ' ').title()}** x{count}\n"
            text += f"   *{item['rarity'].title()}* - {desc}\n\n"
        
        text += "*Weapon/Shield items auto-used on operation turn.* ⚡"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def ranking_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current game ranking - GROUP ONLY."""
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ **This command works only in groups!**")
        return
    
    chat_id = update.effective_chat.id
    
    if chat_id not in games:
        await update.message.reply_text("❌ No active game!")
        return
    
    game = games[chat_id]
    
    if not game.is_active:
        await update.message.reply_text("❌ Game hasn't started yet!")
        return
    
    sorted_players = sorted(
        game.players.items(),
        key=lambda x: (x[1]['alive'], x[1]['hp'], x[1]['stats']['kills']),
        reverse=True
    )
    
    text = f"""
╔══════════════════════╗
      🏅 CURRENT RANKINGS   
╚══════════════════════╝

📅 **Day {game.day}** | 🗺️ {MAPS[game.map_type]['name']}

"""
    
    for i, (uid, player) in enumerate(sorted_players, 1):
        status = "🚢" if player['alive'] else "💀"
        hp_ind = get_hp_indicator(player['hp'], player['max_hp']) if player['alive'] else "💀"
        px, py = player['position']
        
        team_emoji = ""
        if game.mode == 'team' and player['team']:
            team_emoji = f" {'🔵' if player['team'] == 'alpha' else '🔴'}"
        
        text += f"{i}. {status} {hp_ind} **{player['first_name']}**{team_emoji}\n"
        text += f"   HP: {player['hp']}/{player['max_hp']} | 💀 Kills: {player['stats']['kills']} | 📍 ({px},{py})\n\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent game history with enhanced UI."""
    if check_spam(update.effective_user.id):
        await update.message.reply_text("⚠️ **Slow down!** Please wait before using commands again.")
        return
    
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    c.execute('''SELECT winner_name, total_players, total_rounds, map_name, end_time 
                 FROM game_history 
                 ORDER BY game_id DESC 
                 LIMIT 5''')
    results = c.fetchall()
    conn.close()
    
    if not results:
        await update.message.reply_text("❌ No game history yet!")
        return
    
    text = """
╔══════════════════════╗
      📜 RECENT BATTLES     
╚══════════════════════╝

"""
    
    for winner, players, rounds, map_name, end_time in results:
        date = datetime.fromisoformat(end_time).strftime("%Y-%m-%d %H:%M")
        map_display = MAPS.get(map_name, {}).get('name', 'Unknown Map')
        text += f"🏆 **{winner}** (Winner)\n"
        text += f"   👥 Players: {players} | 📅 Days: {rounds}\n"
        text += f"   🗺️ {map_display}\n"
        text += f"   🕒 {date}\n\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def tips_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show game tips with enhanced UI."""
    if check_spam(update.effective_user.id):
        await update.message.reply_text("⚠️ **Slow down!** Please wait before using commands again.")
        return
    
    tips = [
        "🛡️ **Defense Tip:** Defend when HP drops below 50 to stay in the fight!",
        "🗡️ **Attack Tip:** Target low-HP enemies for quick eliminations.",
        "💊 **Heal Tip:** Heal strategically when you need it most.",
        "📦 **Loot Tip:** Collect rare items early to build your arsenal.",
        "🎯 **Strategy:** Mix your actions to keep opponents guessing!",
        "⏱️ **Timing:** Use shields when under attack, not after.",
        "🗺️ **Map Tip:** Position strategically - corner enemies or flee!",
        "⚠️ **AFK Warning:** Stay active! 3 missed turns = elimination!",
        "🤝 **Team Tip:** Coordinate with teammates - focus fire!",
        "📍 **Range Tip:** Keep enemies at 2 cells for safe attacks!",
        "🌌 **Event Tip:** Adapt strategy when cosmic events trigger!",
        "🤝 **Alliance Tip:** Form alliances early, betray strategically!",
        "😈 **Betrayal Tip:** Betrayal gives damage bonus - time it right!",
        "🏙️ **Big Maps:** Larger maps need more movement strategy!",
        "⚡ **Speed Tip:** Choose operations quickly to end rounds fast!"
    ]
    
    tip = random.choice(tips)
    text = f"""
╔══════════════════════╗
      💡 STRATEGY TIP     
╚══════════════════════╝

{tip}

*Master the battlefield!* 🚀
"""
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def compare_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Compare stats with another player."""
    if check_spam(update.effective_user.id):
        await update.message.reply_text("⚠️ **Slow down!** Please wait before using commands again.")
        return
    
    user_id = update.effective_user.id
    stats1 = get_player_stats(user_id)
    
    if not stats1:
        await update.message.reply_text("❌ You have no stats yet! Play a game first.")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Usage: `/compare @username`")
        return
    
    username = context.args[0].replace('@', '')
    stats2 = get_player_stats_by_username(username)
    
    if not stats2:
        await update.message.reply_text(f"❌ Player @{username} not found! Check username spelling.")
        return
    
    # Use index 16 for coins, 17 for title (if available, added in the updated DB init)
    _, u1, g1, w1, l1, k1, d1, dmg1, dmgt1, h1, _, _, _, s1, _, _, c1, t1 = stats1[:18]
    _, u2, g2, w2, l2, k2, d2, dmg2, dmgt2, h2, _, _, _, s2, _, _, c2, t2 = stats2[:18]
    
    def compare_val(v1, v2):
        if v1 > v2:
            return "🟢"
        elif v1 < v2:
            return "🔴"
        return "⚪"
    
    text = f"""
╔══════════════════════╗
      📊 STAT COMPARISON    
╚══════════════════════╝

**{u1}** vs **{u2}**

┏━━━━━━━━━━━━━━━━━━━━━━┓
      🎮 GAME RECORD
┣━━━━━━━━━━━━━━━━━━━━━━┫
   Games: {compare_val(g1, g2)} {g1} vs {g2}
   Wins: {compare_val(w1, w2)} {w1} vs {w2}
   Losses: {compare_val(l2, l1)} {l1} vs {l2}
   Score: {compare_val(s1, s2)} {s1} vs {s2}
   Coins: {compare_val(c1, c2)} {c1} vs {c2}
━━━━━━━━━━━━━━━━━━━━━━━

┏━━━━━━━━━━━━━━━━━━━━━━┓
┃      ⚔️ COMBAT STATS
┣━━━━━━━━━━━━━━━━━━━━━━┫
   Kills: {compare_val(k1, k2)} {k1} vs {k2}
   Deaths: {compare_val(d2, d1)} {d1} vs {d2}
   Damage: {compare_val(dmg1, dmg2)} {dmg1} vs {dmg2}
   Healed: {compare_val(h1, h2)} {h1} vs {h2}
━━━━━━━━━━━━━━━━━━━━━━━

*🟢 You're ahead | 🔴 Behind*
"""
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Configure game settings - ADMIN ONLY, GROUP ONLY."""
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ **This command works only in groups!**")
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if not await is_admin_or_owner(context, chat_id, user_id):
        await update.message.reply_text("❌ **Admin Only Command!**")
        return
    
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    c.execute('SELECT * FROM group_settings WHERE chat_id = ?', (chat_id,))
    settings = c.fetchone()
    
    if not settings:
        c.execute('''INSERT INTO group_settings (chat_id) VALUES (?)''', (chat_id,))
        conn.commit()
        settings = (chat_id, 120, 120, 2, 20, 1)
    
    conn.close()
    
    text = f"""
╔══════════════════════╗
      ⚙️ GAME SETTINGS    
╚══════════════════════╝

┏━━━━━━━━━━━━━━━━━━━━━┓
  ⚡ CURRENT CONFIG
┣━━━━━━━━━━━━━━━━━━━━━┫
   ⏱️ Join Time: {settings[1]}s
   🎮 Operation Time: {settings[2]}s
   👥 Min Players: {settings[3]}
   🚢 Max Players: {settings[4]}
   👁️ Spectators: {"Yes" if settings[5] else "No"}
━━━━━━━━━━━━━━━━━━━━━

**Commands to Modify:**
- `/setjointime <seconds>`
- `/setoptime <seconds>`

*Customize your battlefield!* 🚀
"""
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def extend_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Extend joining time - ADMIN ONLY, GROUP ONLY."""
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ **This command works only in groups!**")
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if chat_id not in games:
        await update.message.reply_text("❌ No active game!")
        return
    
    game = games[chat_id]
    
    if not game.is_joining:
        await update.message.reply_text("❌ Can only extend during joining phase!")
        return
    
    if not await is_admin_or_owner(context, chat_id, user_id):
        await update.message.reply_text("❌ **Admin Only Command!**")
        return
    
    game.join_end_time += timedelta(seconds=30)
    
    caption = """
╔═════════════════════╗
      ⏱️ TIME EXTENDED    
╚═════════════════════╝

*+30 seconds added!*

More time to join the battle! 🚀
"""
    
    gif_url = get_random_gif('extend')
    await safe_send_animation(
        context, chat_id, gif_url,
        caption=caption,
        parse_mode=ParseMode.MARKDOWN
    )

async def endgame_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force end game - ADMIN ONLY, GROUP ONLY."""
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ **This command works only in groups!**")
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if chat_id not in games:
        await update.message.reply_text("❌ No active game!")
        return
    
    if not await is_admin_or_owner(context, chat_id, user_id):
        await update.message.reply_text("❌ **Admin Only Command!**")
        return
    
    game = games[chat_id]
    game.is_active = False
    game.is_joining = False
    game.operation_end_time = None
    
    await safe_send(
        context, chat_id,
        """
╔══════════════════════╗
      ❌ GAME TERMINATED!   
╚══════════════════════╝

*Admin force-ended the game.*

Better luck next time! 🚀
""",
        parse_mode=ParseMode.MARKDOWN
    )
    
    del games[chat_id]

async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Join an ongoing game - GROUP ONLY."""
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ **This command works only in groups!**")
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    
    if chat_id not in games:
        await update.message.reply_text("❌ No active game to join!")
        return
    
    game = games[chat_id]
    
    if not game.is_joining:
        await update.message.reply_text("❌ Game has already started! Use /spectate to watch.")
        return
    
    # Check if banned
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM banned_players WHERE chat_id = ? AND user_id = ?', (chat_id, user_id))
    if c.fetchone():
        await update.message.reply_text("❌ You are banned from games in this group!")
        conn.close()
        return
    conn.close()
    
    if game.mode == 'team':
        await update.message.reply_text("❌ Use the inline buttons to join a team!")
        return
    
    success, msg = game.add_player(user_id, username, first_name)
    if success:
        await safe_send(
            context, chat_id,
            f"✅ **{first_name}** joined the armada! 💥",
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
    """Leave a game during joining phase - GROUP ONLY."""
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ **This command works only in groups!**")
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    
    if chat_id not in games:
        await update.message.reply_text("❌ No active game!")
        return
    
    game = games[chat_id]
    
    if not game.is_joining:
        await update.message.reply_text("❌ Can only leave during joining phase!")
        return
    
    if user_id not in game.players:
        await update.message.reply_text("❌ You're not in the game!")
        return
    
    team = game.players[user_id].get('team')
    if team:
        game.teams[team].remove(user_id)
    
    del game.players[user_id]
    await safe_send(
        context, chat_id,
        f"❌ **{first_name}** abandoned ship! ⚠️",
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
    """Spectate an ongoing game - GROUP ONLY."""
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ **This command works only in groups!**")
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    
    if chat_id not in games:
        await update.message.reply_text("❌ No active game to spectate!")
        return
    
    game = games[chat_id]
    
    if not game.settings['allow_spectators']:
        await update.message.reply_text("❌ Spectators are not allowed in this game!")
        return
    
    if user_id in game.players:
        await update.message.reply_text("❌ You can't spectate while playing!")
        return
    
    game.spectators.add(user_id)
    await update.message.reply_text(
        f"👁️ **{first_name}** is now spectating! Enjoy the battle! 🍿",
        parse_mode=ParseMode.MARKDOWN
    )

async def setjointime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set joining phase time - ADMIN ONLY, GROUP ONLY."""
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ **This command works only in groups!**")
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if not await is_admin_or_owner(context, chat_id, user_id):
        await update.message.reply_text("❌ **Admin Only Command!**")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("❌ Usage: `/setjointime <seconds>`")
        return
    
    seconds = int(context.args[0])
    if seconds < 30 or seconds > 600:
        await update.message.reply_text("❌ Join time must be between 30 and 600 seconds!")
        return
    
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO group_settings (chat_id, join_time) VALUES (?, ?)', (chat_id, seconds))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"✅ **Join time set to {seconds} seconds!**",
        parse_mode=ParseMode.MARKDOWN
    )

async def setoptime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set operation phase time - ADMIN ONLY, GROUP ONLY."""
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ **This command works only in groups!**")
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if not await is_admin_or_owner(context, chat_id, user_id):
        await update.message.reply_text("❌ **Admin Only Command!**")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("❌ Usage: `/setoptime <seconds>`")
        return
    
    seconds = int(context.args[0])
    if seconds < 30 or seconds > 600:
        await update.message.reply_text("❌ Operation time must be between 30 and 600 seconds!")
        return
    
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO group_settings (chat_id, operation_time) VALUES (?, ?)', (chat_id, seconds))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"✅ **Operation time set to {seconds} seconds!**",
        parse_mode=ParseMode.MARKDOWN
    )

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a player from participating - OWNER ONLY, GROUP ONLY."""
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ **This command works only in groups!**")
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if not await is_owner(user_id):
        await update.message.reply_text("❌ **Owner Only Command!**")
        return
    
    if not context.args or not context.args[0].startswith('@'):
        await update.message.reply_text("❌ Usage: `/ban @username`")
        return
    
    username = context.args[0].replace('@', '')
    
    # Try to find user_id using the username from the players table
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM players WHERE username = ? COLLATE NOCASE', (username,))
    result = c.fetchone()
    
    if not result:
        await update.message.reply_text(f"❌ Player @{username} not found in bot records!")
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
    """Unban a player - OWNER ONLY, GROUP ONLY."""
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ **This command works only in groups!**")
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if not await is_owner(user_id):
        await update.message.reply_text("❌ **Owner Only Command!**")
        return
    
    if not context.args or not context.args[0].startswith('@'):
        await update.message.reply_text("❌ Usage: `/unban @username`")
        return
    
    username = context.args[0].replace('@', '')
    conn = sqlite3.connect('ship_battle.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM players WHERE username = ? COLLATE NOCASE', (username,))
    result = c.fetchone()
    
    if not result:
        await update.message.reply_text(f"❌ Player @{username} not found in bot records!")
        conn.close()
        return
    
    banned_user_id = result[0]
    c.execute('DELETE FROM banned_players WHERE chat_id = ? AND user_id = ?', (chat_id, banned_user_id))
    rows_deleted = c.rowcount
    conn.commit()
    conn.close()
    
    if rows_deleted > 0:
        await update.message.reply_text(
            f"✅ **@{username}** has been unbanned!",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            f"❌ **@{username}** was not found in the banned list for this group.",
            parse_mode=ParseMode.MARKDOWN
        )
async def backup_game_state(game):
    """Auto-save game state to JSON."""
    try:
        backup_data = {
            'game_id': game.game_id,
            'chat_id': game.chat_id,
            'day': game.day,
            'players': {str(uid): {
                'hp': p['hp'],
                'position': p['position'],
                'alive': p['alive'],
                'stats': p['stats']
            } for uid, p in game.players.items()},
            'timestamp': datetime.now().isoformat()
        }
        
        with open(f'backup_game_{game.chat_id}.json', 'w') as f:
            json.dump(backup_data, f)
            
    except Exception as e:
        logger.error(f"Backup failed: {e}")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel participation during joining - GROUP ONLY."""
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ **This command works only in groups!**")
        return
    
    await leave_command(update, context)

async def handle_show_info(query, context):
    """Handle show info buttons."""
    data = query.data
    user_id = query.from_user.id
    
    if data == "show_rules":
        await query.answer()
        await rules_command(query.message, context)
    
    elif data == "show_leaderboard":
        await query.answer()
        await leaderboard_command(query.message, context)
    
    elif data == "show_mystats":
        await query.answer()
        await mystats_command(query.message, context)
    
    elif data == "show_achievements":
        await query.answer()
        await achievements_command(query.message, context)

async def recover_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recover last game state from backup."""
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ This command works only in groups!")
        return
    
    chat_id = update.effective_chat.id
    backup_file = f'backup_game_{chat_id}.json'
    
    if not os.path.exists(backup_file):
        await update.message.reply_text("❌ No backup found for this group!")
        return
    
    try:
        with open(backup_file, 'r') as f:
            backup_data = json.load(f)
        
        await update.message.reply_text(
            f"""
✅ **Game Recovered!**
📍 Day: {backup_data['day']}
🚢 Players: {len(backup_data['players'])}
🕐 Last saved: {backup_data['timestamp']}

Game state restored! Continue playing with `/creategame`
""",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Recovery failed: {e}")

# ======================== DATABASE RESTORE/EXPORT ========================

async def restore_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Restore database from JSON backup file via reply.
    Usage: Reply to a JSON file with /restore
    """
    
    if not await is_owner(update.effective_user.id):
        await update.message.reply_text("❌ **Owner Only Command!**")
        return
    
    if not update.message.reply_to_message or not update.message.reply_to_message.document:
        await update.message.reply_text(
            "❌ **Usage:** Reply to a JSON backup file with `/restore`\n\n"
            "Expected JSON format:\n"
            "```json\n"
            "{\n"
            '  "players": [\n'
            "    {\n"
            '      "user_id": 123456,\n'
            '      "username": "player_name",\n'
            '      "wins": 10,\n'
            '      "kills": 50,\n'
            '      "losses": 5,\n'
            '      "deaths": 5,\n'
            '      "damage_dealt": 2000,\n'
            '      "damage_taken": 1000,\n'
            '      "heals_done": 500,\n'
            '      "loots_collected": 25,\n'
            '      "total_score": 1500,\n'
            '      "coins": 5000,\n'
            '      "title": "star_admiral"\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "```",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    try:
        document = update.message.reply_to_message.document
        file = await context.bot.get_file(document.file_id)
        
        temp_file = 'temp_backup.json'
        await file.download_to_drive(temp_file)
        
        with open(temp_file, 'r') as f:
            backup_data = json.load(f)
        
        if 'players' not in backup_data:
            await update.message.reply_text("❌ Invalid JSON format! Missing 'players' key.")
            os.remove(temp_file)
            return
        
        conn = sqlite3.connect('ship_battle.db')
        c = conn.cursor()
        
        restored_count = 0
        error_count = 0
        
        for player_data in backup_data['players']:
            try:
                user_id = player_data.get('user_id')
                username = player_data.get('username', 'Unknown')
                wins = player_data.get('wins', 0)
                losses = player_data.get('losses', 0)
                kills = player_data.get('kills', 0)
                deaths = player_data.get('deaths', 0)
                damage_dealt = player_data.get('damage_dealt', 0)
                damage_taken = player_data.get('damage_taken', 0)
                heals_done = player_data.get('heals_done', 0)
                loots_collected = player_data.get('loots_collected', 0)
                total_games = player_data.get('total_games', wins + losses)
                total_score = player_data.get('total_score', 0)
                coins = player_data.get('coins', 0)
                title = player_data.get('title', 'novice_captain')
                
                if title not in PLAYER_TITLES:
                    title = 'novice_captain'
                
                c.execute('''
                    INSERT OR REPLACE INTO players (
                        user_id, username, wins, losses, kills, deaths,
                        damage_dealt, damage_taken, heals_done, loots_collected,
                        total_games, total_score, coins, title, last_played
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id, username, wins, losses, kills, deaths,
                    damage_dealt, damage_taken, heals_done, loots_collected,
                    total_games, total_score, coins, title, datetime.now().isoformat()
                ))
                
                restored_count += 1
                
            except Exception as e:
                logger.error(f"Error restoring player data: {e}")
                error_count += 1
                continue
        
        conn.commit()
        conn.close()
        os.remove(temp_file)
        
        await update.message.reply_text(
            f"✅ **Database Restored Successfully!**\n\n"
            f"📊 Players restored: {restored_count}\n"
            f"❌ Errors: {error_count}\n"
            f"🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"The database has been updated!",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            await context.bot.send_message(
                SUPPORTIVE_GROUP_ID,
                f"🔄 **Database Restored**\n✅ Restored: {restored_count} players\n❌ Errors: {error_count}",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
        
    except json.JSONDecodeError:
        await update.message.reply_text("❌ Invalid JSON file! Please check the format.")
    except Exception as e:
        logger.error(f"Restore error: {e}")
        await update.message.reply_text(f"❌ Restore failed: {str(e)}")
        if os.path.exists('temp_backup.json'):
            os.remove('temp_backup.json')


async def export_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export entire database as JSON file."""
    
    if not await is_owner(update.effective_user.id):
        await update.message.reply_text("❌ **Owner Only Command!**")
        return
    
    try:
        conn = sqlite3.connect('ship_battle.db')
        c = conn.cursor()
        
        c.execute('SELECT * FROM players')
        players_data = c.fetchall()
        conn.close()
        
        export_data = {
            "exported_at": datetime.now().isoformat(),
            "total_players": len(players_data),
            "players": []
        }
        
        for player in players_data:
            player_dict = {
                "user_id": player[0],
                "username": player[1],
                "total_games": player[2],
                "wins": player[3],
                "losses": player[4],
                "kills": player[5],
                "deaths": player[6],
                "damage_dealt": player[7],
                "damage_taken": player[8],
                "heals_done": player[9],
                "loots_collected": player[10],
                "win_streak": player[11],
                "best_streak": player[12],
                "total_score": player[13],
                "betrayals": player[14],
                "alliances_formed": player[15],
                "coins": player[17],
                "title": player[18] if len(player) > 18 else "novice_captain"
            }
            export_data["players"].append(player_dict)
        
        filename = f"database_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        with open(filename, 'rb') as f:
            await context.bot.send_document(
                chat_id=update.effective_user.id,
                document=f,
                caption=f"✅ Database Exported\n📊 Players: {len(players_data)}\n📁 File: {filename}"
            )
        
        os.remove(filename)
        
        await update.message.reply_text(
            f"✅ **Database Exported!**\n"
            f"📊 Total Players: {len(players_data)}\n"
            f"Check your DM for the JSON file.",
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Export error: {e}")
        await update.message.reply_text(f"❌ Export failed: {str(e)}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors without crashing."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)

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
        application.add_handler(CommandHandler("compare", compare_command))
        application.add_handler(CommandHandler("ally", ally_command))
        application.add_handler(CommandHandler("betray", betray_command))
        application.add_handler(CommandHandler("selectmap", selectmap_command))
        application.add_handler(CommandHandler("broadcast", broadcast_command))
        application.add_handler(CommandHandler("daily", daily_command)) # New command
        application.add_handler(CommandHandler("shop", shop_command)) # New command
        application.add_handler(CommandHandler("backup", backup_command)) # New command
        application.add_handler(CommandHandler("dailystats", stats_detailed_command))
        application.add_handler(CommandHandler("export", export_database))
        application.add_handler(CommandHandler("restore", restore_database))
        application.add_handler(CommandHandler("challenges", challenges_command))
        application.add_handler(CommandHandler("cosmetics", cosmetics_command))

        application.add_error_handler(error_handler)
        
        # Register callback query handler for inline buttons
        application.add_handler(CallbackQueryHandler(button_handler))
        
        # Start the bot
        logger.info("╔═════════════════════════════╗")
        logger.info("   🚀 SHIP BATTLE ROYALE BOT    ")
        logger.info("╚═════════════════════════════╝")
        logger.info("✨ Enhanced Features Loaded:")
        logger.info("   • Advanced UI & Stats System")
        logger.info("   • 5 Unique Battle Maps")
        logger.info("   • Alliance & Betrayal System")
        logger.info("   • Map Voting System")
        logger.info("   • Anti-Spam Protection")
        logger.info("   • Auto-Pin Messages")
        logger.info("   • Broadcast System (Owner/Group)")
        logger.info("   • Max 20 Players Support")
        logger.info("   • New Loot Items & Shop System")
        logger.info("   • DM Operation Fixes & Map Integration")
        logger.info("   • Owner/Admin Permissions Refined")
        logger.info("═══════════════════════════════")
        logger.info("🎮 Bot is now online and ready!")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"❌ Bot startup error: {e}")

if __name__ == '__main__':

    main()
