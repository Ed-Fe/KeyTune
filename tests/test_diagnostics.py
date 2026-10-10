from __future__ import annotations

import pathlib
import sys
import unittest
from unittest.mock import Mock, patch


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from player.diagnostics import OK, PROBLEM, WARNING, CheckResult, format_report, has_findings, run_diagnostics
from player.diagnostics import checks
from player.diagnostics.mpv_library import (
    VISUAL_CPP_REDISTRIBUTABLE_URL,
    MpvLibraryDiagnosis,
    describe_mpv_load_failure,
    explain_mpv_library,
    pe_imports,
)

DLL_PATH = pathlib.Path("C:/KeyTune/mpv/libmpv-2.dll")


def failed(**fields):
    return MpvLibraryDiagnosis(dll_path=DLL_PATH, error_code=fields.pop("error_code", 126), **fields)


class MpvLibraryExplanationTests(unittest.TestCase):
    def test_loaded_library_needs_no_explanation(self):
        self.assertEqual(explain_mpv_library(MpvLibraryDiagnosis(dll_path=DLL_PATH)), ("", ""))

    def test_missing_library_folder_asks_for_reinstall(self):
        detail, advice = explain_mpv_library(MpvLibraryDiagnosis(dll_path=None))

        self.assertIn("não foi encontrada", detail)
        self.assertIn("Reinstale", advice)

    def test_old_vulkan_loader_points_to_the_bundled_loader_and_the_video_driver(self):
        diagnosis = failed(
            error_code=127,
            missing_functions=(("vkGetPhysicalDeviceProperties2", r"C:\Windows\System32\vulkan-1.dll"),),
        )

        detail, advice = explain_mpv_library(diagnosis)

        self.assertIn("vkGetPhysicalDeviceProperties2 (vulkan-1.dll)", detail)
        self.assertIn("driver de vídeo", advice)

    def test_missing_visual_cpp_runtime_points_to_the_redistributable(self):
        detail, advice = explain_mpv_library(failed(missing_libraries=("VCRUNTIME140.dll", "MSVCP140.dll")))

        self.assertIn("VCRUNTIME140.dll", detail)
        self.assertIn(VISUAL_CPP_REDISTRIBUTABLE_URL, advice)

    def test_missing_universal_crt_points_to_windows_update(self):
        _detail, advice = explain_mpv_library(failed(missing_libraries=("api-ms-win-crt-runtime-l1-1-0.dll",)))

        self.assertIn("Universal C Runtime", advice)
        self.assertNotIn(VISUAL_CPP_REDISTRIBUTABLE_URL, advice)

    def test_refused_bundled_file_is_named_instead_of_the_mpv_library(self):
        detail, _advice = explain_mpv_library(failed(error_code=193, broken_libraries=("vulkan-1.dll",)))

        self.assertIn("vulkan-1.dll", detail)
        self.assertNotIn("libmpv-2.dll", detail)

    def test_blocked_library_mentions_the_antivirus(self):
        detail, _advice = explain_mpv_library(failed(error_code=225))

        self.assertIn("antivírus", detail)

    def test_load_failure_sentence_is_empty_when_there_is_no_library_to_explain(self):
        with patch(
            "player.diagnostics.mpv_library.diagnose_mpv_library",
            return_value=MpvLibraryDiagnosis(dll_path=None),
        ):
            self.assertEqual(describe_mpv_load_failure(), "")

    @unittest.skipUnless(sys.platform == "win32", "reads a Windows system DLL")
    def test_pe_imports_reads_a_system_dll(self):
        imports = pe_imports(pathlib.Path(r"C:\Windows\System32\version.dll"))

        self.assertTrue(any(name.casefold().endswith(".dll") for name in imports))
        self.assertTrue(any(imports.values()))

    def test_pe_imports_of_a_file_that_is_not_a_dll_is_empty(self):
        self.assertEqual(pe_imports(pathlib.Path(__file__)), {})


class DiagnosticsReportTests(unittest.TestCase):
    def test_report_lists_problems_before_warnings_and_what_is_fine(self):
        results = [
            CheckResult("Sistema", OK, "Windows"),
            CheckResult("FFmpeg", WARNING, "Não encontrado.", "Instale."),
            CheckResult("Biblioteca do MPV", PROBLEM, "Falta X.", "Reinstale o KeyTune."),
        ]

        report = format_report(results, intro="O player não iniciou.")

        self.assertTrue(report.startswith("O player não iniciou."))
        self.assertIn("Problemas: 1. Avisos: 1.", report)
        self.assertLess(report.index("Biblioteca do MPV"), report.index("FFmpeg"))
        self.assertLess(report.index("FFmpeg"), report.index("Sistema"))
        self.assertIn("O que fazer: Reinstale o KeyTune.", report)
        self.assertTrue(has_findings(results))

    def test_report_says_so_when_nothing_is_wrong(self):
        results = [CheckResult("Sistema", OK, "Windows")]

        self.assertIn("Nenhum problema encontrado.", format_report(results))
        self.assertFalse(has_findings(results))


class RunDiagnosticsTests(unittest.TestCase):
    def test_player_is_not_started_when_the_library_did_not_load(self):
        with patch.object(checks, "diagnose_mpv_library", return_value=failed(missing_libraries=("X.dll",))), patch.object(
            checks.sys, "platform", "win32"
        ), patch.object(checks, "_player_results") as player_results:
            results = run_diagnostics(include_optional=False)

        player_results.assert_not_called()
        self.assertEqual([result.status for result in results], [OK, PROBLEM])

    def test_a_check_that_raises_becomes_a_result_and_the_others_still_run(self):
        with patch.object(checks, "diagnose_mpv_library", side_effect=OSError("disco")), patch.object(
            checks, "_yt_dlp_results", return_value=[CheckResult("yt-dlp", OK)]
        ), patch.object(checks, "_youtube_resolution_results", return_value=[]), patch.object(
            checks, "_node_results", return_value=[]
        ), patch.object(
            checks, "_youtubejs_results", return_value=[]
        ), patch.object(checks, "_ffmpeg_results", side_effect=RuntimeError("quebrou")):
            results = run_diagnostics()

        by_title = {result.title: result for result in results}
        self.assertEqual(by_title["Biblioteca do MPV"].status, PROBLEM)
        self.assertIn("disco", by_title["Biblioteca do MPV"].detail)
        self.assertEqual(by_title["yt-dlp"].status, OK)
        self.assertIn("quebrou", by_title["FFmpeg"].detail)

    def test_missing_youtubejs_is_a_warning_only_when_the_preference_is_on(self):
        with patch("player.youtube_music.youtubejs_runtime.youtubejs_dependencies_available", return_value=False):
            self.assertEqual(checks._youtubejs_results(True)[0].status, WARNING)
            self.assertEqual(checks._youtubejs_results(False)[0].status, OK)

    def test_youtubejs_that_does_not_answer_is_a_problem(self):
        with patch("player.youtube_music.youtubejs_runtime.youtubejs_dependencies_available", return_value=True), patch(
            "player.youtube_music.youtubejs_runtime.validate_youtubejs_dependencies",
            side_effect=RuntimeError("Não foi possível validar o processo do YouTube.js."),
        ):
            result = checks._youtubejs_results(True)[0]

        self.assertEqual(result.status, PROBLEM)
        self.assertIn("YouTube.js", result.detail)

    def test_node_version_the_app_refuses_is_a_warning(self):
        from types import SimpleNamespace

        old_node = SimpleNamespace(runtime_name="node", executable_path="C:/node.exe", version="18.0.0", supported=False)
        with patch("player.youtube_music.yt_dlp_runtime.inspect_javascript_runtimes", return_value=(old_node,)):
            result = checks._node_results()[0]

        self.assertEqual(result.status, WARNING)
        self.assertIn("18.0.0", result.detail)

    def test_optional_checks_are_skipped_for_the_startup_failure_report(self):
        with patch.object(checks, "diagnose_mpv_library", return_value=MpvLibraryDiagnosis(dll_path=None)), patch.object(
            checks, "_yt_dlp_results"
        ) as yt_dlp_results:
            run_diagnostics(include_optional=False)

        yt_dlp_results.assert_not_called()

    def test_expired_youtube_account_is_a_problem_and_a_network_failure_only_a_warning(self):
        expired = Exception("A autenticação salva do YouTube não é mais válida.")
        offline = Exception("Não foi possível validar a autenticação do YouTube agora.")
        offline.should_disconnect = False

        for error, status in ((expired, PROBLEM), (offline, WARNING)):
            with self.subTest(status=status):
                service = Mock()
                service.has_saved_browser_auth.return_value = True
                service.get_connected_account_name.side_effect = error

                self.assertEqual(checks._youtube_account_results(service)[0].status, status)

    def test_youtube_account_is_not_contacted_when_none_is_connected(self):
        service = Mock()
        service.has_saved_browser_auth.return_value = False

        self.assertEqual(checks._youtube_account_results(service)[0].status, OK)
        service.get_connected_account_name.assert_not_called()


class YouTubeResolutionTests(unittest.TestCase):
    def _results(self, *, youtubejs_error=None, yt_dlp_error=None, youtubejs_installed=True, youtubejs_enabled=True):
        from player.diagnostics import youtube_resolution as module

        with patch.object(module, "_youtubejs_installed", return_value=youtubejs_installed), patch.object(
            module, "_yt_dlp_ready", return_value=True
        ), patch.object(module, "_resolve_with_youtubejs", side_effect=youtubejs_error), patch.object(
            module, "_resolve_with_yt_dlp", side_effect=yt_dlp_error
        ):
            return module.youtube_resolution_results(youtubejs_enabled=youtubejs_enabled)

    def test_both_resolvers_working_is_fine(self):
        self.assertEqual([result.status for result in self._results()], [OK, OK])

    def test_one_resolver_failing_is_only_a_warning_because_youtube_still_plays(self):
        results = self._results(youtubejs_error=RuntimeError("403"))

        self.assertEqual([result.status for result in results], [WARNING, OK])
        self.assertIn("403", results[0].detail)

    def test_both_resolvers_failing_is_a_problem_that_points_to_the_connection_first(self):
        results = self._results(youtubejs_error=RuntimeError("a"), yt_dlp_error=RuntimeError("b"))

        self.assertEqual([result.status for result in results], [PROBLEM, PROBLEM])
        self.assertIn("internet", results[0].advice)

    def test_youtubejs_is_not_tried_when_turned_off_or_not_installed(self):
        self.assertEqual(len(self._results(youtubejs_enabled=False)), 1)
        self.assertEqual(len(self._results(youtubejs_installed=False)), 1)

    def test_yt_dlp_answer_without_formats_counts_as_a_failure(self):
        from types import SimpleNamespace

        from player.diagnostics import youtube_resolution as module

        with patch("player.youtube_music.yt_dlp_runtime.extract_info", return_value=SimpleNamespace(data={"formats": []})), patch(
            "player.youtube_music.yt_dlp_runtime.find_all_available_javascript_runtimes", return_value={"node": "node.exe"}
        ):
            with self.assertRaisesRegex(RuntimeError, "formato"):
                module._resolve_with_yt_dlp()


if __name__ == "__main__":
    unittest.main()
