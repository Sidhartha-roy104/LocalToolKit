"""Tests for /api/health and server binding."""
from __future__ import annotations
import socket


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["host"] == "127.0.0.1"
    assert "dependencies" in data


def test_server_only_binds_loopback():
    """Verify our config only ever sets HOST to 127.0.0.1."""
    from backend.config import HOST
    assert HOST == "127.0.0.1", "Server must bind to loopback only!"


def test_spa_fallback(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"LocalToolkit" in r.content


def test_openapi(client):
    r = client.get("/api/openapi.json")
    assert r.status_code == 200

