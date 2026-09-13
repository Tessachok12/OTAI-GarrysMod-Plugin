# OTAI Garrys Mod Plugin

# Для работы требуется
[OTAI Garrys Addon - NPC Bot]([[https://github.com/Tessachok12/Open-Tess-AI])
[Open Tess AI (OTAI)](https://github.com/Tessachok12/Open-Tess-AI)


Плагин для Open Tess AI: seq2seq-бот становится игровым персонажем
на сервере Garry's Mod. Управляет ботом по RCON, принимает события по UDP,
ведёт эмоции, память, дружбу и играет в мини-игры.

Работает в связке с аддоном **OTAI Garrys Addon — NPC Bot**.

## Возможности

- **Бот-игрок** через `player.CreateNextBot` (управление из Python)
- **Навигация**: NavMesh, manual, гибрид, патруль
- **Бой**: дистанция, смена оружия, стрейф, укрытия, реакция на гранаты
- **Эмоции**: 4 уровня обид, скрытые обиды, шрамы, извинения
- **Социальное**: дружба, романтика, дневник, конфликты, медиация
- **Мини-игры**: армрестлинг, КНБ со ставкой, монетка, загадки, салки,
  прятки, тир (moving/coop), командный бой, дуэли
- **Экономика**: очки, награды, штрафы, лидерборд
- **Строительство**: wall, tower, platform, box, house, stack, place
- **Модель**: «горячий» поток генерирует RP-реплики на события

## Структура

```
plugins/game_character/
├── plugin.py       ядро: RCON, UDP, команды, эмоции
├── games.py        мини-игры
├── games_ext.py    тир, командный бой
├── emotions.py     эмоции, обиды, дружба
├── social.py       шрамы, дневник, конфликты, романтика
└── README.md
```

## Установка

1. Скопируй папку `game_character/` в `plugins/`.
2. Установи аддон **OTAI Garrys Addon — NPC Bot** на GMod-сервер.
3. В `server.cfg`:
   ```
   rcon_password "changeme"
   otai_host "127.0.0.1"
   otai_port "27099"
   ```
4. Запусти `python core.py`, в консоли бота: `!game join`.

## Конфиг

`plugins/game_character/config.json` — создаётся автоматически.
Секции: `rcon`, `character`, `bridge`, `bot`, `duel`, `games`, `range`,
`teams`, `economy`, `combat`, `emotions`, `friendship`, `protect`,
`bad_day`, `scars`, `diary`, `conflicts`, `romance`, `builder`.
Отключаются флагом `enabled: false`.

## Команды бота

```
!game join | leave | status
!game say <текст> | cmd <rcon> | char <поле> <знач.>
!game bot spawn | remove | goto | follow | stop | aim | fire
!game bot navmode ai|manual | hybrid on|off | strafe on|off
!game bot patrol add|addhere|clear|start|stop|status
!game bot combat start|stop|status | cover spawn|clear|rebuild
!game games | game <название>
!game points | top-points | setpoints
!game тир [N] [сек] [moving] [coop] | тим red|blue|start|score
!game обижен | forgive <ник> | friends | badday | diary | scars
!game build wall|tower|platform|box|house|stack|place|clear|undo
```

## Команды в чате

```
!рп-режим on|off       RP-режим
!дуэль <ник>           дуэль
!кнб камень 20         КНБ со ставкой
!тир [N] [moving] [coop]
!тим red|blue|start    командный бой
!ко мне / !стой        управление ботом
!укрытие / !бой <ник>  тактика
!топ / !игры           списки
извини / прости / мир  примирение
```

## Хранилище

- `config.json` — настройки
- `state.json` — память (обиды, дружба, дневник, конфликты)
- `game_character.log` — лог
- `builds/*.json` — сохранённые постройки

## Требования

- Python 3.10+, PyTorch
- Garry's Mod сервер с RCON
- Аддон **OTAI Garrys Addon — NPC Bot**

## Лицензия

MIT
