class NationalGalleryError(Exception):
    """Base error for the national_gallery_api package."""


class APIError(NationalGalleryError):
    """Raised when the API returns an error response."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class NotFoundError(APIError):
    """Raised when a requested entity does not exist."""
