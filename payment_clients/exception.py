class PaymentClientExc(Exception):
    def __init__(
            self,
            client_name: str,
            message: str = 'Unknown error',
            details: dict | None = None
    ):
        self.client_name = client_name
        self.details = details
        super().__init__(message)


class PaymentClientRegisterExc(PaymentClientExc):

    def __init__(self, client_name: str):
        super().__init__(
            message=f"Client {client_name} already registered",
            client_name=client_name
        )


class PaymentClientNotFoundExc(PaymentClientExc):

    def __init__(self, client_name: str):
        super().__init__(
            message=f"Client {client_name} not found",
            client_name=client_name
        )


class PaymentClientWebhookSupportExc(PaymentClientExc):

    def __init__(self, client_name: str):
        super().__init__(
            message=f"Client {client_name} doesn't support webhooks",
            client_name=client_name
        )
