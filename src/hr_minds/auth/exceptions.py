from fastapi import HTTPException, status


class AuthError(Exception):
    """Base class for auth errors. Catch this to handle any auth failure."""


class EmailAlreadyRegistered(AuthError):
    """A user with this email already exists."""


class InvalidCredentials(AuthError):
    """The email or password is wrong. Deliberately vague to avoid account enumeration."""


class InactiveUser(AuthError):
    """The account exists and the password is correct, but the account is disabled."""


class Unauthorized(HTTPException):
    """The request has no valid credentials. Automatically returns HTTP 401."""

    def __init__(self, detail: str = "Invalid or expired token"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )
