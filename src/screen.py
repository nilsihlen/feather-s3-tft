"""Driftsbildet på TFT-skjermen, 240 x 135 piksler."""

import board
import displayio
import terminalio
from adafruit_display_text import label

WHITE = 0xFFFFFF
GREY = 0x707070
DIM = 0x8A8A8A
GREEN = 0x30D060
AMBER = 0xFFB000
RED = 0xFF3030
CYAN = 0x40C0FF
SUN = 0xFFD840

WIDTH = 240
GRAPH_Y = 49
GRAPH_H = 26
GRAPH_REFS = (20, 90)
TILE_W = 60
TILE_LABEL_Y = 77
TILE_VALUE_Y = 89
FOOTER_Y = 118

# Under gul og rød grense skifter SOC-tallet farge. Aggregatplanen lader fra 20 %.
SOC_RED = 20
SOC_AMBER = 40

BATT_STATES = {0: ("HVILE", DIM), 1: ("LADER", GREEN), 2: ("TAPPER", AMBER)}


def _text(group, x, y, scale, color, anchor=(0, 0), text=""):
    item = label.Label(terminalio.FONT, text=text, color=color, scale=scale)
    item.anchor_point = anchor
    item.anchored_position = (x, y)
    group.append(item)
    return item


def show_splash(text, detail=""):
    """Enkel tekst på svart bakgrunn, så konsollen aldri vises."""
    group = displayio.Group()
    _text(group, 120, 55 if detail else 67, 2, WHITE, anchor=(0.5, 0.5), text=text)
    if detail:
        _text(group, 120, 85, 1, AMBER, anchor=(0.5, 0.5), text=detail)
    board.DISPLAY.root_group = group


def _number(value):
    return "--" if value is None else "%d" % value


def _hours(hours):
    if hours < 1.5:
        return "%d min" % (hours * 60)
    return "%d t" % round(hours)


def _soc_color(soc):
    if soc < SOC_RED:
        return RED
    if soc < SOC_AMBER:
        return AMBER
    return WHITE


def _detail_text(data):
    if data["generator_on"] and data["ac_in_v"] is not None:
        return "AC inn %dV %.1fHz" % (data["ac_in_v"], data["ac_in_hz"] or 0)
    parts = []
    if data["operation"]:
        parts.append(data["operation"])
    elif data["tech_rh"] is not None:
        parts.append("Teknisk %d%%" % data["tech_rh"])
    if data["start_v"] is not None:
        parts.append("Start %.1fV" % data["start_v"])
    return "  ".join(parts)


class Screen:
    def __init__(self):
        self._root = displayio.Group()
        root = self._root
        self._history = []
        self._soc = _text(root, 2, -9, 6, GREY, text="--%")
        self._state = _text(root, 239, -3, 2, GREY, anchor=(1, 0))
        self._bank = _text(root, 239, 14, 2, GREY, anchor=(1, 0))
        self._eta = _text(root, 239, 35, 1, DIM, anchor=(1, 0))
        self._make_graph(root)
        _text(root, 2, GRAPH_Y + 13, 1, DIM, text="24 t")
        self._tiles = []
        for index, name in enumerate(("SOL W", "LAST W", "AGGR W", "KJELLER %")):
            x = index * TILE_W
            _text(root, x + 1, TILE_LABEL_Y, 1, DIM, text=name)
            self._tiles.append(_text(root, x + 1, TILE_VALUE_Y, 2, GREY, text="--"))
        self._detail = _text(root, 0, FOOTER_Y, 1, DIM)
        self._status = _text(root, 239, FOOTER_Y, 1, DIM, anchor=(1, 0))
        # Blå etikett når tallene kommer ferske fra Cerbo-en via VRM-skyen.
        self._cerbo = label.Label(
            terminalio.FONT, text="Cerbo online", color=WHITE,
            background_color=0x2255DD, padding_left=2, padding_right=2,
            padding_top=1, padding_bottom=1,
        )
        self._cerbo.anchor_point = (0, 0)
        self._cerbo.anchored_position = (0, FOOTER_Y - 1)
        self._cerbo.hidden = True
        root.append(self._cerbo)
        # Rulleteksten, gul som åpningsteksten i filmene. Ligger under alarmflaten.
        self._ticker = label.Label(terminalio.FONT, text="", color=SUN)
        self._ticker.hidden = True
        self._ticker.y = FOOTER_Y + 6
        root.append(self._ticker)
        self._make_alarm(root)

    def activate(self):
        board.DISPLAY.root_group = self._root

    def _make_graph(self, root):
        self._bitmap = displayio.Bitmap(WIDTH, GRAPH_H, 4)
        palette = displayio.Palette(4)
        palette[0] = 0x000000
        palette[1] = 0x204060  # flaten under kurven
        palette[2] = CYAN
        palette[3] = 0x505050  # 20 % og 90 %
        self._draw_refs()
        root.append(displayio.TileGrid(self._bitmap, pixel_shader=palette, y=GRAPH_Y))

    def _make_alarm(self, root):
        self._alarm = displayio.Group()
        self._alarm.hidden = True
        background = displayio.Bitmap(WIDTH, 135, 1)
        palette = displayio.Palette(1)
        palette[0] = 0xA00000
        self._alarm.append(displayio.TileGrid(background, pixel_shader=palette))
        _text(self._alarm, 120, 40, 3, WHITE, anchor=(0.5, 0.5), text="INVERTER")
        self._alarm_code = _text(self._alarm, 120, 90, 3, WHITE, anchor=(0.5, 0.5))
        root.append(self._alarm)

    def _y(self, soc):
        return (100 - soc) * (GRAPH_H - 1) // 100

    def _draw_refs(self):
        for soc in GRAPH_REFS:
            for x in range(0, WIDTH, 4):
                self._bitmap[x, self._y(soc)] = 3

    def add_soc(self, soc):
        """Ett punkt per kolonne. Historikken ligger bare i RAM."""
        self._history.append(soc)
        del self._history[:-WIDTH]
        self._bitmap.fill(0)
        left = WIDTH - len(self._history)
        for index, value in enumerate(self._history):
            top = self._y(value)
            for y in range(top + 1, GRAPH_H):
                self._bitmap[left + index, y] = 1
            self._bitmap[left + index, top] = 2
        self._draw_refs()

    def _set(self, item, text, color):
        if item.text != text:
            item.text = text
        if item.color != color:
            item.color = color

    def show_message(self, status, color=AMBER):
        self._set(self._status, status, color)

    def show_stale(self, status):
        """Et gammelt bilde skal ikke se ferskt ut."""
        for item in [self._soc, self._state, self._bank] + self._tiles:
            item.color = GREY
        self._alarm.hidden = True
        self.set_cerbo(False)
        self._set(self._eta, "", DIM)
        self._set(self._detail, "", DIM)
        self._set(self._status, status, AMBER)

    def show(self, data, age):
        soc = data["soc"]
        if soc is None:
            self._set(self._soc, "--%", GREY)
        else:
            self._set(self._soc, "%d%%" % soc, _soc_color(soc))

        state, color = BATT_STATES.get(data["batt_state"], ("?", DIM))
        self._set(self._state, state, color)

        if data["bank_w"] is None:
            self._set(self._bank, "--", GREY)
        else:
            self._set(self._bank, "~%+d W" % data["bank_w"], WHITE)

        if data["hours"] is None:
            self._set(self._eta, "", DIM)
        else:
            eta = "%d%% om ca %s" % (data["target_pct"], _hours(data["hours"]))
            self._set(self._eta, eta, DIM)

        self._set(self._tiles[0], _number(data["pv_w"]), SUN if data["pv_w"] else GREY)
        self._set(self._tiles[1], _number(data["load_w"]), WHITE)
        if data["generator_on"]:
            self._set(self._tiles[2], _number(data["ac_in_w"]), GREEN)
        else:
            self._set(self._tiles[2], "AV", GREY)
        self._show_cellar(data)
        self._set(self._detail, _detail_text(data), DIM)
        self._set(self._status, age, GREEN)

        error = data["vebus_error"]
        self._alarm.hidden = not error
        if error:
            self._alarm_code.text = "FEIL %d" % error

    def set_cerbo(self, online):
        """Viser den blå etiketten og flytter detaljlinja så de ikke overlapper."""
        self._cerbo.hidden = not online
        self._detail.anchored_position = (84 if online else 0, FOOTER_Y)

    def show_age(self, text):
        """Rapportalderen nederst til høyre, kalt hvert sekund mellom hentingene."""
        self._set(self._status, text, GREEN)

    def start_ticker(self, text):
        """Starter et sitat som glir over bunnlinja, fra høyre kant og ut til venstre."""
        self._ticker.text = text
        self._ticker.x = WIDTH
        self._ticker.hidden = False
        # Bunnlinjene gjemmes mens sitatet glir, så tekstene ikke ligger oppå hverandre.
        self._detail.hidden = True
        self._status.hidden = True

    def step_ticker(self):
        """Flytter sitatet litt mot venstre. Kalles fra ventesløyfa mellom hentingene."""
        if self._ticker.hidden:
            return
        self._ticker.x -= 2
        if self._ticker.x < -self._ticker.bounding_box[2]:
            self._ticker.hidden = True
            self._detail.hidden = False
            self._status.hidden = False

    def _show_cellar(self, data):
        rh = data["cellar_rh"]
        over_limit = rh is not None and data["rh_limit"] and rh > data["rh_limit"]
        self._set(self._tiles[3], _number(rh), RED if over_limit else WHITE)
