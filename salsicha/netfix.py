"""Força IPv4 primeiro (Mojang IPv6 trava nesta rede)."""
import socket

_orig_getaddrinfo = socket.getaddrinfo
_done = False


def force_ipv4():
    global _done
    if _done:
        return
    _done = True

    def patched(host, port, family=0, *args, **kwargs):
        try:
            res = _orig_getaddrinfo(host, port, family, *args, **kwargs)
        except Exception:
            return _orig_getaddrinfo(host, port, family, *args, **kwargs)
        # IPv4 (AF_INET=2) primeiro
        res.sort(key=lambda r: 0 if r[0] == socket.AF_INET else 1)
        return res

    socket.getaddrinfo = patched
