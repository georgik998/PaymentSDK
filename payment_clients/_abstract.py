from abc import ABC, abstractmethod
from typing import Awaitable, Callable, Type
from functools import wraps
from dataclasses import dataclass

import httpx
from fastapi import APIRouter
from flask import Blueprint
from aiohttp.web import RouteTableDef
from django.urls import path as django_path
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from payment_clients.dto import BaseCreatePaymentDto, PaymentDto
from payment_clients.exception import PaymentClientWebhookSupportExc
from payment_clients._http_client import HttpClient

from typing import TypeVar

TCreatePaymentDto = TypeVar('TCreatePaymentDto', bound=BaseCreatePaymentDto, covariant=True)
TPaymentWebhookSchema = TypeVar('TPaymentWebhookSchema', bound=BaseModel, covariant=True)


class _PaymentConfig(BaseSettings):

    def __init__(self, env_path: str = '.env'):
        super().__init__(_env_file=env_path, _env_file_encoding='utf-8')

    model_config = SettingsConfigDict(extra='allow')


def require_webhooks(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.supports_webhooks:
            raise PaymentClientWebhookSupportExc(client_name=self.__class__.__name__)
        return func(self, *args, **kwargs)

    return wrapper


@dataclass
class WebhooksDto:
    fastapi: APIRouter
    flask: Blueprint
    django: django_path
    aiohttp: RouteTableDef


class AbstractPaymentClient(ABC, HttpClient):
    config: _PaymentConfig
    create_payment_dto: TCreatePaymentDto
    webhook_schema: Type[TPaymentWebhookSchema] = None
    include_webhooks: bool = False

    def __init__(self, callback_url: str = None, httpx_client: httpx.AsyncClient = None):
        HttpClient.__init__(self, httpx_client=httpx_client)
        self.callback_url = callback_url

    @classmethod
    @abstractmethod
    def from_env_file(cls, env_file_path: str = '.env', **kwargs) -> 'AbstractPaymentClient':
        """Создает инстанс класса подтягивая конфиг из .env (env_file_path) файла"""

    @property
    def supports_webhooks(self) -> bool:
        if not self.include_webhooks or not self.webhook_schema:
            return False
        return True

    # =============================== Методы для вызова API ============================== #
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

    # =============================== Методы для работы с вебхуками ============================== #
    @require_webhooks
    def check_webhook_sign(self, data: TPaymentWebhookSchema, headers: dict) -> bool:
        """Проверяет подпись запроса
        Args:
            data:
                Тело запроса
            headers:
                Заголовки запроса
        Returns:
            bool:
                True - если подпись верна, иначе False
        """

    @require_webhooks
    def get_webhooks(
            self,
            process_func: Callable[[TPaymentWebhookSchema], Awaitable[bool]],
            path: str = ""
    ) -> WebhooksDto:
        """Создает ручки-вебхуков для различных фреймворков

        Args:
          process_func:
              Функция обрабатывающая платеж.
              На вход принимает тело запроса, которое отправляет платежная система в вебухке.
              Возвращает True - если платеж можно считать успешно засчитанным, иначе False.
          check_sign_func:
            Функция проверяющая подпись платежа.
            На вход принимает:
                data: BaseModel - тело запроса, которое отправляет платежная система в вебухке.
                headers: dict | None - заголовки запроса
          path:
              Путь к вебхук ручке
              Пример:
                  path='/webhook/platima'
                  path='/webhook/cryptobot'
        Returns:
           WebhooksDto: датакласс с вебхуками для различных фреймворков
        """

        def _fastapi():
            from fastapi import APIRouter, Request
            from fastapi.responses import JSONResponse
            from pydantic import ValidationError

            router = APIRouter()

            webhook_schema = self.webhook_schema

            @router.post(path=path)
            async def webhook(request: Request):
                content = 'not-ok'
                status_code = 500

                try:
                    content_type = request.headers.get('content-type', '')

                    if 'multipart/form-data' in content_type or 'application/x-www-form-urlencoded' in content_type:
                        form_data = await request.form()
                        raw_data = dict(form_data)
                    else:
                        raw_data = await request.json()

                    data = webhook_schema(**raw_data)
                except (ValidationError, ValueError, Exception):
                    return JSONResponse(content=content, status_code=status_code)

                if not self.check_webhook_sign(data, dict(request.headers)):
                    return JSONResponse(content=content, status_code=status_code)

                try:
                    res = await process_func(data)
                    if res:
                        content = 'ok'
                        status_code = 200
                except Exception:
                    ...

                return JSONResponse(content=content, status_code=status_code)

            return router

        def _aiohttp():
            import json
            from aiohttp import web
            from pydantic import ValidationError

            routes = web.RouteTableDef()

            @routes.post(path)
            async def webhook(request: web.Request) -> web.Response:
                content = 'not-ok'
                status_code = 500

                try:
                    content_type = request.headers.get('content-type', '')
                    if 'multipart/form-data' in content_type or 'application/x-www-form-urlencoded' in content_type:
                        form_data = await request.post()
                        raw_data = dict(form_data)
                    else:
                        raw_data = await request.json()

                    if not isinstance(raw_data, dict):
                        return web.json_response(data=content, status=status_code)

                    data = self.webhook_schema(**raw_data)
                except (json.JSONDecodeError, ValidationError, ValueError):
                    return web.json_response(data=content, status=status_code)

                if not self.check_webhook_sign(data, request.headers):
                    return web.json_response(data=content, status=status_code)

                try:
                    result = await process_func(data)
                    if result:
                        content = 'ok'
                        status_code = 200
                except Exception:
                    ...

                return web.json_response(data=content, status=status_code)

            return routes

        def _flask():
            import json
            from flask import Blueprint, jsonify, request
            from pydantic import ValidationError

            blueprint = Blueprint(
                path.strip('/').replace('/', '_') or f'{self.__name__[:len("Client")]}_webhook',
                __name__
            )

            @blueprint.route(path, methods=['POST'])
            async def webhook():
                content = 'not-ok'
                status_code = 500

                try:
                    content_type = request.headers.get('content-type', '')
                    if 'multipart/form-data' in content_type or 'application/x-www-form-urlencoded' in content_type:
                        raw_data = dict(request.form)
                    else:
                        raw_data = request.get_json()

                    if not isinstance(raw_data, dict):
                        return jsonify(content), status_code

                    data = self.webhook_schema(**raw_data)
                except (json.JSONDecodeError, ValidationError, ValueError):
                    return jsonify(content), status_code

                if not self.check_webhook_sign(data, dict(request.headers)):
                    return jsonify(content), status_code

                try:
                    res = await process_func(data)
                    if res:
                        content = 'ok'
                        status_code = 200
                except Exception:
                    ...

                return jsonify(content), status_code

            return blueprint

        def _django():
            import json
            from django.urls import path as django_path
            from django.http import JsonResponse, HttpRequest
            from django.views.decorators.csrf import csrf_exempt
            from django.views.decorators.http import require_POST
            from pydantic import ValidationError
            import asyncio

            @csrf_exempt
            @require_POST
            async def webhook_view(request: HttpRequest) -> JsonResponse:
                status_code = 500
                content = 'not-ok'

                try:
                    content_type = request.headers.get('content-type', '')
                    if 'multipart/form-data' in content_type or 'application/x-www-form-urlencoded' in content_type:
                        raw_data = dict(request.POST)
                    else:
                        raw_data = json.loads(request.body)

                    if not isinstance(raw_data, dict):
                        return JsonResponse(data=content, status=status_code)

                    data = self.webhook_schema(**raw_data)
                except (json.JSONDecodeError, ValidationError, ValueError):
                    return JsonResponse(data=content, status=status_code)

                if not self.check_webhook_sign(data, dict(request.headers)):
                    return JsonResponse(data=content, status=status_code)

                try:
                    result = await process_func(data)
                    if result:
                        content = 'ok'
                        status_code = 200
                except Exception:
                    ...

                return JsonResponse(data=content, status=status_code)

            clean_path = path.lstrip('/')
            view_name = path.lstrip('/').replace('/', '_') or f'{self.__name__[:len("Client")]}_webhook'

            return django_path(clean_path, webhook_view, name=view_name)

        return WebhooksDto(
            flask=_flask(),
            fastapi=_fastapi(),
            django=_django(),
            aiohttp=_aiohttp()
        )
