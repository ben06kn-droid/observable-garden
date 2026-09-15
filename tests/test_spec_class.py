"""garden/spec_class.py: parsing, membership, and class sizes."""
import numpy as np
import pytest

from garden.spec_class import SubsetClass, parse


def test_parse_and_names():
    assert parse("none") is None
    assert parse("subsets:max_size=3") == SubsetClass(max_size=3)
    assert parse("subsets:max_size=2,signs=positive") == SubsetClass(max_size=2)
    signed = parse("subsets:max_size=2,signs=both")
    assert signed == SubsetClass(max_size=2, signed=True)
    assert signed.name == "subsets:max_size=2,signs=both"
    assert parse(signed.name) == signed


@pytest.mark.parametrize("bad", [
    "lookbacks:max=3", "subsets", "subsets:max_size=0", "subsets:max_size=two",
    "subsets:max_size=2,weights=mean", "subsets:max_size=2,signs=negative", "subsets:max_size",
])
def test_parse_rejects_malformed_or_unregistered_classes(bad):
    with pytest.raises(ValueError):
        parse(bad)


def test_membership_follows_the_unit_sum_convention_and_signs():
    e = np.eye(5)
    cls = SubsetClass(max_size=2)
    assert cls.contains(e[0]) and cls.contains(e[1] + e[3])
    assert not cls.contains(e[0] + e[1] + e[2])
    assert not cls.contains(np.zeros(5))
    assert not cls.contains(0.5 * (e[0] + e[1]))   # mean-weighted: a different class
    assert not cls.contains(e[0] - e[1])
    assert SubsetClass(max_size=2, signed=True).contains(e[0] - e[1])


def test_sizes_match_enumerated_members():
    for cls, K, expected in [(SubsetClass(2), 20, 210), (SubsetClass(3), 20, 1350), (SubsetClass(2, signed=True), 20, 800)]:
        assert cls.size(K) == expected
        assert sum(len(cls.members(K, m)[0]) for m in range(1, cls.max_size + 1)) == expected
    assert SubsetClass(3).size(60) == 36_050
    assert SubsetClass(3).size(200) == 1_333_500
