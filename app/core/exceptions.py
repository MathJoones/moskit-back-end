from fastapi import status


class AppException(Exception):
    def __init__(self, error_code: str, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.error_code = error_code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class NotFoundError(AppException):
    def __init__(self, resource: str, resource_id: str = ""):
        super().__init__(
            error_code="NOT_FOUND",
            detail=f"{resource} nao encontrado" + (f": {resource_id}" if resource_id else ""),
            status_code=status.HTTP_404_NOT_FOUND,
        )


class UnauthorizedError(AppException):
    def __init__(self, detail: str = "Credenciais invalidas"):
        super().__init__(
            error_code="UNAUTHORIZED",
            detail=detail,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenError(AppException):
    def __init__(self, detail: str = "Acesso negado"):
        super().__init__(
            error_code="FORBIDDEN",
            detail=detail,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ConflictError(AppException):
    def __init__(self, detail: str):
        super().__init__(
            error_code="CONFLICT",
            detail=detail,
            status_code=status.HTTP_409_CONFLICT,
        )


class ValidationError(AppException):
    def __init__(self, detail: str):
        super().__init__(
            error_code="VALIDATION_ERROR",
            detail=detail,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class AccountLockedError(AppException):
    def __init__(self):
        super().__init__(
            error_code="ACCOUNT_LOCKED",
            detail="Conta bloqueada temporariamente por excesso de tentativas de login.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )
