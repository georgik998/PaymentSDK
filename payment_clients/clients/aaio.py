from dataclasses import dataclass, asdict
from typing import Literal
import hashlib

from pydantic import BaseModel

from payment_clients.dto import BaseCreatePaymentDto, PaymentDto
from payment_clients._abstract import AbstractPaymentClient, _PaymentConfig

_method_literal = Literal[
    "cards_ru", "cards_ua", "cards_kz", "cards_uzs", "cards_azn",
    "sbp", "sbp_sber", "sbp_tink",
    "qiwi", "perfectmoney", "yoomoney", "advcash", "payeer",
    "skins",
    "beeline_ru", "tele2", "megafon_ru", "mts_ru", "yota",
    "bitcoin", "bitcoincash", "ethereum",
    "tether_trc20", "tether_erc20", "tether_ton", "tether_polygon", "tether_bsc",
    "usdcoin_trc20", "usdcoin_erc20", "usdcoin_bsc",
    "bnb_bsc", "notcoin", "hamstercoin", "tron",
    "litecoin", "dogecoin", "dai_erc20", "dai_bsc", "dash", "monero",
    "coupon", "balance",
]


class AaioWebhookSchema(BaseModel):
    # Может иметь значения:
    # success - Оплачен
    # hold - Оплачен, но средства в холде
    # Оба статуса означают что заказ успешно оплачен!
    status: str

    merchant_id: str
    invoice_id: str
    order_id: str
    amount: float
    currency: Literal['RUB', 'UAH', 'EUR', 'USD']
    profit: float
    commission: float
    commission_client: float
    commission_type: str
    sign: str
    method: _method_literal
    desc: str
    email: str
    us_key: str


@dataclass
class AaioCreatePaymentDto(BaseCreatePaymentDto):
    amount: float
    order_id: str
    currency: Literal['RUB', 'UAH', 'EUR', 'USD'] = 'RUB'
    method: _method_literal = None
    desc: str = None  # Описание заказа
    email: str = None
    lang: Literal['ru', 'en'] = 'ru'
    us_key: str = None  # metadata


class AaioConfig(_PaymentConfig):
    AAIO_MERCHANT_ID: str
    AAIO_SECRET_KEY: str
    AAIO_API_KEY: str
    AAIO_BASE_URL: str = "https://aaio.so"


class AaioClient(AbstractPaymentClient):
    include_webhooks = True
    webhook_schema = AaioWebhookSchema
    create_payment_dto = AaioCreatePaymentDto
    config = AaioConfig

    def __init__(
            self,
            merchant_id: str,
            secret_key: str,
            api_key: str,
            base_url: str = "https://aaio.so",
            **kwargs
    ):
        super().__init__(**kwargs)
        self.merchant_id = merchant_id
        self.secret_key = secret_key
        self.api_key = api_key
        self.base_url = base_url

    @classmethod
    def from_env_file(cls, env_file_path: str = ".env", **kwargs) -> "AaioClient":
        settings = cls.config(env_path=env_file_path)
        return cls(
            merchant_id=settings.AAIO_MERCHANT_ID,
            secret_key=settings.AAIO_SECRET_KEY,
            api_key=settings.AAIO_API_KEY,
            base_url=settings.AAIO_BASE_URL,
            **kwargs
        )

    def _create_headers(self):
        return {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Api-Key": self.api_key,
        }

    async def create_payment(self, data: AaioCreatePaymentDto) -> PaymentDto:
        def _create_sign() -> str:
            return hashlib.sha256(
                f'{self.merchant_id}:{data.amount}:{data.currency}:{self.secret_key}:{data.order_id}'.encode('utf-8')
            ).hexdigest()

        endpoint = "/merchant/get_pay_url"

        json_data = asdict(data)
        json_data = {k: v for k, v in json_data.items() if v is not None}
        json_data['merchant_id'] = self.merchant_id
        json_data['sign'] = _create_sign()

        response = await self.post(
            url=self.base_url + endpoint,
            data=json_data,
            headers=self._create_headers(),
        )
        result = response.json()
        if result['type'] == 'success':
            # Так как aaio не отдает id в их системе, нужно сделать доп. запрос ( возможно из ссылки вытащить можно )
            pay = await self._get_payment(order_id=data.order_id)

            return PaymentDto(
                link=result['url'],
                id=pay['id']
            )

    async def check_status(self, order_id: str) -> bool:
        endpoint = "/api/info-pay"

        json_data = {
            'order_id': order_id,
            'merchant_id': self.merchant_id
        }

        response = await self.post(
            url=self.base_url + endpoint,
            data=json_data,
            headers=self._create_headers(),
        )
        result = response.json()
        return result.get("type") == "success"

    async def _get_payment(self, order_id: str) -> dict:
        endpoint = "/api/info-pay"

        json_data = {
            'order_id': order_id,
            'merchant_id': self.merchant_id
        }

        response = await self.post(
            url=self.base_url + endpoint,
            data=json_data,
            headers=self._create_headers(),
        )
        result = response.json()
        return result

    def check_webhook_sign(self, data: AaioWebhookSchema, headers: dict) -> bool:
        expected_sign = hashlib.sha256(
            f'{self.merchant_id}:{data.amount}:{data.currency}:{self.secret_key}:{data.order_id}'.encode('utf-8')
        ).hexdigest()
        received_sign = data.sign
        return received_sign == expected_sign

