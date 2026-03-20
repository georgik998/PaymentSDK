# Changelog

Все заметные изменения в этом проекте будут документироваться в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/),
и этот проект придерживается [Semantic Versioning](https://semver.org/lang/ru/).

---

## [0.2.0] - 2026-03-19

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
