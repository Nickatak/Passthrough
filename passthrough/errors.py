class PassthroughError(Exception):
    """Base for all errors the pipeline can raise."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class InvalidRequest(PassthroughError):
    """Bad input - malformed URL, unsupported method, etc."""

    def __init__(self, message: str):
        super().__init__("invalid_request", message)


class NavigationFailed(PassthroughError):
    """Browser couldn't reach the page - DNS, timeout, SSL, connection refused."""

    def __init__(self, message: str):
        super().__init__("navigation_failed", message)


class ChallengeBlocked(PassthroughError):
    """Provider blocked us with no solve path."""

    def __init__(self, message: str):
        super().__init__("challenge_blocked", message)


class SolveFailed(PassthroughError):
    """Challenge detected but couldn't be solved."""

    def __init__(self, message: str):
        super().__init__("solve_failed", message)


class CaptureFailed(PassthroughError):
    """Page loaded but content extraction failed."""

    def __init__(self, message: str):
        super().__init__("capture_failed", message)
