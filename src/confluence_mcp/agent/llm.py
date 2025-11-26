import os
from typing import Optional
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

def get_llm(provider: str = "openai", model: Optional[str] = None) -> BaseChatModel:
    """
    Factory to get a LangChain ChatModel based on provider and model name.
    """
    provider = provider.lower()
    
    if provider == "openai":
        model = model or "gpt-4o"
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        return ChatOpenAI(model=model, api_key=api_key, temperature=0)
        
    elif provider == "anthropic":
        model = model or "claude-3-5-sonnet-20240620"
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")
        return ChatAnthropic(model=model, api_key=api_key, temperature=0)
        
    elif provider == "google":
        model = model or "gemini-1.5-pro"
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment")
        return ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=0)
        
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
