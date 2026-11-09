import re

import pytest

from hr_minds.auth.models import Organization


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("Srijan", "srijan"),
        ("O'Brien", "obrien"),
        ("Acme Corp & Sons!!", "acme-corp-sons"),
        ("李华", "org"),  # nothing usable left
        ("x" * 60, "x" * 30),
    ],
)
def test_new_public_id(name, slug):
    public_id = Organization.new_public_id(name)
    assert re.fullmatch(rf"org_{slug}_[a-z0-9]{{10}}", public_id), public_id
    assert len(public_id) <= 50  # column size


def test_new_public_id_is_random():
    assert Organization.new_public_id("acme") != Organization.new_public_id("acme")
