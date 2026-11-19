from fastapi import HTTPException, status


class RecruitmentError(HTTPException):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Bad request"

    def __init__(self):
        super().__init__(status_code=self.status_code, detail=self.detail)


class JobPostingNotFound(RecruitmentError):
    # Also what another org's posting looks like: existence isn't leaked.
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Job posting not found"


class JobCandidateNotFound(RecruitmentError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Candidate not found"


class ResumeNotFound(RecruitmentError):
    # Also what a resume from another org looks like.
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Resume not found"


class CandidateAlreadySelected(RecruitmentError):
    status_code = status.HTTP_409_CONFLICT
    detail = "This resume is already selected for this job posting"


class InvalidJobPostingRange(RecruitmentError):
    # Maximum below minimum (experience or salary), or a salary with no currency.
    detail = "Check the experience and salary ranges: the maximum must not be below the minimum, and a salary needs a currency"
