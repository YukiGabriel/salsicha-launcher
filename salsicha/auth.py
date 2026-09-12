"""Auth offline + Microsoft (via minecraft-launcher-lib)."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import minecraft_launcher_lib

CONFIG_DIR = Path.home() / ".salsicha-launcher"
ACCOUNTS_FILE = CONFIG_DIR / "accounts.json"
LOCAL_ACCOUNTS_FILE = CONFIG_DIR / "local_accounts.json"

CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_local_accounts() -> dict:
    """Contas locais (sem Microsoft): {nick: {name, uuid, created}}."""
    if not LOCAL_ACCOUNTS_FILE.exists():
        return {}
    try:
        data = json.loads(LOCAL_ACCOUNTS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_local_account(username: str) -> dict:
    """Cria (ou confirma) a conta local e retorna a entrada salva."""
    username = (username or "").strip()
    accounts = load_local_accounts()
    if username in accounts and isinstance(accounts[username], dict):
        return accounts[username]
    import time as _t
    entry = {"name": username, "uuid": get_offline_uuid(username),
             "created": int(_t.time()), "_type": "local"}
    accounts[username] = entry
    LOCAL_ACCOUNTS_FILE.write_text(json.dumps(accounts, indent=2, ensure_ascii=False),
                                   encoding="utf-8")
    return entry


def remove_local_account(username: str) -> None:
    accounts = load_local_accounts()
    if username in accounts:
        del accounts[username]
        LOCAL_ACCOUNTS_FILE.write_text(json.dumps(accounts, indent=2, ensure_ascii=False),
                                       encoding="utf-8")


def get_offline_uuid(username: str) -> str:
    """UUID offline padrão (Mojang offline). Sem traços, como o jogo espera."""
    return str(uuid.uuid3(uuid.NAMESPACE_OID, f"OfflinePlayer:{username}")).replace("-", "")


def offline_options(username: str) -> dict:
    return {
        "username": username,
        "uuid": get_offline_uuid(username),
        "token": "0",
    }


def get_login_url(client_id: str, redirect_uri: str):
    """Retorna (login_url, state, code_verifier) para abrir no navegador."""
    return minecraft_launcher_lib.microsoft_account.get_login_url(client_id, redirect_uri)


def complete_login(client_id: str, client_secret, redirect_uri: str, auth_code: str, code_verifier: str) -> dict:
    return minecraft_launcher_lib.microsoft_account.complete_login(
        client_id, client_secret, redirect_uri, auth_code, code_verifier
    )


def extract_code_from_url(url: str, state: str | None = None) -> str:
    """Aceita URL completa de retorno ou code puro. Usa helpers da lib."""
    ms = minecraft_launcher_lib.microsoft_account
    url = url.strip()
    try:
        if ms.url_contains_auth_code(url):
            code = ms.get_auth_code_from_url(url)
            if code:
                return code
    except Exception:
        pass
    from urllib.parse import urlparse, parse_qs

    q = parse_qs(urlparse(url).query)
    if "code" in q:
        return q["code"][0]
    return url


def save_account(name: str, data: dict) -> None:
    accounts = load_accounts()
    accounts[name] = data
    ACCOUNTS_FILE.write_text(json.dumps(accounts, indent=2), encoding="utf-8")


def load_accounts() -> dict:
    if not ACCOUNTS_FILE.exists():
        return {}
    try:
        return json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def microsoft_options(login_data: dict) -> dict:
    return {
        "username": login_data["name"],
        "uuid": login_data["id"],
        "token": login_data["access_token"],
    }


def refresh_login(client_id: str, redirect_uri: str, stored: dict) -> dict:
    """Renova via refresh_token. Levanta InvalidRefreshToken se expirado."""
    ms = minecraft_launcher_lib.microsoft_account
    return ms.complete_refresh(client_id, None, redirect_uri, stored["refresh_token"])


def validate_profile(access_token: str) -> dict | None:
    """Retorna perfil ou None se token inválido."""
    try:
        return minecraft_launcher_lib.microsoft_account.get_profile(access_token)
    except Exception:
        return None


# ---------- login fácil por código de dispositivo (sem app Azure) ----------
# Mesmo mecanismo do launcher oficial: o jogo mostra um código, o senhor
# confirma em microsoft.com/link no navegador/celular. Nada de Client ID.
DEVICE_CLIENT_ID = "00000000402b5328"
DEVICE_SCOPE = "service::user.auth.xboxlive.com::MBI_SSL"


class DevicePending(Exception):
    """O senhor ainda não confirmou o código."""


class DeviceDeclined(Exception):
    pass


class DeviceExpired(Exception):
    pass


class XboxError(Exception):
    def __init__(self, msg: str, xerr: str = ""):
        super().__init__(msg)
        self.xerr = xerr


def device_start() -> dict:
    """Pede um código à Microsoft. Retorna {user_code, device_code, verification_uri, ...}."""
    import requests

    r = requests.post(
        "https://login.live.com/oauth20_connect.srf",
        data={"client_id": DEVICE_CLIENT_ID, "scope": DEVICE_SCOPE,
              "response_type": "device_code", "display": "touch"},
        headers={"User-Agent": "Salsicha-Launcher/0.1.0"}, timeout=20)
    r.raise_for_status()
    return r.json()


def device_poll(device_code: str) -> dict:
    """Troca o device_code por tokens. Levanta DevicePending/Declined/Expired."""
    import requests

    try:
        r = requests.post(
            "https://login.live.com/oauth20_token.srf",
            data={"grant_type": "device_code", "client_id": DEVICE_CLIENT_ID,
                  "device_code": device_code, "scope": DEVICE_SCOPE},
            headers={"User-Agent": "Salsicha-Launcher/0.1.0"}, timeout=20)
    except Exception as e:
        raise DevicePending(str(e))
    if r.status_code != 200:
        try:
            err = r.json().get("error", "")
        except Exception:
            err = ""
        if err == "authorization_declined":
            raise DeviceDeclined("Login recusado na Microsoft.")
        if err in ("expired_token", "bad_verification_code"):
            raise DeviceExpired("O código expirou — gere outro.")
        raise DevicePending(err or f"HTTP {r.status_code}")
    return r.json()


def device_refresh(refresh_token: str) -> dict:
    """Renova via refresh_token do fluxo de dispositivo."""
    import requests

    r = requests.post(
        "https://login.live.com/oauth20_token.srf",
        data={"grant_type": "refresh_token", "client_id": DEVICE_CLIENT_ID,
              "refresh_token": refresh_token, "scope": DEVICE_SCOPE},
        headers={"User-Agent": "Salsicha-Launcher/0.1.0"}, timeout=20)
    r.raise_for_status()
    return r.json()


_XERR_MEANING = {
    "2148916233": "esta conta não tem Xbox — entre em xbox.com e crie o perfil",
    "2148916238": "conta infantil: peça ao responsável em family.microsoft.com",
    "2148916235": "Xbox bloqueado em sua região",
    "2148916229": "conta banida no Xbox",
}


def _xbox_login(ms_access_token: str) -> tuple[str, str]:
    """(uhs, xsts_token) a partir do token da Microsoft."""
    import requests

    r = requests.post("https://user.auth.xboxlive.com/user/authenticate",
                      json={"Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com",
                                           "RpsTicket": f"d={ms_access_token}"},
                            "RelyingParty": "http://auth.xboxlive.com", "TokenType": "JWT"},
                      timeout=20)
    r.raise_for_status()
    xbl = r.json()["Token"]
    r = requests.post("https://xsts.auth.xboxlive.com/xsts/authorize",
                      json={"Properties": {"SandboxId": "RETAIL", "UserTokens": [xbl]},
                            "RelyingParty": "rp://api.minecraftservices.com/", "TokenType": "JWT"},
                      timeout=20)
    data = r.json()
    if "Token" not in data:
        xerr = str(data.get("XErr", ""))
        raise XboxError(_XERR_MEANING.get(xerr, f"Xbox recusou (XErr {xerr or '?'})."), xerr)
    uhs = data["DisplayClaims"]["xui"][0]["uhs"]
    return uhs, data["Token"]


def device_complete(tokens: dict) -> dict:
    """tokens (com access_token) -> login_data pronto p/ salvar (name, id, ...)."""
    import requests

    uhs, xsts = _xbox_login(tokens["access_token"])
    r = requests.post("https://api.minecraftservices.com/authentication/login_with_xbox",
                      json={"identityToken": f"XBL3.0 x={uhs};{xsts}"}, timeout=20)
    r.raise_for_status()
    mc = r.json()
    prof = validate_profile(mc["access_token"])
    if not prof or "name" not in prof:
        raise XboxError("Esta conta Microsoft não tem Minecraft Java comprado.")
    return {"name": prof["name"], "id": prof["id"],
            "access_token": mc["access_token"],
            "refresh_token": tokens.get("refresh_token", ""),
            "expires_in": mc.get("expires_in", 86400),
            "_client_id": "DEVICE", "_redirect": ""}


def device_refresh_login(stored: dict) -> dict:
    """Renova uma conta DEVICE salva. Levanta exceção se precisar relogar."""
    if not stored.get("refresh_token"):
        raise DeviceExpired("Sem refresh — entre de novo.")
    tokens = device_refresh(stored["refresh_token"])
    data = device_complete(tokens)
    data["_client_id"] = "DEVICE"
    return data
