import os
import sys
from langchain.chat_models import init_chat_model
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from src.config.settings import settings
from src.agents.llm import get_llm

print("=== Starting LLM Fallback Verification ===")

# 1. Test Primary LLM
print("\n--- Testing Primary LLM ---")
try:
    primary_model = init_chat_model(
        model=settings.LLM_MODEL,
        api_key=settings.API_KEY,
        base_url=settings.BASE_URL,
    )
    res = primary_model.invoke("Say 'Primary LLM working'")
    print(f"Success! Response: {res.content}")
except Exception as e:
    print(f"Error testing Primary LLM: {e}")

# 2. Test Groq Fallback (First Fallback)
print("\n--- Testing Groq Fallback (First Fallback) ---")
try:
    groq_llm = ChatGroq(
        model=settings.FIRST_FALLBACK_LLM,
        api_key=settings.GROQ_API_KEY,
        max_tokens=512,
        streaming=True,
        reasoning_effort='none'
    )
    res = groq_llm.invoke("Say 'Groq Fallback working'")
    print(f"Success! Response: {res.content}")
except Exception as e:
    print(f"Error testing Groq Fallback: {e}")

# 3. Test Hugging Face Fallback (Second Fallback)
print("\n--- Testing Hugging Face Fallback (Second Fallback) ---")
try:
    llama_endpoint = HuggingFaceEndpoint(
        repo_id=settings.SECOND_FALLBACK_LLM,
        huggingfacehub_api_token=settings.HF_TOKEN,
        max_new_tokens=512,
        temperature=0.01,
        streaming=True
    )
    llama_model = ChatHuggingFace(llm=llama_endpoint)
    res = llama_model.invoke("Say 'Hugging Face Fallback working'")
    print(f"Success! Response: {res.content}")
except Exception as e:
    print(f"Error testing Hugging Face Fallback: {e}")

# 4. Test Chain Fallback Behavior
print("\n--- Testing Chain Fallback Behavior (forcing fallback) ---")
try:
    # Temporarily set API key to invalid one to force primary model to fail and trigger fallbacks
    original_api_key = settings.API_KEY
    settings.API_KEY = "invalid_key"
    
    chain = get_llm()
    print("Invoking get_llm() chain (should fall back to Groq)...")
    res = chain.invoke("Say 'Chain Fallback working'")
    print(f"Success! Response: {res.content}")
    
    settings.API_KEY = original_api_key
except Exception as e:
    print(f"Error testing Chain Fallback: {e}")
    if 'original_api_key' in locals():
        settings.API_KEY = original_api_key