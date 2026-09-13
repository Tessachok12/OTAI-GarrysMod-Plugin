# plugins/game_character/emotions.py
# -*- coding: utf-8 -*-
import time, random

LEVELS = {
    1: {"name":"задет","ttl":60,"refuse_games":False,"refuse_duel":False},
    2: {"name":"обижен","ttl":180,"refuse_games":True,"refuse_duel":False},
    3: {"name":"разозлён","ttl":600,"refuse_games":True,"refuse_duel":True},
    4: {"name":"в ярости","ttl":1800,"refuse_games":True,"refuse_duel":True},
}
TRIGGERS = {"insult_chat":2,"mock_chat":1,"unfair_kill":3,"friendly_fire":2,
            "third_party":3,"spam_games":1,"ignore":1,"griefing_cover":2}
_INSULT = ("дурак","дура","идиот","тупой","тупая","лох","лохушка","придурок","клоун",
           "ничтожество","мразь","ублюдок","дебил","дебила","нуб","noob","нубло",
           "крыса","тварь","fuck you","idiot","moron","loser")
_MOCK = ("ха-ха","ахах","ахахах","хахаха","лол","lol","кекаю","ржу","ahaha")
_APOLOGY = ("извини","извиняюсь","прости","прошу прощения","сорри","sorry","сори",
            "мирись","мир","помиримся","давай мир","мировая","забудь","забудем")
_LEVEL_LINES = {
    1: ["* {n} холодно кивает.","Хм. Ладно.","* {n} делает вид, что не замечает."],
    2: ["* {n} демонстративно отворачивается.","Не хочу с тобой разговаривать.","* {n} скрещивает руки."],
    3: ["* {n} смотрит исподлобья.","Ещё раз — и будет плохо.","* {n} медленно сжимает кулаки."],
    4: ["* {n} в ярости: лучше не подходи.","* {n} достаёт оружие.","* {n} смотрит на тебя как на цель."],
}
_FORGIVE = {
    1: ["Ладно, забыли.","Проехали."],
    2: ["Хорошо, мир.","Ладно, не держу зла."],
    3: ["* {n} долго смотрит, потом кивает.","Ок, но запомню."],
    4: ["* {n} медленно опускает оружие. В этот раз прощаю.","* {n} вздыхает. Не испытывай моё терпение больше."],
}
_REFUSE = {"game": ["Не буду с тобой играть.","Ищи кого-нибудь другого."],
           "duel": ["С тобой — нет.","Дуэли не будет."],
           "talk": ["Не о чем говорить.","* {n} молчит."]}
SUBTLE_CHANCE = 0.6

def detect_insult(t): t=t.lower(); return any(w in t for w in _INSULT)
def detect_mock(t):   t=t.lower(); return any(w in t for w in _MOCK)
def detect_apology(t):t=t.lower().strip(); return any(w in t for w in _APOLOGY)
def level_name(l):    return LEVELS.get(l, {}).get("name","?")
def level_props(l):   return LEVELS.get(l, LEVELS[1])
def combine_levels(a,b): return min(4, max(a,b) + (1 if a>=2 and b>=2 else 0))
def pick_line(l,n):   return random.choice(_LEVEL_LINES.get(l,_LEVEL_LINES[1])).format(n=n)
def pick_forgive(l,n):return random.choice(_FORGIVE.get(l,_FORGIVE[1])).format(n=n)
def pick_refuse(k):   return random.choice(_REFUSE.get(k,_REFUSE["talk"]))
def maybe_subtle(l):  return l == 1 and random.random() < SUBTLE_CHANCE

_CONTEXT = {
    "killed_me":       "* {n} помнит, как {who} уложил(а) его(её) из «{weapon}».",
    "killed_me_duel":  "* {n} помнит «{weapon}» в честной дуэли.",
    "third_party":     "* {n} помнит, как {who} вмешался в дуэль.",
    "insulted":        "* {n} помнит слова: «{text}».",
    "friendly_fire":   "* {n} помнит выстрел в спину от {who}.",
    "broke_cover":     "* {n} помнит, как {who} сломал(а) укрытие.",
}
def make_context(kind, **kw):
    c = {"kind": kind}; c.update(kw); c["ts"] = time.time(); return c
def render_context(c, n):
    if not c: return None
    tpl = _CONTEXT.get(c.get("kind"))
    if not tpl: return None
    try: return tpl.format(n=n, **c)
    except KeyError: return None

FRIEND_THRESHOLD = 15
BESTIE_THRESHOLD = 40
FRIENDSHIP_GAINS  = {"apology_accepted":5,"won_duel_together":3,"coop_win":4,
                     "kind_words":1,"long_chat":1,"helped_in_fight":6}
FRIENDSHIP_LOSSES = {"insulted":-10,"friendly_fire":-5,"broke_cover":-3,
                     "unfair_kill":-15,"spam_games":-1}

def friendship_tier(s):
    if s >= BESTIE_THRESHOLD: return "bestie"
    if s >= FRIEND_THRESHOLD: return "friend"
    return "neutral"

def pick_friend_greeting(tier, n):
    if tier == "bestie":
        return random.choice([f"* {n} улыбается во все зубы.","О, ты! Рад(а) видеть!","Наконец-то. Скучал(а) по тебе."])
    if tier == "friend":
        return random.choice(["Привет-привет!",f"* {n} кивает как старому знакомому.","Рад(а), что ты снова здесь."])
    return None

_BAD_DAY = {"start":["* {n} сегодня не в духе. Лучше не злить.","* {n} хмуро осматривает окружение."],
            "end":["* {n} вздыхает. День был так себе.","* Кажется, {n} чуть-чуть отпустило."]}
def pick_bad_day(kind, n): return random.choice(_BAD_DAY.get(kind,[""])).format(n=n)

def forgive_chance(lvl, mood, ap, inter, friendship=0, bad_day=False):
    base = {1:0.95, 2:0.7, 3:0.4, 4:0.15}[lvl]
    base += 0.15 * ap + min(0.1, inter * 0.005) + min(0.15, friendship * 0.005)
    if mood == "friendly":  base += 0.1
    if mood == "annoyed":   base -= 0.1
    if mood == "inspired":  base += 0.05
    if bad_day:             base -= 0.15
    return max(0.05, min(0.98, base))