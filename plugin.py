# plugins/game_character/plugin.py
# -*- coding: utf-8 -*-
"""
Игровой персонаж v1.4 — итоговая сборка.
"""

import os
import re
import sys
import json
import time
import socket
import struct
import random
import threading
import atexit

from games     import ALL_GAMES, find_game as _find_game, catalog_text
from games_ext import EXT_GAMES
import emotions as _emo
import social   as _soc

ALL_GAMES.extend(EXT_GAMES)

PLUGIN_DIR  = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(PLUGIN_DIR, 'config.json')
STATE_PATH  = os.path.join(PLUGIN_DIR, 'state.json')
LOG_PATH    = os.path.join(PLUGIN_DIR, 'game_character.log')

DEFAULT_CONFIG = {
    "commands_prefix": "!game",
    "rcon":  {"host": "127.0.0.1", "port": 27015, "password": "changeme"},
    "character": {
        "name": "ТАИБ",
        "bio": "Дружелюбный, немного саркастичный напарник.",
        "color": "255 200 100",
        "greeting": "Привет! Я {name}, готова к приключениям.",
        "farewell": "Ухожу в оффлайн. До связи!"
    },
    "listener": {"enabled": True, "poll_interval_sec": 15,
                 "greet_new_players": True, "farewell_on_leave": True},
    "idle":     {"enabled": True, "interval_sec": 120, "min_silence_sec": 90},
    "bridge":   {"enabled": True, "udp_host": "0.0.0.0",
                 "udp_port": 27099, "shared_secret": ""},
    "rp_mode":  {"enabled": False,
                 "triggers": ["!рп-режим", "!рп", "!rp-mode", "!rp"]},
    "duel": {
        "weapon": "weapon_357", "countdown_sec": 3,
        "max_duration_sec": 180,
        "challenge_keywords": ["дуэль", "duel", "поединок", "стреляться"],
        "bot_engage_distance": 400,
    },
    "bot": {"auto_spawn_on_join": True, "default_weapon": "weapon_357",
            "combat_tick_sec": 0.5},
    "nav":        {"prefer_ai": True, "fallback_to_manual_on_warn": True},
    "patrol":     {"enabled": True, "default_pause": 2.0, "max_points": 30},
    "games": {"enabled": True, "tick_interval_sec": 1.0,
              "duel_weapon_strict": True, "duel_bad_weapon_penalty": 60,
              "duel_cheater_score_penalty": 1},
    "range":      {"enabled": True, "default_count": 5, "default_duration": 30},
    "teams":      {"enabled": True, "red_id": 2, "blue_id": 3},
    "model_rp": {"enabled": True, "min_length": 4,
                 "hot_enabled": True, "hot_interval_sec": 30,
                 "hot_chance": 0.5, "hot_window_sec": 90},
    "economy": {"enabled": True, "start_balance": 100,
                "duel_win": 25, "duel_loss": -15, "duel_violation_fine": 50,
                "rps_default_bet": 10,
                "range_per_hit": 3, "range_all_hit_bonus": 20,
                "team_win_bonus": 30, "team_loss_penalty": -10,
                "max_bet": 200},
    "combat": {"enabled": True, "cover_spawn": True, "cover_auto_rebuild": True,
               "covers_per_session": 2,
               "desired_dist_min": 250, "desired_dist_max": 700,
               "weapon_switch": True, "grenade_flee": True},
    "smart_patrol": {"enabled": True, "greet_radius": 400, "greet_cooldown": 20},
    "emotions": {"enabled": True, "decay_check_sec": 30, "max_simultaneous": 10,
                 "apology_cooldown_sec": 3,
                 "furious_attack_range": 250, "furious_attack_duration": 3,
                 "subtle_enabled": True,
                 "remember_context": True, "remember_cooldown_sec": 90},
    "friendship":   {"enabled": True},
    "protect":      {"enabled": True, "friend_threshold": 15,
                     "reaction_range": 800, "engage_duration": 6},
    "bad_day":      {"enabled": True, "check_interval_sec": 600,
                     "chance": 0.10, "duration_sec": 900},
    "scars":        {"enabled": True},
    "diary":        {"enabled": True, "remember_long_absence": True,
                     "absence_days_threshold": 3},
    "conflicts":    {"enabled": True, "mediate_chance": 0.3,
                     "decay_check_sec": 300},
    "romance":      {"enabled": True, "threshold": 80, "decay_days": 7},
    "team_grudges": {"enabled": True},
    "quiet_hours":  {"enabled": True},
    "builder": {
        "enabled": True,
        "save_dir": "builds",
        "default_model": "models/props_junk/wood_crate001a.mdl",
        "models": {
            "wood":   "models/props_junk/wood_crate001a.mdl",
            "small":  "models/props_junk/wood_crate002a.mdl",
            "barrel": "models/props_c17/oildrum001.mdl",
            "blue":   "models/props_borealis/bluebarrel001.mdl",
            "panel":  "models/props_wasteland/panel_leanto01a.mdl",
            "jar":    "models/props_lab/jar01b.mdl",
        },
        "max_per_command": 200,
        "anim_speed": 0.15,
    },
}

DEFAULT_STATE = {
    "connected": False, "history": [], "mood": "neutral",
    "last_user_msg_ts": 0.0, "last_idle_ts": 0.0,
    "players_seen": {}, "players_online": [],
    "rp_mode": False, "duel": None, "duel_scores": {}, "chat_log": [],
    "game": None, "grudges": {}, "range_scores": {},
    "teams": {"red": [], "blue": []}, "points": {},
    "bot": {"spawned": False, "name": None, "pos": None, "hp": None,
            "armor": None, "weapon": None, "last_state_ts": 0, "nav_mode": "ai"},
    "patrol": {"points": [], "active": False, "index": 0},
    "combat": {"active": False, "target": None, "covers": 0,
               "last_event": None, "mode": None},
    "smart_patrol": {"active_until": 0, "reason": None},
    "emotions": {"offended": {}},
    "friendship": {}, "bad_day": {"until": 0}, "remember_ctx": {},
    "scars": {}, "diary": {}, "conflicts": {}, "team_grudges": {},
    "builder": {"anim": False, "last_build": None, "count": 0},
}

# ---------------------------------------------------------------------------
#  JSON / лог
# ---------------------------------------------------------------------------

def _save_json(path, data):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass

def _load_json(path, default):
    if not os.path.exists(path):
        _save_json(path, default)
        return json.loads(json.dumps(default))
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return json.loads(json.dumps(default))

def _log(msg):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(f"[{ts}] {msg}\n")
    except OSError:
        pass

# ---------------------------------------------------------------------------
#  RCON
# ---------------------------------------------------------------------------

class RCONError(Exception): pass

class RCONClient:
    SERVERDATA_AUTH           = 3
    SERVERDATA_AUTH_RESPONSE  = 2
    SERVERDATA_EXECCOMMAND    = 2

    def __init__(self, host, port, password, timeout=5.0):
        self.host, self.port = host, int(port)
        self.password, self.timeout = password, timeout
        self.sock, self._req_id = None, 0
        self._lock = threading.Lock()

    def _next_id(self): self._req_id += 1; return self._req_id

    def _send_packet(self, rid, ptype, body):
        payload = struct.pack('<ii', rid, ptype) + body.encode('utf-8') + b'\x00\x00'
        self.sock.sendall(struct.pack('<i', len(payload)) + payload)

    def _recv_exact(self, n):
        buf = b''
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk: return None
            buf += chunk
        return buf

    def _recv_packet(self):
        raw = self._recv_exact(4)
        if raw is None: return None
        length = struct.unpack('<i', raw)[0]
        if length < 10 or length > 8192:
            raise RCONError(f"bad length {length}")
        data = self._recv_exact(length)
        if data is None: return None
        rid, ptype = struct.unpack('<ii', data[:8])
        return rid, ptype, data[8:-2].decode('utf-8', errors='replace')

    def _drain(self, t=0.15):
        try:
            self.sock.settimeout(t)
            while True:
                if not self.sock.recv(4096): break
        except (socket.timeout, OSError): pass
        finally: self.sock.settimeout(self.timeout)

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        try: self.sock.connect((self.host, self.port))
        except OSError as e: raise RCONError(f"connect failed: {e}")
        aid = self._next_id()
        self._send_packet(aid, self.SERVERDATA_AUTH, self.password)
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            resp = self._recv_packet()
            if resp is None: raise RCONError("closed during auth")
            rid, ptype, _ = resp
            if ptype == self.SERVERDATA_AUTH_RESPONSE:
                if rid == -1: raise RCONError("bad password")
                self._drain(); return True
        raise RCONError("auth timeout")

    def command(self, cmd):
        if self.sock is None: raise RCONError("no connection")
        with self._lock:
            rid = self._next_id()
            self._send_packet(rid, self.SERVERDATA_EXECCOMMAND, cmd)
            resp = self._recv_packet()
            if resp is None: raise RCONError("closed")
            chunks = [resp[2]]
            try:
                self.sock.settimeout(0.2)
                while True:
                    ex = self._recv_packet()
                    if ex is None or ex[2] == "": break
                    chunks.append(ex[2])
            except (socket.timeout, OSError, RCONError): pass
            finally: self.sock.settimeout(self.timeout)
            return "".join(chunks)

    def disconnect(self):
        if self.sock is not None:
            try: self.sock.close()
            except OSError: pass
            self.sock = None

# ---------------------------------------------------------------------------
#  Состояние модуля
# ---------------------------------------------------------------------------

_cfg   = _load_json(CONFIG_PATH, DEFAULT_CONFIG)
_state = _load_json(STATE_PATH, DEFAULT_STATE)

for _k, _v in DEFAULT_STATE.items(): _state.setdefault(_k, _v)
for _k, _v in DEFAULT_CONFIG.items(): _cfg.setdefault(_k, _v)
for _sub in ("listener", "idle", "bridge", "rp_mode", "duel", "bot", "nav",
             "patrol", "games", "range", "teams", "model_rp", "economy",
             "combat", "smart_patrol", "emotions", "friendship", "protect",
             "bad_day", "scars", "diary", "conflicts", "romance",
             "team_grudges", "quiet_hours", "builder"):
    for _k, _v in DEFAULT_CONFIG[_sub].items():
        _cfg[_sub].setdefault(_k, _v)

_rcon = None
_rcon_lock = threading.Lock()

_listener_thread = None; _listener_stop = threading.Event()
_idle_thread     = None; _idle_stop     = threading.Event()
_bridge_thread   = None; _bridge_stop   = threading.Event()
_duel_thread     = None; _duel_stop     = threading.Event()
_game_thread     = None; _game_stop     = threading.Event()
_hot_thread      = None; _hot_stop      = threading.Event()
_bot_target_thread = None; _bot_target_stop = threading.Event()

_model_ref  = None
_vocab_ref  = None
_device_ref = None

_event_buffer      = []
_event_buffer_lock = threading.Lock()

_GAME_CTX = None

_MOOD_LINES = {
    "neutral":  ["Хм.", "Ладно.", "Понятно."],
    "friendly": ["Рада тебя видеть!", "Как дела, друг?", "Всегда рада поболтать!"],
    "annoyed":  ["Опять ты...", "Может, хватит?", "Мне это уже надоело."],
    "inspired": ["О, идея!", "Хочу исследовать это место!", "Что-то мне подсказывает — будет весело!"],
}

_IDLE_ACTIONS = [
    "осматривается по сторонам.", "перезаряжает оружие.",
    "потягивается, разминая плечи.", "садится на ящик и отдыхает.",
    "чиркает что-то в блокноте.", "пьёт воду из фляги.",
    "затачивает нож.", "прислушивается к доносящимся звукам.",
    "проверяет снаряжение.", "смотрит на часы.",
]

_RP_REACTIONS = {
    "greeting":   ["{n} кивает в ответ.", "{n} приветственно машет рукой."],
    "question":   ["{n} задумчиво хмыкает.", "{n} приподнимает бровь."],
    "insult":     ["{n} прищуривается.", "{n} скрещивает руки на груди."],
    "combat":     ["{n} напрягается и берётся за оружие.", "{n} пригибается к земле."],
    "compliment": ["{n} улыбается.", "{n} довольно кивает."],
    "generic":    ["{n} реагирует едва заметным движением.",
                   "{n} на миг переводит взгляд на собеседника."],
}

_STORY_POOL = [
    "Однажды я забрела в заброшенный сектор и нашла там старый терминал. "
    "Он всё ещё работал и показывал чей-то дневник.",
    "Как-то я сцепилась с тремя солдатами сразу. Двое меня недооценили, "
    "третий оказался умнее. Мы потом даже выпили вместе.",
    "Я нашла револьвер в куче мусора. Ржавый, но живой. С тех пор он всегда со мной.",
]

def _name():     return _cfg["character"].get("name", "ТАИБ")
def _bot_name(): return _cfg["bot"].get("name") or _name()

def _say(text):
    safe = str(text).replace('"', "'").replace('\n', ' ').strip()
    b = _state.get("bot") or {}
    cmd = f'otai_bot_say "{safe}"' if b.get("spawned") else f'say "[{_name()}] {safe}"'
    with _rcon_lock: cli = _rcon
    if cli is None:
        _log(f"(offline) {cmd}"); return False
    try:
        cli.command(cmd); _log(f"-> {cmd}"); return True
    except RCONError as e:
        _log(f"say error: {e}"); return False

def _rcon_cmd(cmd):
    with _rcon_lock: cli = _rcon
    if cli is None: return None
    try:    return cli.command(cmd)
    except RCONError as e:
        _log(f"rcon error: {e}"); return None

def _apply_identity():
    ch = _cfg["character"]
    _rcon_cmd(f'setinfo name "{ch.get("name", "Player")}"')
    if ch.get("color"):
        _rcon_cmd(f'say "/color {ch["color"]}"')

def _fmt_ts(ts):
    try:    return time.strftime('%Y-%m-%d %H:%M', time.localtime(ts))
    except (TypeError, ValueError): return "—"

_MOODS = ("neutral", "friendly", "annoyed", "inspired")

def _set_mood(m):
    if m in _MOODS:
        _state["mood"] = m; _save_json(STATE_PATH, _state); return True
    return False

def _get_mood():  return _state.get("mood", "neutral")
def _mood_line(): return random.choice(_MOOD_LINES.get(_get_mood(), ["Хм."]))

def _classify_chat(text):
    t = text.lower().strip()
    if not t: return "generic"
    if any(w in t for w in ("привет","хай","здарова","hello","hi","ку")): return "greeting"
    if t.endswith("?"): return "question"
    if any(w in t for w in ("дурак","идиот","тупой","лох","fuck","задолбал")): return "insult"
    if any(w in t for w in ("стреля","убей","атака","бой","драка")): return "combat"
    if any(w in t for w in ("молодец","круто","спасибо","класс","красиво")): return "compliment"
    return "generic"

def _is_quiet():
    if not _cfg["quiet_hours"].get("enabled", True): return False
    bot = _bot_name()
    return len([p for p in _state.get("players_online", []) if p != bot]) == 0

# -------- дневник --------

def _diary_for(nick):
    if not _cfg["diary"].get("enabled", True): return None
    return _state.setdefault("diary", {}).setdefault(nick, [])

def _diary_add(nick, kind, **fields):
    entries = _diary_for(nick)
    if entries is None: return
    _soc.diary_add(entries, kind, **fields)
    _save_json(STATE_PATH, _state)

# -------- экономика --------

def _points_get(nick):
    pts = _state.setdefault("points", {})
    if nick not in pts:
        pts[nick] = int(_cfg["economy"].get("start_balance", 100))
        _save_json(STATE_PATH, _state)
    return pts[nick]

def _points_add(nick, delta):
    pts = _state.setdefault("points", {})
    pts[nick] = max(0, _points_get(nick) + int(delta))
    _save_json(STATE_PATH, _state)
    return pts[nick]

def _points_leaderboard():
    pts = _state.get("points", {})
    if not pts: return "[экономика] Пока пусто."
    rows = sorted(pts.items(), key=lambda kv: kv[1], reverse=True)[:15]
    return ("[экономика] Топ по очкам:\n" +
            "\n".join(f"  {i+1:2d}. {n:20s} — {v:>5d}"
                      for i, (n, v) in enumerate(rows)))

# -------- дружба/романтика --------

def _friend_add(nick, event):
    if not _cfg["friendship"].get("enabled", True): return
    if not nick or nick == _bot_name(): return
    delta = _emo.FRIENDSHIP_GAINS.get(event, 0)
    if not delta: return
    fr = _state.setdefault("friendship", {})
    fr[nick] = max(0, fr.get(nick, 0) + delta)
    _save_json(STATE_PATH, _state)

def _friend_sub(nick, event):
    if not _cfg["friendship"].get("enabled", True): return
    if not nick or nick == _bot_name(): return
    delta = _emo.FRIENDSHIP_LOSSES.get(event, 0)
    if not delta: return
    fr = _state.setdefault("friendship", {})
    fr[nick] = max(0, fr.get(nick, 0) + delta)
    _save_json(STATE_PATH, _state)

def _friend_score(nick): return _state.get("friendship", {}).get(nick, 0)
def _friend_tier(nick):  return _emo.friendship_tier(_friend_score(nick))
def _is_friend(nick):
    return _friend_score(nick) >= int(_cfg["protect"].get("friend_threshold", 15))

def _is_romantic(nick):
    if not _cfg["romance"].get("enabled", True): return False
    rec = _state.get("players_seen", {}).get(nick, {})
    return _soc.is_romantic(_friend_score(nick), rec.get("last_seen"))

# -------- обиды --------

def _emo_store():
    return _state.setdefault("emotions", {}).setdefault("offended", {})

def _add_offense(nick, reason, context=None, level=None, ttl=None):
    if not nick or nick == _bot_name(): return 0
    store = _emo_store()
    rec = store.get(nick, {"level": 0, "until": 0, "since": time.time(),
                           "reason": "", "apologies": 0, "last_apology": 0,
                           "context": None, "subtle": False})
    new_lvl = level if level else _emo.TRIGGERS.get(reason, 1)
    new_lvl = _emo.combine_levels(rec.get("level", 0), new_lvl)

    scars = _state.setdefault("scars", {})
    scar  = scars.get(nick)
    if scar and _soc.scar_active(scar) and _cfg["scars"].get("enabled", True):
        bonus = _soc.scar_decayed_level(scar)
        if bonus > 0:
            new_lvl = min(4, new_lvl + bonus)
            if ttl is None:
                ttl = _emo.level_props(new_lvl)["ttl"] * _soc.SCAR_TTL_MULTIPLIER

    props = _emo.level_props(new_lvl)
    ttl   = ttl if ttl else props["ttl"]

    subtle = (new_lvl == 1
              and _cfg["emotions"].get("subtle_enabled", True)
              and _emo.maybe_subtle(new_lvl)
              and not rec.get("subtle"))

    rec.update({"level": new_lvl, "until": time.time() + ttl,
                "reason": reason, "since": rec.get("since") or time.time(),
                "apologies": 0, "context": context or rec.get("context"),
                "subtle": subtle})
    store[nick] = rec

    max_sim = int(_cfg["emotions"].get("max_simultaneous", 10))
    if len(store) > max_sim:
        oldest = sorted(store.items(), key=lambda kv: kv[1].get("until", 0))[:len(store)-max_sim]
        for k, _ in oldest: store.pop(k, None)

    if _cfg["team_grudges"].get("enabled", True):
        teams = _state.get("teams", {})
        offender_teams = [t for t in ("red", "blue") if nick in teams.get(t, [])]
        if offender_teams:
            tg = _state.setdefault("team_grudges", {})
            for t in offender_teams: _soc.apply_team_grudge(tg, t, reason)

    _save_json(STATE_PATH, _state)
    if not subtle: _say(_emo.pick_line(new_lvl, _bot_name()))
    _log(f"[emo] {nick} -> level {new_lvl} subtle={subtle} by {reason}")
    return new_lvl

def _get_offense(nick):
    store = _emo_store()
    rec = store.get(nick)
    if not rec: return None
    if rec.get("until", 0) <= time.time():
        store.pop(nick, None); _save_json(STATE_PATH, _state); return None
    return rec

def _has_grudge(nick): return _get_offense(nick) is not None

def _clear_grudge(nick):
    store = _emo_store()
    if nick in store:
        store.pop(nick); _save_json(STATE_PATH, _state); return True
    return False

def _offense_allows(nick, action):
    rec = _get_offense(nick)
    if rec:
        props = _emo.level_props(rec["level"])
        if rec.get("subtle"):
            if action == "game" and props["refuse_games"]:
                return (random.random() > 0.5), "game"
            return True, None
        if action == "game" and props["refuse_games"]: return False, "game"
        if action == "duel" and props["refuse_duel"]:  return False, "duel"
        if action == "talk" and rec["level"] >= 3:     return False, "talk"

    if _cfg["team_grudges"].get("enabled", True):
        teams = _state.get("teams", {})
        tg    = _state.get("team_grudges", {})
        for t in ("red", "blue"):
            if nick in teams.get(t, []) and _soc.team_grudge_active(tg, t):
                if action in ("game", "duel"): return False, action
    return True, None

def _try_apology(nick, text):
    if not _emo.detect_apology(text): return False
    rec = _get_offense(nick)
    if not rec: return False

    now = time.time()
    cd  = float(_cfg["emotions"].get("apology_cooldown_sec", 3))
    if now - rec.get("last_apology", 0) < cd: return True

    rec["apologies"] = rec.get("apologies", 0) + 1
    rec["last_apology"] = now

    if rec["level"] >= 4 and rec["apologies"] < 2:
        _say(f"* {_bot_name()} не сразу, но слышит.")
        _save_json(STATE_PATH, _state); return True

    rec_seen = _state.get("players_seen", {}).get(nick, {})
    chance = _emo.forgive_chance(
        rec["level"], _get_mood(), rec["apologies"],
        rec_seen.get("interactions", 0),
        friendship=_friend_score(nick), bad_day=_is_bad_day())

    scar = _state.get("scars", {}).get(nick)
    if scar and _soc.scar_active(scar):
        chance -= 0.1 * _soc.scar_decayed_level(scar)
        chance = max(0.05, chance)

    if random.random() < chance:
        if _is_romantic(nick):
            line = _soc.pick_romantic("forgive", _bot_name())
            _say(line or _emo.pick_forgive(rec["level"], _bot_name()))
        else:
            _say(_emo.pick_forgive(rec["level"], _bot_name()))

        if _cfg["scars"].get("enabled", True):
            _state.setdefault("scars", {})[nick] = _soc.create_scar(
                nick, rec["level"], rec.get("reason", "?"))
        _clear_grudge(nick); _set_mood("neutral")
        _friend_add(nick, "apology_accepted")
        _diary_add(nick, "apology")
    else:
        _say(f"* {_bot_name()} не верит(а) тебе пока.")
        new_lvl = max(1, rec["level"] - 1)
        rec["level"] = new_lvl
        rec["until"] = now + _emo.level_props(new_lvl)["ttl"]
    _save_json(STATE_PATH, _state)
    return True

# -------- плохие дни --------

def _is_bad_day(): return _state.get("bad_day", {}).get("until", 0) > time.time()

def _start_bad_day():
    dur = float(_cfg["bad_day"].get("duration_sec", 900))
    _state["bad_day"] = {"until": time.time() + dur}
    _save_json(STATE_PATH, _state)
    _set_mood("annoyed")
    _say(_emo.pick_bad_day("start", _bot_name()))

def _end_bad_day():
    _state["bad_day"] = {"until": 0}
    _save_json(STATE_PATH, _state)
    _set_mood("neutral")
    _say(_emo.pick_bad_day("end", _bot_name()))

# -------- RP --------

def _rp_is_on(): return bool(_state.get("rp_mode"))
def _rp_set(on):
    _state["rp_mode"] = bool(on); _save_json(STATE_PATH, _state)
    return _state["rp_mode"]

def _rp_wrap(kind, extra=None):
    pool = _RP_REACTIONS.get(kind, _RP_REACTIONS["generic"])
    text = random.choice(pool).format(n=_bot_name())
    if extra: text += f" {extra}"
    return text

# -------- модель --------

def _model_say(prompt, max_len=25):
    if _model_ref is None or _vocab_ref is None: return None
    try:
        import torch
        _model_ref.eval()
        with torch.no_grad():
            src = _vocab_ref.encode(prompt, 50).unsqueeze(0).to(_device_ref)
            out = _model_ref(src, None, teacher_forcing_ratio=0)
            idx = out.argmax(dim=-1).squeeze(0).cpu().tolist()
            text = _vocab_ref.decode(idx).strip()
        min_len = int(_cfg["model_rp"].get("min_length", 4))
        return text if len(text) >= min_len else None
    except Exception as e:
        _log(f"[model] {e!r}"); return None

def _rp_say(event_prompt, fallback):
    if _cfg["model_rp"].get("enabled", True):
        gen = _model_say(event_prompt)
        if gen: _say(gen); return
    _say(fallback)

def _push_event(kind, prompt, fallback):
    with _event_buffer_lock:
        _event_buffer.append({"ts": time.time(), "kind": kind,
                              "prompt": prompt, "fallback": fallback, "used": False})
        if len(_event_buffer) > 60:
            _event_buffer[:] = _event_buffer[-60:]

# -------- бот --------

def _bot_spawn():
    nm = _bot_name()
    resp = _rcon_cmd(f'otai_bot_spawn "{nm}"')
    if resp is None: return False, "нет RCON-соединения"
    time.sleep(0.5)
    _rcon_cmd(f'otai_bot_give "{_cfg["bot"]["default_weapon"]}"')
    return True, f"бот «{nm}» создаётся"

def _bot_remove():
    _rcon_cmd('otai_bot_remove')
    _state.setdefault("bot", {})["spawned"] = False
    _save_json(STATE_PATH, _state)

def _bot_goto(x, y, z):
    if (_bot_get().get("nav_mode") == "ai"
            and not _cfg["nav"].get("prefer_ai", True)):
        _rcon_cmd("otai_bot_navmode manual")
    _rcon_cmd(f'otai_bot_goto {x} {y} {z}')

def _bot_goto_player(nick): _rcon_cmd(f'otai_bot_goto_player "{nick}"')
def _bot_follow(nick):
    _rcon_cmd(f'otai_bot_follow "{nick}"' if nick else 'otai_bot_follow ""')
def _bot_stop():            _rcon_cmd('otai_bot_stop')
def _bot_aim(nick):
    _rcon_cmd(f'otai_bot_aim "{nick}"' if nick else 'otai_bot_aim ""')
def _bot_fire_at(nick, s=5): _rcon_cmd(f'otai_bot_fire_at "{nick}" {s}')
def _bot_ceasefire():       _rcon_cmd('otai_bot_ceasefire')

def _bot_get():      return _state.get("bot") or {}
def _bot_is_alive():
    b = _bot_get()
    return bool(b.get("spawned")) and (b.get("hp") or 0) > 0

def _sync_patrol_to_server():
    pts = _state.get("patrol", {}).get("points", [])
    if not pts:
        _rcon_cmd("otai_bot_patrol_clear"); return
    args = " ".join(f"{p[0]:.1f} {p[1]:.1f} {p[2]:.1f}" for p in pts)
    _rcon_cmd(f"otai_bot_patrol_set {args}")

# -------- GameContext --------

class GameContext:
    def __init__(self, plugin): self.p = plugin
    def say(self, t):              return self.p._say(t)
    def bot_name(self):            return self.p._bot_name()
    def bot_alive(self):           return self.p._bot_is_alive()
    def set_mood(self, m):         return self.p._set_mood(m)
    def get_mood(self):            return self.p._get_mood()
    def bot_pos(self):
        b = self.p._bot_get(); return b.get("pos")
    def player_pos(self, nick):
        rec = self.p._state.get("players_seen", {}).get(nick)
        return rec.get("last_pos") if rec else None
    def bot_follow(self, nick):       return self.p._bot_follow(nick)
    def bot_goto(self, x, y, z):      return self.p._bot_goto(x, y, z)
    def bot_goto_player(self, nick):  return self.p._bot_goto_player(nick)
    def bot_stop(self):               return self.p._bot_stop()
    def bot_aim(self, nick):          return self.p._bot_aim(nick)
    def bot_fire_at(self, nick, s=3): return self.p._bot_fire_at(nick, s)
    def bot_ceasefire(self):          return self.p._bot_ceasefire()
    def bot_hp(self):
        b = self.p._bot_get(); return b.get("hp")
    def rcon(self, cmd):              return self.p._rcon_cmd(cmd)
    def remember(self, nick, ev):     return self.p._remember_player(nick, ev)
    def diary_add(self, nick, kind, **fields): return self.p._diary_add(nick, kind, **fields)
    def points_get(self, nick):       return self.p._points_get(nick)
    def points_add(self, nick, d):    return self.p._points_add(nick, d)
    def points_top(self):             return self.p._points_leaderboard()
    def cfg(self, section, key, default=None):
        return self.p._cfg.get(section, {}).get(key, default)
    def start_bot_target_loop(self):  self.p._start_bot_target_loop()
    def stop_bot_target_loop(self):   self.p._stop_bot_target_loop()
    def range_score(self, nick, hits, elapsed, total):
        rs = self.p._state.setdefault("range_scores", {})
        best = rs.get(nick, {"hits": 0, "time": 999, "total": 0})
        if hits > best["hits"] or (hits == best["hits"] and elapsed < best["time"]):
            rs[nick] = {"hits": hits, "time": round(elapsed, 1), "total": total}
            self.p._save_json(self.p.STATE_PATH, self.p._state)
    def teams_join(self, nick, side):
        t = self.p._state.setdefault("teams", {"red": [], "blue": []})
        for s in ("red", "blue"):
            if nick in t.get(s, []): t[s].remove(nick)
        t.setdefault(side, []).append(nick)
        self.p._save_json(self.p.STATE_PATH, self.p._state)
        tid = int(self.p._cfg["teams"].get(f"{side}_id", 2 if side == "red" else 3))
        self.rcon(f'otai_setteam "{nick}" {tid}')
    def teams_leave(self, nick):
        t = self.p._state.setdefault("teams", {"red": [], "blue": []})
        for s in ("red", "blue"):
            if nick in t.get(s, []): t[s].remove(nick)
        self.p._save_json(self.p.STATE_PATH, self.p._state)
    def teams_lists(self):
        t = self.p._state.get("teams", {"red": [], "blue": []})
        return list(t.get("red", [])), list(t.get("blue", []))
    def teams_stop(self): self.rcon('otai_targets_clear')
    @property
    def state(self): return self.p._state
    def get_game(self): return self.p._state.get("game")
    def set_game(self, name, state, challenger, data):
        self.p._state["game"] = {"name": name, "state": state,
                                 "challenger": challenger,
                                 "data": data or {}, "started": time.time()}
        self.p._save_json(self.p.STATE_PATH, self.p._state)
    def set_game_state(self, s):
        g = self.p._state.get("game")
        if g:
            g["state"] = s; self.p._save_json(self.p.STATE_PATH, self.p._state)
    def set_game_data(self, k, v):
        g = self.p._state.get("game")
        if g:
            g.setdefault("data", {})[k] = v
            self.p._save_json(self.p.STATE_PATH, self.p._state)
    def clear_game(self):
        self.p._state["game"] = None
        self.p._save_json(self.p.STATE_PATH, self.p._state)

def _ctx():
    global _GAME_CTX
    if _GAME_CTX is None:
        _GAME_CTX = GameContext(sys.modules[__name__])
    return _GAME_CTX

def _remember_player(nick, event="seen"):
    if nick == _bot_name(): return
    players = _state.setdefault("players_seen", {})
    rec = players.get(nick); now = time.time()
    if rec is None:
        players[nick] = {"first_seen": now, "last_seen": now,
                         "interactions": 1, "last_event": event}
        _diary_add(nick, "first_meet", when=_fmt_ts(now))
    else:
        rec["last_seen"] = now
        rec["interactions"] = rec.get("interactions", 0) + 1
        rec["last_event"] = event
    _save_json(STATE_PATH, _state)

def _parse_status_players(raw):
    names = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line.startswith("#"): continue
        first = line.find('"')
        if first < 0: continue
        second = line.find('"', first + 1)
        if second < 0: continue
        nick = line[first + 1:second].strip()
        if nick: names.append(nick)
    return names

# -------- дуэли --------

def _duel_get():   return _state.get("duel")
def _duel_clear():
    _state["duel"] = None; _save_json(STATE_PATH, _state)
def _duel_scores():return _state.setdefault("duel_scores", {})
def _duel_inc_score(nick, won=True):
    s = _duel_scores()
    rec = s.setdefault(nick, {"wins": 0, "losses": 0})
    rec["wins" if won else "losses"] += 1
    _save_json(STATE_PATH, _state)

def _duel_start(opponent):
    ok, _ = _offense_allows(opponent, "duel")
    if not ok:
        _say(_emo.pick_refuse("duel")); return
    weapon = _cfg["duel"].get("weapon", "weapon_357")
    cdn    = int(_cfg["duel"].get("countdown_sec", 3))
    now    = time.time()

    if not _bot_is_alive():
        ok, _ = _bot_spawn()
        if not ok: _say("Не могу выйти на дуэль."); return

    _state["duel"] = {"opponent": opponent, "state": "countdown",
                      "started": now,
                      "deadline": now + int(_cfg["duel"].get("max_duration_sec", 180)),
                      "weapon": weapon}
    _save_json(STATE_PATH, _state)

    _rcon_cmd(f'otai_bot_give "{weapon}"')
    _rcon_cmd(f'otai_give "{opponent}" "{weapon}"')
    _rcon_cmd(f'otai_combat_start "{opponent}" duel')
    _rcon_cmd('otai_combat_setting weapon_switch_enabled 0')
    _rcon_cmd('otai_combat_setting desired_dist_min 200')
    _rcon_cmd('otai_combat_setting desired_dist_max 500')

    if _rp_is_on():
        _say(f"* {_bot_name()} принимает вызов и достаёт револьвер. Противник: {opponent}.")
    else:
        _say(f"Принимаю вызов! {opponent}, револьверы на изготовку.")

    def _countdown():
        for i in range(cdn, 0, -1):
            _say(f"{i}..."); time.sleep(1)
        _say("Огонь!")
        d = _state.get("duel")
        if d:
            d["state"] = "active"
            d["deadline"] = time.time() + int(_cfg["duel"].get("max_duration_sec", 180))
            _save_json(STATE_PATH, _state)
        _duel_engage(opponent)
    threading.Thread(target=_countdown, daemon=True).start()

def _duel_engage(opponent):
    global _duel_thread
    _duel_stop.clear()
    tick = float(_cfg["bot"].get("combat_tick_sec", 0.5))
    def _loop():
        time.sleep(1.0)
        while not _duel_stop.is_set():
            d = _duel_get()
            if not d or d.get("state") != "active": return
            if not _bot_is_alive(): return
            _bot_aim(opponent); _bot_fire_at(opponent, seconds=2)
            time.sleep(tick)
    _duel_thread = threading.Thread(target=_loop, daemon=True)
    _duel_thread.start()

def _duel_try_accept(nick, text):
    d = _duel_get()
    if not d or d.get("state") != "challenging": return False
    if d.get("challenger") not in (nick, _bot_name()) and d.get("opponent") != nick:
        return False
    low = text.lower()
    if not any(w in low for w in ("да", "принима", "ок", "yes", "go")):
        return False
    opponent = d.get("opponent") if d.get("challenger") == nick else d.get("challenger") or nick
    _duel_clear(); _duel_start(opponent); return True

def _duel_weapon_ok(weapon, allowed):
    if not weapon: return False
    w, a = weapon.lower(), allowed.lower()
    a_short = a.replace("weapon_", "")
    return a in w or a_short in w or "357" in w or "revolver" in w or "deagle" in w

def _duel_violation(reason, offender, self_blame=False):
    bot = _bot_name()
    _set_mood("annoyed"); _bot_ceasefire(); _duel_stop.set()
    _rcon_cmd('otai_combat_stop')
    if self_blame:
        _say(f"* {bot} смотрит на своё оружие с недоумением. "
             f"Кажется, я нарушил(а) правила. Дуэль отменяется.")
    else:
        _say(f"* {bot} в ярости! {reason}. Дуэль отменяется.")
        if offender:
            _say(f"Запомню это, {offender}.")
            _friend_sub(offender, "unfair_kill")
            fine = int(_cfg["economy"].get("duel_violation_fine", 50))
            _points_add(offender, -fine)
            _say(f"{offender}, штраф {fine} очков.")
            _add_offense(offender, "unfair_kill",
                         context=_emo.make_context("killed_me_duel", who=offender, weapon="—"))
            s = _duel_scores()
            rec = s.setdefault(offender, {"wins": 0, "losses": 0})
            rec["losses"] += int(_cfg["games"].get("duel_cheater_score_penalty", 1))
            _save_json(STATE_PATH, _state)
    _duel_clear()

def _duel_finish(winner, loser, reason="kill"):
    d = _duel_get()
    if not d or d.get("state") not in ("active", "countdown"): return
    bot = _bot_name(); opp = d.get("opponent", "?")
    win_pts  = int(_cfg["economy"].get("duel_win", 25))
    lose_pts = int(_cfg["economy"].get("duel_loss", -15))

    if winner == bot and loser == opp:
        _duel_inc_score(bot, True); _duel_inc_score(opp, False)
        _points_add(bot, win_pts); _points_add(opp, lose_pts)
        _say(f"Дуэль окончена: {bot} победил(а) {opp}. "
             f"+{win_pts} очков мне, {lose_pts} — тебе.")
        _diary_add(opp, "lost_duel", nick=bot); _diary_add(bot, "won_duel", nick=opp)
    elif winner == opp and loser == bot:
        _duel_inc_score(opp, True); _duel_inc_score(bot, False)
        _points_add(opp, win_pts); _points_add(bot, lose_pts)
        _say(f"Дуэль окончена: {opp} побеждает. +{win_pts} очков.")
        _diary_add(opp, "won_duel", nick=bot); _diary_add(bot, "lost_duel", nick=opp)
    else:
        _say(f"Дуэль прервана ({reason}).")
    _duel_clear(); _duel_stop.set(); _bot_ceasefire()
    _rcon_cmd('otai_combat_stop')

def _duel_challenge(target):
    if _duel_get(): return "[персонаж] Дуэль уже идёт."
    ok, _ = _offense_allows(target, "duel")
    if not ok: return f"[персонаж] {_emo.pick_refuse('duel')}"
    _state["duel"] = {"challenger": _bot_name(), "opponent": target,
                      "state": "challenging", "started": time.time(),
                      "deadline": time.time() + 30}
    _save_json(STATE_PATH, _state)
    _say(f"{target}, вызываю тебя на дуэль! Ответь «да» или «принимаю».")
    def _timeout():
        time.sleep(30)
        d = _duel_get()
        if d and d.get("state") == "challenging" and d.get("challenger") == _bot_name():
            _say(f"{target} не ответил. Отменяю вызов.")
            _duel_clear()
    threading.Thread(target=_timeout, daemon=True).start()
    return f"[персонаж] Вызов отправлен: {target}."

def _duel_leaderboard():
    s = _duel_scores()
    if not s: return "[персонаж] Пока никто не дуэлился."
    rows = sorted(s.items(), key=lambda kv: kv[1].get("wins", 0), reverse=True)[:10]
    return ("[персонаж] Таблица лидеров дуэлей:\n" +
            "\n".join(f"  {i+1}. {n} — {r.get('wins',0)}п / {r.get('losses',0)}пр"
                      for i, (n, r) in enumerate(rows)))

# -------- защита/медиация --------

def _protect_friend(victim, attacker):
    if not _cfg["protect"].get("enabled", True): return
    if not _is_friend(victim): return
    if not _bot_is_alive(): return
    if attacker in (None, "world", _bot_name()): return
    if _duel_get(): return
    _friend_add(victim, "helped_in_fight"); _diary_add(victim, "help")
    dur = float(_cfg["protect"].get("engage_duration", 6))
    if _is_romantic(victim):
        line = _soc.pick_romantic("protect", _bot_name())
        _say(line or f"* {_bot_name()} бросается на помощь {victim}!")
    else:
        _say(f"* {_bot_name()} бросается на помощь {victim}!")
    _bot_aim(attacker); _bot_fire_at(attacker, dur)
    _add_offense(attacker, "friendly_fire", level=2,
                 context=_emo.make_context("friendly_fire", who=attacker))

def _try_mediate(a, b):
    if not _cfg["conflicts"].get("enabled", True): return False
    if _state.get("game") or _duel_get(): return False
    if not (_is_friend(a) and _is_friend(b)): return False
    if not _soc.are_enemies(_state.get("conflicts", {}), a, b): return False
    if random.random() > float(_cfg["conflicts"].get("mediate_chance", 0.3)): return False
    _say(f"* {_bot_name()} встаёт между {a} и {b}.")
    _say(f"{a}, {b} — прекратите. Мне дороги вы оба.")
    _set_mood("annoyed"); return True

# -------- UDP мост --------

_BRIDGE_PREFIX = "OTAI-BRIDGE/2"

def _on_chat(nick, text):
    if not nick or nick == _bot_name(): return
    _remember_player(nick, event="chat")
    clog = _state.setdefault("chat_log", [])
    clog.append({"ts": time.time(), "nick": nick, "text": text})
    _state["chat_log"] = clog[-100:]
    _state["last_user_msg_ts"] = time.time()
    _save_json(STATE_PATH, _state)

    low = text.lower().strip()

    if _cfg["emotions"].get("enabled", True):
        if _emo.detect_insult(text):
            _friend_sub(nick, "insulted")
            _add_offense(nick, "insult_chat",
                         context=_emo.make_context("insulted", text=text[:40]))
            _diary_add(nick, "insult", reason="insult_chat"); return
        if _emo.detect_mock(text) and _has_grudge(nick):
            _add_offense(nick, "mock_chat"); return
        if _try_apology(nick, text): return

    if _cfg["emotions"].get("remember_context", True):
        rec = _get_offense(nick)
        if rec and rec.get("context") and not rec.get("subtle"):
            rmem = _state.setdefault("remember_ctx", {})
            last = rmem.get(nick, 0)
            cd = float(_cfg["emotions"].get("remember_cooldown_sec", 90))
            if time.time() - last > cd and random.random() < 0.35:
                line = _emo.render_context(rec["context"], _bot_name())
                if line:
                    _say(line); rmem[nick] = time.time()
                    _save_json(STATE_PATH, _state)

    for trig in _cfg["rp_mode"].get("triggers", []):
        if low.startswith(trig.lower()):
            arg = low[len(trig):].strip()
            if arg in ("on", "вкл", "включить", ""):
                _rp_set(True); _say("* Режим RP включён. Я в образе."); return
            if arg in ("off", "выкл", "выключить"):
                _rp_set(False); _say("RP-режим выключен."); return
            _say(f"RP-режим: {'вкл' if _rp_is_on() else 'выкл'}"); return

    if low.startswith("!дуэль") or low.startswith("!duel"):
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            target = parts[1].strip()
            _say(f"{target}, вызываю тебя! Ответь «да».")
            _state["duel"] = {"challenger": _bot_name(), "opponent": target,
                              "state": "challenging", "started": time.time(),
                              "deadline": time.time() + 30}
            _save_json(STATE_PATH, _state)
        return

    if low.startswith("!топ") or low.startswith("!leaderboard"):
        _say(_duel_leaderboard().replace("\n", " | ")); return
    if low.startswith("!история") or low.startswith("!story"):
        _say(random.choice(_STORY_POOL)); return
    if low in ("!помощь", "!help"):
        _say("Команды: !рп-режим on|off, !дуэль <ник>, !топ, !история, "
             "!иди сюда, !стой, !укрытие, !бой <ник>, !отбой, !игры"); return
    if low.startswith("!игры") or low == "!games":
        _say(catalog_text().replace("\n", " | ")); return

    if _bot_is_alive():
        if low in ("!ко мне", "!иди сюда", "!подойди", "!сюда"):
            if _state.get("patrol", {}).get("active"):
                _rcon_cmd("otai_bot_patrol_stop")
            _bot_follow(nick); _say(f"Иду, {nick}."); return
        if low in ("!назад", "!патруль", "!продолжай"):
            pts = _state.get("patrol", {}).get("points", [])
            if pts:
                _sync_patrol_to_server()
                _rcon_cmd("otai_bot_patrol_start loop")
                _say("Возвращаюсь на маршрут.")
            return
        if low in ("!укрытие", "!прикройся"):
            _rcon_cmd("otai_cover_rebuild"); _say("* Укрываюсь."); return
        if low.startswith("!бой "):
            target = text[5:].strip()
            if target: _rcon_cmd(f'otai_combat_start "{target}" combat')
            return
        if low in ("!отбой", "!прекратить бой"):
            _rcon_cmd("otai_combat_stop"); return
        if low in ("!стой", "!стоп"):
            _bot_stop(); _say("Стою."); return
        if low in ("!следуй за мной", "!за мной"):
            _bot_follow(nick); _say(f"Иду за тобой, {nick}."); return
        if low.startswith("!скажи "):
            _say(text[7:]); return

    for obj in ALL_GAMES:
        for alias in obj.aliases:
            if low == f"!{alias}" or low.startswith(f"!{alias} "):
                args = text[len(alias) + 1:].strip().split()
                _game_start_from_chat(nick, obj.name, args); return

    if _bot_name().lower() in low and any(w in low for w in ("давай", "го", "сыграем", "хочу")):
        for obj in ALL_GAMES:
            for alias in obj.aliases:
                if alias in low:
                    _game_start_from_chat(nick, obj.name); return

    if _duel_try_accept(nick, text): return

    challenge_words = _cfg["duel"].get("challenge_keywords", [])
    mentions_bot = _bot_name().lower() in low
    if any(w in low for w in challenge_words) and mentions_bot and not _duel_get():
        _duel_clear(); _duel_start(nick); return

    g = _state.get("game")
    if g:
        obj = _find_game(g.get("name"))
        if obj and obj.on_chat(_ctx(), nick, text): return

    if _cfg["emotions"].get("enabled", True):
        ok, _ = _offense_allows(nick, "talk")
        if not ok:
            if random.random() < 0.4:
                _say(_emo.pick_refuse("talk"))
            return

    if _rp_is_on() and not _is_quiet():
        kind = _classify_chat(text)
        if kind == "compliment": _friend_add(nick, "kind_words")
        if random.random() < 0.6:
            _push_event(f"chat_{kind}",
                        f"Игрок {nick} пишет: «{text}»",
                        _rp_wrap(kind))

def _game_start_from_chat(nick, game_name, args=None):
    if not _cfg["games"].get("enabled", True):
        _say("Игры сейчас выключены."); return
    ok, kind = _offense_allows(nick, "game")
    if not ok: _say(_emo.pick_refuse("game")); return
    if _duel_get() or _state.get("game"):
        _say("Уже идёт другая игра."); return
    obj = _find_game(game_name)
    if not obj:
        _say(f"Не знаю такой игры «{game_name}». Напиши !игры."); return
    args = args or []
    resp = obj.start(_ctx(), nick, args)
    if resp: _log(f"[game] start {game_name} with {nick}: {resp}")

def _on_kill(victim, attacker, weapon):
    if victim != _bot_name() and attacker not in (None, "world", _bot_name()):
        _protect_friend(victim, attacker)

    if (_cfg["conflicts"].get("enabled", True)
            and attacker not in (None, "world", _bot_name())
            and victim and victim != _bot_name()):
        _soc.conflict_delta(_state.setdefault("conflicts", {}), attacker, victim, -3)
        _save_json(STATE_PATH, _state)
        if _try_mediate(attacker, victim): return

    _remember_player(victim, event="died")
    if attacker and attacker != "world":
        _remember_player(attacker, event="killed")

    d = _duel_get()
    if d and d.get("state") in ("countdown", "active"):
        bot = _bot_name(); opp = d.get("opponent")
        allowed = d.get("weapon", "weapon_357")
        if victim == bot and attacker not in (bot, opp, "world"):
            _duel_violation(f"{attacker} вмешался в честную дуэль", attacker); return
        if victim == bot and not _duel_weapon_ok(weapon, allowed):
            _duel_violation(f"{attacker} использовал «{weapon or '?'}» вместо револьвера", attacker); return
        if victim == opp and not _duel_weapon_ok(weapon, allowed):
            _duel_violation("я применил(а) не то оружие", None, self_blame=True); return
        if {victim, attacker} & {bot, opp}:
            _duel_finish(attacker, victim, reason="kill"); return

    g = _state.get("game")
    if g and g.get("state") == "active":
        obj = _find_game(g.get("name"))
        if obj and hasattr(obj, "on_kill") and obj.on_kill(_ctx(), victim, attacker, weapon):
            return
        if victim == _bot_name():
            _set_mood("annoyed")
            _say(f"* {_bot_name()} раздосадован(а). Игра отменяется.")
            if attacker and attacker != "world": _add_offense(attacker, "third_party")
            _ctx().clear_game(); return

    if _is_quiet(): return
    if _rp_is_on():
        if weapon and "357" in weapon.lower():
            _push_event("kill_pistol", f"{attacker} застрелил {victim} из револьвера",
                        f"* {_bot_name()} провожает взглядом {victim}: меткий выстрел.")
        else:
            _push_event("kill_other", f"{attacker} убил {victim} оружием {weapon}",
                        f"* {victim} падает. {_bot_name()} отворачивается.")
    else:
        if attacker and attacker != "world":
            _push_event("kill_neutral", f"{attacker} убил {victim}",
                        f"{attacker} только что уложил {victim}. Неплохо.")

def _on_hurt(victim, attacker, damage, *extra):
    if victim != _bot_name(): _protect_friend(victim, attacker)
    d = _duel_get()
    if d and d.get("state") in ("countdown", "active"):
        bot = _bot_name(); opp = d.get("opponent")
        if attacker not in (bot, opp, "world") and victim in (bot, opp):
            _duel_violation(f"{attacker} наносит урон в дуэли", attacker); return
    if (victim == _bot_name() and attacker and attacker != "world"
            and not _duel_get() and _cfg["emotions"].get("enabled", True)):
        _friend_sub(attacker, "friendly_fire")
        _add_offense(attacker, "friendly_fire",
                     context=_emo.make_context("friendly_fire", who=attacker))
    if victim == _bot_name() and _rp_is_on():
        _say(f"* {_bot_name()} получает {damage} урона и отступает.")

def _on_spawn(nick):
    _remember_player(nick, event="spawn")
    if (_cfg["smart_patrol"].get("enabled", True)
            and _state.get("patrol", {}).get("active")):
        sp = _state.setdefault("smart_patrol", {})
        now = time.time()
        cd = float(_cfg["smart_patrol"].get("greet_cooldown", 20))
        if now - sp.get("active_until", 0) > cd:
            sp["active_until"] = now; sp["reason"] = f"greet:{nick}"
            _save_json(STATE_PATH, _state)
            _rcon_cmd("otai_bot_patrol_stop"); _bot_goto_player(nick)
            _say(f"{nick} появился. Иду поздороваться."); return
    rec = _get_offense(nick)
    if rec and not rec.get("subtle"):
        _say(_emo.pick_line(rec["level"], _bot_name())); return
    if _rp_is_on() and not _is_quiet():
        _push_event("spawn", f"{nick} появился рядом",
                    f"* {nick} появляется рядом. {_bot_name()} кивает.")

def _on_leave(nick):
    if _is_romantic(nick) and not _is_quiet():
        line = _soc.pick_romantic("farewell", _bot_name())
        if line: _say(line); return
    if _rp_is_on() and not _is_quiet():
        _push_event("leave", f"{nick} покинул сервер",
                    f"* {nick} уходит. {_bot_name()} провожает взглядом.")

def _on_target_hit(nick, remaining):
    g = _state.get("game")
    if not g: return
    obj = _find_game(g.get("name"))
    if obj and hasattr(obj, "on_target_hit"):
        try: obj.on_target_hit(_ctx(), nick, remaining)
        except Exception as e: _log(f"[range] {e!r}")

def _on_teamkill(victim, vteam, ateam):
    g = _state.get("game")
    if not g or g.get("name") != "team": return
    obj = _find_game("тим")
    if obj and hasattr(obj, "on_team_kill"):
        red_id  = str(_cfg["teams"].get("red_id", 2))
        blue_id = str(_cfg["teams"].get("blue_id", 3))
        vside = "red" if vteam == red_id else ("blue" if vteam == blue_id else None)
        asid  = "red" if ateam == red_id else ("blue" if ateam == blue_id else None)
        if vside and asid and vside != asid:
            try: obj.on_team_kill(_ctx(), victim, vside, asid)
            except Exception as e: _log(f"[team] {e!r}")

def _on_player_init(nick):
    entries = _state.get("diary", {}).get(nick, [])
    if not entries: return
    days = _soc.diary_days_since_last(entries)
    if days is None: return
    if (days >= float(_cfg["diary"].get("absence_days_threshold", 3))
            and _cfg["diary"].get("remember_long_absence", True)):
        summary = _soc.diary_summary(entries, _bot_name(), max_lines=2)
        _say(f"{nick}, давно не виделись ({int(days)} дн).")
        if summary: _say(summary)
        _diary_add(nick, "long_absence", nick=nick, days=int(days))

def _on_bot_spawned(name):
    b = _state.setdefault("bot", {})
    b.update({"spawned": True, "name": name, "hp": 100, "last_state_ts": time.time()})
    _save_json(STATE_PATH, _state)

def _on_bot_removed():
    b = _state.setdefault("bot", {})
    b.update({"spawned": False, "hp": None, "pos": None, "weapon": None})
    _save_json(STATE_PATH, _state)

def _on_bot_state(x, y, z, hp, armor, weapon, nav_mode=""):
    b = _state.setdefault("bot", {})
    b["pos"] = [float(x), float(y), float(z)]
    try: b["hp"] = int(hp)
    except (TypeError, ValueError): b["hp"] = None
    try: b["armor"] = int(armor)
    except (TypeError, ValueError): b["armor"] = None
    b["weapon"] = weapon or None
    b["last_state_ts"] = time.time()
    b["spawned"] = True
    if nav_mode in ("ai", "manual"): b["nav_mode"] = nav_mode
    _save_json(STATE_PATH, _state)

def _on_bot_death(killer):
    d = _duel_get()
    if d and d.get("state") in ("countdown", "active"):
        _duel_finish(killer, _bot_name(), reason="bot_died")
    else:
        if _rp_is_on():
            _say(f"* {_bot_name()} падает. {killer} оказался быстрее.")
    b = _state.setdefault("bot", {}); b["hp"] = 0
    _save_json(STATE_PATH, _state)

def _on_bot_respawned():
    b = _state.setdefault("bot", {})
    b["hp"] = 100; b["spawned"] = True
    _save_json(STATE_PATH, _state)

def _on_bot_nav_mode(mode, reason=""):
    b = _state.setdefault("bot", {})
    prev = b.get("nav_mode"); b["nav_mode"] = mode
    _save_json(STATE_PATH, _state)
    if prev != mode:
        label = {"ai": "по навмешу", "manual": "вручную"}.get(mode, mode)
        msg = f"* Режим навигации: {label}"
        if reason and reason != "ok": msg += f" ({reason})"
        _say(msg)

def _on_patrol_set(count):
    p = _state.setdefault("patrol", {"points": [], "active": False, "index": 0})
    p["points"] = [None] * int(count) if count != "0" else []
    _save_json(STATE_PATH, _state)

def _on_patrol_start(reason):
    p = _state.setdefault("patrol", {})
    if reason == "ok":
        p["active"] = True; _save_json(STATE_PATH, _state)

def _on_patrol_stop():
    _state.setdefault("patrol", {})["active"] = False
    _save_json(STATE_PATH, _state)

def _on_patrol_state(count, index, state):
    p = _state.setdefault("patrol", {})
    p["index"] = int(index) if str(index).isdigit() else 0
    p["active"] = (state == "active")
    _save_json(STATE_PATH, _state)

def _on_combat_started(nick, mode="combat"):
    c = _state.setdefault("combat", {})
    c.update({"active": True, "target": nick, "mode": mode, "last_event": "started"})
    _save_json(STATE_PATH, _state)

def _on_combat_stopped():
    c = _state.setdefault("combat", {})
    c.update({"active": False, "target": None, "last_event": "stopped"})
    _save_json(STATE_PATH, _state)

def _on_cover_spawned(count):
    c = _state.setdefault("combat", {})
    c["covers"] = int(count) if str(count).isdigit() else 0
    _save_json(STATE_PATH, _state)
    _say(f"* {_bot_name()} ставит укрытия ({count} шт).")

def _on_cover_destroyed(remaining, *extra):
    attacker = extra[0] if extra else ""
    c = _state.setdefault("combat", {})
    c["covers"] = int(remaining) if str(remaining).isdigit() else 0
    _save_json(STATE_PATH, _state)
    if attacker:
        _friend_sub(attacker, "broke_cover")
        _add_offense(attacker, "griefing_cover",
                     context=_emo.make_context("broke_cover", who=attacker, count=1))

def _on_cover_cleared():
    _state.setdefault("combat", {})["covers"] = 0
    _save_json(STATE_PATH, _state)

def _on_grenade_spotted(cls):
    _push_event("grenade", f"рядом граната ({cls})",
                f"* {_bot_name()} уходит с линии взрыва!")

def _bridge_loop():
    host = _cfg["bridge"].get("udp_host", "0.0.0.0")
    port = int(_cfg["bridge"].get("udp_port", 27099))
    secret = _cfg["bridge"].get("shared_secret", "")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
    except OSError as e:
        _log(f"[bridge] bind failed {host}:{port}: {e}"); return
    sock.settimeout(1.0)
    _log(f"[bridge] listening UDP {host}:{port}")

    while not _bridge_stop.is_set():
        try:
            data, addr = sock.recvfrom(4096)
        except socket.timeout: continue
        except OSError: break
        try: line = data.decode("utf-8", errors="replace")
        except Exception: continue
        parts = line.split("\t")
        if len(parts) < 3 or parts[0] != _BRIDGE_PREFIX: continue
        if secret and parts[1] != secret: continue
        ptype, rest = parts[2], parts[3:]
        try:
            if   ptype == "CHAT" and len(rest) >= 2: _on_chat(rest[0], rest[1])
            elif ptype == "KILL" and len(rest) >= 3: _on_kill(rest[0], rest[1], rest[2])
            elif ptype == "HURT" and len(rest) >= 3: _on_hurt(rest[0], rest[1], rest[2])
            elif ptype == "SPAWN" and len(rest) >= 1: _on_spawn(rest[0])
            elif ptype == "LEAVE" and len(rest) >= 1: _on_leave(rest[0])
            elif ptype == "BOT_SPAWNED" and len(rest) >= 1: _on_bot_spawned(rest[0])
            elif ptype == "BOT_REMOVED": _on_bot_removed()
            elif ptype == "BOT_STATE" and len(rest) >= 6: _on_bot_state(*rest[:7])
            elif ptype == "BOT_DEATH" and len(rest) >= 1: _on_bot_death(rest[0])
            elif ptype == "BOT_RESPAWNED": _on_bot_respawned()
            elif ptype == "BOT_NAV_MODE" and len(rest) >= 1:
                _on_bot_nav_mode(rest[0], rest[1] if len(rest) > 1 else "")
            elif ptype == "BOT_NAV_WARN" and len(rest) >= 1:
                _say(f"* Навигация недоступна: {rest[0]}.")
            elif ptype == "PATROL_SET" and len(rest) >= 1: _on_patrol_set(rest[0])
            elif ptype == "PATROL_START" and len(rest) >= 1: _on_patrol_start(rest[0])
            elif ptype == "PATROL_STOP": _on_patrol_stop()
            elif ptype == "PATROL_STATE" and len(rest) >= 3:
                _on_patrol_state(rest[0], rest[1], rest[2])
            elif ptype == "PATROL_DONE":
                _say("* Патруль окончен."); _on_patrol_stop()
            elif ptype == "COMBAT_STARTED" and len(rest) >= 1:
                _on_combat_started(rest[0], rest[1] if len(rest) > 1 else "combat")
            elif ptype == "COMBAT_STOPPED": _on_combat_stopped()
            elif ptype == "COVER_SPAWNED" and len(rest) >= 1: _on_cover_spawned(rest[0])
            elif ptype == "COVER_DESTROYED" and len(rest) >= 1: _on_cover_destroyed(*rest)
            elif ptype == "COVER_CLEARED": _on_cover_cleared()
            elif ptype == "COVER_COUNT" and len(rest) >= 1:
                _state.setdefault("combat", {})["covers"] = int(rest[0])
                _save_json(STATE_PATH, _state)
            elif ptype == "GRENADE_SPOTTED" and len(rest) >= 1: _on_grenade_spotted(rest[0])
            elif ptype == "RANGE_START": pass
            elif ptype == "TARGET_HIT" and len(rest) >= 2:
                _on_target_hit(rest[0], int(rest[1]))
            elif ptype == "TEAMKILL" and len(rest) >= 3:
                _on_teamkill(rest[0], rest[1], rest[2])
            elif ptype == "HP_CHANGED": pass
            elif ptype == "PLAYER_INIT" and len(rest) >= 1:
                _remember_player(rest[0], "init"); _on_player_init(rest[0])
            elif ptype == "BUILD_DONE" and len(rest) >= 2:
                b = _state.setdefault("builder", {})
                try: b["count"] = int(rest[1])
                except ValueError: b["count"] = 0
                _save_json(STATE_PATH, _state)
            elif ptype == "BUILD_CLEARED":
                _state.setdefault("builder", {})["count"] = 0
                _save_json(STATE_PATH, _state)
                _say("* Все постройки снесены.")
            elif ptype == "BUILD_UNDO": pass
            elif ptype == "BUILD_COUNT" and len(rest) >= 1:
                _state.setdefault("builder", {})["count"] = int(rest[0])
                _save_json(STATE_PATH, _state)
            elif ptype == "BUILD_ANIM" and len(rest) >= 1:
                _state.setdefault("builder", {})["anim"] = (rest[0] == "on")
                _save_json(STATE_PATH, _state)
        except Exception as e:
            _log(f"[bridge] handler {ptype} error: {e!r}")
    try: sock.close()
    except OSError: pass

# -------- фоновые потоки --------

def _listener_loop():
    interval = max(5, int(_cfg["listener"].get("poll_interval_sec", 15)))
    while not _listener_stop.is_set():
        try:
            with _rcon_lock: cli = _rcon
            if cli is None:
                _listener_stop.wait(interval); continue
            raw = cli.command("status")
            online = _parse_status_players(raw)
            prev, cur = set(_state.get("players_online", [])), set(online)
            joined, left = cur - prev, prev - cur
            bot = _bot_name()
            if _cfg["listener"].get("greet_new_players", True):
                for nick in joined:
                    if nick == bot: continue
                    _remember_player(nick, event="join")
                    if _is_romantic(nick):
                        line = _soc.pick_romantic("greet", _bot_name())
                        if line: _say(line)
                    else:
                        tier = _friend_tier(nick)
                        fl = _emo.pick_friend_greeting(tier, _bot_name())
                        _say(fl or f"Привет, {nick}! {_mood_line()}")
            if _cfg["listener"].get("farewell_on_leave", True):
                for nick in left:
                    if nick == bot: continue
                    _say(f"{nick} покинул нас. Удачи!")
            _state["players_online"] = sorted(cur)
            _save_json(STATE_PATH, _state)
        except RCONError as e: _log(f"[listener] rcon: {e}")
        except Exception as e: _log(f"[listener] exc: {e!r}")
        _listener_stop.wait(interval)

def _idle_loop():
    cfg = _cfg["idle"]
    interval = max(30, int(cfg.get("interval_sec", 120)))
    min_silence = max(10, int(cfg.get("min_silence_sec", 90)))
    while not _idle_stop.is_set():
        _idle_stop.wait(interval)
        if not _cfg["idle"].get("enabled", True): continue
        if _is_quiet(): continue
        if not _bot_is_alive(): continue
        if time.time() - _state.get("last_user_msg_ts", 0.0) < min_silence: continue
        try:
            _say(f"* {_bot_name()} {random.choice(_IDLE_ACTIONS)}")
            _state["last_idle_ts"] = time.time()
            _save_json(STATE_PATH, _state)
        except Exception as e: _log(f"[idle] {e!r}")

def _game_tick_loop():
    interval = float(_cfg["games"].get("tick_interval_sec", 1.0))
    while not _game_stop.is_set():
        _game_stop.wait(interval)
        g = _state.get("game")
        if not g: continue
        obj = _find_game(g.get("name"))
        if not obj: continue
        try: obj.on_tick(_ctx())
        except Exception as e: _log(f"[game] tick error: {e!r}")
        if getattr(obj, "timeout", 0) and time.time() - g.get("started", 0) > obj.timeout:
            _say(f"Игра «{obj.name}» прервана по времени.")
            _bot_stop(); _ctx().clear_game()

def _bot_target_loop():
    while not _bot_target_stop.is_set():
        _bot_target_stop.wait(0.8)
        g = _state.get("game")
        if not g or g.get("name") != "range" or g.get("state") != "active": continue
        _rcon_cmd('otai_bot_fire_at "" 1')

def _hot_loop():
    interval = int(_cfg["model_rp"].get("hot_interval_sec", 30))
    chance   = float(_cfg["model_rp"].get("hot_chance", 0.5))
    window   = int(_cfg["model_rp"].get("hot_window_sec", 90))
    while not _hot_stop.is_set():
        _hot_stop.wait(interval)
        if not _cfg["model_rp"].get("enabled", True): continue
        if not _cfg["model_rp"].get("hot_enabled", True): continue
        if _model_ref is None: continue
        if _is_quiet(): continue
        if not _bot_is_alive(): continue
        if random.random() > chance: continue
        now = time.time()
        with _event_buffer_lock:
            candidates = [e for e in _event_buffer if not e["used"] and now - e["ts"] < window]
        if not candidates: continue
        e = random.choice(candidates); e["used"] = True
        _rp_say(e["prompt"], e["fallback"])
        with _event_buffer_lock:
            _event_buffer[:] = [x for x in _event_buffer if now - x["ts"] < 180]

def _offense_decay_loop():
    interval = int(_cfg["emotions"].get("decay_check_sec", 30))
    while not _listener_stop.is_set():
        _listener_stop.wait(interval)
        store = _emo_store()
        if not store: continue
        now = time.time(); changed = False
        for nick in list(store.keys()):
            if store[nick].get("until", 0) <= now:
                store.pop(nick, None); changed = True
        tg = _state.get("team_grudges", {}); tg_changed = False
        for t in list(tg.keys()):
            if tg[t].get("until", 0) <= now:
                tg.pop(t, None); tg_changed = True
        if changed or tg_changed: _save_json(STATE_PATH, _state)

def _conflict_decay_loop():
    interval = int(_cfg["conflicts"].get("decay_check_sec", 300))
    while not _listener_stop.is_set():
        _listener_stop.wait(interval)
        if not _cfg["conflicts"].get("enabled", True): continue
        conf = _state.get("conflicts", {})
        if not conf: continue
        _soc.decay_conflicts(conf); _save_json(STATE_PATH, _state)

def _furious_attack_loop():
    while not _listener_stop.is_set():
        _listener_stop.wait(2)
        if not _cfg["emotions"].get("enabled", True): continue
        if not _bot_is_alive(): continue
        store = _emo_store()
        if not store: continue
        bp = _bot_get().get("pos")
        if not bp: continue
        rng = float(_cfg["emotions"].get("furious_attack_range", 250))
        dur = float(_cfg["emotions"].get("furious_attack_duration", 3))
        for nick, rec in list(store.items()):
            if rec.get("level", 0) < 4: continue
            pos = _state.get("players_seen", {}).get(nick, {}).get("last_pos")
            if not pos: continue
            d = ((bp[0]-pos[0])**2 + (bp[1]-pos[1])**2 + (bp[2]-pos[2])**2) ** 0.5
            if d < rng:
                _bot_aim(nick); _bot_fire_at(nick, dur)
                _say(f"* {_bot_name()} открывает огонь по {nick}!")
                break

def _bad_day_loop():
    interval = int(_cfg["bad_day"].get("check_interval_sec", 600))
    chance   = float(_cfg["bad_day"].get("chance", 0.10))
    while not _listener_stop.is_set():
        _listener_stop.wait(interval)
        if not _cfg["bad_day"].get("enabled", True): continue
        if _is_bad_day(): continue
        if _is_quiet(): continue
        if random.random() < chance: _start_bad_day()
        if _is_bad_day() and not _listener_stop.is_set():
            _listener_stop.wait(int(_cfg["bad_day"].get("duration_sec", 900)))
            if _is_bad_day(): _end_bad_day()

# -------- start/stop --------

def _start_listener():
    global _listener_thread
    if _listener_thread and _listener_thread.is_alive(): return
    _listener_stop.clear()
    _listener_thread = threading.Thread(target=_listener_loop, name="otai_listener", daemon=True)
    _listener_thread.start()
    for fn, nm in ((_offense_decay_loop, "otai_emo_decay"),
                   (_conflict_decay_loop, "otai_conflicts"),
                   (_furious_attack_loop, "otai_emo_furious"),
                   (_bad_day_loop, "otai_bad_day")):
        threading.Thread(target=fn, name=nm, daemon=True).start()

def _stop_listener(): _listener_stop.set()

def _start_idle():
    global _idle_thread
    if _idle_thread and _idle_thread.is_alive(): return
    _idle_stop.clear()
    _idle_thread = threading.Thread(target=_idle_loop, name="otai_idle", daemon=True)
    _idle_thread.start()

def _stop_idle(): _idle_stop.set()

def _start_bridge():
    global _bridge_thread
    if _bridge_thread and _bridge_thread.is_alive(): return
    _bridge_stop.clear()
    _bridge_thread = threading.Thread(target=_bridge_loop, name="otai_bridge", daemon=True)
    _bridge_thread.start()

def _stop_bridge(): _bridge_stop.set()

def _start_game_loop():
    global _game_thread
    if _game_thread and _game_thread.is_alive(): return
    _game_stop.clear()
    _game_thread = threading.Thread(target=_game_tick_loop, name="otai_game_tick", daemon=True)
    _game_thread.start()

def _start_hot():
    global _hot_thread
    if _hot_thread and _hot_thread.is_alive(): return
    _hot_stop.clear()
    _hot_thread = threading.Thread(target=_hot_loop, name="otai_hot", daemon=True)
    _hot_thread.start()

def _stop_hot(): _hot_stop.set()

def _start_bot_target_loop():
    global _bot_target_thread
    if _bot_target_thread and _bot_target_thread.is_alive(): return
    _bot_target_stop.clear()
    _bot_target_thread = threading.Thread(target=_bot_target_loop, name="otai_bot_range", daemon=True)
    _bot_target_thread.start()

def _stop_bot_target_loop(): _bot_target_stop.set()

@atexit.register
def _shutdown():
    _stop_listener(); _stop_idle(); _stop_bridge()
    _stop_hot(); _stop_bot_target_loop()
    _duel_stop.set(); _game_stop.set()
    try: _bot_remove()
    except Exception: pass

# -------- консольные команды -----

HELP_TEXT = (
    "[персонаж v14] Команды:\n"
    "  !game join | leave | status\n"
    "  !game say <текст> | cmd <rcon> | char <name|bio|color|greeting|farewell> [знач.]\n"
    "  !game players | mood [состояние] | memory <ник> | forget <ник>\n"
    "  !game idle on|off | rp on|off | bridge on|off\n"
    "  !game duel <ник> | duels | history\n"
    "  —— бот ——\n"
    "  !game bot spawn|remove|respawn\n"
    "  !game bot goto|teleport|follow|stop|aim|fire|ceasefire|say|give|status\n"
    "  !game bot navmode ai|manual|status | navviz on|off|toggle | hybrid | strafe\n"
    "  !game bot patrol add|addhere|clear|start [once]|stop|status | patrol_topos <N>\n"
    "  !game bot combat start <ник> [duel]|stop|status\n"
    "  !game bot cover spawn [N]|clear|count|rebuild | combatset <k> <v>\n"
    "  —— игры/экономика ——\n"
    "  !game games | game <название> [ник]\n"
    "  !game points [ник] | top-points | setpoints <ник> <число>\n"
    "  !game тир [N] [сек] [moving] [coop] | top-range\n"
    "  !game тим red|blue|start|score|stop|leave\n"
    "  —— социальное ——\n"
    "  !game обижен | forgive <ник> | emotions\n"
    "  !game friends | badday start|end|status\n"
    "  !game diary <ник> | scars | conflicts | team_grudges\n"
    "  —— строительство ——\n"
    "  !game build wall|tower|platform|box|house|stack|place|clear|undo|count|anim|speed|save|load|list\n"
    "  (в чате): !рп-режим on|off | !дуэль <ник> | !кнб <ход> [ставка] | !тир [N]\n"
    "           !тим <...> | извини/прости | !ко мне | !укрытие | !игры\n"
)

def _cmd_join():
    global _rcon
    with _rcon_lock:
        if _rcon is not None: return "[персонаж] Уже подключён."
        r = _cfg["rcon"]
        cli = RCONClient(r["host"], r["port"], r["password"])
        try: cli.connect()
        except (RCONError, OSError) as e: return f"[персонаж] Не удалось: {e}"
        _rcon = cli
    _state["connected"] = True; _state["teams"] = {"red": [], "blue": []}
    _save_json(STATE_PATH, _state)
    _apply_identity()
    greeting = _cfg["character"]["greeting"].format(name=_name())
    _say(greeting)

    if _cfg["listener"].get("enabled", True): _start_listener()
    if _cfg["idle"].get("enabled", True):     _start_idle()
    if _cfg["bridge"].get("enabled", True):   _start_bridge()
    if _cfg["games"].get("enabled", True):    _start_game_loop()
    if _cfg["model_rp"].get("hot_enabled", True): _start_hot()

    bot_msg = ""
    if _cfg["bot"].get("auto_spawn_on_join", True):
        ok, info = _bot_spawn()
        bot_msg = f" {info}." if ok else f" Бот не поднялся: {info}."
    return (f"[персонаж] Подключился к {r['host']}:{r['port']} как «{_name()}». "
            f"{greeting}{bot_msg}")

def _cmd_leave():
    global _rcon
    _stop_listener(); _stop_idle(); _stop_bridge()
    _stop_hot(); _stop_bot_target_loop(); _game_stop.set()
    _ctx().clear_game()
    try: _bot_remove()
    except Exception: pass
    with _rcon_lock:
        cli, _rcon = _rcon, None
    if cli is None: return "[персонаж] Нет подключения."
    farewell = _cfg["character"].get("farewell", "Пока!").format(name=_name())
    try: _say(farewell)
    except Exception: pass
    try: cli.disconnect()
    except Exception: pass
    _state["connected"] = False; _state["players_online"] = []
    _save_json(STATE_PATH, _state)
    return f"[персонаж] Отключился. {farewell}"

def _cmd_status():
    ch = _cfg["character"]
    with _rcon_lock: on = _rcon is not None
    online = _state.get("players_online", [])
    d = _duel_get()
    duel_str = f"{d.get('state')} vs {d.get('opponent') or d.get('challenger')}" if d else "—"
    b = _bot_get()
    bot_str = "нет"
    if b.get("spawned"):
        pos = b.get("pos") or [0,0,0]
        bot_str = (f"«{b.get('name')}» HP={b.get('hp')} "
                   f"wpn={b.get('weapon') or '—'} "
                   f"pos=({pos[0]:.0f},{pos[1]:.0f},{pos[2]:.0f}) "
                   f"nav={b.get('nav_mode','?')}")
    store = _emo_store()
    active = sum(1 for r in store.values() if r.get("until", 0) > time.time())
    subtle = sum(1 for r in store.values()
                 if r.get("until", 0) > time.time() and r.get("subtle"))
    off = ("нет" if not active else
           (f"{active} (скрытых: {subtle})" if subtle else str(active)))
    bad = " (плохой день)" if _is_bad_day() else ""
    return (f"[персонаж] Имя: {ch.get('name')} | Настроение: {_get_mood()}{bad}\n"
            f"RP: {'вкл' if _rp_is_on() else 'выкл'} | "
            f"Статус: {'в игре' if on else 'оффлайн'}\n"
            f"Игроков онлайн: {len(online)}"
            + (f" — {', '.join(online)}" if online else "") + "\n"
            f"Бот: {bot_str}\n"
            f"Обид: {off}\n"
            f"Активная дуэль: {duel_str}")

def _cmd_say(arg):
    if not arg: return "[персонаж] Текст?"
    return f"[персонаж] {'сказал' if _say(arg) else '(offline)'}: {arg}"

def _cmd_raw(arg):
    if not arg: return "[персонаж] RCON-команда?"
    resp = _rcon_cmd(arg)
    if resp is None: return "[персонаж] Сначала `!game join`."
    return f"[RCON] > {arg}\n{(resp or '').strip()[:500] or '(пусто)'}"

def _cmd_char(arg):
    parts = arg.split(maxsplit=1)
    fields = ("name", "bio", "color", "greeting", "farewell")
    if not parts:
        return "[персонаж] " + ", ".join(f"{k}={_cfg['character'].get(k,'')}" for k in fields)
    field, value = parts[0].lower(), (parts[1] if len(parts) > 1 else "")
    if field not in fields: return f"[персонаж] Поля: {', '.join(fields)}"
    if not value:           return f"[персонаж] {field} = {_cfg['character'].get(field,'')}"
    _cfg["character"][field] = value
    _save_json(CONFIG_PATH, _cfg)
    return f"[персонаж] {field} = {value}"

def _cmd_players():
    online = _state.get("players_online", [])
    if not online: return "[персонаж] Никого нет."
    return "[персонаж] Онлайн:\n" + "\n".join(f"  • {n}" for n in online)

def _cmd_mood(arg):
    a = arg.strip().lower()
    if not a: return f"[персонаж] Настроение: {_get_mood()}. Доступно: {', '.join(_MOODS)}"
    if not _set_mood(a): return f"[персонаж] Неизвестное «{a}»."
    _say(f"* {_bot_name()} меняет настроение на «{a}»")
    return f"[персонаж] Настроение: {a}"

def _cmd_memory(arg):
    nick = arg.strip()
    if not nick: return "[персонаж] Ник?"
    rec = _state.get("players_seen", {}).get(nick)
    if not rec: return f"[персонаж] Не помню «{nick}»."
    return (f"[персонаж] {nick}:\n"
            f"  Первая встреча: {_fmt_ts(rec.get('first_seen'))}\n"
            f"  Последний раз:  {_fmt_ts(rec.get('last_seen'))}\n"
            f"  Общений:        {rec.get('interactions', 0)}\n"
            f"  Дружба:         {_friend_score(nick)} ({_friend_tier(nick)})")

def _cmd_forget(arg):
    nick = arg.strip()
    if not nick: return "[персонаж] Ник?"
    players = _state.get("players_seen", {})
    if nick not in players: return "[персонаж] И так не помню."
    players.pop(nick); _save_json(STATE_PATH, _state)
    return f"[персонаж] Забыл «{nick}»."

def _cmd_idle(arg):
    a = arg.strip().lower()
    if a not in ("on","off",""): return "[персонаж] `!game idle on|off`"
    if a == "": return f"[персонаж] Idle: {'on' if _cfg['idle']['enabled'] else 'off'}"
    _cfg["idle"]["enabled"] = (a == "on"); _save_json(CONFIG_PATH, _cfg)
    (_start_idle() if _cfg["idle"]["enabled"] else _stop_idle())
    return f"[персонаж] Idle {a}."

def _cmd_rp(arg):
    a = arg.strip().lower()
    if a not in ("on","off",""): return "[персонаж] `!game rp on|off`"
    if a == "": return f"[персонаж] RP: {'on' if _rp_is_on() else 'off'}"
    _rp_set(a == "on"); _say(f"* RP-режим {'включён' if _rp_is_on() else 'выключен'}.")
    return f"[персонаж] RP {a}."

def _cmd_bridge(arg):
    a = arg.strip().lower()
    if a not in ("on","off",""): return "[персонаж] `!game bridge on|off`"
    if a == "": return f"[персонаж] Мост: {'on' if _cfg['bridge']['enabled'] else 'off'}"
    _cfg["bridge"]["enabled"] = (a == "on"); _save_json(CONFIG_PATH, _cfg)
    (_start_bridge() if _cfg["bridge"]["enabled"] else _stop_bridge())
    return f"[персонаж] Мост {a}."

def _cmd_duel(arg):
    if not arg.strip(): return "[персонаж] `!game duel <ник>`"
    return _duel_challenge(arg.strip())

def _cmd_duels(): return _duel_leaderboard()

def _cmd_history():
    log = _state.get("chat_log", [])[-10:]
    if not log: return "[персонаж] Пока ничего не слышал."
    return "[персонаж] Последние 10:\n" + \
           "\n".join(f"  [{_fmt_ts(e['ts'])}] {e['nick']}: {e['text']}" for e in log)

def _cmd_game(arg):
    parts = arg.split(maxsplit=1)
    if not parts: return catalog_text()
    obj = _find_game(parts[0])
    if not obj: return f"[игра] Нет игры «{parts[0]}». Набери `!game games`."
    extra = parts[1].split() if len(parts) > 1 else []
    target = extra[0] if extra else _bot_name()
    if _duel_get() or _state.get("game"): return "[игра] Уже идёт другая игра."
    resp = obj.start(_ctx(), target, extra[1:])
    return resp or "[игра] Запущено."

def _cmd_grudges():
    store = _emo_store()
    active = {n: r for n, r in store.items() if r.get("until", 0) > time.time()}
    if not active: return "[персонаж] Обид ни на кого нет."
    lines = ["[персонаж] Обиды:"]
    now = time.time()
    for nick, r in sorted(active.items(), key=lambda kv: -kv[1].get("level", 0)):
        left = int(r["until"] - now)
        lines.append(f"  • {nick:20s} — {_emo.level_name(r.get('level',1))} "
                     f"| причина: {r.get('reason','?')} | ещё {left} с "
                     f"| извинений: {r.get('apologies',0)}"
                     + (" [скрыто]" if r.get("subtle") else ""))
    return "\n".join(lines)

def _cmd_forgive(arg):
    nick = arg.strip()
    if not nick: return "[персонаж] `!game forgive <ник>`"
    rec = _get_offense(nick)
    if not rec: return f"[персонаж] Я и не обижался(ась) на {nick}."
    _say(_emo.pick_forgive(rec["level"], _bot_name()))
    _clear_grudge(nick); _set_mood("neutral")
    return f"[персонаж] Обида на {nick} снята (уровень был {rec['level']})."

def _cmd_emotions_config():
    e = _cfg["emotions"]
    return ("[emotions] Конфиг:\n"
            f"  enabled               = {e.get('enabled')}\n"
            f"  decay_check_sec       = {e.get('decay_check_sec')}\n"
            f"  apology_cooldown_sec  = {e.get('apology_cooldown_sec')}\n"
            f"  furious_attack_range  = {e.get('furious_attack_range')}\n"
            f"  furious_attack_duration = {e.get('furious_attack_duration')}")

def _cmd_points(arg):
    nick = arg.strip() or _bot_name()
    return f"[экономика] {nick}: {_points_get(nick)} очков."

def _cmd_points_top(): return _points_leaderboard()

def _cmd_setpoints(arg):
    parts = arg.split()
    if len(parts) != 2: return "[экономика] `!game setpoints <ник> <число>`"
    nick, val = parts[0], parts[1]
    try: val = int(val)
    except ValueError: return "[экономика] Число?"
    _points_add(nick, val - _points_get(nick))
    return f"[экономика] {nick} → {val} очков."

def _cmd_range(full, arg1="", arg2=""):
    if not _cfg["range"].get("enabled", True): return "[тир] Выключен."
    if _duel_get() or _state.get("game"): return "[тир] Уже идёт другая игра."
    args = (full.split() if full else [])
    obj = _find_game("тир")
    return obj.start(_ctx(), _bot_name(), args) or "[тир] Запущено."

def _cmd_range_top():
    rs = _state.get("range_scores", {})
    if not rs: return "[тир] Пока никто не стрелял."
    rows = sorted(rs.items(), key=lambda kv: (-kv[1]["hits"], kv[1]["time"]))[:10]
    return "[тир] Топ стрелков:\n" + "\n".join(
        f"  {i+1}. {n} — {r['hits']}/{r['total']} за {r['time']}с"
        for i, (n, r) in enumerate(rows))

def _cmd_team(arg):
    if not _cfg["teams"].get("enabled", True): return "[тим] Выключено."
    parts = arg.split()
    if not parts: return _cmd_team_list()
    obj = _find_game("тим")
    return obj.start(_ctx(), _bot_name(), parts) or "[тим] OK"

def _cmd_team_list():
    t = _state.get("teams", {"red": [], "blue": []})
    red, blue = t.get("red", []), t.get("blue", [])
    return (f"[тим] Red ({len(red)}): {', '.join(red) or '—'}\n"
            f"      Blue ({len(blue)}): {', '.join(blue) or '—'}")

def _cmd_friends():
    fr = _state.get("friendship", {})
    if not fr: return "[дружба] Пока никого не знаю достаточно хорошо."
    rows = sorted(fr.items(), key=lambda kv: kv[1], reverse=True)[:15]
    lines = ["[дружба] Отношения:"]
    for nick, score in rows:
        tier = _emo.friendship_tier(score)
        mark = {"bestie": "★", "friend": "•", "neutral": "·"}.get(tier, "·")
        rom  = " ♥" if _is_romantic(nick) else ""
        lines.append(f"  {mark} {nick:20s} — {score:>4} ({tier}){rom}")
    return "\n".join(lines)

def _cmd_bad_day(arg):
    a = arg.strip().lower()
    if a == "start": _start_bad_day(); return "[персонаж] Плохой день запущен."
    if a == "end":   _end_bad_day();   return "[персонаж] Плохой день завершён."
    state = "да" if _is_bad_day() else "нет"
    until = _state.get("bad_day", {}).get("until", 0)
    left = max(0, int(until - time.time()))
    return f"[персонаж] Плохой день: {state} (осталось {left} с)"

def _cmd_diary(arg):
    nick = arg.strip()
    if not nick: return "[персонаж] `!game diary <ник>`"
    entries = _state.get("diary", {}).get(nick, [])
    if not entries: return f"[персонаж] В дневнике пусто про {nick}."
    lines = [f"[дневник] {nick} ({len(entries)} записей):"]
    for e in entries[-15:]:
        txt = _soc.diary_render(e, _bot_name())
        if txt: lines.append(f"  [{_fmt_ts(e.get('ts'))}] {txt}")
    return "\n".join(lines)

def _cmd_scars():
    scars = _state.get("scars", {})
    active = {n: s for n, s in scars.items() if _soc.scar_active(s)}
    if not active: return "[персонаж] Шрамов нет."
    lines = ["[персонаж] Шрамы:"]
    for nick, s in active.items():
        left = int(s["until"] - time.time())
        lvl  = _soc.scar_decayed_level(s)
        lines.append(f"  • {nick:20s} — сила {lvl} | "
                     f"причина: {s.get('reason')} | ещё {left} с")
    return "\n".join(lines)

def _cmd_conflicts():
    conf = _state.get("conflicts", {})
    if not conf: return "[персонаж] Конфликтов не знаю."
    lines = ["[персонаж] Конфликты:"]
    seen = set()
    for a, opps in conf.items():
        for b, info in opps.items():
            key = tuple(sorted([a, b]))
            if key in seen: continue
            seen.add(key)
            lines.append(f"  • {a} ↔ {b}: {info.get('score')}")
    return "\n".join(lines) if len(lines) > 1 else "[персонаж] Явных конфликтов нет."

def _cmd_team_grudges():
    tg = _state.get("team_grudges", {})
    active = {t: r for t, r in tg.items() if _soc.team_grudge_active(tg, t)}
    if not active: return "[персонаж] На команды не обижаюсь."
    lines = ["[персонаж] Командные обиды:"]
    for t, r in active.items():
        left = int(r["until"] - time.time())
        lines.append(f"  • {t}: уровень {r.get('level')} | "
                     f"причина: {r.get('reason')} | ещё {left} с")
    return "\n".join(lines)

def _cmd_patrol_status():
    p = _state.get("patrol", {})
    pts = p.get("points", [])
    state = "активен" if p.get("active") else "стоит"
    idx = p.get("index", 0)
    if not pts: return "[патруль] Точек нет."
    return f"[патруль] {state}, точек: {len(pts)}, текущая: {idx or '—'}/{len(pts)}"

# -------- строительство --------

def _build_models_dir():
    d = os.path.join(PLUGIN_DIR, _cfg["builder"].get("save_dir", "builds"))
    os.makedirs(d, exist_ok=True)
    return d

def _model_alias(name):
    if not name: return _cfg["builder"]["default_model"]
    return _cfg["builder"]["models"].get(name.lower(), name)

def _remember_build(kind, params, anchor):
    b = _state.setdefault("builder", {})
    b["last_build"] = {"kind": kind, "params": params,
                       "anchor": list(anchor), "ts": time.time()}
    _save_json(STATE_PATH, _state)

def _cmd_build(arg):
    if not _cfg["builder"].get("enabled", True):
        return "[строительство] Выключено."
    if not _bot_is_alive():
        return "[строительство] Бот не в игре."

    parts = arg.split()
    if not parts:
        return ("[строительство] Команды:\n"
                "  wall <len> [height] [model]\n"
                "  tower <height> [model]\n"
                "  platform <sx> <sy> [model]\n"
                "  box <w> <h> <d> [model]\n"
                "  house [size] [model]\n"
                "  stack <count> [model]\n"
                "  place <model>\n"
                "  clear | undo | count\n"
                "  anim on|off | speed <сек>\n"
                "  save <name> | load <name> | list")

    sub = parts[0].lower()
    tail = parts[1:]
    pos = _bot_get().get("pos")

    if pos is None and sub not in ("clear", "undo", "count", "anim", "speed", "list"):
        return "[строительство] Позиция бота неизвестна."
    x, y, z = pos if pos else (0, 0, 0)

    if sub == "wall":
        length = int(tail[0]) if tail and tail[0].isdigit() else 5
        height = int(tail[1]) if len(tail) > 1 and tail[1].isdigit() else 1
        model  = _model_alias(tail[2] if len(tail) > 2 else None)
        _rcon_cmd(f'otai_build_wall {x+80} {y} {z} 0 {length} {height} "{model}"')
        _remember_build("wall", {"len": length, "h": height, "model": model}, (x, y, z))
        return f"[строительство] Стена {length}x{height}, {os.path.basename(model)}"

    if sub == "tower":
        height = int(tail[0]) if tail and tail[0].isdigit() else 5
        model  = _model_alias(tail[1] if len(tail) > 1 else None)
        _rcon_cmd(f'otai_build_tower {x+60} {y} {z} {height} "{model}"')
        _remember_build("tower", {"h": height, "model": model}, (x, y, z))
        return f"[строительство] Башня высотой {height}."

    if sub == "platform":
        sx = int(tail[0]) if tail and tail[0].isdigit() else 5
        sy = int(tail[1]) if len(tail) > 1 and tail[1].isdigit() else 5
        model = _model_alias(tail[2] if len(tail) > 2 else None)
        _rcon_cmd(f'otai_build_platform {x+80} {y} {z} {sx} {sy} "{model}"')
        _remember_build("platform", {"sx": sx, "sy": sy, "model": model}, (x, y, z))
        return f"[строительство] Платформа {sx}x{sy}."

    if sub == "box":
        w = int(tail[0]) if tail and tail[0].isdigit() else 5
        h = int(tail[1]) if len(tail) > 1 and tail[1].isdigit() else 2
        d = int(tail[2]) if len(tail) > 2 and tail[2].isdigit() else 5
        model = _model_alias(tail[3] if len(tail) > 3 else None)
        _rcon_cmd(f'otai_build_box {x+100} {y} {z} {w} {h} {d} "{model}"')
        _remember_build("box", {"w": w, "h": h, "d": d, "model": model}, (x, y, z))
        return f"[строительство] Коробка {w}x{h}x{d}."

    if sub == "house":
        size = int(tail[0]) if tail and tail[0].isdigit() else 5
        model = _model_alias(tail[1] if len(tail) > 1 else None)
        _rcon_cmd(f'otai_build_house {x+120} {y} {z} {size} "{model}"')
        _remember_build("house", {"size": size, "model": model}, (x, y, z))
        return f"[строительство] Дом {size}x{size}."

    if sub == "stack":
        count = int(tail[0]) if tail and tail[0].isdigit() else 3
        model = _model_alias(tail[1] if len(tail) > 1 else None)
        _rcon_cmd(f'otai_build_stack {x+60} {y} {z} {count} "{model}"')
        _remember_build("stack", {"count": count, "model": model}, (x, y, z))
        return f"[строительство] Стек из {count}."

    if sub == "place":
        model = _model_alias(tail[0] if tail else None)
        _rcon_cmd(f'otai_build_place "{model}" {x+50} {y} {z} 0 0 0')
        return f"[строительство] Проп {os.path.basename(model)} поставлен."

    if sub == "clear":
        _rcon_cmd("otai_build_clear"); return "[строительство] Всё снесено."
    if sub == "undo":
        _rcon_cmd("otai_build_undo"); return "[строительство] Последняя постройка удалена."
    if sub == "count":
        _rcon_cmd("otai_build_count"); time.sleep(0.15)
        return f"[строительство] Всего построек: {_state.get('builder', {}).get('count', '?')}"
    if sub == "anim":
        m = tail[0].lower() if tail else ""
        if m not in ("on", "off"):
            b = _state.get("builder", {})
            return f"[строительство] Анимация: {'on' if b.get('anim') else 'off'}"
        _rcon_cmd(f"otai_build_anim {m}")
        return f"[строительство] Анимация {m}."
    if sub == "speed":
        if not tail: return "[строительство] `speed <сек>`"
        _rcon_cmd(f"otai_build_speed {tail[0]}")
        return f"[строительство] Скорость: {tail[0]} с/проп."

    if sub == "save":
        if not tail: return "[строительство] `save <имя>`"
        name = re.sub(r'[^\w\-]', '_', tail[0])[:40]
        info = _state.get("builder", {}).get("last_build")
        if not info: return "[строительство] Нечего сохранять — сначала построй."
        path = os.path.join(_build_models_dir(), f"{name}.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        return f"[строительство] Сохранено в builds/{name}.json"

    if sub == "load":
        if not tail: return "[строительство] `load <имя>`"
        name = re.sub(r'[^\w\-]', '_', tail[0])[:40]
        path = os.path.join(_build_models_dir(), f"{name}.json")
        if not os.path.exists(path):
            return f"[строительство] Файла builds/{name}.json нет."
        with open(path, 'r', encoding='utf-8') as f:
            info = json.load(f)
        kind = info.get("kind"); params = info.get("params", {})
        model = params.get("model") or _cfg["builder"]["default_model"]
        if kind == "wall":
            _rcon_cmd(f'otai_build_wall {x+80} {y} {z} 0 {params.get("len",5)} {params.get("h",1)} "{model}"')
        elif kind == "tower":
            _rcon_cmd(f'otai_build_tower {x+60} {y} {z} {params.get("h",5)} "{model}"')
        elif kind == "platform":
            _rcon_cmd(f'otai_build_platform {x+80} {y} {z} {params.get("sx",5)} {params.get("sy",5)} "{model}"')
        elif kind == "box":
            _rcon_cmd(f'otai_build_box {x+100} {y} {z} {params.get("w",5)} {params.get("h",2)} {params.get("d",5)} "{model}"')
        elif kind == "house":
            _rcon_cmd(f'otai_build_house {x+120} {y} {z} {params.get("size",5)} "{model}"')
        elif kind == "stack":
            _rcon_cmd(f'otai_build_stack {x+60} {y} {z} {params.get("count",3)} "{model}"')
        else:
            return f"[строительство] Неизвестный тип: {kind}"
        _remember_build(kind, params, (x, y, z))
        return f"[строительство] Загружено: {kind}."

    if sub == "list":
        d = _build_models_dir()
        files = sorted(f for f in os.listdir(d) if f.endswith(".json"))
        if not files: return "[строительство] Сохранений нет."
        return "[строительство] Сохранения:\n" + "\n".join(
            f"  • {f[:-5]}" for f in files[:30])

    return "[строительство] Неизвестная подкоманда. `!game build`"

# -------- bot-подкоманды --------

def _cmd_bot(sub, arg):
    sub = sub.lower()
    if sub in ("", "help"):
        return ("[бот] spawn|remove|respawn | goto|teleport|follow|stop|aim|fire|ceasefire|"
                "say|give|status | navmode|navviz|hybrid|strafe | "
                "patrol add|addhere|clear|start [once]|stop|status | patrol_topos <N> | "
                "combat start <ник> [duel]|stop|status | "
                "cover spawn [N]|clear|count|rebuild | combatset <k> <v>")

    if sub == "spawn":
        ok, msg = _bot_spawn(); return f"[бот] {msg}"
    if sub == "remove":  _bot_remove(); return "[бот] Удалён."
    if sub == "respawn": _rcon_cmd('otai_bot_respawn'); return "[бот] Respawn."
    if sub in ("goto","teleport"):
        try:
            x, y, z = arg.split()
            cmd = 'otai_bot_goto' if sub == 'goto' else 'otai_bot_teleport'
            _rcon_cmd(f'{cmd} {float(x)} {float(y)} {float(z)}')
            return f"[бот] {sub} → ({x}, {y}, {z})"
        except ValueError: return f"[бот] Формат: {sub} <x> <y> <z>"
    if sub == "follow":
        if not arg.strip(): _bot_follow(None); return "[бот] Follow отменён."
        _bot_follow(arg.strip()); return f"[бот] Следую за {arg.strip()}."
    if sub == "gotoplayer":
        if not arg.strip(): return "[бот] Ник?"
        _bot_goto_player(arg.strip()); return f"[бот] Иду к {arg.strip()}."
    if sub == "stop":    _bot_stop(); return "[бот] Остановлен."
    if sub == "aim":     _bot_aim(arg.strip() or None); return f"[бот] Целюсь: {arg.strip() or '—'}"
    if sub == "fire":
        parts = arg.split()
        if not parts: return "[бот] `fire <ник> [сек]`"
        nick = parts[0]; sec = float(parts[1]) if len(parts) > 1 else 5.0
        _bot_fire_at(nick, sec); return f"[бот] Огонь по {nick} ({sec}s)."
    if sub == "ceasefire": _bot_ceasefire(); return "[бот] Прекратить огонь."
    if sub == "say":
        if not arg.strip(): return "[бот] Текст?"
        _rcon_cmd(f'otai_bot_say "{arg.replace(chr(34), chr(39))}"')
        return f"[бот] Сказал: {arg}"
    if sub == "give":
        if not arg.strip(): return "[бот] Оружие?"
        _rcon_cmd(f'otai_bot_give "{arg.strip()}"')
        return f"[бот] Выдано: {arg.strip()}"
    if sub == "status":
        b = _bot_get()
        if not b.get("spawned"): return "[бот] Не заспавнен."
        pos = b.get("pos") or [0,0,0]
        return (f"[бот] «{b.get('name')}» HP={b.get('hp')} "
                f"armor={b.get('armor')} wpn={b.get('weapon') or '—'} "
                f"pos=({pos[0]:.0f},{pos[1]:.0f},{pos[2]:.0f}) "
                f"nav={b.get('nav_mode','?')}")
    if sub == "navmode":
        mode = arg.strip().lower()
        if mode not in ("ai", "manual", "status", ""): return "[бот] `navmode ai|manual|status`"
        if mode in ("", "status"):
            _rcon_cmd("otai_bot_navmode status"); time.sleep(0.15)
            return f"[бот] Nav-режим: {_bot_get().get('nav_mode', '?')}"
        _rcon_cmd(f'otai_bot_navmode {mode}')
        return f"[бот] Запрошен режим: {mode}"
    if sub == "navviz":
        mode = arg.strip().lower() or "toggle"
        if mode not in ("on", "off", "toggle"): return "[бот] `navviz on|off|toggle`"
        _rcon_cmd(f"otai_nav_viz {mode}")
        return f"[бот] Nav-viz: {mode}"
    if sub == "hybrid":
        mode = arg.strip().lower()
        if mode not in ("on", "off", "status"): return "[бот] `hybrid on|off|status`"
        _rcon_cmd(f"otai_bot_hybrid {mode}")
        return f"[бот] Hybrid: {mode}"
    if sub == "strafe":
        mode = arg.strip().lower()
        if mode not in ("on", "off"): return "[бот] `strafe on|off`"
        _rcon_cmd(f"otai_bot_strafe {mode}")
        return f"[бот] Strafe: {mode}"
    if sub == "patrol":
        parts = arg.split()
        if not parts: return _cmd_patrol_status()
        action = parts[0].lower(); tail = parts[1:]
        if action in ("add", "добавить"):
            if len(tail) < 3: return "[патруль] `patrol add <x> <y> <z>`"
            try: x, y, z = map(float, tail[:3])
            except ValueError: return "[патруль] Числа?"
            pts = _state.setdefault("patrol", {}).setdefault("points", [])
            if len(pts) >= int(_cfg["patrol"].get("max_points", 30)):
                return "[патруль] Слишком много точек."
            pts.append([x, y, z]); _save_json(STATE_PATH, _state)
            _sync_patrol_to_server()
            return f"[патруль] Точка добавлена. Всего: {len(pts)}"
        if action in ("addhere", "тут", "здесь"):
            bp = _bot_get().get("pos")
            if not bp: return "[патруль] Позиция бота неизвестна."
            pts = _state.setdefault("patrol", {}).setdefault("points", [])
            pts.append(bp[:]); _save_json(STATE_PATH, _state)
            _sync_patrol_to_server()
            return f"[патруль] Точка добавлена. Всего: {len(pts)}"
        if action in ("clear", "очистить"):
            _state.setdefault("patrol", {})["points"] = []
            _save_json(STATE_PATH, _state)
            _rcon_cmd("otai_bot_patrol_clear")
            return "[патруль] Точки очищены."
        if action in ("start", "старт"):
            if not _state.get("patrol", {}).get("points"): return "[патруль] Нет точек."
            _sync_patrol_to_server()
            mode = "once" if "once" in tail else "loop"
            _rcon_cmd(f"otai_bot_patrol_start {mode}")
            return f"[патруль] Старт ({mode})."
        if action in ("stop", "стоп"):
            _rcon_cmd("otai_bot_patrol_stop"); return "[патруль] Стоп."
        if action in ("status", "статус", ""):
            return _cmd_patrol_status()
        return "[патруль] add|addhere|clear|start [once]|stop|status"
    if sub == "patrol_topos":
        try:
            idx = int(arg.strip())
            pts = _state.get("patrol", {}).get("points", [])
            if 1 <= idx <= len(pts):
                x, y, z = pts[idx-1]
                _rcon_cmd(f'otai_bot_teleport {x} {y} {z}')
                return f"[патруль] Телепорт в точку #{idx}."
        except (ValueError, TypeError): pass
        return "[патруль] `patrol_topos <номер>`"
    if sub == "combat":
        parts = arg.split()
        if not parts: return "[combat] `combat start <ник> [duel] | stop | status`"
        action = parts[0].lower()
        if action == "start":
            if len(parts) < 2: return "[combat] `combat start <ник> [duel]`"
            mode = parts[2] if len(parts) > 2 else "combat"
            _rcon_cmd(f'otai_combat_start "{parts[1]}" {mode}')
            return f"[combat] Старт против {parts[1]} ({mode})"
        if action == "stop":
            _rcon_cmd("otai_combat_stop"); return "[combat] Стоп."
        if action == "status":
            _rcon_cmd("otai_combat_status"); time.sleep(0.15)
            c = _state.get("combat", {})
            return (f"[combat] {'активен' if c.get('active') else 'стоит'}"
                    f" | цель: {c.get('target') or '—'}"
                    f" | укрытий: {c.get('covers', 0)}")
        return "[combat] start|stop|status"
    if sub == "cover":
        parts = arg.split()
        if not parts: return "[cover] `cover spawn [N] | clear | count | rebuild`"
        action = parts[0].lower()
        if action == "spawn":
            n = parts[1] if len(parts) > 1 else "2"
            _rcon_cmd(f"otai_cover_spawn {n} 120")
            return f"[cover] Спавн {n}."
        if action == "clear":
            _rcon_cmd("otai_cover_clear"); return "[cover] Очищено."
        if action == "count":
            _rcon_cmd("otai_cover_count"); time.sleep(0.15)
            return f"[cover] Укрытий: {_state.get('combat', {}).get('covers', 0)}"
        if action == "rebuild":
            _rcon_cmd("otai_cover_rebuild"); return "[cover] Перестроение."
        return "[cover] spawn|clear|count|rebuild"
    if sub == "combatset":
        parts = arg.split()
        if len(parts) != 2: return "[combat] `combatset <ключ> <значение>`"
        _rcon_cmd(f"otai_combat_setting {parts[0]} {parts[1]}")
        return f"[combat] {parts[0]} = {parts[1]}"
    return f"[бот] Неизвестная «{sub}». `!game bot help`."

def _handle(text):
    prefix = _cfg.get("commands_prefix", "!game")
    rest   = text[len(prefix):].strip()
    parts  = rest.split(maxsplit=2)
    sub    = parts[0].lower() if parts else "help"
    arg    = parts[1] if len(parts) > 1 else ""
    arg2   = parts[2] if len(parts) > 2 else ""
    full   = (arg + (" " + arg2 if arg2 else "")).strip()

    table = {
        "help": lambda: HELP_TEXT, "?": lambda: HELP_TEXT,
        "join": _cmd_join, "leave": _cmd_leave, "status": _cmd_status,
        "say": lambda: _cmd_say(full),
        "cmd": lambda: _cmd_raw(full),
        "char": lambda: _cmd_char(full),
        "emote": lambda: (_say(f"* {_bot_name()} {full}"),
                          f"[персонаж] * {_bot_name()} {full}")[1] if full else "[персонаж] Что?",
        "act": lambda: (_say(f"* {_bot_name()} {full}"),
                        f"[персонаж] * {_bot_name()} {full}")[1] if full else "[персонаж] Что?",
        "look": lambda: (_say(_rp_wrap("generic")), f"[персонаж] {_rp_wrap('generic')}")[1],
        "players": _cmd_players,
        "mood": lambda: _cmd_mood(full),
        "memory": lambda: _cmd_memory(full),
        "forget": lambda: _cmd_forget(full),
        "idle": lambda: _cmd_idle(full),
        "rp": lambda: _cmd_rp(full),
        "duel": lambda: _cmd_duel(full),
        "duels": _cmd_duels,
        "bridge": lambda: _cmd_bridge(full),
        "history": _cmd_history,
        "bot": lambda: _cmd_bot(arg, arg2),
        "games": lambda: catalog_text(),
        "game": lambda: _cmd_game(full),
        "grudges": _cmd_grudges, "обижен": _cmd_grudges, "offended": _cmd_grudges,
        "forgive": lambda: _cmd_forgive(full), "простить": lambda: _cmd_forgive(full),
        "emotions": _cmd_emotions_config, "эмоции": _cmd_emotions_config,
        "points": lambda: _cmd_points(full), "очки": lambda: _cmd_points(full),
        "top-points": _cmd_points_top, "топ-очки": _cmd_points_top,
        "setpoints": lambda: _cmd_setpoints(full),
        "тир": lambda: _cmd_range(full, arg, arg2),
        "range": lambda: _cmd_range(full, arg, arg2),
        "top-range": _cmd_range_top, "топ-тир": _cmd_range_top,
        "тим": lambda: _cmd_team(full), "team": lambda: _cmd_team(full),
        "команды": _cmd_team_list,
        "friends": _cmd_friends, "друзья": _cmd_friends,
        "badday": lambda: _cmd_bad_day(full), "плохойдень": lambda: _cmd_bad_day(full),
        "diary": lambda: _cmd_diary(full), "дневник": lambda: _cmd_diary(full),
        "scars": _cmd_scars, "шрамы": _cmd_scars,
        "conflicts": _cmd_conflicts, "конфликты": _cmd_conflicts,
        "team_grudges": _cmd_team_grudges, "команда_обижена": _cmd_team_grudges,
        "build": lambda: _cmd_build(full), "строй": lambda: _cmd_build(full),
    }
    if sub in table: return table[sub]()
    return f"[персонаж] Неизвестная «{sub}». `{prefix} help`."

# -------- хуки плагина --------

def preprocess(user_message):
    _state["last_user_msg_ts"] = time.time()
    _save_json(STATE_PATH, _state)
    return user_message

def postprocess(bot_response):
    return bot_response

def generate(user_message, db_manager, model=None, vocab=None):
    global _model_ref, _vocab_ref, _device_ref
    if model is not None:
        _model_ref = model; _vocab_ref = vocab
        try:
            import torch
            _device_ref = next(model.parameters()).device
        except Exception: _device_ref = None
    prefix = _cfg.get("commands_prefix", "!game")
    if user_message.strip().lower().startswith(prefix):
        try: return _handle(user_message.strip())
        except Exception as e:
            _log(f"handle error: {e!r}")
            return f"[персонаж] Внутренняя ошибка: {e}"
    return None