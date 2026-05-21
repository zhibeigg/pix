"""支付宝/微信支付 Provider。"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from time import time
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

import httpx
from fastapi import HTTPException, status
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.orm import Session

from pix_web.billing import create_payment_order, mark_order_paid
from pix_web.config import WebSettings
from pix_web.models import PaymentOrder, User


@dataclass(frozen=True)
class CheckoutResult:
    order: PaymentOrder
    provider: str
    payment_url: str | None = None
    code_url: str | None = None


def _read_secret(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    try:
        path = Path(value)
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return value.replace("\\n", "\n")


def _require(value: str, name: str) -> str:
    clean = _read_secret(value)
    if not clean:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"{name} 未配置")
    return clean


def _load_private_key(raw: str):
    key = _require(raw, "支付私钥").encode("utf-8")
    return serialization.load_pem_private_key(key, password=None)


def _load_public_key(raw: str):
    key = _require(raw, "支付公钥").encode("utf-8")
    return serialization.load_pem_public_key(key)


def _rsa_sign(private_key_raw: str, message: str) -> str:
    private_key = _load_private_key(private_key_raw)
    signature = private_key.sign(message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode("ascii")


def _rsa_verify_with_public_key(public_key: Any, message: str, signature_b64: str) -> bool:
    try:
        signature = base64.b64decode(signature_b64)
        public_key.verify(signature, message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


def _rsa_verify(public_key_raw: str, message: str, signature_b64: str) -> bool:
    try:
        return _rsa_verify_with_public_key(_load_public_key(public_key_raw), message, signature_b64)
    except Exception:
        return False


_PEM_CERT_RE = re.compile(
    r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", re.DOTALL
)


def _load_pem_certificates(raw: str, name: str) -> list[x509.Certificate]:
    content = _require(raw, name)
    blocks = _PEM_CERT_RE.findall(content)
    if not blocks:
        blocks = [content]
    certs: list[x509.Certificate] = []
    for block in blocks:
        try:
            certs.append(x509.load_pem_x509_certificate(block.encode("utf-8")))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"{name} 格式不正确") from exc
    return certs


def _load_pem_certificate(raw: str, name: str) -> x509.Certificate:
    return _load_pem_certificates(raw, name)[0]


def _certificate_sn(cert: x509.Certificate) -> str:
    issuer = cert.issuer.rfc4514_string()
    serial = str(cert.serial_number)
    return hashlib.md5(f"{issuer}{serial}".encode("utf-8")).hexdigest()


def _certificate_public_key(raw: str, name: str):
    return _load_pem_certificate(raw, name).public_key()


def _is_rsa_certificate(cert: x509.Certificate) -> bool:
    signature_name = getattr(cert.signature_algorithm_oid, "_name", "").upper()
    return "RSA" in signature_name or isinstance(cert.public_key(), rsa.RSAPublicKey)


def _alipay_app_cert_sn(settings: WebSettings) -> str:
    return _certificate_sn(_load_pem_certificate(settings.alipay_app_cert, "ALIPAY_APP_CERT"))


def _alipay_root_cert_sn(settings: WebSettings) -> str:
    certs = _load_pem_certificates(settings.alipay_root_cert, "ALIPAY_ROOT_CERT")
    serials = [_certificate_sn(cert) for cert in certs if _is_rsa_certificate(cert)]
    if not serials:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="ALIPAY_ROOT_CERT 未包含 RSA 根证书")
    return "_".join(serials)


def _alipay_mode(settings: WebSettings) -> str:
    mode = settings.alipay_mode.lower()
    if mode == "certificate":
        return "certificate"
    if mode == "public_key":
        return "public_key"
    if settings.alipay_app_cert or settings.alipay_public_cert or settings.alipay_root_cert:
        return "certificate"
    return "public_key"


def _alipay_public_key_for_verify(settings: WebSettings):
    if _alipay_mode(settings) == "certificate":
        return _certificate_public_key(settings.alipay_public_cert, "ALIPAY_PUBLIC_CERT")
    return _load_public_key(settings.alipay_public_key)


def _alipay_verify(settings: WebSettings, message: str, signature_b64: str) -> bool:
    try:
        return _rsa_verify_with_public_key(_alipay_public_key_for_verify(settings), message, signature_b64)
    except Exception:
        return False


def _money_yuan(cents: int) -> str:
    return f"{cents / 100:.2f}"


def _public_url(settings: WebSettings, path: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}{path}"


def create_checkout(db: Session, user: User, package_key: str, provider: str, settings: WebSettings) -> CheckoutResult:
    provider = provider.lower()
    if provider == "mock":
        return CheckoutResult(order=create_payment_order(db, user, package_key, provider="mock"), provider="mock")
    if provider == "alipay":
        return create_alipay_checkout(db, user, package_key, settings)
    if provider == "wechat":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="微信支付已关闭")
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="不支持的支付方式")


def _alipay_sign_content(params: dict[str, str]) -> str:
    return "&".join(f"{key}={params[key]}" for key in sorted(params) if params[key] != "")


def create_alipay_checkout(db: Session, user: User, package_key: str, settings: WebSettings) -> CheckoutResult:
    app_id = _require(settings.alipay_app_id, "ALIPAY_APP_ID")
    mode = _alipay_mode(settings)
    if mode == "certificate":
        _require(settings.alipay_app_cert, "ALIPAY_APP_CERT")
        _require(settings.alipay_public_cert, "ALIPAY_PUBLIC_CERT")
        _require(settings.alipay_root_cert, "ALIPAY_ROOT_CERT")
    else:
        _require(settings.alipay_public_key, "ALIPAY_PUBLIC_KEY")
    order = create_payment_order(db, user, package_key, provider="alipay")
    biz_content = json.dumps(
        {
            "out_trade_no": order.provider_order_id,
            "product_code": "FAST_INSTANT_TRADE_PAY",
            "total_amount": _money_yuan(order.amount_cents),
            "subject": f"Pix Credits {order.credits}",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    params = {
        "app_id": app_id,
        "method": "alipay.trade.page.pay",
        "charset": "utf-8",
        "sign_type": "RSA2",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version": "1.0",
        "notify_url": _public_url(settings, "/billing/webhook/alipay"),
        "return_url": _public_url(settings, f"/billing/return/alipay?order_id={order.id}"),
        "biz_content": biz_content,
    }
    if mode == "certificate":
        params["app_cert_sn"] = _alipay_app_cert_sn(settings)
        params["alipay_root_cert_sn"] = _alipay_root_cert_sn(settings)
    params["sign"] = _rsa_sign(settings.alipay_private_key, _alipay_sign_content(params))
    return CheckoutResult(order=order, provider="alipay", payment_url=f"{settings.alipay_gateway}?{urlencode(params)}")


def handle_alipay_notify(db: Session, form: dict[str, str], settings: WebSettings) -> str:
    signature = form.get("sign", "")
    payload = {key: value for key, value in form.items() if key not in {"sign", "sign_type"}}
    if not _alipay_verify(settings, _alipay_sign_content(payload), signature):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="支付宝通知验签失败")
    if form.get("trade_status") not in {"TRADE_SUCCESS", "TRADE_FINISHED"}:
        return "success"
    out_trade_no = form.get("out_trade_no", "")
    order = db.scalar(select(PaymentOrder).where(PaymentOrder.provider_order_id == out_trade_no, PaymentOrder.provider == "alipay"))
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="支付订单不存在")
    if form.get("total_amount") != _money_yuan(order.amount_cents):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="支付宝通知金额不匹配")
    event_id = form.get("trade_no") or f"alipay:{out_trade_no}:{form.get('notify_id', uuid4().hex)}"
    mark_order_paid(db, order, provider_event_id=f"alipay:{event_id}", payload=dict(form))
    return "success"


def _wechat_path(url: str) -> str:
    if url.startswith("http"):
        from urllib.parse import urlsplit

        parsed = urlsplit(url)
        return parsed.path + (f"?{parsed.query}" if parsed.query else "")
    return url


def _wechat_authorization(settings: WebSettings, method: str, url: str, body: str) -> str:
    mchid = _require(settings.wechat_mch_id, "WECHATPAY_MCH_ID")
    serial = _require(settings.wechat_merchant_serial_no, "WECHATPAY_MERCHANT_SERIAL_NO")
    timestamp = str(int(time()))
    nonce = uuid4().hex
    message = f"{method}\n{_wechat_path(url)}\n{timestamp}\n{nonce}\n{body}\n"
    signature = _rsa_sign(settings.wechat_private_key, message)
    token = (
        f'mchid="{mchid}",nonce_str="{nonce}",signature="{signature}",'
        f'timestamp="{timestamp}",serial_no="{serial}"'
    )
    return f"WECHATPAY2-SHA256-RSA2048 {token}"


def create_wechat_checkout(db: Session, user: User, package_key: str, settings: WebSettings) -> CheckoutResult:
    app_id = _require(settings.wechat_app_id, "WECHATPAY_APP_ID")
    mchid = _require(settings.wechat_mch_id, "WECHATPAY_MCH_ID")
    order = create_payment_order(db, user, package_key, provider="wechat")
    url = f"{settings.wechat_api_base}/v3/pay/transactions/native"
    body_obj = {
        "appid": app_id,
        "mchid": mchid,
        "description": f"Pix Credits {order.credits}",
        "out_trade_no": order.provider_order_id,
        "notify_url": _public_url(settings, "/billing/webhook/wechat"),
        "amount": {"total": order.amount_cents, "currency": "CNY"},
    }
    body = json.dumps(body_obj, ensure_ascii=False, separators=(",", ":"))
    headers = {
        "Authorization": _wechat_authorization(settings, "POST", url, body),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    try:
        response = httpx.post(url, content=body.encode("utf-8"), headers=headers, timeout=15)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"微信下单失败: {exc}") from exc
    code_url = response.json().get("code_url")
    if not code_url:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="微信下单未返回 code_url")
    return CheckoutResult(order=order, provider="wechat", code_url=code_url)


def _wechat_verify(headers: dict[str, str], body: str, settings: WebSettings) -> None:
    timestamp = headers.get("wechatpay-timestamp", "")
    nonce = headers.get("wechatpay-nonce", "")
    signature = headers.get("wechatpay-signature", "")
    message = f"{timestamp}\n{nonce}\n{body}\n"
    if not _rsa_verify(settings.wechat_platform_cert, message, signature):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="微信通知验签失败")


def _wechat_decrypt_resource(resource: dict[str, Any], settings: WebSettings) -> dict[str, Any]:
    key = _require(settings.wechat_api_v3_key, "WECHATPAY_API_V3_KEY").encode("utf-8")
    if len(key) != 32:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="WECHATPAY_API_V3_KEY 必须为 32 字节")
    aesgcm = AESGCM(key)
    ciphertext = base64.b64decode(resource["ciphertext"])
    nonce = resource["nonce"].encode("utf-8")
    aad = resource.get("associated_data", "").encode("utf-8")
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, aad)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="微信通知解密失败") from exc
    return json.loads(plaintext.decode("utf-8"))


def handle_wechat_notify(db: Session, headers: dict[str, str], body: bytes, settings: WebSettings) -> dict[str, str]:
    raw = body.decode("utf-8")
    normalized_headers = {key.lower(): value for key, value in headers.items()}
    _wechat_verify(normalized_headers, raw, settings)
    payload = json.loads(raw)
    data = _wechat_decrypt_resource(payload["resource"], settings)
    if data.get("trade_state") != "SUCCESS":
        return {"code": "SUCCESS", "message": "成功"}
    out_trade_no = data.get("out_trade_no", "")
    order = db.scalar(select(PaymentOrder).where(PaymentOrder.provider_order_id == out_trade_no, PaymentOrder.provider == "wechat"))
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="支付订单不存在")
    amount = data.get("amount") or {}
    if int(amount.get("total", -1)) != order.amount_cents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="微信通知金额不匹配")
    event_id = data.get("transaction_id") or f"wechat:{out_trade_no}"
    mark_order_paid(db, order, provider_event_id=f"wechat:{event_id}", payload=data)
    return {"code": "SUCCESS", "message": "成功"}
