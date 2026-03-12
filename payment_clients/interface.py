from abc import ABC, abstractmethod
from typing import Awaitable, Callable
from functools import wraps

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from payment_clients.dto import BaseCreatePaymentDto, PaymentDto
from payment_clients.exception import PaymentClientWebhookSupportExc
from payment_clients.http_client import HttpClient

from typing import TypeVar

TCreatePaymentDto = TypeVar('TCreatePaymentDto', bound=BaseCreatePaymentDto, covariant=True)


def require_webhooks(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.supports_webhooks:
            raise PaymentClientWebhookSupportExc(client_name=self.__class__.__name__)
        return func(self, *args, **kwargs)
    return wrapper


class IPaymentClient(ABC, HttpClient):
    INCLUDE_WEBHOOKS: bool = False
    CREATE_PAYMENT_DTO: TCreatePaymentDto

    def __init__(self, callback_url: str = None, httpx_client: httpx.AsyncClient = None):
        HttpClient.__init__(self, httpx_client=httpx_client)
        self.callback_url = callback_url

    @property
    def supports_webhooks(self) -> bool:
        if self.INCLUDE_WEBHOOKS:
            return True
        return False

    @abstractmethod
    async def create_payment(self, data: TCreatePaymentDto) -> PaymentDto:
        """Создает платеж"""

    @abstractmethod
    async def check_status(self, payment_id: str) -> bool:
        """
        Проверяет статус платежа, оплачен/не оплачен
        Args:
            payment_id: id платежа в системе провайдера
        Returns:
            bool: True если оплачен, иначе False
        """

    @require_webhooks
    def create_webhook_router(self, process_func: Callable[[BaseModel], Awaitable[bool]], path: str = "") -> APIRouter:
        """Создает ручку fastapi для принятия вебхуков по статусам платежей

        Args:
            process_func:
                Функция для обработки платежа, принимает на вход pydantic-model которую вместе с post запросом присылает
                платежный провайдер
            path:
                Путь к ручке, ее полный адрес
                Пример:
                    name='/webhook/visa'
                    name='/webhook/cryptobot'
        Raises:
            PaymentClientWebhookSupportExc:
                Если клиент не поддерживает работу с вебхуками

        Returns:
            APIRouter:
                роутер фастапи с одной ручкой для принятия вебхуков по данной платежной системе
        """
