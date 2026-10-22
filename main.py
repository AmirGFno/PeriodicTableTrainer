"""Periodic Table Trainer - offline Kivy desktop app (Python 3.11+)."""

import random
import sys

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from elements_data import ELEMENTS


Window.size = (800, 600)
Window.minimum_width = 700
Window.minimum_height = 600
Window.clearcolor = (0.055, 0.075, 0.12, 1)

PANEL = (0.095, 0.125, 0.19, 1)
TEXT = (0.93, 0.95, 0.99, 1)
MUTED = (0.66, 0.72, 0.82, 1)
ACCENT = (0.27, 0.62, 0.96, 1)
SUCCESS = (0.35, 0.9, 0.57, 1)
ERROR = (1, 0.58, 0.48, 1)

CATEGORY_COLORS = {
    "noble_gas": (0.58, 0.35, 0.86, 1),
    "metalloid": (0.20, 0.68, 0.43, 1),
    "metal": (0.22, 0.48, 0.86, 1),
    "nonmetal": (0.91, 0.48, 0.19, 1),
}
CATEGORY_LABELS = {
    "noble_gas": "Noble Gas",
    "metalloid": "Metalloid",
    "metal": "Metal",
    "nonmetal": "Nonmetal",
}
MODE_LABELS = {
    "ordered_1_36": "Ordered Quiz: 1 to 36",
    "symbol_number": "Symbol to Atomic Number",
    "number_symbol": "Atomic Number to Symbol",
    "name_full": "Element Name to Symbol + Number",
    "category": "Category Quiz",
}
MODE_DESCRIPTIONS = {
    "ordered_1_36": "Elements 1 through 36, asked in atomic-number order. Type the symbol.",
    "symbol_number": "See a symbol and recall its atomic number.",
    "number_symbol": "See an atomic number and recall its symbol.",
    "name_full": "Provide both the symbol and atomic number.",
    "category": "Identify a category member from four choices.",
}
MODE_COLORS = {
    "ordered_1_36": (0.18, 0.62, 0.58, 1),
    "symbol_number": (0.22, 0.48, 0.86, 1),
    "number_symbol": (0.20, 0.62, 0.62, 1),
    "name_full": (0.58, 0.35, 0.86, 1),
    "category": (0.91, 0.48, 0.19, 1),
}
STATE_MODES = {"ordered_1_36", "category"}
STATE_LABELS = {
    "solid": "solid",
    "liquid": "liquid",
    "gas": "gas",
    "unknown": "unknown",
}


class WrappedLabel(Label):
    """Label that wraps text to its current width and follows widget resizing."""

    def __init__(self, **kwargs):
        kwargs.setdefault("halign", "center")
        kwargs.setdefault("valign", "middle")
        super().__init__(**kwargs)
        self.bind(size=self._sync_text_size)
        self._sync_text_size()

    def _sync_text_size(self, *_):
        self.text_size = (max(0, self.width), None)


class WrappedButton(Button):
    """Button whose text wraps rather than drawing outside its bounds."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(size=self._sync_text_size)
        self._sync_text_size()

    def _sync_text_size(self, *_):
        self.text_size = (max(0, self.width - dp(24)), None)


class RoundedPanel(BoxLayout):
    """BoxLayout with a rounded background drawn in its own canvas."""

    def __init__(self, bg_color=PANEL, radius=dp(16), **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self.color_instruction = Color(*bg_color)
            self.rounded = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[radius],
            )
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def _update_canvas(self, *_):
        self.rounded.pos = self.pos
        self.rounded.size = self.size


class PeriodicTableTrainer(App):
    title = "Periodic Table Trainer"

    def build(self):
        self.current_mode = None
        self.current_element = None
        self.remaining = []
        self.total_questions = 0
        self.ask_state = False
        self.state_stage = False
        self.main_correct = False
        self.main_given = ""
        self.selected_option = None
        self.selected_state = None
        self.score = 0
        self.correct_count = 0
        self.wrong_count = 0
        self.answered = 0
        self.errors = []
        self.input_widgets = {}
        self.option_buttons = []
        self.state_buttons = []
        self.advance_event = None
        self.home_error_label = None
        self.root_widget = BoxLayout(orientation="vertical")
        self._show_home()
        Window.bind(on_key_down=self._on_key_down)
        return self.root_widget

    # ------------------------------------------------------------------
    # Reusable widgets and screen helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _make_button(text, callback, color=ACCENT, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(46))
        kwargs.setdefault("font_size", dp(16))
        kwargs.setdefault("bold", True)
        kwargs.setdefault("color", TEXT)
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("background_color", color)
        button = WrappedButton(text=text, **kwargs)
        button.bind(on_release=callback)
        return button

    @staticmethod
    def _make_label(text="", font_size=16, color=TEXT, **kwargs):
        kwargs.setdefault("halign", "center")
        kwargs.setdefault("valign", "middle")
        return WrappedLabel(
            text=text,
            font_size=dp(font_size),
            color=color,
            **kwargs,
        )

    def _clear_root(self):
        self.root_widget.clear_widgets()
        self.root_widget.padding = dp(20)
        self.root_widget.spacing = dp(12)

    def _make_scroll_content(self):
        scroll = ScrollView(
            do_scroll_x=False,
            bar_width=dp(8),
            scroll_type=["bars", "content"],
        )
        content = GridLayout(
            cols=1,
            spacing=dp(12),
            padding=(dp(4), dp(8)),
            size_hint_x=1,
            size_hint_y=None,
        )
        content.bind(minimum_height=content.setter("height"))
        scroll.add_widget(content)
        return scroll, content

    # ------------------------------------------------------------------
    # Home and per-mode setup screens
    # ------------------------------------------------------------------
    def _show_home(self, *_):
        self._clear_root()
        scroll, content = self._make_scroll_content()
        content.add_widget(self._make_label(
            "PERIODIC TABLE TRAINER",
            font_size=dp(27),
            bold=True,
            size_hint_x=1,
            size_hint_y=None,
            height=dp(54),
        ))
        content.add_widget(self._make_label(
            "Choose a game mode. Each mode runs as its own complete quiz.",
            font_size=dp(15),
            color=MUTED,
            size_hint_x=1,
            size_hint_y=None,
            height=dp(44),
        ))
        self.home_error_label = self._make_label(
            "",
            font_size=dp(14),
            color=ERROR,
            size_hint_x=1,
            size_hint_y=None,
            height=dp(30),
        )
        content.add_widget(self.home_error_label)

        # Ordered mode is deliberately first and therefore prominent.
        mode_grid = GridLayout(
            cols=2,
            spacing=dp(12),
            padding=(dp(2), dp(2)),
            size_hint_x=1,
            size_hint_y=None,
            height=dp(376),
            row_default_height=dp(116),
            row_force_default=True,
        )
        for mode_key, title in MODE_LABELS.items():
            button = self._make_button(
                f"{title}\n\n{MODE_DESCRIPTIONS[mode_key]}",
                lambda _button, key=mode_key: self._select_mode(key),
                color=MODE_COLORS[mode_key],
                font_size=dp(16),
                size_hint_x=1,
                size_hint_y=None,
                height=dp(116),
            )
            mode_grid.add_widget(button)
        content.add_widget(mode_grid)
        content.add_widget(self._make_label(
            f"Offline | {len(ELEMENTS)} unique elements | Press Enter to submit answers",
            font_size=dp(13),
            color=MUTED,
            size_hint_x=1,
            size_hint_y=None,
            height=dp(34),
        ))
        self.root_widget.add_widget(scroll)

    def _select_mode(self, mode_key):
        if mode_key not in MODE_LABELS:
            if self.home_error_label is not None:
                self.home_error_label.text = "Please choose one of the listed game modes."
            return
        if mode_key in STATE_MODES:
            self._show_mode_setup(mode_key)
        else:
            self._start_game(mode_key, ask_state=False)

    def _show_mode_setup(self, mode_key):
        """Show the optional state-quiz setting for Ordered and Category modes."""
        self._clear_root()
        scroll, content = self._make_scroll_content()
        content.add_widget(self._make_label(
            MODE_LABELS[mode_key],
            font_size=dp(25),
            bold=True,
            size_hint_x=1,
            size_hint_y=None,
            height=dp(58),
        ))
        content.add_widget(self._make_label(
            MODE_DESCRIPTIONS[mode_key],
            font_size=dp(15),
            color=MUTED,
            size_hint_x=1,
            size_hint_y=None,
            height=dp(58),
        ))

        setting_panel = RoundedPanel(
            orientation="vertical",
            padding=dp(18),
            spacing=dp(12),
            size_hint_x=1,
            size_hint_y=None,
            height=dp(150),
        )
        setting_panel.add_widget(self._make_label(
            "Optional extra question",
            font_size=dp(18),
            bold=True,
            size_hint_x=1,
            size_hint_y=None,
            height=dp(34),
        ))
        setting_row = BoxLayout(
            orientation="horizontal",
            spacing=dp(10),
            size_hint_x=1,
            size_hint_y=None,
            height=dp(48),
        )
        self.setup_state_checkbox = CheckBox(
            active=False,
            size_hint_x=None,
            width=dp(48),
            size_hint_y=1,
        )
        setting_text = self._make_label(
            "Also ask about physical state at room temperature",
            font_size=dp(15),
            color=TEXT,
            halign="left",
            size_hint_x=1,
            size_hint_y=1,
        )
        setting_row.add_widget(self.setup_state_checkbox)
        setting_row.add_widget(setting_text)
        setting_panel.add_widget(setting_row)
        content.add_widget(setting_panel)

        self.setup_error_label = self._make_label(
            "",
            font_size=dp(14),
            color=ERROR,
            size_hint_x=1,
            size_hint_y=None,
            height=dp(30),
        )
        content.add_widget(self.setup_error_label)
        content.add_widget(self._make_button(
            "Start This Mode",
            lambda *_: self._start_game(
                mode_key,
                ask_state=self.setup_state_checkbox.active,
            ),
            size_hint_x=1,
            size_hint_y=None,
            height=dp(52),
        ))
        content.add_widget(self._make_button(
            "Back to Menu",
            self._show_home,
            color=(0.22, 0.38, 0.58, 1),
            size_hint_x=1,
            size_hint_y=None,
            height=dp(46),
        ))
        self.root_widget.add_widget(scroll)

    # ------------------------------------------------------------------
    # Game initialization and screen
    # ------------------------------------------------------------------
    def _start_game(self, mode_key, ask_state=False, *_):
        if mode_key not in MODE_LABELS:
            if self.home_error_label is not None:
                self.home_error_label.text = "Please choose one of the listed game modes."
            return
        if self.advance_event is not None:
            self.advance_event.cancel()
            self.advance_event = None

        self.current_mode = mode_key
        self.ask_state = bool(ask_state and mode_key in STATE_MODES)
        self.state_stage = False
        self.current_element = None
        self.score = 0
        self.correct_count = 0
        self.wrong_count = 0
        self.answered = 0
        self.errors = []
        self.selected_option = None
        self.selected_state = None
        self.input_widgets = {}
        self.option_buttons = []
        self.state_buttons = []

        if mode_key == "ordered_1_36":
            self.remaining = sorted(
                (element for element in ELEMENTS if 1 <= element["atomic_number"] <= 36),
                key=lambda element: element["atomic_number"],
                reverse=True,
            )
            self.total_questions = 36
        else:
            self.remaining = list(ELEMENTS)
            random.shuffle(self.remaining)
            self.total_questions = len(ELEMENTS)

        self._build_game_screen()
        self._next_question()

    def _build_game_screen(self):
        self._clear_root()
        header = BoxLayout(
            orientation="horizontal",
            size_hint_x=1,
            size_hint_y=None,
            height=dp(44),
            spacing=dp(10),
        )
        self.mode_label = self._make_label(
            f"Mode: {MODE_LABELS[self.current_mode]}",
            font_size=dp(16),
            bold=True,
            halign="left",
            size_hint_x=None,
            width=dp(450),
            size_hint_y=1,
        )
        self.score_label = self._make_label(
            "Score: 0",
            font_size=dp(15),
            color=SUCCESS,
            bold=True,
            size_hint_x=None,
            width=dp(105),
            size_hint_y=1,
        )
        end_button = self._make_button(
            "End Game",
            self._show_results,
            color=(0.58, 0.25, 0.3, 1),
            font_size=dp(14),
            size_hint_x=None,
            width=dp(105),
            size_hint_y=None,
            height=dp(40),
        )
        header.add_widget(self.mode_label)
        header.add_widget(self.score_label)
        header.add_widget(end_button)
        header.bind(size=self._size_game_header)
        self.root_widget.add_widget(header)

        progress_row = BoxLayout(
            orientation="horizontal",
            size_hint_x=1,
            size_hint_y=None,
            height=dp(28),
            spacing=dp(10),
        )
        self.progress_label = self._make_label(
            f"0 / {self.total_questions}",
            font_size=dp(13),
            color=MUTED,
            size_hint_x=None,
            width=dp(86),
            size_hint_y=1,
        )
        self.progress_bar = ProgressBar(
            max=self.total_questions,
            value=0,
            size_hint_x=1,
            width=dp(600),
            size_hint_y=1,
        )
        progress_row.add_widget(self.progress_label)
        progress_row.add_widget(self.progress_bar)
        self.root_widget.add_widget(progress_row)

        self.prompt_label = self._make_label(
            "",
            font_size=dp(20),
            bold=True,
            size_hint_x=1,
            size_hint_y=None,
            height=dp(34),
        )
        self.root_widget.add_widget(self.prompt_label)

        self.question_panel = RoundedPanel(
            orientation="vertical",
            padding=dp(10),
            spacing=dp(5),
            size_hint_x=1,
            size_hint_y=0.78,
        )
        self.tile_anchor = AnchorLayout(
            anchor_x="center",
            anchor_y="center",
            size_hint_x=1,
            size_hint_y=1,
        )
        self.tile_panel = RoundedPanel(
            orientation="vertical",
            padding=(dp(14), dp(10)),
            spacing=dp(3),
            size_hint=(None, None),
            width=dp(330),
            height=dp(205),
        )
        self.tile_anchor.add_widget(self.tile_panel)
        self.question_panel.add_widget(self.tile_anchor)
        self.root_widget.add_widget(self.question_panel)

        self.answer_area = BoxLayout(
            orientation="vertical",
            spacing=dp(8),
            size_hint_x=1,
            size_hint_y=0.22,
        )
        self.root_widget.add_widget(self.answer_area)

        self.feedback_label = self._make_label(
            "",
            font_size=dp(14),
            color=MUTED,
            size_hint_x=1,
            size_hint_y=None,
            height=dp(38),
        )
        self.root_widget.add_widget(self.feedback_label)
        self.submit_button = self._make_button(
            "Submit  (Enter)",
            self._submit_answer,
            size_hint_x=1,
            size_hint_y=None,
            height=dp(46),
        )
        self.root_widget.add_widget(self.submit_button)

    def _size_game_header(self, header, *_):
        fixed_width = dp(105 + 105 + 20)
        self.mode_label.width = max(dp(170), header.width - fixed_width)

    def _next_question(self):
        if not self.remaining:
            self.current_element = None
            self._show_results()
            return

        # Ordered mode is stored backwards so pop() yields atomic numbers 1..36.
        self.current_element = self.remaining.pop()
        self.state_stage = False
        self.main_correct = False
        self.main_given = ""
        self.selected_option = None
        self.selected_state = None
        self.input_widgets = {}
        self.option_buttons = []
        self.state_buttons = []
        self.feedback_label.text = ""
        self.feedback_label.color = MUTED
        self.submit_button.disabled = False
        self.submit_button.text = "Submit  (Enter)"
        self.answer_area.clear_widgets()

        element = self.current_element
        if self.current_mode == "ordered_1_36":
            self.prompt_label.text = (
                f"Atomic number {element['atomic_number']} - what is the symbol?"
            )
        elif self.current_mode == "symbol_number":
            self.prompt_label.text = f"What is the atomic number of {element['symbol']}?"
        elif self.current_mode == "number_symbol":
            self.prompt_label.text = f"Which element has atomic number {element['atomic_number']}?"
        elif self.current_mode == "name_full":
            self.prompt_label.text = f"Enter the symbol and atomic number for {element['name']}"
        else:
            category = element["category"]
            category_name = CATEGORY_LABELS.get(category, category.replace("_", " ").title())
            self.prompt_label.text = f"Type the symbol of a {category_name}."

        self.main_question_text = self.prompt_label.text
        self._build_question_tile(element)
        self.question_panel.color_instruction.rgba = PANEL
        Clock.schedule_once(lambda _dt: self._focus_first_input(), 0.15)

    def _build_question_tile(self, element):
        """Draw the question as an element tile; unknown fields are answer inputs."""
        self.tile_panel.clear_widgets()
        self.tile_panel.color_instruction.rgba = PANEL
        self.input_widgets = {}

        number_known = self.current_mode in {"ordered_1_36", "number_symbol"}
        number_needed = self.current_mode in {"symbol_number", "name_full"}
        symbol_known = self.current_mode == "symbol_number"
        name_known = self.current_mode == "name_full"

        if number_known:
            number_widget = self._make_label(
                str(element["atomic_number"]),
                font_size=dp(18),
                bold=True,
                halign="left",
                size_hint_x=1,
                size_hint_y=None,
                height=dp(28),
            )
            self.tile_panel.add_widget(number_widget)
        elif number_needed:
            self._add_text_input(
                "number", "Atomic number", numeric=True,
                parent=self.tile_panel, height=dp(34), font_size=dp(17),
            )
        else:
            self.tile_panel.add_widget(Widget(size_hint_y=None, height=dp(34)))

        if symbol_known:
            symbol_widget = self._make_label(
                element["symbol"],
                font_size=dp(38),
                bold=True,
                size_hint_x=1,
                size_hint_y=None,
                height=dp(58),
            )
            self.tile_panel.add_widget(symbol_widget)
        else:
            self._add_text_input(
                "symbol", "Type symbol", parent=self.tile_panel,
                height=dp(58), font_size=dp(26),
            )

        if name_known:
            name_widget = self._make_label(
                element["name"],
                font_size=dp(17),
                size_hint_x=1,
                size_hint_y=None,
                height=dp(30),
            )
            self.tile_panel.add_widget(name_widget)
        else:
            self.tile_panel.add_widget(Widget(size_hint_y=None, height=dp(30)))

        self.tile_panel.add_widget(self._make_label(
            "Enter the missing tile value",
            font_size=dp(11),
            color=MUTED,
            size_hint_x=1,
            size_hint_y=None,
            height=dp(22),
        ))

    def _focus_first_input(self):
        for field in self.input_widgets.values():
            if field.parent is not None and not field.disabled:
                field.focus = True
                return

    def _reveal_element_tile(self, element, reveal_state=True):
        """Replace the partially filled question tile with the full element record."""
        self.tile_panel.clear_widgets()
        color = CATEGORY_COLORS.get(element["category"], PANEL)
        self.tile_panel.color_instruction.rgba = (
            color[0], color[1], color[2], 0.72
        )
        self.tile_panel.add_widget(self._make_label(
            f"Atomic number {element['atomic_number']}",
            font_size=dp(14),
            bold=True,
            halign="left",
            size_hint_x=1,
            size_hint_y=None,
            height=dp(23),
        ))
        self.tile_panel.add_widget(self._make_label(
            element["symbol"],
            font_size=dp(37),
            bold=True,
            size_hint_x=1,
            size_hint_y=None,
            height=dp(50),
        ))
        self.tile_panel.add_widget(self._make_label(
            element['name'],
            font_size=dp(16),
            size_hint_x=1,
            size_hint_y=None,
            height=dp(28),
        ))
        category_text = CATEGORY_LABELS.get(
            element["category"], element["category"].replace("_", " ").title()
        )
        self.tile_panel.add_widget(self._make_label(
            f"{category_text}  |  Group {element['group']}  |  Period {element['period']}",
            font_size=dp(12),
            size_hint_x=1,
            size_hint_y=None,
            height=dp(23),
        ))
        if reveal_state:
            state_text = self._state_parenthetical(element).strip("()")
            self.tile_panel.add_widget(self._make_label(
                f"State: {state_text}",
                font_size=dp(12),
                size_hint_x=1,
                size_hint_y=None,
                height=dp(22),
            ))

    def _size_input_row(self, row, *_):
        gap = dp(12)
        field_width = max(dp(120), (row.width - gap) / 2)
        for child in row.children:
            child.size_hint_x = None
            child.width = field_width

    def _add_text_input(
        self, key, hint, numeric=False, parent=None, height=dp(50), font_size=dp(18)
    ):
        field = TextInput(
            hint_text=hint,
            multiline=False,
            font_size=font_size,
            padding=(dp(10), dp(7)),
            size_hint_x=1,
            size_hint_y=None,
            height=height,
            input_filter="int" if numeric else None,
            write_tab=False,
            halign="center",
        )
        self.input_widgets[key] = field
        (parent if parent is not None else self.answer_area).add_widget(field)

    def _build_category_options(self, correct_element):
        options = random.sample(
            [element for element in ELEMENTS if element is not correct_element],
            3,
        ) + [correct_element]
        random.shuffle(options)
        grid = GridLayout(
            cols=2,
            spacing=dp(10),
            size_hint_x=1,
            size_hint_y=None,
            height=dp(100),
            row_default_height=dp(45),
            row_force_default=True,
        )
        for element in options:
            button = self._make_button(
                element["symbol"],
                lambda _button, symbol=element["symbol"]: self._select_option(symbol),
                color=(0.18, 0.23, 0.33, 1),
                font_size=dp(18),
                size_hint_x=1,
                size_hint_y=None,
                height=dp(45),
            )
            self.option_buttons.append(button)
            grid.add_widget(button)
        self.answer_area.add_widget(grid)

    # ------------------------------------------------------------------
    # Two-part answer flow (main answer + optional physical state)
    # ------------------------------------------------------------------
    def _select_option(self, symbol):
        if self.submit_button.disabled or self.state_stage:
            return
        self.selected_option = symbol
        for button in self.option_buttons:
            button.background_color = (
                ACCENT if button.text == symbol else (0.18, 0.23, 0.33, 1)
            )

    def _select_state(self, state):
        if self.submit_button.disabled or not self.state_stage:
            return
        self.selected_state = state
        for button in self.state_buttons:
            button.background_color = (
                ACCENT if button.text.casefold() == state else (0.18, 0.23, 0.33, 1)
            )

    def _submit_answer(self, *_):
        if self.current_element is None or self.submit_button.disabled:
            return

        if self.state_stage:
            if self.selected_state is None:
                self.feedback_label.text = "Choose a physical state before submitting."
                self.feedback_label.color = ERROR
                return
            self._finish_round(self.selected_state == self.current_element["state"])
            return

        element = self.current_element
        mode = self.current_mode
        if mode == "ordered_1_36":
            given = self.input_widgets["symbol"].text.strip()
            main_correct = given.casefold() == element["symbol"].casefold()
        elif mode == "symbol_number":
            given = self.input_widgets["number"].text.strip()
            main_correct = given == str(element["atomic_number"])
        elif mode == "number_symbol":
            given = self.input_widgets["symbol"].text.strip()
            main_correct = given.casefold() == element["symbol"].casefold()
        elif mode == "name_full":
            symbol = self.input_widgets["symbol"].text.strip()
            number = self.input_widgets["number"].text.strip()
            given = f"symbol={symbol or '(blank)'}, number={number or '(blank)'}"
            main_correct = (
                symbol.casefold() == element["symbol"].casefold()
                and number == str(element["atomic_number"])
            )
        else:
            given = self.input_widgets["symbol"].text.strip() or "(blank)"
            main_correct = given.casefold() == element["symbol"].casefold()

        self.main_correct = main_correct
        self.main_given = given
        if self.ask_state and mode in STATE_MODES:
            self._begin_state_stage()
        else:
            self._finish_round(state_correct=None)

    def _begin_state_stage(self):
        self.state_stage = True
        self.selected_state = None
        element = self.current_element
        self.answer_area.clear_widgets()
        self.input_widgets = {}
        self.option_buttons = []
        self.state_buttons = []
        self.prompt_label.text = (
            f"What is the physical state of {element['symbol']}?\n"
            "(solid / liquid / gas / unknown)"
        )
        self._reveal_element_tile(element, reveal_state=False)
        if self.main_correct:
            self.feedback_label.text = "Main answer correct. Now identify its physical state."
            self.feedback_label.color = SUCCESS
        else:
            self.feedback_label.text = (
                f"Main answer incorrect. The correct element is {element['symbol']}. "
                "Now identify its physical state."
            )
            self.feedback_label.color = ERROR

        grid = GridLayout(
            cols=4,
            spacing=dp(8),
            size_hint_x=1,
            size_hint_y=None,
            height=dp(44),
            row_default_height=dp(44),
            row_force_default=True,
        )
        for state in ("solid", "liquid", "gas", "unknown"):
            button = self._make_button(
                state,
                lambda _button, value=state: self._select_state(value),
                color=(0.18, 0.23, 0.33, 1),
                font_size=dp(16),
                size_hint_x=1,
                size_hint_y=None,
                height=dp(44),
            )
            self.state_buttons.append(button)
            grid.add_widget(button)
        self.answer_area.add_widget(grid)
        self.submit_button.disabled = False
        self.submit_button.text = "Submit State  (Enter)"

    def _state_parenthetical(self, element):
        state = STATE_LABELS.get(element.get("state", "unknown"), "unknown")
        if state == "unknown":
            return "(physical state unknown)"
        return f"({state} at room temperature)"

    def _state_success_sentence(self, element):
        state = STATE_LABELS.get(element.get("state", "unknown"), "unknown")
        if state == "unknown":
            return f"{element['name']}'s physical state is unknown."
        # Solid, liquid, and gas all take the article "a" here.
        return f"{element['name']} is a {state} at room temperature."

    def _correct_answer_text(self, element, include_state=True):
        if self.current_mode == "ordered_1_36":
            base = f"{element['symbol']} - {element['name']}"
        elif self.current_mode == "symbol_number":
            base = f"{element['atomic_number']} - {element['symbol']} ({element['name']})"
        elif self.current_mode == "number_symbol":
            base = f"{element['symbol']} - {element['name']}"
        elif self.current_mode == "name_full":
            base = f"{element['symbol']}, {element['atomic_number']} - {element['name']}"
        else:
            base = f"{element['symbol']} - {element['name']}"
        if include_state:
            return f"{base} {self._state_parenthetical(element)}"
        return base

    def _finish_round(self, state_correct):
        element = self.current_element
        main_correct = self.main_correct
        state_was_asked = self.ask_state and self.current_mode in STATE_MODES
        round_correct = main_correct and (state_correct if state_was_asked else True)
        self.answered += 1

        feedback_answer = self._correct_answer_text(
            element,
            include_state=state_was_asked,
        )
        answer_text = self._correct_answer_text(element, include_state=True)
        if round_correct:
            self.score += 1
            self.correct_count += 1
            if state_was_asked:
                self.feedback_label.text = (
                    f"Correct! +1 - {self._state_success_sentence(element)}"
                )
            else:
                self.feedback_label.text = "Correct! +1 point"
            self.feedback_label.color = SUCCESS
            self._beep()
        else:
            self.wrong_count += 1
            if state_was_asked and not state_correct:
                self.feedback_label.text = (
                    f"Not quite. Correct answer: {feedback_answer}. State wrong."
                )
            else:
                self.feedback_label.text = f"Not quite. Correct answer: {feedback_answer}"
            self.feedback_label.color = ERROR

            if state_was_asked:
                if not main_correct and not state_correct:
                    status = "main answer wrong; state wrong"
                elif not main_correct:
                    status = "main answer wrong; state correct"
                else:
                    status = "state wrong"
                given = f"{self.main_given}; state={self.selected_state} ({status})"
            else:
                given = self.main_given
                status = "main answer wrong"

            self.errors.append({
                "mode": MODE_LABELS[self.current_mode],
                "question": (
                    self.main_question_text
                    + (" | physical state" if state_was_asked else "")
                ),
                "your_answer": given,
                "correct_answer": answer_text,
                "status": status,
            })

        self._reveal_element_tile(element, reveal_state=True)
        self.score_label.text = f"Score: {self.score}"
        self.progress_bar.value = self.answered
        self.progress_label.text = f"{self.answered} / {self.total_questions}"
        self.submit_button.disabled = True
        self.submit_button.text = "Answer recorded"
        for field in self.input_widgets.values():
            field.disabled = True
        for button in self.option_buttons + self.state_buttons:
            button.disabled = True
        self.advance_event = Clock.schedule_once(self._advance_question, 2.0)

    # ------------------------------------------------------------------
    # Progress, keyboard, and sound
    # ------------------------------------------------------------------
    def _advance_question(self, _dt):
        self.advance_event = None
        if self.current_element is not None:
            self._next_question()

    def _on_key_down(self, _window, key, _scancode, _codepoint, _modifiers):
        if key in (13, 271) and self.current_element is not None:
            self._submit_answer()
            return True
        return False

    @staticmethod
    def _beep():
        try:
            if sys.platform.startswith("win"):
                import winsound
                winsound.Beep(880, 130)
            else:
                print("\\a", end="", flush=True)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Results, replay, and navigation
    # ------------------------------------------------------------------
    def _show_results(self, *_):
        if self.advance_event is not None:
            self.advance_event.cancel()
            self.advance_event = None
        self.current_element = None

        percentage = (self.correct_count / self.answered * 100) if self.answered else 0.0
        self._clear_root()
        self.root_widget.add_widget(self._make_label(
            "GAME RESULTS",
            font_size=dp(27),
            bold=True,
            size_hint_x=1,
            size_hint_y=None,
            height=dp(44),
        ))
        self.root_widget.add_widget(self._make_label(
            f"Mode: {MODE_LABELS.get(self.current_mode, 'Game')}",
            font_size=dp(15),
            color=MUTED,
            size_hint_x=1,
            size_hint_y=None,
            height=dp(28),
        ))

        stats = GridLayout(
            cols=4,
            spacing=dp(8),
            size_hint_x=1,
            size_hint_y=None,
            height=dp(82),
            row_default_height=dp(82),
            row_force_default=True,
        )
        for text, color in (
            (f"Correct\n{self.correct_count}", SUCCESS),
            (f"Incorrect\n{self.wrong_count}", ERROR),
            (f"Success rate\n{percentage:.1f}%", TEXT),
            (f"Answered\n{self.answered} / {self.total_questions}", MUTED),
        ):
            stats.add_widget(self._make_label(
                text,
                font_size=dp(15),
                color=color,
                size_hint_x=1,
                size_hint_y=None,
                height=dp(82),
            ))
        self.root_widget.add_widget(stats)
        self.root_widget.add_widget(self._make_label(
            "Mistakes and correct answers",
            font_size=dp(16),
            bold=True,
            size_hint_x=1,
            size_hint_y=None,
            height=dp(30),
        ))

        scroll = ScrollView(
            do_scroll_x=False,
            bar_width=dp(8),
            scroll_type=["bars", "content"],
            size_hint_x=1,
            size_hint_y=1,
        )
        mistake_list = GridLayout(
            cols=1,
            spacing=dp(6),
            padding=(dp(4), dp(4)),
            size_hint_x=1,
            size_hint_y=None,
        )
        mistake_list.bind(minimum_height=mistake_list.setter("height"))
        if not self.errors:
            mistake_list.add_widget(self._make_label(
                "No mistakes - excellent work!",
                font_size=dp(15),
                color=SUCCESS,
                size_hint_x=1,
                size_hint_y=None,
                height=dp(42),
            ))
        else:
            for index, item in enumerate(self.errors, 1):
                text = (
                    f"{index}. {item['mode']} | {item['question']}\n"
                    f"Your answer: {item['your_answer']}\n"
                    f"Correct: {item['correct_answer']}"
                )
                mistake_list.add_widget(self._make_label(
                    text,
                    font_size=dp(13),
                    color=TEXT,
                    halign="left",
                    size_hint_x=1,
                    size_hint_y=None,
                    height=dp(78),
                ))
        scroll.add_widget(mistake_list)
        self.root_widget.add_widget(scroll)

        actions = GridLayout(
            cols=2,
            spacing=dp(12),
            size_hint_x=1,
            size_hint_y=None,
            height=dp(48),
            row_default_height=dp(48),
            row_force_default=True,
        )
        actions.add_widget(self._make_button(
            "Play This Mode Again",
            lambda *_: self._start_game(self.current_mode, ask_state=self.ask_state),
            size_hint_x=1,
            size_hint_y=None,
            height=dp(48),
        ))
        actions.add_widget(self._make_button(
            "Back to Menu",
            self._show_home,
            color=(0.22, 0.38, 0.58, 1),
            size_hint_x=1,
            size_hint_y=None,
            height=dp(48),
        ))
        self.root_widget.add_widget(actions)

    def on_stop(self):
        if self.advance_event is not None:
            self.advance_event.cancel()
            self.advance_event = None
        Window.unbind(on_key_down=self._on_key_down)


if __name__ == "__main__":
    PeriodicTableTrainer().run()
