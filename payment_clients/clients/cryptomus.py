from dataclasses import dataclass, asdict
import hashlib
import base64
import json
from typing import Literal

from pydantic import BaseModel, Field

from payment_clients.dto import BaseCreatePaymentDto, PaymentDto
from payment_clients._abstract import AbstractPaymentClient, _PaymentConfig


class _CryptomusWebhookConvertSchema(BaseModel):
    to_currency: str
    commission: str | None
    rate: str
    amount: str


class CryptomusWebhookSchema(BaseModel):
    type: Literal['payment', 'wallet']
    uuid: str
    order_id: str
    amount: str
    payment_amount: str
    payment_amount_usd: str
    merchant_amount: str
    commission: str
    is_final: bool
    status: Literal[
        'paid', 'confirm_check', 'paid_over', 'fail', 'wrong_amount', 'cancel', 'system_fail',
        'refund_process', 'refund_fail', 'refund_paid'
    ]
    from_: str = Field(alias='from')
    wallet_address_uuid: str | None = None
    network: str
    currency: str
    payer_currency: str
    payer_amount: str
    payer_amount_exchange_rate: str
    transfer_id: str | None = None
    additional_data: str | None = None
    convert: _CryptomusWebhookConvertSchema | None = None
    txid: str | None = None
    sign: str


@dataclass
class CryptomusCreatePaymentDto(BaseCreatePaymentDto):
    amount: str
    order_id: str
    currency: str = 'RUB'
    network: str = None
    # Перед оплатой пользователь может нажать на кнопку в форме оплаты и вернуться на страницу магазина по этому URL.
    url_return: str = None
    url_success: str = None
    url_callback: str = None
    is_payment_multiple: bool = True
    lifetime: int = 3600
    to_currency: str = None
    subtract: int = 0
    accuracy_payment_percent: float = 0
    # metadata
    additional_data: str = None
    currencies: list[str] = None
    except_currencies: list[str] = None
    course_source: Literal['Binance', 'BinanceP2P', 'Exmo', 'Kucoin'] = None
    from_referral_code: str = None
    discount_percent: int = None
    is_refresh: bool = False


class CryptomusConfig(_PaymentConfig):
    CRYPTOMUS_USER_ID: str
    CRYPTOMUS_API_KEY: str
    CRYPTOMUS_BASE_URL: str = 'https://api.cryptomus.com/v1'
    CRYPTOMUS_HOST_IP: str = '91.227.144.54'


class CryptomusClient(AbstractPaymentClient):
    include_webhooks = True
    webhook_schema = CryptomusWebhookSchema
    create_payment_dto = CryptomusCreatePaymentDto
    config = CryptomusConfig

    def __init__(
            self,
            user_id: str,
            api_key: str,
            base_url: str = 'https://api.cryptomus.com/v1',
            **kwargs
    ):
        super().__init__(**kwargs)
        self.user_id = user_id
        self.api_key = api_key
        self.base_url = base_url

    @classmethod
    def from_env_file(cls, env_file_path: str = '.env', **kwargs) -> 'CryptomusClient':
        settings = cls.config(env_path=env_file_path)
        return cls(
            user_id=settings.CRYPTOMUS_USER_ID,
            api_key=settings.CRYPTOMUS_API_KEY,
            base_url=settings.CRYPTOMUS_BASE_URL,
            **kwargs
        )

    def create_headers(self, req_body: dict = None) -> dict:
        if req_body:
            json_data = json.dumps(req_body, separators=(',', ':'))
            json_base64 = base64.b64encode(json_data.encode('utf-8')).decode('utf-8')
        else:
            json_base64 = ''
        string_to_hash = json_base64 + self.api_key
        sign = hashlib.md5(string_to_hash.encode('utf-8')).hexdigest()
        return {
            'userId': self.user_id,
            'sign': sign
        }

    async def create_payment(self, data: CryptomusCreatePaymentDto) -> PaymentDto:
        endpoint = '/payment'

        if data.url_callback is None:
            data.url_callback = self.callback_url

        json_data = asdict(data)
        # убираем None поля
        json_data = {k: v for k, v in json_data.items() if v is not None}

        response = await self.post(
            url=self.base_url + endpoint,
            json=json_data,
            headers=self.create_headers(req_body=json_data)
        )
        data = response.json()
        return PaymentDto(
            link=data['url'],
            id=data['uuid']
        )

    async def check_status(self, payment_id: str = None, order_id: str = None) -> bool:
        """
        Поиск можно осуществить по одному из двух параметров

        Args:
            payment_id:
                id заказа в системе плаженого шлюза
            order_id:
                id заказа в нашей системе
        Returns:
            bool:
                True - если платеж оплачен, иначе False если платеж не оплачен или не найден
        """
        endpoint = '/payment/info'

        if payment_id:
            json_data = {'uuid': payment_id}
        if order_id:
            json_data = {'order_id': order_id}

        response = await self.post(
            url=self.base_url + endpoint,
            json=json_data,
            headers=self.create_headers(json_data)
        )
        data = response.json()

        if data['state'] != 0:
            return False
        return data['result']['is_final']

    def check_webhook_sign(self, data: CryptomusWebhookSchema, headers: dict) -> bool:
        received_sign = data.sign

        json_data = json.dumps(
            data.model_dump(by_alias=True, exclude={'sign'}),
            ensure_ascii=False,
            separators=(',', ':'),
            sort_keys=True
        )
        base64_data = base64.b64encode(json_data.encode('utf-8')).decode('utf-8')
        sign_string = base64_data + self.api_key
        true_sign = hashlib.md5(sign_string.encode('utf-8')).hexdigest()

        return true_sign == received_sign
