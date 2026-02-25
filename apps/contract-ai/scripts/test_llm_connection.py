#!/usr/bin/env python3
"""
Test script for LLM API connections
Tests connectivity to DeepSeek, Claude, and OpenAI APIs
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.llm_config import get_llm_config
import asyncio
import httpx


class LLMConnectionTester:
    def __init__(self):
        self.config = get_llm_config()
        self.results = {}

    async def test_deepseek(self) -> dict:
        """Test DeepSeek API connection"""
        print("\n🔍 Testing DeepSeek-V3 API...")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.config.DEEPSEEK_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.config.DEEPSEEK_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.config.DEEPSEEK_MODEL,
                        "messages": [{"role": "user", "content": "Hello, test message"}],
                        "max_tokens": 10,
                        "temperature": 0.1
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ DeepSeek-V3: Connected successfully")
                    print(f"   Model: {self.config.DEEPSEEK_MODEL}")
                    print(f"   Response: {data.get('choices', [{}])[0].get('message', {}).get('content', 'N/A')[:50]}...")
                    return {"status": "success", "model": self.config.DEEPSEEK_MODEL}
                else:
                    print(f"❌ DeepSeek-V3: Failed (Status {response.status_code})")
                    print(f"   Error: {response.text[:200]}")
                    return {"status": "failed", "error": response.text}

        except Exception as e:
            print(f"❌ DeepSeek-V3: Connection error")
            print(f"   Error: {str(e)}")
            return {"status": "error", "error": str(e)}

    async def test_claude(self) -> dict:
        """Test Anthropic Claude API connection"""
        print("\n🔍 Testing Claude 4.5 Sonnet API...")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.config.ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.config.ANTHROPIC_MODEL,
                        "messages": [{"role": "user", "content": "Hello, test message"}],
                        "max_tokens": 10,
                        "temperature": 0.1
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Claude 4.5: Connected successfully")
                    print(f"   Model: {self.config.ANTHROPIC_MODEL}")
                    print(f"   Response: {data.get('content', [{}])[0].get('text', 'N/A')[:50]}...")
                    return {"status": "success", "model": self.config.ANTHROPIC_MODEL}
                else:
                    print(f"❌ Claude 4.5: Failed (Status {response.status_code})")
                    print(f"   Error: {response.text[:200]}")
                    return {"status": "failed", "error": response.text}

        except Exception as e:
            print(f"❌ Claude 4.5: Connection error")
            print(f"   Error: {str(e)}")
            return {"status": "error", "error": str(e)}

    async def test_openai(self, model: str = None) -> dict:
        """Test OpenAI API connection"""
        model = model or self.config.OPENAI_MODEL
        print(f"\n🔍 Testing OpenAI {model} API...")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.config.OPENAI_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "Hello, test message"}],
                        "max_tokens": 10,
                        "temperature": 0.1
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ OpenAI {model}: Connected successfully")
                    print(f"   Model: {model}")
                    print(f"   Response: {data.get('choices', [{}])[0].get('message', {}).get('content', 'N/A')[:50]}...")
                    return {"status": "success", "model": model}
                else:
                    print(f"❌ OpenAI {model}: Failed (Status {response.status_code})")
                    print(f"   Error: {response.text[:200]}")
                    return {"status": "failed", "error": response.text}

        except Exception as e:
            print(f"❌ OpenAI {model}: Connection error")
            print(f"   Error: {str(e)}")
            return {"status": "error", "error": str(e)}

    async def run_all_tests(self):
        """Run all API connection tests"""
        print("=" * 60)
        print("🚀 Contract AI System v2.0 - LLM API Connection Tests")
        print("=" * 60)

        # Test DeepSeek
        self.results["deepseek"] = await self.test_deepseek()

        # Test Claude
        self.results["claude"] = await self.test_claude()

        # Test GPT-4o
        self.results["gpt-4o"] = await self.test_openai(self.config.OPENAI_MODEL)

        # Test GPT-4o-mini
        self.results["gpt-4o-mini"] = await self.test_openai(self.config.OPENAI_MODEL_MINI)

        # Summary
        print("\n" + "=" * 60)
        print("📊 Test Results Summary")
        print("=" * 60)

        success_count = sum(1 for r in self.results.values() if r["status"] == "success")
        total_count = len(self.results)

        for name, result in self.results.items():
            status_icon = "✅" if result["status"] == "success" else "❌"
            print(f"{status_icon} {name:15s} - {result['status']}")

        print(f"\n✅ {success_count}/{total_count} APIs connected successfully")

        if success_count < total_count:
            print("\n⚠️  Some APIs failed to connect. Check your .env file and API keys.")
            return False
        else:
            print("\n🎉 All APIs connected successfully! System ready to use.")
            return True


async def main():
    """Main entry point"""
    tester = LLMConnectionTester()

    # Show config
    print("\n📋 Configuration:")
    print(f"   Default model: {tester.config.ROUTER_DEFAULT_MODEL}")
    print(f"   Complexity threshold: {tester.config.ROUTER_COMPLEXITY_THRESHOLD}")
    print(f"   RAG enabled: {tester.config.RAG_ENABLED}")
    print(f"   RAG top-k: {tester.config.RAG_TOP_K}")

    # Run tests
    success = await tester.run_all_tests()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
