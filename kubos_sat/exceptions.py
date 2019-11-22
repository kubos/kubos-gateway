class GatewayError(Exception):
    """Base error class for the KubOS Gateway"""


class CommandError(GatewayError):
    """
    Raised when there is an error with finding a command resolver.
    *.command is the command object
    *.message is the message issued
    """

    def __init__(self, command, message):
        self.command = command
        self.message = message
        super().__init__(message)


class GraphqlError(GatewayError):
    """
    Raised when a GraphQL query fails
    """

    def __init__(self, errors):
        self.errors = errors
        super().__init__(f"GraphQL query failed: {errors}")


class GraphqlMutationError(GatewayError):
    """
    Raised when a GraphQL query fails
    """

    def __init__(self, errors):
        self.errors = errors
        super().__init__(f"GraphQL mutation failed: {errors}")


class ShellClientError(GatewayError):
    """
    Raised when the shell service fails to respond.
    *.output is the output object from the subprocess command
    """

    def __init__(self, output):
        self.output = output
        super().__init__(f"Shell Service Failed to Respond: {output.stderr.decode('ascii')}")


class FileTransferError(GatewayError):
    """
    Raised when a file transfer fails.
    *.output is the output object from the subprocess command
    """

    def __init__(self, output):
        self.output = output
        super().__init__(f"File Failed to Transfer: {output.stderr.decode('ascii')}")
