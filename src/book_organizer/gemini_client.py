# -*- coding: utf-8 -*-
"""Lazy Gemini SDK helpers for the packaged macOS app.

Importing google.generativeai loads grpc native modules immediately. Keeping the
SDK out of startup paths avoids grpc shutdown crashes when the app exits.
"""

from typing import Any


def get_genai() -> Any | None:
    try:
        import google.generativeai as genai
    except ImportError:
        return None
    return genai


def configure_genai(api_key: str) -> Any | None:
    genai = get_genai()
    if genai is None:
        return None
    genai.configure(api_key=api_key, transport="rest")
    return genai


def create_gemini_model(api_key: str, model_name: str) -> Any | None:
    genai = configure_genai(api_key)
    if genai is None:
        return None
    return genai.GenerativeModel(model_name)
