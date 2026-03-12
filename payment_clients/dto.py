from dataclasses import dataclass


@dataclass
class BaseCreatePaymentDto:
    """Базовый класс для наследования"""
    amount: float


@dataclass
class PaymentDto:
    link: str
    id: str
