"""The quick target is `pytest tests -m "not slow"` (under two minutes; the GitHub Actions
workflow runs it). The tests named here take two seconds or more each on a laptop and are marked
slow centrally, so the test files themselves are unchanged; `pytest tests` still runs them all."""
import pytest

SLOW = (
    "tests/test_meta_adaptive.py::test_moment_scoring_matches_column_scoring_on_the_design_block",
    "tests/test_meta_adaptive.py::test_greedy_continuation_searchers_separate_only_rarely",
    "tests/test_watch.py::test_a_ladder_run_that_stays_on_ladder_matches_the_union_verdict",
    "tests/test_watch.py::test_refused_attempt_is_counted_not_fatal",
    "tests/test_watch.py::test_random_anchored_search_chases_at_about_one_over_K",
    "tests/test_quixote_pricing.py::test_pricing_a_greedy_continuation_is_a_no_op_and_that_is_structural",
    "tests/test_lattice_greedy_optimality.py::test_greedy_suboptimality_rate_is_measured_not_assumed",
    "tests/test_analytic_sharpe.py::test_matches_simulation",
    "tests/test_garden.py::test_bundled_examples_return_their_documented_verdicts",
)


def pytest_collection_modifyitems(config, items):
    for item in items:
        if item.nodeid.startswith(SLOW):
            item.add_marker(pytest.mark.slow)
