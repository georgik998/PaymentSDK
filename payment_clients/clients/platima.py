from typing import Callable, Awaitable
from dataclasses import dataclass
import hashlib
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from payment_clients.dto import BaseCreatePaymentDto, PaymentDto
from payment_clients.interface import IPaymentClient


class PlatimaWebhookSchema(BaseModel):
    id: str
    order_id: str
    project_id: int
    amount: float
    currency: str
    amount_pay: float
    currency_pay: str
    method: str
    createDateTime: datetime
    sign: str


@dataclass
class PlatimaCreatePaymentDto(BaseCreatePaymentDto):
    order_id: str  # ID заказа в нашей системе
    success_url: str | None = None
    failed_url: str | None = None


class PlatimaClient(IPaymentClient):
    INCLUDE_WEBHOOKS = True
    CREATE_PAYMENT_DTO = PlatimaCreatePaymentDto

    def __init__(
            self,
            api_key_project: str,
            project_id: int,
            base_url: str = 'https://platimapayments.com/api/v1',
            **kwargs
    ):
        super().__init__(**kwargs)
        self.api_key_project = api_key_project
        self.project_id = project_id
        self.base_url = base_url

    @staticmethod
    def _build_headers(signature):
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {signature}'
        }

    async def create_payment(self, data: PlatimaCreatePaymentDto) -> PaymentDto:
        endpoint = '/acquiring'
        currency = 'RUB'
        method = 'sbp'

        def _create_signature():
            return hashlib.sha512(
                f"{self.api_key_project}{data.order_id}{self.project_id}{data.amount:.2f}{currency}"
                .encode("utf-8")
            ).hexdigest()

        json = {
            "project_id": self.project_id,
            "order_id": data.order_id,
            "amount": data.amount,
            "currency": currency,
            "method": method,
        }
        if data.success_url:
            json['success_url'] = data.success_url
        if data.failed_url:
            json['failed_url'] = data.failed_url
        if self.callback_url:
            json["callback_url"] = self.callback_url

        response = await self.post(
            url=self.base_url + endpoint,
            json=json,
            headers=self._build_headers(_create_signature())
        )
        data = response.json()
        return PaymentDto(
            link=data['link'],
            id=data['id']
        )

    async def check_status(self, payment_id: str) -> bool:
        endpoint = '/getpayAcquiring'

        def _create_sign():
            return hashlib.sha512(
                f"{self.api_key_project}{payment_id}"
                .encode("utf-8")
            ).hexdigest()

        response = await self.post(
            url=self.base_url + endpoint,
            json={
                'project_id': self.project_id,
                'id': payment_id
            },
            headers=self._build_headers(signature=_create_sign())
        )
        data = response.json()

        if data.get("status"):
            if data['status'] == 'SUCCESS':
                return True
        return False

    def create_webhook_router(
            self, process_func: Callable[[PlatimaWebhookSchema], Awaitable[bool]], path: str = ""
    ) -> APIRouter:
        router = APIRouter()

        def _check_sign(data: PlatimaWebhookSchema, api_key_project=self.api_key_project) -> bool:
            expected_sign = hashlib.sha256(
                f"{api_key_project}{data.id}{data.order_id}{data.project_id}{data.amount:.2f}{data.currency}"
                .encode("utf-8")
            ).hexdigest()
            return expected_sign == data.sign

        @router.post(path=path)
        async def webhook(data: PlatimaWebhookSchema):
            # платима требует возврата 'ok' + 200 в случае успешной обработки
            content = 'not-ok'
            status_code = 419

            if not _check_sign(data):
                return JSONResponse(content=content, status_code=status_code)

            res = await process_func(data)

            if res:
                content = 'ok'
                status_code = 200
            return JSONResponse(content=content, status_code=status_code)

        return router
