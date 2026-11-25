"""Driftsbildet på TFT-skjermen, 240 x 135 piksler."""

import board
import displayio
import terminalio
from adafruit_display_text import label

from version import VERSION

WHITE = 0xFFFFFF
GREY = 0x707070
DIM = 0x8A8A8A
GREEN = 0x30D060
AMBER = 0xFFB000
RED = 0xFF3030
CYAN = 0x40C0FF
SUN = 0xFFD840

WIDTH = 240
# Fonten er 6 x 12 per tegn, og tegnene står fra rad 2. Store tall i skala 5.
BIG = 5
CELLAR_LABEL_Y = -1
CELLAR_VALUE_Y = 0
GRAPH_Y = 49
GRAPH_H = 26
GRAPH_REFS = (20, 90)
TILE_W = 60
TILE_LABEL_Y = 77
TILE_VALUE_Y = 87
ETA_Y = 108
FOOTER_Y = 118
# Nederst til høyre: versjonen («v2.6») og så sekundene som teller ned. Feltet for
# sekundene er 6 tegn bredt («henter» er lengst), og versjonen står rett til venstre for det.
STATUS_CHARS = 6
STATUS_W = 70

# Under gul og rød grense skifter SOC-tallet farge. Aggregatplanen lader fra 20 %.
SOC_RED = 20
SOC_AMBER = 40
# Vinkjelleren: grønn under 80 %, gul opp til portalens grense, rød over.
RH_AMBER = 80

BATT_STATES = {0: ("HVILE W", DIM), 1: ("LADER W", GREEN), 2: ("TAPPER W", AMBER)}


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


def _rh_color(rh, limit):
    if limit and rh > limit:
        return RED
    if rh >= RH_AMBER:
        return AMBER
    return GREEN


def short_version(version):
    """«0.2.6» skrives «v2.6». Nullen foran er alltid 0 så lenge programmet er under 1.0."""
    return "v" + (version[2:] if version.startswith("0.") else version)


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


def _detail_text(data, room):
    """Detaljlinja, kortet ned til `room` tegn så den ikke går inn i tiden."""
    if data["generator_on"] and data["ac_in_v"] is not None:
        text = "AC inn %dV %.1fHz" % (data["ac_in_v"], data["ac_in_hz"] or 0)
        return text if len(text) <= room else text.replace("AC inn", "AC")
    parts = []
    if data["operation"]:
        parts.append(data["operation"])
    elif data["tech_rh"] is not None:
        parts.append("Teknisk %d%%" % data["tech_rh"])
    if data["start_v"] is not None:
        parts.append("Start %.1fV" % data["start_v"])
    text = ""
    for part in parts:
        longer = text + "  " + part if text else part
        if len(longer) <= room:
            text = longer
    return text


class Screen:
    def __init__(self):
        self._root = displayio.Group()
        root = self._root
        self._history = []
        # Temperaturen i vinkjelleren og rapporten den kom fra, se _show_cellar.
        self._temp = None
        self._temp_report = None
        # Øverst: fukt og temperatur i vinkjelleren, store.
        _text(root, 2, CELLAR_LABEL_Y, 1, DIM, text="VINKJELLER")
        self._rh = _text(root, 2, CELLAR_VALUE_Y, BIG, GREY, text="--%")
        self._rh_change = _text(root, 0, 29, 1, DIM)
        self._rh_window = _text(root, 0, 39, 1, DIM, text="24 t")
        self._temp_text = _text(root, 239, CELLAR_VALUE_Y, BIG, GREY, anchor=(1, 0), text="--")
        self._degree = self._make_degree(root)
        self._make_graph(root)
        _text(root, 2, GRAPH_Y + 13, 1, DIM, text="SOC 24 t")
        self._labels = []
        self._tiles = []
        for index, name in enumerate(("SOL W", "LAST W", "SOC %", "HVILE W")):
            x = index * TILE_W
            self._labels.append(_text(root, x + 1, TILE_LABEL_Y, 1, DIM, text=name))
            self._tiles.append(_text(root, x + 1, TILE_VALUE_Y, 2, GREY, text="--"))
        self._eta = _text(root, 239, ETA_Y, 1, DIM, anchor=(1, 0))
        self._detail = _text(root, 0, FOOTER_Y, 1, DIM)
        self._status = _text(root, 239, FOOTER_Y, 1, DIM, anchor=(1, 0))
        self._version = _text(
            root, 239 - 6 * STATUS_CHARS - 6, FOOTER_Y, 1, DIM, anchor=(1, 0),
            text=short_version(VERSION),
        )
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
        # Versjonen glir over bunnlinja ved hver oppstart, så den kan leses over telefon (M4).
        self.start_ticker("Programvare v" + VERSION)

    def _make_degree(self, root):
        """Gradetegnet tegnes selv: fonten har bare ASCII."""
        bitmap = displayio.Bitmap(3, 3, 2)
        for x, y in ((0, 0), (1, 0), (2, 0), (0, 1), (2, 1), (0, 2), (1, 2), (2, 2)):
            bitmap[x, y] = 1
        self._degree_palette = displayio.Palette(2)
        self._degree_palette.make_transparent(0)
        self._degree_palette[1] = GREY
        group = displayio.Group(scale=BIG)
        group.append(displayio.TileGrid(bitmap, pixel_shader=self._degree_palette))
        group.hidden = True
        root.append(group)
        return group

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

    def _put_status(self, text, color):
        """Skriver bunnlinja til høyre. Versjonen vises bare når det er plass til den."""
        self._set(self._status, text, color)
        self._sync_version()

    def _sync_version(self):
        self._version.hidden = not self._ticker.hidden or len(self._status.text) > STATUS_CHARS

    def show_message(self, status, color=AMBER):
        self._put_status(status, color)

    def show_stale(self, status):
        """Et gammelt bilde skal ikke se ferskt ut."""
        for item in [self._rh, self._temp_text] + self._tiles:
            item.color = GREY
        self._degree_palette[1] = GREY
        self._labels[3].color = DIM
        self._rh_change.hidden = True
        self._rh_window.hidden = True
        self._alarm.hidden = True
        self.set_cerbo(False)
        self._set(self._eta, "", DIM)
        self._set(self._detail, "", DIM)
        self._put_status(status, AMBER)

    def show(self, data, age):
        self._show_cellar(data)

        soc = data["soc"]
        if soc is None:
            self._set(self._tiles[2], "--", GREY)
        else:
            self._set(self._tiles[2], "%d" % soc, _soc_color(soc))

        state, color = BATT_STATES.get(data["batt_state"], ("BANK W", DIM))
        self._set(self._labels[3], state, color)
        if data["bank_w"] is None:
            self._set(self._tiles[3], "--", GREY)
        else:
            self._set(self._tiles[3], "%+d" % data["bank_w"], WHITE)

        if data["hours"] is None:
            self._set(self._eta, "", DIM)
        else:
            eta = "%d%% om %s" % (data["target_pct"], _hours(data["hours"]))
            self._set(self._eta, eta, DIM)

        self._set(self._tiles[0], _number(data["pv_w"]), SUN if data["pv_w"] else GREY)
        self._set(self._tiles[1], _number(data["load_w"]), WHITE)
        room = (WIDTH - STATUS_W - self._detail.anchored_position[0] - 6) // 6
        self._set(self._detail, _detail_text(data, room), DIM)
        self._put_status(age, GREEN)

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
        self._put_status(text, GREEN)

    def start_ticker(self, text):
        """Starter et sitat som glir over bunnlinja, fra høyre kant og ut til venstre."""
        self._ticker.text = text
        self._ticker.x = WIDTH
        self._ticker.hidden = False
        # Bunnlinjene gjemmes mens sitatet glir, så tekstene ikke ligger oppå hverandre.
        self._detail.hidden = True
        self._status.hidden = True
        self._version.hidden = True

    def step_ticker(self):
        """Flytter sitatet litt mot venstre. Kalles fra ventesløyfa mellom hentingene."""
        if self._ticker.hidden:
            return
        self._ticker.x -= 2
        if self._ticker.x < -self._ticker.bounding_box[2]:
            self._ticker.hidden = True
            self._detail.hidden = False
            self._status.hidden = False
            self._sync_version()

    def _show_cellar(self, data):
        rh = data["cellar_rh"]
        if rh is None:
            self._set(self._rh, "--%", GREY)
        else:
            self._set(self._rh, "%d%%" % round(rh), _rh_color(rh, data["rh_limit"]))
        # 100 % får ett hakk mindre skrift, så tallet ikke går inn i temperaturen.
        scale = BIG if len(self._rh.text) <= 3 else BIG - 1
        if self._rh.scale != scale:
            self._rh.scale = scale
            # Mindre skrift ligger høyere i linja, så tallet skyves ned under etiketten.
            self._rh.anchored_position = (2, CELLAR_VALUE_Y + (0 if scale == BIG else 5))
        right = 2 + len(self._rh.text) * 6 * scale + 4
        change = data.get("cellar_rh_change")
        # Ved 100 % er det ikke plass til endringen ved siden av tallet.
        show_change = change is not None and scale == BIG
        self._rh_change.hidden = not show_change
        self._rh_window.hidden = not show_change
        if show_change:
            self._set(self._rh_change, "%+d" % round(change), DIM)
            self._rh_change.anchored_position = (right, 29)
            self._rh_window.anchored_position = (right, 39)

        # Portalen sender temperaturen bare de første 20 min etter en rapport. Kortet
        # henter hvert minutt og holder den til neste rapport, som fukttallet.
        temp = data.get("cellar_temp")
        if temp is not None:
            self._temp, self._temp_report = temp, data["report_at"]
        elif self._temp_report != data["report_at"]:
            self._temp = None
        if self._temp is None:
            self._set(self._temp_text, "--", GREY)
            self._degree.hidden = True
            return
        # Et mellomrom gir plass til gradetegnet: «12 C».
        self._set(self._temp_text, "%d C" % round(self._temp), WHITE)
        cell = 6 * BIG
        self._degree.x = 239 - 2 * cell + BIG
        self._degree.y = CELLAR_VALUE_Y + 2 * BIG
        self._degree_palette[1] = WHITE
        self._degree.hidden = False
