import hashlib

from app.services import click as click_service


class TestPremiumPlans:
    def test_three_durations_with_expected_prices(self):
        assert click_service.PREMIUM_PLANS["premium_1_day"].amount == 8_000
        assert click_service.PREMIUM_PLANS["premium_1_day"].days == 1
        assert click_service.PREMIUM_PLANS["premium_1_week"].amount == 20_000
        assert click_service.PREMIUM_PLANS["premium_1_week"].days == 7
        assert click_service.PREMIUM_PLANS["premium_1_month"].amount == 37_000
        assert click_service.PREMIUM_PLANS["premium_1_month"].days == 30


class TestClickSignatures:
    def test_prepare_signature_accepts_correctly_signed_payload(self, monkeypatch):
        monkeypatch.setattr(click_service.settings, "click_secret_key", "test_secret")
        data = {
            "click_trans_id": "111",
            "service_id": "222",
            "merchant_trans_id": "333-abc",
            "amount": "8000",
            "action": "0",
            "sign_time": "2026-01-01 00:00:00",
        }
        data["sign_string"] = hashlib.md5(
            (
                data["click_trans_id"]
                + data["service_id"]
                + "test_secret"
                + data["merchant_trans_id"]
                + data["amount"]
                + data["action"]
                + data["sign_time"]
            ).encode("utf-8")
        ).hexdigest()

        assert click_service.verify_prepare_signature(data) is True

    def test_prepare_signature_rejects_tampered_amount(self, monkeypatch):
        monkeypatch.setattr(click_service.settings, "click_secret_key", "test_secret")
        data = {
            "click_trans_id": "111",
            "service_id": "222",
            "merchant_trans_id": "333-abc",
            "amount": "8000",
            "action": "0",
            "sign_time": "2026-01-01 00:00:00",
            "sign_string": "deadbeef",
        }
        assert click_service.verify_prepare_signature(data) is False

    def test_complete_signature_includes_merchant_prepare_id(self, monkeypatch):
        monkeypatch.setattr(click_service.settings, "click_secret_key", "test_secret")
        data = {
            "click_trans_id": "111",
            "service_id": "222",
            "merchant_trans_id": "333-abc",
            "merchant_prepare_id": "7",
            "amount": "8000",
            "action": "1",
            "sign_time": "2026-01-01 00:00:00",
        }
        data["sign_string"] = hashlib.md5(
            (
                data["click_trans_id"]
                + data["service_id"]
                + "test_secret"
                + data["merchant_trans_id"]
                + data["merchant_prepare_id"]
                + data["amount"]
                + data["action"]
                + data["sign_time"]
            ).encode("utf-8")
        ).hexdigest()

        assert click_service.verify_complete_signature(data) is True


class TestBuildPayUrl:
    def test_raises_when_not_configured(self, monkeypatch):
        monkeypatch.setattr(click_service.settings, "click_service_id", "")
        monkeypatch.setattr(click_service.settings, "click_merchant_id", "")
        try:
            click_service.build_pay_url("order-1", 8_000)
        except click_service.ClickConfigError:
            pass
        else:
            raise AssertionError("expected ClickConfigError")

    def test_builds_url_with_params(self, monkeypatch):
        monkeypatch.setattr(click_service.settings, "click_service_id", "222")
        monkeypatch.setattr(click_service.settings, "click_merchant_id", "333")
        url = click_service.build_pay_url("order-1", 8_000)
        assert url.startswith(click_service.CLICK_PAY_URL)
        assert "service_id=222" in url
        assert "merchant_id=333" in url
        assert "amount=8000" in url
        assert "transaction_param=order-1" in url
