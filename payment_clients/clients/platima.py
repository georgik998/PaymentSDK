from dataclasses import dataclass
import hashlib
from datetime import datetime

from pydantic import BaseModel

from payment_clients.dto import BaseCreatePaymentDto, PaymentDto
from payment_clients._abstract import AbstractPaymentClient, _PaymentConfig


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


class PlatimaConfig(_PaymentConfig):
    PLATIMA_API_KEY_PROJECT: str
    PLATIMA_PROJECT_ID: int
    PLATIMA_BASE_URL: str = 'https://platimapayments.com/api/v1'


class PlatimaClient(AbstractPaymentClient):
    include_webhooks = True
    webhook_schema = PlatimaWebhookSchema
    create_payment_dto = PlatimaCreatePaymentDto
    config = PlatimaConfig

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

    @classmethod
    def from_env_file(cls, env_file_path: str = '.env', **kwargs) -> 'PlatimaClient':
        settings = cls.config(env_path=env_file_path)
        return cls(
            api_key_project=settings.PLATIMA_API_KEY_PROJECT,
            project_id=settings.PLATIMA_PROJECT_ID,
            base_url=settings.PLATIMA_BASE_URL,
            **kwargs
        )

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

    def check_webhook_sign(self, data: PlatimaWebhookSchema, headers: dict) -> bool:
        def _check_sign(_data: PlatimaWebhookSchema, api_key_project=self.api_key_project) -> bool:
            expected_sign = hashlib.sha256(
                f"{api_key_project}{_data.id}{_data.order_id}{_data.project_id}{_data.amount:.2f}{_data.currency}"
                .encode("utf-8")
            ).hexdigest()
            return expected_sign == _data.sign

        return _check_sign(_data=data)
