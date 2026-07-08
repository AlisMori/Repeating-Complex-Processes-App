from django.test import SimpleTestCase

from templates_mgmt.scheduling import resolve_effective_offsets


class ResolveEffectiveOffsetsTests(SimpleTestCase):
    def test_task_with_no_dependency_uses_its_own_offset(self):
        nodes = {1: {"offset": 5, "duration": 3, "fixed": False}}
        effective, circular, conflicts = resolve_effective_offsets(nodes, {})

        self.assertEqual(effective[1], (5, 8))
        self.assertEqual(circular, set())
        self.assertEqual(conflicts, set())

    def test_dependent_task_is_pushed_past_its_dependency(self):
        # A: day 0, duration 10 -> ends day 10
        # B: day_offset 2, depends on A -> must start no earlier than day 10
        nodes = {
            "A": {"offset": 0, "duration": 10, "fixed": False},
            "B": {"offset": 2, "duration": 4, "fixed": False},
        }
        edges = {"B": ["A"]}

        effective, circular, conflicts = resolve_effective_offsets(nodes, edges)

        self.assertEqual(effective["A"], (0, 10))
        self.assertEqual(effective["B"], (10, 14))
        self.assertEqual(circular, set())
        self.assertEqual(conflicts, set())

    def test_multi_hop_chain_cascades_through_every_link(self):
        # A -> B -> C, three hops deep. This is exactly the case the
        # old single-hop implementation got wrong.
        nodes = {
            "A": {"offset": 0, "duration": 10, "fixed": False},
            "B": {"offset": 1, "duration": 5, "fixed": False},
            "C": {"offset": 2, "duration": 3, "fixed": False},
        }
        edges = {"B": ["A"], "C": ["B"]}

        effective, circular, conflicts = resolve_effective_offsets(nodes, edges)

        self.assertEqual(effective["A"], (0, 10))
        self.assertEqual(effective["B"], (10, 15))
        self.assertEqual(effective["C"], (15, 18))
        self.assertEqual(circular, set())

    def test_dependency_that_already_ends_before_own_offset_is_unaffected(self):
        # A ends day 3, B's own offset is already day 10 - the
        # dependency isn't the binding constraint here.
        nodes = {
            "A": {"offset": 0, "duration": 3, "fixed": False},
            "B": {"offset": 10, "duration": 2, "fixed": False},
        }
        edges = {"B": ["A"]}

        effective, _, _ = resolve_effective_offsets(nodes, edges)

        self.assertEqual(effective["B"], (10, 12))

    def test_task_with_multiple_dependencies_uses_the_latest_end(self):
        nodes = {
            "A": {"offset": 0, "duration": 5, "fixed": False},   # ends day 5
            "B": {"offset": 0, "duration": 20, "fixed": False},  # ends day 20
            "C": {"offset": 1, "duration": 2, "fixed": False},
        }
        edges = {"C": ["A", "B"]}

        effective, _, _ = resolve_effective_offsets(nodes, edges)

        self.assertEqual(effective["C"], (20, 22))

    def test_fixed_date_task_is_never_shifted(self):
        nodes = {
            "A": {"offset": 0, "duration": 10, "fixed": False},  # ends day 10
            "B": {"offset": 2, "duration": 3, "fixed": True},    # fixed at day 2
        }
        edges = {"B": ["A"]}

        effective, circular, conflicts = resolve_effective_offsets(nodes, edges)

        # B stays at its fixed offset...
        self.assertEqual(effective["B"], (2, 5))
        # ...but the conflict (A finishes after B's fixed start) is reported
        self.assertIn("B", conflicts)

    def test_fixed_date_task_with_no_conflict_reports_nothing(self):
        nodes = {
            "A": {"offset": 0, "duration": 3, "fixed": False},   # ends day 3
            "B": {"offset": 10, "duration": 2, "fixed": True},   # fixed, well after A
        }
        edges = {"B": ["A"]}

        effective, _, conflicts = resolve_effective_offsets(nodes, edges)

        self.assertEqual(effective["B"], (10, 12))
        self.assertEqual(conflicts, set())

    def test_circular_dependency_does_not_infinite_loop_and_is_reported(self):
        nodes = {
            "A": {"offset": 0, "duration": 3, "fixed": False},
            "B": {"offset": 1, "duration": 2, "fixed": False},
        }
        edges = {"A": ["B"], "B": ["A"]}

        effective, circular, _ = resolve_effective_offsets(nodes, edges)

        # Must terminate (no infinite recursion / stack overflow) and
        # flag that a cycle was involved — there is no single
        # "correct" schedule for a circular dependency, so we only
        # assert on safety, not on one specific arbitrary value.
        self.assertTrue(len(circular) > 0)
        self.assertIn("A", effective)
        self.assertIn("B", effective)
        for task_id, (start, end) in effective.items():
            self.assertGreaterEqual(start, 0)
            self.assertGreater(end, start)

    def test_dependency_on_unknown_task_is_ignored_safely(self):
        nodes = {"A": {"offset": 5, "duration": 2, "fixed": False}}
        edges = {"A": ["does-not-exist"]}

        effective, _, _ = resolve_effective_offsets(nodes, edges)

        self.assertEqual(effective["A"], (5, 7))