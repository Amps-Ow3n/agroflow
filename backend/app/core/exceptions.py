class AgroFlowException(Exception):

    def __init__(
        self,
        message,
        status_code=400,
        error_code=None
    ):

        self.message = message
        self.status_code = status_code
        self.error_code = error_code