from hr_minds.auth.models import User


def test_password_is_hashed_and_verifiable():
    user = User()
    user.set_password("password123")

    assert user.password != "password123"
    assert user.password.startswith("$argon2id$")
    assert user.check_password("password123")
    assert not user.check_password("password124")


def test_same_password_hashes_differently():
    assert User.hash_password("password123") != User.hash_password("password123")  # salted
