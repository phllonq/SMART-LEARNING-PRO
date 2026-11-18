from fastapi import HTTPException, status


class EntityNotFoundException(HTTPException):
    def __init__(self, entity_name: str, entity_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{entity_name} with id '{entity_id}' not found."
        )


class PermissionDeniedException(HTTPException):
    def __init__(self, detail: str = "Permission denied for this operation."):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


class DuplicateEntityException(HTTPException):
    def __init__(self, detail: str = "Entity with this identifier already exists."):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail
        )


class InvalidCredentialsException(HTTPException):
    def __init__(self, detail: str = "Invalid email or password."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )
