"""Application error hierarchy.

Services and domain code raise these errors instead of HTTP exceptions.  The
API layer translates them into JSON responses, so the business rules stay free
of transport concerns.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for every error the application reports to a client."""

    status_code: int = 500
    default_detail: str = "The request could not be completed."

    def __init__(self, detail: str | None = None, *, status_code: int | None = None) -> None:
        self.detail: str = detail or self.default_detail
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.detail)


class BadRequestError(AppError):
    """The request payload is malformed or semantically invalid."""

    status_code = 400
    default_detail = "The request could not be understood."


class AuthenticationError(AppError):
    """The caller is not signed in."""

    status_code = 401
    default_detail = "Sign in is required."


class PermissionDeniedError(AppError):
    """The caller is signed in but lacks the required role."""

    status_code = 403
    default_detail = "This action is not allowed."


class NotFoundError(AppError):
    """The requested resource does not exist in the caller's scope."""

    status_code = 404
    default_detail = "The requested resource was not found."


class PayloadTooLargeError(AppError):
    """The uploaded payload exceeds the accepted size."""

    status_code = 413
    default_detail = "The uploaded payload is too large."


class UnsupportedMediaTypeError(AppError):
    """The uploaded payload has an unsupported file type."""

    status_code = 415
    default_detail = "This file type is not supported."


class UnprocessableEntityError(AppError):
    """The request is well formed but cannot be processed by the model."""

    status_code = 422
    default_detail = "The request could not be processed."


class ServiceUnavailableError(AppError):
    """A required upstream dependency is not configured."""

    status_code = 503
    default_detail = "The service is not available."


class InvalidOriginError(PermissionDeniedError):
    """A browser origin is malformed or not registered for the application."""

    default_detail = "This browser origin is not registered for the application."


class DatasetValidationError(BadRequestError):
    """An uploaded dataset does not satisfy the time-series requirements."""

    default_detail = "The uploaded dataset is not a valid time series."


class UnsupportedModelError(NotFoundError):
    """The requested forecasting model does not exist."""

    default_detail = "Choose LSTM, GRU, or RGF-LSTM."
