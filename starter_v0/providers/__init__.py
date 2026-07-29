from providers.openai_provider import OpenAIProvider
from providers.openrouter_provider import OpenRouterProvider
from providers.anthropic_provider import AnthropicProvider
from providers.gemini_provider import GeminiProvider
from providers.yescale_provider import YeScaleProvider


# Single source of truth for the --provider CLI choices (chat.py, run_eval.py,
# scripts/preflight_provider.py) so a new provider never has to be added twice.
PROVIDERS = {
    "openai": OpenAIProvider,
    "openrouter": OpenRouterProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "yescale": YeScaleProvider,
}

PROVIDER_CHOICES = sorted(PROVIDERS)


def make_provider(name: str):
    try:
        factory = PROVIDERS[name]
    except KeyError:
        raise ValueError(f"Unknown provider: {name}. Choose one of: {', '.join(PROVIDER_CHOICES)}") from None
    return factory()
