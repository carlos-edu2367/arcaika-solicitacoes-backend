class DomainError(Exception):
    def __init__(self, message: str = "Generic"):
        self.message = message
        super().__init__(message)