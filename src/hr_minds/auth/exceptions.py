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


# --- RBAC ---
# These carry their HTTP status so services can raise them and FastAPI renders them.


class RBACError(HTTPException):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Bad request"

    def __init__(self):
        super().__init__(status_code=self.status_code, detail=self.detail)


class OrganizationNotFound(RBACError):
    """Also used for non-members, so outsiders can't tell an org exists."""

    status_code = status.HTTP_404_NOT_FOUND
    detail = "Organization not found"


class RoleNotFound(RBACError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Role not found"


class MemberNotFound(RBACError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Member not found"


class InvitationNotFound(RBACError):
    """Covers unknown, expired, used, and someone else's invitation alike."""

    status_code = status.HTTP_404_NOT_FOUND
    detail = "Invitation not found or expired"


class RoleNameTaken(RBACError):
    status_code = status.HTTP_409_CONFLICT
    detail = "A role with this name already exists"


class RoleInUse(RBACError):
    status_code = status.HTTP_409_CONFLICT
    detail = "Role is assigned to members; reassign them first"


class AlreadyMember(RBACError):
    status_code = status.HTTP_409_CONFLICT
    detail = "User is already a member of this organization"


class UnknownPermission(RBACError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    detail = "Unknown feature or action"


class PrivilegeEscalation(RBACError):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "You can't grant or manage permissions you don't have"


class OwnedOrganizationHasMembers(RBACError):
    status_code = status.HTTP_409_CONFLICT
    detail = "Your organization still has members; remove them before deleting your account"


class CannotModifyMember(RBACError):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "The owner and your own membership can't be changed"
