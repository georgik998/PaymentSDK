# 🏦 Набор готовых интеграций платежных систем

# Payment_clients v0.2.0

## ❓ В чем суть проекта

Данный код позволяет быстро подключить платежные системы в ваше проект.

Не нужно с нуля самому делать интеграцию - все уже прописано.

Можно работать как с одной конкретной системой, так и со всеми сразу используя встроенную фабрику

Ничего нового и тем более иновационного нет - просто удобный пакет, который позволит вам сэкономить ваше время

### [Мой телеграм :D](https://t.me/kaifomen)

## 💎Какие платежные системы сейчас поддерживаются ?

- [Platima](https://platima.com/)
- [Antilopa](https://antilopay.com/)
- [Cryptomus](https://doc.cryptomus.com/ru)
- [Aaio](https://wiki.aaio.so/api)

P.S - будут еще добавляться

## ⚙️ Стек

- httpx для работы с запросами

Также используются сторонние библиотеки,
например, **cryptography** для работы с подписями запросов у провайдера [ANTILOPA](https://antilopay.com/);
**fastapi**, **flask**, **django**, **aiohttp** - для обработки вебхуков

## 📁 Структура

```text
├── payment_clients
│   ├── __init__.py     # Основные импорты
│   ├── clients     # Платежные провайдеры
│   │   └── {entity}.py     # Клиент платежной системы {entity}
│   ├── dto.py      # датаклассы для работы с платежами
│   ├── exception.py    # ошибки, в основном для фабрики (клиент не найден | клиент не зарегистрирован)
│   ├── _factory.py      # фабрика для работы с несколькими клиентами
│   ├── _http_client.py      # класс для работы с http запросами
│   └── _abstract.py    # абстрактный класс для клиентов 
├── README.md
├── CHANGELOG.md
├── .env_example
└── requirements.txt
```

Если вы хотите добавить платежного провайдера которого нет, добавьте файл с соответствующим названием в папку `/clients`
и реализуйте дочерний класс от интерфейса `AbstractPaymentClient` из файла `_abstract.py`, затем добавьте импорт вашего
класса,
dto и (опционально) pydantic схемы для вебхука в файл `__init__.py`

## ▶️ Примеры кода & Быстрый старт

1) ### Создания платежа при использовании клиента на прямую

```python
import asyncio

from payment_clients import PlatimaClient, PlatimaCreatePaymentDto
from payment_clients.dto import PaymentDto


async def main() -> PaymentDto:
    platima_client = PlatimaClient(
        api_key_project='your-project-id',
        project_id=1,
        callback_url='https://your-callback-url'
    )
    payment = await platima_client.create_payment(
        PlatimaCreatePaymentDto(
            amount=100.00,
            order_id='order-id-in-your-system'
        )
    )
    # Закрываем пул соединений httpx
    await platima_client.close()
    return payment


if __name__ == '__main__':
    payment = asyncio.run(main())
```

2) ### Создания платежа с использованием фабрики и нескольких платежных систем

```python
import asyncio

from payment_clients import (
    PaymentFactory,
    PlatimaClient, PlatimaCreatePaymentDto,
    AntilopaClient, AntilopaCreatePaymentDto
)
from payment_clients.dto import PaymentDto


async def main() -> tuple[PaymentDto, PaymentDto]:
    payment_factory = PaymentFactory()

    payment_factory.register_many(
        [
            PlatimaClient(
                api_key_project='your-project-id',
                project_id=1,
                callback_url='https://your-callback-url'
            ),
            # Так же можно не указывать параметры вручную, а считать их из .env файла.
            # Чтобы узнать нейминг/формат записи переменных .env файла, посмотрите атрибут config 
            # соответствующего класса платежного клиента
            AntilopaClient.from_env_file(
                env_file_path='.env',
                callback_url='https://your-callback-url'
            )
        ]
    )

    # Выберите нужный {PaymentClient}CreatePaymentDto - фабрика сама подтянет необходимый платежный клиент
    payment1 = await payment_factory.create_payment(
        PlatimaCreatePaymentDto(
            amount=100.00,
            order_id='order-id-in-your-system'
        )
    )
    # Или можно выбрать клиент через метод get
    payment2 = await payment_factory.get(AntilopaClient).create_payment(
        AntilopaCreatePaymentDto(
            amount=100.00,
            order_id='order-id-in-your-system',
            product_name='your-product-name',
            description='your-payment-description'
        )
    )

    # Закрываем пул соединений httpx
    await payment_factory.close_connections()

    return payment1, payment2


if __name__ == '__main__':
    payment_platima, payment_antilopa = asyncio.run(main())
```

3) ### Пример быстрой интеграции вебхука

```python
import asyncio

from fastapi import FastAPI
from payment_clients import PlatimaClient
from payment_clients.clients.platima import PlatimaWebhookSchema

PLATIMA_WEBHOOK_PATH = '/webhook/platima'


async def platima_process_webhook(data: PlatimaWebhookSchema) -> bool:
    """Ваш код логики обработки вебхука
    
    Функция должна вернуть True если платеж можно считать успешно засчитанным, иначе False
    """


async def main() -> FastAPI:
    platima_client = PlatimaClient(
        api_key_project='your-project-id',
        project_id=1,
    )
    platima_webhooks = platima_client.get_webhooks(
        process_func=platima_process_webhook,
        path=PLATIMA_WEBHOOK_PATH
    )
    # Закрываем пул соединений httpx
    await platima_client.close()

    app = FastAPI()

    @app.get('/ping')
    async def ping():
        return "pong"

    # Подключаем нужный для нагешо фреймворка вебхук с адресом PLATIMA_WEBHOOK_PATH
    app.include_router(platima_webhooks.fastapi)
    return app


if __name__ == '__main__':
    fastapi_app = asyncio.run(main())
```

