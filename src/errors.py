class AppError(Exception):
    """Error controlado de la aplicación. main.py lo convierte en ErrorResponse."""

    def __init__(
        self,
        code: str,
        message: str,
        http_status: int,
        status: str = "error",
        missing_fields: list[str] | None = None,
        details: dict | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.status = status
        self.missing_fields = missing_fields or []
        self.details = details or {}