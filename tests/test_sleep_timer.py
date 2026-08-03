from __future__ import annotations

import pathlib
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.constants import (
    SLEEP_TIMER_MODE_COUNTDOWN,
    SLEEP_TIMER_MODE_END_OF_TRACK,
    SLEEP_TIMER_MODE_OFF,
)
from player.frames.sleep_timer import FrameSleepTimerMixin


class _FakeTimer:
    def __init__(self):
        self.running = False
        self.intervals = []

    def IsRunning(self):
        return self.running

    def Start(self, interval):
        self.running = True
        self.intervals.append(interval)

    def Stop(self):
        self.running = False


class _SleepTimerFrame(FrameSleepTimerMixin):
    def __init__(self):
        self.sleep_timer = _FakeTimer()
        self.announcements = []
        self.status_messages = []
        self.pause_calls = 0
        self.playing = True
        self._initialize_sleep_timer_state()

    def _announce(self, message):
        self.announcements.append(message)

    def _set_status_message(self, message, auto_clear_ms=6000):
        self.status_messages.append(message)

    def _refresh_sleep_timer_menu_state(self):
        return

    def _pause_playback_for_sleep_timer(self):
        if not self.playing:
            return False
        self.pause_calls += 1
        self.playing = False
        return True


class SleepTimerTests(unittest.TestCase):
    def test_countdown_arms_timer_and_reports_remaining_time(self):
        frame = _SleepTimerFrame()

        self.assertTrue(frame._arm_sleep_timer_countdown(30))

        self.assertEqual(frame._sleep_timer_mode, SLEEP_TIMER_MODE_COUNTDOWN)
        self.assertTrue(frame.sleep_timer.IsRunning())
        self.assertLessEqual(frame._sleep_timer_remaining_seconds(), 30 * 60)
        self.assertGreater(frame._sleep_timer_remaining_seconds(), 30 * 60 - 5)
        self.assertIn("30", frame.announcements[-1])

    def test_countdown_duration_is_clamped_to_the_supported_range(self):
        frame = _SleepTimerFrame()

        frame._arm_sleep_timer_countdown(0)
        self.assertEqual(frame._sleep_timer_total_minutes, 1)

        frame._arm_sleep_timer_countdown(10_000)
        self.assertEqual(frame._sleep_timer_total_minutes, 720)

    def test_invalid_duration_is_rejected(self):
        frame = _SleepTimerFrame()

        self.assertFalse(frame._arm_sleep_timer_countdown("meia hora"))
        self.assertEqual(frame._sleep_timer_mode, SLEEP_TIMER_MODE_OFF)

    def test_end_of_track_mode_does_not_start_the_tick_timer(self):
        frame = _SleepTimerFrame()

        frame._arm_sleep_timer_end_of_track()

        self.assertEqual(frame._sleep_timer_mode, SLEEP_TIMER_MODE_END_OF_TRACK)
        self.assertFalse(frame.sleep_timer.IsRunning())
        self.assertTrue(frame._sleep_timer_should_stop_at_media_end())

    def test_media_end_hook_clears_the_timer_once(self):
        frame = _SleepTimerFrame()
        frame._arm_sleep_timer_end_of_track()

        frame._handle_sleep_timer_media_end()

        self.assertEqual(frame._sleep_timer_mode, SLEEP_TIMER_MODE_OFF)
        self.assertFalse(frame._sleep_timer_should_stop_at_media_end())

    def test_expired_countdown_pauses_playback_and_disarms(self):
        frame = _SleepTimerFrame()
        frame._arm_sleep_timer_countdown(5)
        # Simula o vencimento do prazo sem esperar em tempo real.
        frame._sleep_timer_deadline = frame._sleep_timer_deadline - 5 * 60

        frame.on_sleep_timer_tick(None)

        self.assertEqual(frame.pause_calls, 1)
        self.assertEqual(frame._sleep_timer_mode, SLEEP_TIMER_MODE_OFF)
        self.assertFalse(frame.sleep_timer.IsRunning())

    def test_tick_warns_once_per_warning_threshold(self):
        frame = _SleepTimerFrame()
        frame._arm_sleep_timer_countdown(10)
        frame.announcements.clear()

        frame._maybe_warn_sleep_timer(60)
        frame._maybe_warn_sleep_timer(60)

        warnings = [message for message in frame.announcements if "minuto" in message]
        self.assertEqual(len(warnings), 1)

    def test_cancelling_an_idle_timer_reports_that_nothing_was_armed(self):
        frame = _SleepTimerFrame()

        self.assertFalse(frame._clear_sleep_timer(announce=True))
        self.assertIn("Nenhum temporizador", frame.announcements[-1])

    def test_cancelling_an_armed_timer_stops_the_ticks(self):
        frame = _SleepTimerFrame()
        frame._arm_sleep_timer_countdown(15)

        self.assertTrue(frame._clear_sleep_timer(announce=True))

        self.assertFalse(frame.sleep_timer.IsRunning())
        self.assertEqual(frame._sleep_timer_mode, SLEEP_TIMER_MODE_OFF)
        self.assertIn("cancelado", frame.announcements[-1])

    def test_warning_uses_the_singular_form_for_one_minute(self):
        frame = _SleepTimerFrame()
        frame._arm_sleep_timer_countdown(10)
        frame.announcements.clear()

        frame._maybe_warn_sleep_timer(60)

        self.assertIn("falta 1 minuto.", frame.announcements[-1])
        self.assertNotIn("minuto(s)", frame.announcements[-1])

    def test_countdown_announcement_uses_the_plural_form(self):
        frame = _SleepTimerFrame()

        frame._arm_sleep_timer_countdown(30)

        self.assertIn("30 minutos", frame.announcements[-1])

        frame._arm_sleep_timer_countdown(1)

        self.assertIn("1 minuto.", frame.announcements[-1])

    def test_status_sentence_is_empty_when_disarmed(self):
        frame = _SleepTimerFrame()

        self.assertEqual(frame._sleep_timer_status_sentence(), "")

        frame._arm_sleep_timer_end_of_track()
        self.assertIn("fim da faixa", frame._sleep_timer_status_sentence())

    def test_remaining_time_is_formatted_in_minutes_and_seconds(self):
        frame = _SleepTimerFrame()

        self.assertEqual(frame._format_sleep_timer_remaining(90), "1 min e 30 s")
        self.assertEqual(frame._format_sleep_timer_remaining(120), "2 min")
        self.assertEqual(frame._format_sleep_timer_remaining(45), "45 s")


if __name__ == "__main__":
    unittest.main()
