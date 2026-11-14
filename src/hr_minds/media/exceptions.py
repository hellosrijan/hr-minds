from fastapi import HTTPException, status


class MediaError(HTTPException):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Bad request"

    def __init__(self):
        super().__init__(status_code=self.status_code, detail=self.detail)


class LocalMediaScanNotFound(MediaError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Local media scan not found"


class MediaFolderInvalid(MediaError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    detail = "Folder path does not exist or is not a directory"
