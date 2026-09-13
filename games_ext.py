# plugins/game_character/games_ext.py
# -*- coding: utf-8 -*-
import time
from games import Game


class ShootingRange(Game):
    name = "тир"
    aliases = ("тир","range","стрельбище","кооп-тир")
    kind = "interactive"
    description = "Тир. !тир [кол-во] [сек] [moving] [coop]"
    timeout = 0

    def start(self, ctx, challenger, args):
        if not ctx.bot_alive(): return "[тир] Бот не в игре — не могу расставить мишени."
        count = 5; duration = 30; moving = False; coop = False
        for a in args:
            low = a.lower()
            if low in ("moving","движ","движущиеся"): moving = True
            elif low in ("coop","кооп","вместе"):     coop = True
            else:
                try:
                    n = int(a)
                    if count == 5 and not moving and not coop and n > 1: count = n
                    elif duration == 30 and n > 5: duration = n
                except (ValueError, TypeError): pass
        count = max(1, min(count, 20)); duration = max(10, min(duration, 180))
        bp = ctx.bot_pos() or [0,0,0]
        cmd = "otai_targets_spawn_moving" if moving else "otai_targets_spawn"
        ctx.rcon(f'{cmd} {count} {bp[0]+400} {bp[1]} {bp[2]}')
        ctx.set_game("range", "active", challenger, {
            "count": count, "hits": {}, "deadline": time.time() + duration,
            "start": time.time(), "moving": moving, "coop": coop})
        if coop:
            ctx.rcon(f'otai_bot_give "{ctx.cfg("bot", "default_weapon", "weapon_357")}"')
            ctx.say(f"{challenger}, кооп! {count} мишеней, {duration}с. Огонь!")
            ctx.start_bot_target_loop()
        else:
            ctx.say(f"{challenger}, мишени: {count} шт, у тебя {duration} секунд. Огонь!")
        return f"[тир] Старт: {count}, {duration}с, moving={moving}, coop={coop}"

    def on_target_hit(self, ctx, nick, remaining):
        g = ctx.get_game()
        if not g or g.get("name") != "range" or g.get("state") != "active": return False
        if not g.get("data", {}).get("coop") and nick != g.get("challenger"): return False
        data = g.setdefault("data", {})
        hits = data.setdefault("hits", {})
        hits[nick] = hits.get(nick, 0) + 1
        ctx.set_game_data("hits", hits)
        if remaining == 0: self._finish(ctx)
        return True

    def on_tick(self, ctx):
        g = ctx.get_game()
        if not g or g.get("name") != "range" or g.get("state") != "active": return
        if time.time() > g.get("data", {}).get("deadline", 0): self._finish(ctx)

    def _finish(self, ctx):
        g = ctx.get_game() or {}
        data = g.get("data", {})
        hits = data.get("hits", {}); total = data.get("count", 0)
        elapsed = time.time() - data.get("start", time.time())
        per_hit = int(ctx.cfg("economy", "range_per_hit", 3))
        bonus   = int(ctx.cfg("economy", "range_all_hit_bonus", 20))
        ctx.rcon("otai_targets_clear")
        for nick, n in hits.items():
            pts = n * per_hit
            if n >= total: pts += bonus
            ctx.points_add(nick, pts)
            ctx.range_score(nick, n, elapsed, total)
            ctx.diary_add(nick, "range_win", nick=nick, hits=n, total=total)
            ctx.say(f"{nick} — {n}/{total} за {elapsed:.1f}с. +{pts} очков.")
        if not hits:
            ctx.say("Ни одного попадания."); ctx.set_mood("annoyed")
        else:
            ctx.set_mood("inspired")
        ctx.stop_bot_target_loop(); ctx.clear_game()


class TeamBattle(Game):
    name = "тим"
    aliases = ("тим","team","команда","командный")
    kind = "instant"
    description = "Командный бой. !тим red|blue / !тим start [сек]"

    def start(self, ctx, challenger, args):
        if not args: return "[тим] red|blue|start [сек]|score|stop|leave"
        sub = args[0].lower()
        if sub in ("red","красные","красн"):
            ctx.teams_join(challenger, "red"); ctx.say(f"{challenger} в красной команде.")
            return f"[тим] {challenger} → red"
        if sub in ("blue","синие","син"):
            ctx.teams_join(challenger, "blue"); ctx.say(f"{challenger} в синей команде.")
            return f"[тим] {challenger} → blue"
        if sub in ("start","старт","начать"):
            duration = 120
            if len(args) > 1:
                try: duration = max(20, min(int(args[1]), 600))
                except (ValueError, TypeError): pass
            return self._start_match(ctx, duration)
        if sub in ("score","счёт","счет"): return self._score_text(ctx)
        if sub in ("stop","стоп"):
            ctx.teams_stop(); ctx.say("Матч остановлен."); return "[тим] Остановлено."
        if sub in ("leave","выход","выйти"):
            ctx.teams_leave(challenger); ctx.say(f"{challenger} вышел из команд.")
            return f"[тим] {challenger} вышел."
        return "[тим] red|blue|start|score|stop|leave"

    def _start_match(self, ctx, duration):
        red, blue = ctx.teams_lists()
        if len(red) + len(blue) < 2: return "[тим] Нужно минимум 2 игрока."
        if not ctx.bot_alive(): return "[тим] Бот не в игре."
        bot_side = "red" if len(red) <= len(blue) else "blue"
        ctx.rcon(f'otai_setteam "{ctx.bot_name()}" {2 if bot_side == "red" else 3}')
        ctx.set_game("team", "active", ctx.bot_name(), {
            "deadline": time.time() + duration,
            "red": 0, "blue": 0, "bot_side": bot_side})
        ctx.say(f"Матч начался! Красные {len(red)} против синих {len(blue)}. "
                f"{duration} секунд. Бот — за "
                f"{'красных' if bot_side=='red' else 'синих'}.")
        return f"[тим] Матч запущен на {duration}с."

    def _score_text(self, ctx):
        g = ctx.get_game()
        if not g or g.get("name") != "team": return "[тим] Матч не идёт."
        d = g.get("data", {})
        return f"[тим] Red {d.get('red',0)} : {d.get('blue',0)} Blue"

    def on_team_kill(self, ctx, victim_nick, victim_team, attacker_team):
        g = ctx.get_game()
        if not g or g.get("name") != "team" or g.get("state") != "active": return False
        d = g.setdefault("data", {})
        if victim_team == "red":   d["blue"] = d.get("blue", 0) + 1
        elif victim_team == "blue": d["red"]  = d.get("red", 0) + 1
        ctx.set_game_data("red", d["red"]); ctx.set_game_data("blue", d["blue"])
        return True

    def on_tick(self, ctx):
        g = ctx.get_game()
        if not g or g.get("name") != "team" or g.get("state") != "active": return
        d = g.get("data", {}); deadline = d.get("deadline", 0)
        if time.time() > deadline:
            red, blue = d.get("red", 0), d.get("blue", 0)
            win_bonus = int(ctx.cfg("economy", "team_win_bonus", 30))
            lose_pen  = int(ctx.cfg("economy", "team_loss_penalty", -10))
            if red > blue:   win_team, wname = "red", "Красные"
            elif blue > red: win_team, wname = "blue", "Синие"
            else:            win_team, wname = None, None
            if win_team:
                ctx.say(f"Матч окончен. {wname} побеждают {max(red,blue)}:{min(red,blue)}.")
                wlist, llist = ctx.teams_lists()
                winners = wlist if win_team == "red" else llist
                losers  = llist if win_team == "red" else wlist
                for n in winners: ctx.points_add(n, win_bonus)
                for n in losers:  ctx.points_add(n, lose_pen)
                ctx.say(f"Победителям +{win_bonus}, проигравшим {lose_pen}.")
            else:
                ctx.say(f"Ничья {red}:{blue}. Все получают по 5 очков.")
                wlist, llist = ctx.teams_lists()
                for n in wlist + llist: ctx.points_add(n, 5)
            ctx.set_mood("inspired" if win_team else "neutral")
            ctx.clear_game(); return
        elapsed = 120 - (deadline - time.time())
        if int(elapsed) % 30 == 0 and elapsed > 0:
            last = d.get("last_announce", 0)
            if time.time() - last > 25:
                ctx.say(f"Счёт: Red {d.get('red',0)} : {d.get('blue',0)} Blue")
                ctx.set_game_data("last_announce", time.time())


EXT_GAMES = [ShootingRange(), TeamBattle()]