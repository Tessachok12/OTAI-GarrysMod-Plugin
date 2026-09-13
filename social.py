# plugins/game_character/social.py
# -*- coding: utf-8 -*-
import time, random

SCAR_TTL            = 3 * 24 * 3600
SCAR_TTL_MULTIPLIER = 2.0

def create_scar(nick, level, reason):
    return {"level": level, "reason": reason, "ts": time.time(),
            "until": time.time() + SCAR_TTL}
def scar_active(s, now=None): return bool(s) and s.get("until",0) > (now or time.time())
def scar_decayed_level(s, now=None):
    if not scar_active(s, now): return 0
    age = (now or time.time()) - s.get("ts",0)
    ratio = max(0.0, 1.0 - age / SCAR_TTL)
    return max(0, int(round(s.get("level",0) * ratio)))

DIARY_MAX_ENTRIES = 60
_DIARY = {
    "first_meet":   "Познакомились {when}.",
    "long_absence": "Не видел(а) {nick} {days} дн.",
    "won_duel":     "Дуэль против {nick}: победа.",
    "lost_duel":    "Дуэль против {nick}: поражение.",
    "played":       "Играли с {nick} в {game}.",
    "insult":       "Обидел(а) меня ({reason}).",
    "apology":      "Извинился(ась) — принял(а).",
    "range_win":    "Тир: {nick} выбил(а) {hits}/{total}.",
    "team_together":"В одной команде с {nick} ({side}).",
    "help":         "Помог(ла) мне в бою.",
}
def diary_add(diary, kind, **fields):
    entry = {"ts": time.time(), "kind": kind}; entry.update(fields)
    diary.append(entry)
    if len(diary) > DIARY_MAX_ENTRIES: del diary[:-DIARY_MAX_ENTRIES]
    return entry
def diary_render(e, n):
    tpl = _DIARY.get(e.get("kind"))
    if not tpl: return None
    try:    return tpl.format(**e)
    except KeyError: return None
def diary_summary(entries, n, max_lines=3):
    if not entries: return None
    tail = entries[-6:]
    picked = random.sample(tail, min(max_lines, len(tail)))
    lines = [diary_render(e,n) for e in picked]
    lines = [l for l in lines if l]
    return "Помню: " + " ".join(lines) if lines else None
def diary_days_since_last(entries):
    if not entries: return None
    return (time.time() - max(e.get("ts",0) for e in entries)) / 86400.0

ROMANCE_THRESHOLD = 80
ROMANCE_DECAY_DAYS = 7

def is_romantic(score, last_seen=None):
    if score < ROMANCE_THRESHOLD: return False
    if last_seen and (time.time()-last_seen) > ROMANCE_DECAY_DAYS*86400: return False
    return True

_ROMANTIC = {
    "greet":   ["* {n} замечает тебя и улыбается.","Ты как раз вовремя.","* {n} подходит ближе, чем обычно."],
    "farewell":["* {n} долго смотрит вслед.","Возвращайся скорее."],
    "protect": ["* {n} бросается на помощь без раздумий.","* {n} рвётся в бой — никто не тронет тебя."],
    "forgive": ["* {n} вздыхает. Я не могу долго злиться на тебя.","* {n} качает головой. Ладно, всё."],
}
def pick_romantic(kind, n):
    lines = _ROMANTIC.get(kind) or []
    return random.choice(lines).format(n=n) if lines else None

CONFLICT_THRESHOLD = -5
CONFLICT_DECAY_PER_HOUR = 1

def conflict_delta(conflicts, a, b, delta):
    if a == b: return
    for x, y in ((a,b),(b,a)):
        pair = conflicts.setdefault(x, {}).setdefault(y, {"score":0,"last":time.time()})
        pair["score"] += delta; pair["last"] = time.time()

def decay_conflicts(conflicts, now=None):
    now = now or time.time()
    for a, opps in list(conflicts.items()):
        for b, info in list(opps.items()):
            hours = (now - info.get("last", now)) / 3600
            if hours < 1: continue
            decay = int(hours * CONFLICT_DECAY_PER_HOUR)
            s = info["score"]
            s = max(0, s-decay) if s > 0 else min(0, s+decay)
            info["score"] = s
            if s == 0: del opps[b]
        if not opps: del conflicts[a]

def are_enemies(conflicts, a, b):
    info = conflicts.get(a, {}).get(b)
    return bool(info) and info.get("score",0) <= CONFLICT_THRESHOLD

TEAM_GRUDGE_TTL = 1200
TEAM_GRUDGE_LEVEL = 2

def apply_team_grudge(tg, key, reason):
    rec = tg.get(key, {"level":0,"until":0,"reason":""})
    rec["level"] = min(4, max(rec.get("level",0), TEAM_GRUDGE_LEVEL))
    rec["until"] = time.time() + TEAM_GRUDGE_TTL
    rec["reason"] = reason
    tg[key] = rec
    return rec

def team_grudge_active(tg, key):
    rec = tg.get(key); return bool(rec) and rec.get("until",0) > time.time()

def team_grudge_level(tg, key):
    return tg[key].get("level",0) if team_grudge_active(tg,key) else 0