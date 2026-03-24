# Changelog

Все заметные изменения в этом проекте будут документироваться в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/),
и этот проект придерживается [Semantic Versioning](https://semver.org/lang/ru/).

---

## [0.2.1] - 2026-03-24

### Добавлено

#### 1) Удобная поддержка прокси
Ранее прокси можно было добавить только через указание в `httpx_client`, сейчас для
этого есть отдельный параметр `proxy` в методе `__init__` 

Раньше:
```python
client = PlatimaClient.from_env_file(
  
    env_file_path='.env',
    httpx_client=httpx.AsyncClient(
        proxy='http://log:pass@ip:port',
    )
)
```
Сейчас:
```python
client = PlatimaClient.from_env_file(
    env_file_path='.env',
    proxy='http://log:pass@ip:port'
)
```
**Важное замечание !**

Если прокси были переданы через параметр `proxy` и через `httpx_client`, прокси переданные
через `httpx_client` будут игнорироваться

Пример:
```python
client = PlatimaClient.from_env_file(
    env_file_path='.env',
    # Для PlatimaClient будут использоваться эти прокси
    proxy='http://log:pass@ip:port',
    httpx_client=httpx.AsyncClient(
        # Данные прокси будут игнорироваться
        proxy='http://log:pass@ip:another_port'
    )
)
```

Также, если вы используете фабрику для работы с платежными клиентами, вы можете указать общие
прокси, которые будут использоваться по умолчанию для всех клиентов, если в самом клиенте не указано другого. Если вы хотите чтобы прокси фабрики
использовались для всех клиентов, независимо от того, указаны ли у них прокси, используйте параметр `strict_proxy` при
создании фабрики

Пример c "нестрогими" прокси:

`strict_proxy=False` - по умолчанию
- Клиенты со своим прокси → используют свой
- Клиенты без прокси → используют прокси фабрики
```python
payment_factory = PaymentFactory(
  proxy='http://log:pass@ip:port'
)

payment_factory.register_many(
    [
        # PlatimaClient использует свои прокси, так как strict_proxy по умолчанию False
        PlatimaClient.from_env_file(
            env_file_path='.env',
            callback_url='https://your-callback-url',
            proxy='http://log:pass@ip:another_port'
        ),
        # AntilopaClient использует общие прокси из фабрики
        AntilopaClient.from_env_file(
            env_file_path='.env',
            callback_url='https://your-callback-url'
        )
    ]
)
```
Пример с "строгими" прокси:

`strict_proxy=True` - указано вручную
- Все клиенты → используют прокси фабрики (свой прокси игнорируется)
```python
payment_factory = PaymentFactory(
  proxy='http://log:pass@ip:port',
  strict_proxy=True
)

payment_factory.register_many(
    [
        # PlatimaClient использует общие прокси из фабрики, его прокси игнорируются, так как параметр strict_proxy=True
        PlatimaClient.from_env_file(
            env_file_path='.env',
            callback_url='https://your-callback-url',
            proxy='http://log:pass@ip:another_port'
        ),
        # AntilopaClient использует общие прокси из фабрики
        AntilopaClient.from_env_file(
            env_file_path='.env',
            callback_url='https://your-callback-url'
        )
    ]
)
```

---

## [0.2.0] - 2026-03-20

### Добавлено

#### 1) Поддержка вебхуков через:

- **Flask**
- **Django**
- **Aiohttp**

Ранее вебхуки были доступны только для интеграции в **Fastapi**

#### 2) Платежные системы:

- [Cryptomus](https://doc.cryptomus.com/ru)
- [Aaio](https://wiki.aaio.so/api)

#### 3) Возможность быстрого создания класса клиента

Ранее было возможно создавать класс только через указание всех параметров напрямую:

  ```python
  platima_client = PlatimaClient(
    api_key_project='your-project-id',
    project_id=1,
    callback_url='https://your-callback-url'
)
  ```

Сейчас можно быстро создать класс, получив параметры платежного клиента из `.env`

  ```python
  platima_client = PlatimaClient.from_env_file(
    env_file_path='.env',
    callback_url='https://your-callback-url'
)
  ```

Посмотрите атрибут `config` у соответствующего класса
платежного клиента для понимания формата записи переменных в файле `.env`

### Изменено

#### 1) Нейминг переменных

- `IPaymentClient` переименован в `AbstractPaymentClient`

#### 2) Метод создание вебхука

- Удален метод `create_webhook_router` у `AbstractPaymentClient`

  Теперь для создания вебхука используйте `get_webhooks` и выбирайте через атрибуты нужный вебхук для вашего фреймворка

  Раньше:
  ```python
  platima_fastapi_webhook = platima_client.create_webhook_router(
        process_func=platima_process_webhook,
        path=PLATIMA_WEBHOOK_PATH
  )
  ```
  Теперь используйте:
  ```python
  platima_webhooks = platima_client.get_webhooks(
      process_func=platima_process_webhook,
      path=PLATIMA_WEBHOOK_PATH
  )
  platima_fastapi_webhook = platima_webhooks.fastapi
  ```

---

## [0.1.0] - 2026-03-12

### Добавлено

#### Первый стабильный релиз

- Полная типизация
- Асинхронные http запросы на базе `httpx.AsyncClient`
- Базовый функционал создания платежей

#### Добавлена поддержка платежных систем:

- [Platima](https://platima.com/)
- [Antilopa](https://antilopay.com/)
