# plugins/game_character/games.py
# -*- coding: utf-8 -*-
import random, time

class Game:
    name = "?"; aliases = (); kind = "instant"; description = ""; timeout = 30
    def start(self, ctx, challenger, args): raise NotImplementedError
    def on_chat(self, ctx, nick, text):        return False
    def on_kill(self, ctx, victim, attacker, weapon): return False
    def on_tick(self, ctx):                    return None

_ACCEPT = ("да","принима","ок","yes","go","ага","конечно","погнали")
def _is_accept(text):
    low = text.lower().strip()
    return any(w in low.split() or low == w for w in _ACCEPT)


class ArmWrestle(Game):
    name = "армрестлинг"
    aliases = ("армрестлинг","armwrestle","руки","побороться")
    kind = "interactive"
    description = "Кто сильнее.      !армрестлинг [ник]"
    timeout = 25

    def start(self, ctx, challenger, args):
        if not ctx.bot_alive(): return "[игра] Бот не в игре."
        ctx.set_game("armwrestle", "challenging", challenger, {})
        ctx.bot_goto_player(challenger)
        ctx.say(f"{challenger}, заходим на руку? Ответь «да».")
        return f"[игра] Вызов на армрестлинг: {challenger}."

    def _begin(self, ctx, challenger):
        ctx.set_game_state("countdown")
        ctx.say(f"{challenger}, ставь локоть. Считаю до трёх.")
        for i in range(3, 0, -1): ctx.say(str(i)); time.sleep(1)
        rec = ctx.state.get("players_seen", {}).get(challenger, {})
        familiarity = min(rec.get("interactions", 0), 20) / 20.0
        bot_chance = 0.55 - 0.25 * familiarity
        if ctx.get_mood() == "inspired": bot_chance += 0.10
        if ctx.get_mood() == "annoyed":  bot_chance += 0.05
        bot_wins = random.random() < bot_chance
        if bot_wins:
            ctx.say(f"* {ctx.bot_name()} прижимает руку {challenger} к столу. Победа!")
            ctx.set_mood("inspired")
        else:
            ctx.say(f"* {challenger} побеждает! Сильная хватка.")
            ctx.set_mood("neutral")
        ctx.remember(challenger, "armwrestle"); ctx.clear_game()

    def on_chat(self, ctx, nick, text):
        g = ctx.get_game()
        if not g or g.get("state") != "challenging": return False
        if nick != g.get("challenger"): return False
        if not _is_accept(text): return False
        self._begin(ctx, nick); return True


_RPS_MAP = {"камень":"камень","rock":"камень","к":"камень",
            "ножницы":"ножницы","scissors":"ножницы","н":"ножницы",
            "бумага":"бумага","paper":"бумага","б":"бумага"}
_RPS_BEATS = {"камень":"ножницы","ножницы":"бумага","бумага":"камень"}


class RPS(Game):
    name = "камень-ножницы-бумага"
    aliases = ("кнб","rps","цугундер")
    kind = "instant"
    description = "Сыграть в КНБ.     !кнб камень|ножницы|бумага [ставка]"

    def start(self, ctx, challenger, args):
        if not args:
            return "[игра] Скажи ход: !кнб камень | ножницы | бумага [ставка]"
        pick = _RPS_MAP.get(args[0].lower())
        if not pick: return f"[игра] Не понимаю «{args[0]}»."
        max_bet = int(ctx.cfg("economy", "max_bet", 200))
        bet = 0
        if len(args) > 1:
            try: bet = max(0, min(int(args[1]), max_bet))
            except (ValueError, TypeError): bet = 0
        if bet > 0 and ctx.points_get(challenger) < bet:
            return f"[игра] У тебя {ctx.points_get(challenger)} очков, ставка {bet} не по карману."
        bot_pick = random.choice(list(_RPS_BEATS.keys()))
        if bot_pick == pick: outcome = "draw"; result = f"Ничья — оба «{pick}»."
        elif _RPS_BEATS[bot_pick] == pick:
            outcome = "bot_win"; result = f"{ctx.bot_name()}: «{bot_pick}». Побеждаю!"
            ctx.set_mood("inspired")
        else:
            outcome = "player_win"; result = f"{ctx.bot_name()}: «{bot_pick}». Твоя взяла."
            ctx.set_mood("annoyed")
        ctx.say(result)
        if bet == 0:
            pts = int(ctx.cfg("economy", "rps_default_bet", 10))
            if outcome == "bot_win":
                ctx.points_add(challenger, -pts); ctx.points_add(ctx.bot_name(), pts)
                ctx.say(f"Минус {pts} очков с тебя.")
            elif outcome == "player_win":
                ctx.points_add(challenger, pts); ctx.points_add(ctx.bot_name(), -pts)
                ctx.say(f"Держи {pts} очков.")
        else:
            if outcome == "bot_win":
                ctx.points_add(challenger, -bet); ctx.points_add(ctx.bot_name(), bet)
                ctx.say(f"* {bet} очков уходят мне.")
            elif outcome == "player_win":
                ctx.points_add(challenger, bet); ctx.points_add(ctx.bot_name(), -bet)
                ctx.say(f"* Забирай свои {bet} очков.")
        ctx.remember(challenger, "rps")
        return f"[игра] КНБ: {result}" + (f" (ставка {bet})" if bet else "")


class Coin(Game):
    name = "монетка"
    aliases = ("монетка","coin","орёл","орел")
    kind = "instant"
    description = "Подбросить монетку. !монетка [орёл|решка]"

    def start(self, ctx, challenger, args):
        result = random.choice(["орёл","решка"])
        ctx.say(f"* {ctx.bot_name()} подбрасывает монетку... {result}!")
        if args:
            guess = args[0].lower().strip()
            hit = ((guess in ("орёл","орел","heads") and result == "орёл") or
                   (guess in ("решка","tails") and result == "решка"))
            if hit: ctx.say(f"{challenger} угадал!"); ctx.set_mood("friendly")
            elif guess in ("орёл","орел","heads","решка","tails"):
                ctx.say(f"{challenger} не угадал.")
        ctx.remember(challenger, "coin")
        return f"[игра] Монетка: {result}"


_RIDDLES = [
    ("Висит груша — нельзя скушать. Что это?", ["лампа","лампочка"]),
    ("Зимой и летом одним цветом.",           ["ёлка","елка","сосна"]),
    ("Не портной, а всю жизнь с иголками.",   ["ёж","еж"]),
    ("Сто одёжек и все без застёжек.",        ["капуста"]),
    ("Что можно приготовить, но нельзя съесть?", ["уроки"]),
    ("Что идёт, не двигаясь с места?",        ["время"]),
    ("Что принадлежит тебе, но другие этим пользуются чаще?", ["имя"]),
    ("Кто говорит на всех языках?",           ["эхо"]),
]


class Riddle(Game):
    name = "загадка"
    aliases = ("загадка","riddle","загадки")
    kind = "interactive"
    description = "Отгадать загадку.  !загадка"
    timeout = 45

    def start(self, ctx, challenger, args):
        q, ans = random.choice(_RIDDLES)
        ctx.set_game("riddle", "awaiting", challenger,
                     {"question": q, "answers": [a.lower() for a in ans]})
        ctx.say(f"Загадка для {challenger}: {q}")
        return f"[игра] Загадка: {q}"

    def on_chat(self, ctx, nick, text):
        g = ctx.get_game()
        if not g or g.get("state") != "awaiting": return False
        if nick != g.get("challenger"): return False
        low = text.lower().strip()
        answers = g.get("data", {}).get("answers", [])
        if any(a in low for a in answers):
            ctx.say(f"Верно, {nick}! Уважение.")
            ctx.set_mood("friendly"); ctx.remember(nick, "riddle_won")
        else:
            ctx.say(f"Не то, {nick}. Ответ был: «{answers[0]}».")
            ctx.remember(nick, "riddle_lost")
        ctx.clear_game(); return True


class Tag(Game):
    name = "салки"
    aliases = ("салки","tag","догони","догонялки")
    kind = "interactive"
    description = "Догоню — и ты водишь. !салки"
    timeout = 60

    def start(self, ctx, challenger, args):
        ctx.set_game("tag", "challenging", challenger, {})
        ctx.say(f"{challenger}, играем в салки? Ответь «да», и побежали.")
        return f"[игра] Салки с {challenger}."

    def _begin(self, ctx, challenger):
        ctx.set_game_state("active")
        ctx.say(f"Раз, два, три — беги, {challenger}!")
        ctx.bot_follow(challenger)

    def on_chat(self, ctx, nick, text):
        g = ctx.get_game()
        if not g or g.get("state") != "challenging": return False
        if nick != g.get("challenger"): return False
        if not _is_accept(text): return False
        self._begin(ctx, nick); return True

    def on_tick(self, ctx):
        g = ctx.get_game()
        if not g or g.get("state") != "active": return
        ch = g.get("challenger")
        bp, pp = ctx.bot_pos(), ctx.player_pos(ch)
        if not bp or not pp: return
        d = ((bp[0]-pp[0])**2 + (bp[1]-pp[1])**2 + (bp[2]-pp[2])**2) ** 0.5
        if d < 100:
            ctx.say(f"* {ctx.bot_name()} хлопает {ch} по плечу. Поймал(а)!")
            ctx.bot_stop(); ctx.set_mood("inspired"); ctx.remember(ch, "tag_caught")
            ctx.clear_game()


class Hide(Game):
    name = "прятки"
    aliases = ("прятки","hide","искать")
    kind = "interactive"
    description = "Считаю до 10 — и ищу.  !прятки"
    timeout = 90

    def start(self, ctx, challenger, args):
        ctx.set_game("hide", "challenging", challenger, {})
        ctx.say(f"{challenger}, играем в прятки? Ответь «да».")
        return f"[игра] Прятки с {challenger}."

    def _begin(self, ctx, challenger):
        ctx.set_game_state("counting")
        ctx.say(f"* {ctx.bot_name()} отворачивается и закрывает глаза.")
        for i in range(1, 11): ctx.say(str(i)); time.sleep(1)
        pp = ctx.player_pos(challenger)
        ctx.set_game_data("target_pos", pp)
        ctx.say("Иду искать!")
        if pp: ctx.bot_goto(*pp)
        ctx.set_game_state("active")

    def on_chat(self, ctx, nick, text):
        g = ctx.get_game()
        if not g or g.get("state") != "challenging": return False
        if nick != g.get("challenger"): return False
        if not _is_accept(text): return False
        self._begin(ctx, nick); return True

    def on_tick(self, ctx):
        g = ctx.get_game()
        if not g or g.get("state") != "active": return
        ch = g.get("challenger")
        bp, pp, tp = ctx.bot_pos(), ctx.player_pos(ch), g.get("data", {}).get("target_pos")
        if not bp or not pp or not tp: return
        d_to_tp = ((bp[0]-tp[0])**2 + (bp[1]-tp[1])**2 + (bp[2]-tp[2])**2) ** 0.5
        if d_to_tp < 80:
            d_to_player = ((bp[0]-pp[0])**2 + (bp[1]-pp[1])**2 + (bp[2]-pp[2])**2) ** 0.5
            if d_to_player < 200:
                ctx.say(f"* {ctx.bot_name()} находит {ch}. Поймал(а)!")
                ctx.set_mood("inspired"); ctx.remember(ch, "hide_lost")
            else:
                ctx.say(f"Здесь пусто. {ch} хорошо спрятался(ась).")
                ctx.set_mood("annoyed"); ctx.remember(ch, "hide_won")
            ctx.bot_stop(); ctx.clear_game()


ALL_GAMES = [ArmWrestle(), RPS(), Coin(), Riddle(), Tag(), Hide()]


def find_game(name):
    low = name.lower().strip()
    for g in ALL_GAMES:
        if low == g.name or low in g.aliases: return g
    return None


def catalog_text():
    lines = ["[игры] Доступные мини-игры:"]
    for g in ALL_GAMES:
        lines.append(f"  • {g.name:22s} — {g.description}")
    lines.append("  • дуэль                 — !дуэль <ник>")
    lines.append("  • тир                   — !тир [N] [сек] [moving] [coop]")
    lines.append("  • командный бой         — !тим red|blue|start|score")
    return "\n".join(lines)