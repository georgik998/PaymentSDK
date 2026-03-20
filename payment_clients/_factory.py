from typing import TypeVar, Type

from payment_clients._abstract import AbstractPaymentClient, TCreatePaymentDto
from payment_clients.exception import PaymentClientRegisterExc, PaymentClientNotFoundExc
from payment_clients.dto import PaymentDto

T = TypeVar('T', bound=AbstractPaymentClient)


class PaymentFactory:

    def __init__(self):
        self._clients: dict[Type[AbstractPaymentClient] | TCreatePaymentDto, AbstractPaymentClient] = {}

    def register(self, client: T) -> T:
        client_type = type(client)
        if client_type in self._clients:
            raise PaymentClientRegisterExc(client_type.__name__)
        self._clients[client_type] = client
        self._clients[client.create_payment_dto] = client
        return client

    def register_many(self, clients: list[T]) -> list[T]:
        res = []
        for client in clients:
            client = self.register(client)
            res.append(client)
        return res

    def get(self, client_type: Type[T]) -> T:
        client = self._clients.get(client_type)
        if client is None:
            raise PaymentClientNotFoundExc(client_type.__name__)
        return client

    @property
    def all_clients(self) -> list[AbstractPaymentClient]:
        return list(self._clients.values())

    def has_client(self, client_type: Type[AbstractPaymentClient]) -> bool:
        return client_type in self._clients

    async def close_connections(self):
        for client in self._clients.values():
            await client.close()

    async def create_payment(self, data: TCreatePaymentDto) -> PaymentDto:
        client = self._clients.get(data)
        if client is None:
            raise PaymentClientNotFoundExc(client_name=data.__name__)
        payment = await client.create_payment(data)
        return payment
