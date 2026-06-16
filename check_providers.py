#!/usr/bin/env python3
"""
Diagnostic script to check all AI providers for food analysis.
Run this to verify configuration and connectivity.
"""
import sys
import json
import time
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings
from app import ml_service

def check_gemini():
    """Check Gemini provider."""
    print("\n🔍 Checking Gemini Provider...")
    print(f"   API Key: {'✅ Set' if settings.GEMINI_API_KEY else '❌ Missing'}")
    print(f"   Model: {settings.GEMINI_MODEL}")
    
    if not settings.GEMINI_API_KEY:
        print("   ⚠️  Set GEMINI_API_KEY environment variable to use Gemini")
        return False
    
    try:
        provider = ml_service._get_provider_by_name("gemini")
        provider._ensure_client()
        print("   ✅ Gemini client initialized successfully")
        return True
    except Exception as e:
        print(f"   ❌ Gemini error: {e}")
        return False


def check_deepseek():
    """Check DeepSeek provider."""
    print("\n🔍 Checking DeepSeek Provider...")
    print(f"   API Key: {'✅ Set' if settings.DEEPSEEK_API_KEY else '❌ Missing'}")
    print(f"   API URL: {'✅ Set' if settings.DEEPSEEK_VISION_API_URL else '❌ Missing'}")
    print(f"   Model: {settings.DEEPSEEK_VISION_MODEL}")
    
    if not settings.DEEPSEEK_API_KEY or not settings.DEEPSEEK_VISION_API_URL:
        print("   ⚠️  Set DEEPSEEK_API_KEY and DEEPSEEK_VISION_API_URL to use DeepSeek")
        return False
    
    print("   ✅ DeepSeek credentials configured")
    return True


def check_ollama():
    """Check Ollama provider."""
    print("\n🔍 Checking Ollama Provider...")
    print(f"   Host: {settings.OLLAMA_HOST}")
    print(f"   Model: {settings.OLLAMA_MODEL}")
    
    import httpx
    try:
        client = httpx.Client(timeout=5.0)
        response = client.get(f"{settings.OLLAMA_HOST}/api/tags")
        response.raise_for_status()
        data = response.json()
        models = [m.get("name") for m in data.get("models", [])]
        
        if settings.OLLAMA_MODEL in models:
            print(f"   ✅ Ollama is running with model {settings.OLLAMA_MODEL}")
            return True
        else:
            print(f"   ⚠️  Ollama is running but model '{settings.OLLAMA_MODEL}' not found")
            print(f"      Available models: {models}")
            return False
    except httpx.ConnectError:
        print(f"   ❌ Cannot connect to Ollama at {settings.OLLAMA_HOST}")
        print("      Make sure Ollama service is running")
        return False
    except Exception as e:
        print(f"   ❌ Ollama error: {e}")
        return False
    finally:
        client.close()


def check_redis():
    """Check Redis connection."""
    print("\n🔍 Checking Redis Connection...")
    print(f"   URL: {settings.REDIS_URL}")
    
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL, decode_responses=True)
        r.ping()
        print("   ✅ Redis is connected")
        return True
    except Exception as e:
        print(f"   ❌ Redis error: {e}")
        return False


def main():
    """Run all checks."""
    print("=" * 60)
    print("🚀 AI Provider Configuration Check")
    print("=" * 60)
    
    results = {
        "redis": check_redis(),
        "gemini": check_gemini(),
        "deepseek": check_deepseek(),
        "ollama": check_ollama(),
    }
    
    print("\n" + "=" * 60)
    print("📊 Summary:")
    print("=" * 60)
    
    for provider, status in results.items():
        icon = "✅" if status else "❌"
        print(f"{icon} {provider.capitalize()}: {'Ready' if status else 'Not Ready'}")
    
    # Check at least one provider is ready
    providers_ready = [k for k, v in results.items() if v and k != "redis"]
    redis_ready = results["redis"]
    
    print("\n" + "=" * 60)
    if redis_ready and providers_ready:
        print(f"✅ System ready! {len(providers_ready)} provider(s) available")
        print(f"   Working providers: {', '.join(providers_ready)}")
        return 0
    else:
        if not redis_ready:
            print("❌ Redis is not available - required for task queue")
        if not providers_ready:
            print("❌ No AI providers are configured")
            print("\nTo enable providers:")
            print("  1. For Gemini: Set GEMINI_API_KEY")
            print("  2. For DeepSeek: Set DEEPSEEK_API_KEY and DEEPSEEK_VISION_API_URL")
            print("  3. For Ollama: Run Ollama service and load a model")
        return 1


if __name__ == "__main__":
    sys.exit(main())
