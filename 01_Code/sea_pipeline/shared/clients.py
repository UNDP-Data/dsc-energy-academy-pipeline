from __future__ import annotations

from openai import AsyncAzureOpenAI, AzureOpenAI

from .env import EnvConfig


def build_async_azure_openai_client(env: EnvConfig) -> AsyncAzureOpenAI:
    return AsyncAzureOpenAI(
        api_key=env.azure_openai_api_key,
        azure_endpoint=env.azure_openai_endpoint,
        api_version=env.azure_openai_api_version,
    )


def build_azure_openai_client(env: EnvConfig) -> AzureOpenAI:
    return AzureOpenAI(
        api_key=env.azure_openai_api_key,
        azure_endpoint=env.azure_openai_endpoint,
        api_version=env.azure_openai_api_version,
    )
