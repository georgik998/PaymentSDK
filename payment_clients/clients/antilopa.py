from typing import  Literal
from dataclasses import dataclass
import json
import base64

from pydantic import BaseModel

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_der_private_key, load_der_public_key

from payment_clients.dto import BaseCreatePaymentDto, PaymentDto
from payment_clients._abstract import AbstractPaymentClient, _PaymentConfig


class AntilopaWebookCustomerSchema(BaseModel):
    email: str
    phone: str
    address: str
    ip: str
    fullname: str


class AntilopaWebhookSchema(BaseModel):
    type: str
    payment_id: str
    order_id: str
    ctime: str
    amount: float
    original_amount: float
    fee: float
    status: str
    currency: str
    product_name: str
    description: str
    pay_method: str
    pay_data: str
    customer_ip: str
    customer_useragent: str
    customer: AntilopaWebookCustomerSchema
    merchant_extra: str


@dataclass
class AntilopaCreatePaymentDto(BaseCreatePaymentDto):
    order_id: str
    product_name: str
    description: str
    product_type: Literal['goods', 'services'] = 'goods'
    success_url: str = None
    failed_url: str = None
    metadata: dict = None


class AntilopaConfig(_PaymentConfig):
    ANTILOPA_SECRET_ID: str
    ANTILOPA_PROJECT_ID: str
    ANTILOPA_PRIVATE_KEY: str
    ANTILOPA_PUBLIC_KEY: str | None
    ANTILOPA_BASE_URL: str = 'https://lk.antilopay.com/api/v2'


class AntilopaClient(AbstractPaymentClient):
    include_webhooks = True
    webhook_schema = AntilopaWebhookSchema
    create_payment_dto = AntilopaCreatePaymentDto
    config = AntilopaConfig

    def __init__(
            self,
            secret_id: str,
            private_key: str,
            project_id: str,
            public_key: str | None,  # Используется только для вебхука
            base_url: str = 'https://lk.antilopay.com/api/v2',
            **kwargs
    ):
        super().__init__(**kwargs)
        self.secret_id = secret_id
        self.private_key = private_key
        self.project_id = project_id
        self.base_url = base_url
        self.public_key = public_key

    @property
    def supports_webhooks(self) -> bool:
        if self.public_key is None:
            return False
        return self.include_webhooks

    @classmethod
    def from_env_file(cls, env_file_path: str = '.env', **kwargs) -> 'AbstractPaymentClient':
        settings = cls.config(env_path=env_file_path)
        return cls(
            secret_id=settings.ANTILOPA_SECRET_ID,
            public_key=settings.ANTILOPA_PUBLIC_KEY,
            project_id=settings.ANTILOPA_PROJECT_ID,
            private_key=settings.ANTILOPA_PRIVATE_KEY,
            base_url=settings.ANTILOPA_BASE_URL,
            **kwargs
        )

    def _create_rsa_signature(self, payload) -> str:
        json_str = json.dumps(payload, separators=(',', ':'))
        private_key_bytes = base64.b64decode(self.private_key)
        private_key = load_der_private_key(private_key_bytes, password=None)
        signature = private_key.sign(
            json_str.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode('utf-8')

    def _build_headers(self, payload) -> dict:
        signature = self._create_rsa_signature(payload)
        return {
            'Content-Type': 'application/json',
            'X-Apay-Secret-Id': self.secret_id,
            'X-Apay-Sign': signature,
            'X-Apay-Sign-Version': '1'  # SHA256WithRSA
        }

    async def create_payment(self, data: AntilopaCreatePaymentDto) -> PaymentDto:
        endpoint = '/payment/create'
        currency = 'RUB'

        payload = {
            "project_identifier": self.project_id,
            "order_id": data.order_id,
            "amount": data.amount,
            "currency": currency,
            "product_name": data.product_name,
            "product_type": data.product_type,
            "description": data.description,
            "prefer_methods": ["SBP"]  # Предпочитаемый метод оплаты
        }

        if data.metadata:
            payload["merchant_extra"] = json.dumps(data.metadata)
        if data.failed_url:
            payload['fail_url'] = data.failed_url
        if data.success_url:
            payload["success_url"] = data.success_url

        response = await self.post(
            url=self.base_url + endpoint,
            json=payload,
            headers=self._build_headers(payload)
        )
        data = response.json()
        return PaymentDto(
            link=data['payment_url'],
            id=data['payment_id']
        )

    async def check_status(self, payment_id: str) -> bool:
        endpoint = '/payment/check'

        payload = {
            'order_id': payment_id,
            "project_identifier": self.project_id
        }
        response = await self.post(
            url=self.base_url + endpoint,
            json=payload,
            headers=self._build_headers(payload)
        )
        data = response.json()

        status: Literal['PENDING', 'SUCCESS', 'FAIL', 'CANCEL', 'EXPIRED', 'CHARGEBACK', 'REVERSED'] = data['status']
        if status == 'SUCCESS':
            return True
        return False

    def check_webhook_sign(self, data: AntilopaWebhookSchema, headers: dict) -> bool:
        def _check_sign(sign: str, body: str) -> bool:
            try:
                public_key_bytes = base64.b64decode(self.public_key)
                signature_bytes = base64.b64decode(sign)
                public_key = load_der_public_key(public_key_bytes)
                public_key.verify(
                    signature_bytes,
                    body.encode('utf-8'),
                    padding.PKCS1v15(),
                    hashes.SHA256()
                )
                return True
            except Exception:
                return False

        return _check_sign(
            sign=headers['X-Apay-Callback'],
            body=json.dumps(data.model_dump_json())
        )
