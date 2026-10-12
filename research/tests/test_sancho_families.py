"""Sancho's copy of the registered family map equals model version 1's (research/learn)."""
from learn.inputs import FAMILIES as F1, PAIRS as P1

from sancho.families import FAMILIES, PAIRS


def test_the_family_map_is_byte_identical_to_learn_inputs():
    assert FAMILIES == F1 and PAIRS == P1


def test_learn2_is_an_alias_of_sancho():
    import learn2
    import learn2.learner
    import sancho.learner
    assert learn2.learner is sancho.learner and learn2.views is __import__("sancho.views").views
