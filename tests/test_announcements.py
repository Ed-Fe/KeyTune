import unittest
from types import SimpleNamespace

from player import announcements


class AnnouncementCategoryTests(unittest.TestCase):
    def _settings(self, **fields):
        return SimpleNamespace(**fields)

    def test_a_message_without_category_always_speaks(self):
        self.assertTrue(announcements.should_speak(self._settings(), None, window_active=True))

    def test_a_disabled_category_is_silent(self):
        settings = self._settings(announcements_disabled=[announcements.ANNOUNCE_CHAT_MESSAGES])
        self.assertFalse(
            announcements.should_speak(settings, announcements.ANNOUNCE_CHAT_MESSAGES, window_active=False)
        )
        self.assertTrue(
            announcements.should_speak(settings, announcements.ANNOUNCE_NOTIFICATIONS, window_active=False)
        )

    def test_events_can_stay_silent_while_the_window_is_active(self):
        settings = self._settings(announcements_in_window=False)
        self.assertFalse(
            announcements.should_speak(settings, announcements.ANNOUNCE_NOTIFICATIONS, window_active=True)
        )
        self.assertTrue(
            announcements.should_speak(settings, announcements.ANNOUNCE_NOTIFICATIONS, window_active=False)
        )

    def test_events_speak_in_the_window_by_default(self):
        self.assertTrue(
            announcements.should_speak(self._settings(), announcements.ANNOUNCE_CHAT_MESSAGES, window_active=True)
        )

    def test_responses_to_keys_ignore_the_speak_in_window_option(self):
        # Quem aperta uma tecla está com o KeyTune ativo: se a opção valesse aqui,
        # volume, abas e erros ficariam mudos o tempo todo.
        settings = self._settings(announcements_in_window=False)
        for category in announcements.RESPONSE_CATEGORIES:
            with self.subTest(category=category):
                self.assertTrue(announcements.should_speak(settings, category, window_active=True))

    def test_each_response_category_can_be_silenced_alone(self):
        for silenced in announcements.RESPONSE_CATEGORIES:
            settings = self._settings(announcements_disabled=[silenced])
            for category in announcements.RESPONSE_CATEGORIES:
                with self.subTest(silenced=silenced, category=category):
                    self.assertEqual(
                        announcements.should_speak(settings, category, window_active=True),
                        category != silenced,
                    )

    def test_categories_are_unique_and_split_into_responses_and_events(self):
        every = announcements.ANNOUNCEMENT_CATEGORIES
        self.assertEqual(len(every), len(set(every)))
        self.assertFalse(set(announcements.RESPONSE_CATEGORIES) & set(announcements.EVENT_CATEGORIES))

    def test_track_change_and_speed_pitch_have_their_own_boxes(self):
        names = [name for name, _label in announcements.announcement_labels()]
        self.assertIn(announcements.ANNOUNCE_TRACK_CHANGE, names)
        self.assertIn(announcements.ANNOUNCE_SPEED_PITCH, names)
        settings = self._settings(announcements_disabled=[announcements.ANNOUNCE_TRACK_CHANGE])
        self.assertFalse(
            announcements.should_speak(settings, announcements.ANNOUNCE_TRACK_CHANGE, window_active=True)
        )
        # Calar a troca de faixa não cala a pausa nem a velocidade.
        for other in (announcements.ANNOUNCE_PLAYBACK, announcements.ANNOUNCE_SPEED_PITCH):
            self.assertTrue(announcements.should_speak(settings, other, window_active=True))

    def test_time_volume_and_status_keys_never_depend_on_a_category(self):
        # T, V e S respondem a uma pergunta direta: nenhuma caixa da lista pode calá-los.
        import ast
        import pathlib

        sources = {
            "frames/playback/controls.py": ("_announce_playback_time", "_announce_current_volume", "_announce_player_status"),
            "quick_player/frame.py": ("_announce_time", "_announce_volume", "_announce_status"),
        }
        root = pathlib.Path(__file__).resolve().parents[1] / "src" / "player"
        for relative, functions in sources.items():
            tree = ast.parse((root / relative).read_text(encoding="utf-8"))
            found = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name in functions:
                    found.add(node.name)
                    for call in ast.walk(node):
                        if (
                            isinstance(call, ast.Call)
                            and isinstance(call.func, ast.Attribute)
                            and call.func.attr == "_announce"
                        ):
                            categorized = len(call.args) > 1 or call.keywords
                            if categorized:
                                # só "Nenhuma mídia carregada." (erro) pode ter categoria
                                self.assertEqual(
                                    getattr(call.args[-1], "id", ""),
                                    "ANNOUNCE_ERRORS",
                                    f"{relative}:{call.lineno}",
                                )
            self.assertEqual(found, set(functions), relative)

    def test_the_disabled_list_keeps_only_known_categories_in_order(self):
        self.assertEqual(
            announcements.normalize_disabled_announcements(["timer", "nope", "chat_messages"]),
            ["chat_messages", "timer"],
        )
        self.assertEqual(announcements.normalize_disabled_announcements("timer"), [])

    def test_every_category_has_a_label(self):
        self.assertEqual(
            [name for name, _label in announcements.announcement_labels()],
            list(announcements.ANNOUNCEMENT_CATEGORIES),
        )


if __name__ == "__main__":
    unittest.main()
