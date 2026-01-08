import os
from typing import List, Tuple
from copy import deepcopy
import sqlite3
import json
import time
import hashlib

import boto3
from botocore.exceptions import ClientError
from filelock import FileLock

from .base import BaseLLM, LLMConfig
from ..utils.llm_utils import TextChatMessage
from ..utils.logging_utils import get_logger


logger = get_logger(__name__)


class LLM_Cache:
    def __init__(self, cache_dir: str, cache_filename):
        os.makedirs(cache_dir, exist_ok=True)
        self.cache_filepath =  os.path.join(cache_dir, f"{cache_filename}.sqlite")
        self.lock_file = self.cache_filepath + ".lock"

        self.__db_operation("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                message TEXT,
                metadata TEXT
            )
        """, commit=True)
    
    def __db_operation(self, sql, parameters=(), commit=False, fetchone=False):
        with FileLock(self.lock_file):
            conn = sqlite3.connect(self.cache_filepath)
            c = conn.cursor()
            c.execute(sql, parameters)
            if commit:
                conn.commit()
            if fetchone:
                row = c.fetchone()
            conn.close()
            if fetchone:
                return row

    def __params_to_key(self, params):
        key_str = f"Model: {params['model']}, Temperature: {params['temperature']}, Messages: {params['messages']}"
        return hashlib.sha256(key_str.encode("utf-8")).hexdigest()

    def read(self, params):
        key = self.__params_to_key(params)
        row = self.__db_operation("SELECT message, metadata FROM cache WHERE key = ?", (key,), fetchone=True)
        if row is None:
            return None
        message, metadata_str = row
        metadata = json.loads(metadata_str)
        return message, metadata

    def write(self, params, message, metadata):
        key = self.__params_to_key(params)
        metadata_str = json.dumps(metadata)
        self.__db_operation("INSERT OR REPLACE INTO cache (key, message, metadata) VALUES (?, ?, ?)", (key, message, metadata_str), commit=True)


class BedrockLLM(BaseLLM):
    """
    To select this implementation you can initialise HippoRAG with:
        llm_model_name="anthropic.claude-3-5-haiku-20241022-v1:0" or any other Bedrock Model-ID
    """
    def __init__(self, global_config = None):
        self.global_config = global_config
        super().__init__(global_config)
        self._init_llm_config()

        self.cache = LLM_Cache(
            os.path.join(global_config.save_dir, "llm_cache"),
            self.llm_name.replace('/', '_'))        
        
        self.bedrock_runtime = boto3.client(service_name='bedrock-runtime')
        self.retry = 5
        
        logger.info(f"[BedrockLLM] Model-ID: {self.global_config.llm_name}, Cache: {self.cache.cache_filepath}")

    def _init_llm_config(self) -> None:
        config_dict = self.global_config.__dict__
        config_dict['llm_name'] = self.global_config.llm_name
        config_dict['generate_params'] = {
                "model": self.global_config.llm_name,
                "n": 1,
                "temperature": config_dict.get("temperature", 0.0),
            }

        self.llm_config = LLMConfig.from_dict(config_dict=config_dict)
        logger.info(f"[BedrockLLM] Config: {self.llm_config}")

    def __llm_call(self, model_id, messages, temperature):
        """
        Invoke Bedrock model using boto3.
        Converts OpenAI-style messages format to Bedrock API format.
        """
        num, wait_s = 0, 0.5
        while True:
            try:
                # Convert OpenAI messages format to Bedrock format
                # TextChatMessage is a TypedDict, so messages are dictionaries
                bedrock_messages = []
                for msg in messages:
                    if isinstance(msg, dict):
                        role = msg.get("role", "user")
                        content = msg.get("content", "")
                        # Handle Template objects - convert to string
                        if hasattr(content, 'substitute') or hasattr(content, 'safe_substitute'):
                            content = str(content)
                        bedrock_messages.append({
                            "role": role,
                            "content": [{"text": str(content)}]
                        })
                    elif hasattr(msg, 'role') and hasattr(msg, 'content'):
                        # Handle object-style messages (if any)
                        content = msg.content
                        if hasattr(content, 'substitute') or hasattr(content, 'safe_substitute'):
                            content = str(content)
                        bedrock_messages.append({
                            "role": msg.role,
                            "content": [{"text": str(content)}]
                        })
                    else:
                        # Assume it's a string, treat as user message
                        bedrock_messages.append({
                            "role": "user",
                            "content": [{"text": str(msg)}]
                        })
                
                # Handle different model providers (Claude uses anthropic format)
                if model_id.startswith("anthropic."):
                    # Claude models use Messages API
                    request_body = {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 4096,
                        "messages": bedrock_messages,
                        "temperature": temperature
                    }
                elif model_id.startswith("amazon."):
                    # Amazon Titan models use Text Generation API
                    last_message = messages[-1] if messages else {}
                    if isinstance(last_message, dict):
                        content = last_message.get('content', '')
                    elif hasattr(last_message, 'content'):
                        content = last_message.content
                    else:
                        content = str(last_message) if last_message else ''
                    
                    # Handle Template objects
                    if hasattr(content, 'substitute') or hasattr(content, 'safe_substitute'):
                        content = str(content)
                    
                    request_body = {
                        "inputText": str(content),
                        "textGenerationConfig": {
                            "maxTokenCount": 4096,
                            "temperature": temperature
                        }
                    }
                else:
                    # Default to Claude format (most common)
                    request_body = {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 4096,
                        "messages": bedrock_messages,
                        "temperature": temperature
                    }
                
                response = self.bedrock_runtime.invoke_model(
                    modelId=model_id,
                    body=json.dumps(request_body),
                    accept='application/json',
                    contentType='application/json'
                )
                
                response_body = json.loads(response.get('body').read())
                
                # Parse response based on model type
                if model_id.startswith("anthropic."):
                    # Claude models
                    content = response_body.get('content', [])
                    message_content = content[0].get('text', '') if content else ''
                    usage = response_body.get('usage', {})
                    finish_reason = response_body.get('stop_reason', 'stop')
                    
                    # Create a response-like object similar to litellm
                    class BedrockResponse:
                        class Choice:
                            class Message:
                                def __init__(self, content):
                                    self.content = content
                            def __init__(self, content):
                                self.message = self.Message(content)
                                self.finish_reason = finish_reason
                        
                        class Usage:
                            def __init__(self, prompt_tokens, completion_tokens):
                                self.prompt_tokens = prompt_tokens
                                self.completion_tokens = completion_tokens
                        
                        def __init__(self, content, prompt_tokens, completion_tokens, finish_reason):
                            self.choices = [self.Choice(content)]
                            self.usage = self.Usage(prompt_tokens, completion_tokens)
                            self.choices[0].finish_reason = finish_reason
                    
                    return BedrockResponse(
                        message_content,
                        usage.get('input_tokens', 0),
                        usage.get('output_tokens', 0),
                        finish_reason
                    )
                elif model_id.startswith("amazon."):
                    # Amazon Titan models
                    results = response_body.get('results', [])
                    message_content = results[0].get('outputText', '') if results else ''
                    finish_reason = results[0].get('completionReason', 'stop') if results else 'stop'
                    
                    class BedrockResponse:
                        class Choice:
                            class Message:
                                def __init__(self, content):
                                    self.content = content
                            def __init__(self, content):
                                self.message = self.Message(content)
                                self.finish_reason = finish_reason
                        
                        class Usage:
                            def __init__(self, prompt_tokens, completion_tokens):
                                self.prompt_tokens = prompt_tokens
                                self.completion_tokens = completion_tokens
                        
                        def __init__(self, content, finish_reason):
                            self.choices = [self.Choice(content)]
                            # Amazon models don't provide token counts in same format
                            self.usage = self.Usage(0, 0)
                            self.choices[0].finish_reason = finish_reason
                    
                    return BedrockResponse(message_content, finish_reason)
                else:
                    raise ValueError(f"Unsupported Bedrock model: {model_id}")
                    
            except ClientError as e:
                num += 1
                if num > self.retry:
                    raise Exception(f"Bedrock LLM ClientError: {e.response.get('Error', {}).get('Message', str(e))}")
                
                logger.warning(f"Bedrock LLM Exception: {e}\nRetry #{num} after {wait_s} seconds")
                time.sleep(wait_s)
                wait_s *= 2
            except Exception as e:
                num += 1
                if num > self.retry:
                    raise e
                
                logger.warning(f"Bedrock LLM Exception: {e}\nRetry #{num} after {wait_s} seconds")
                time.sleep(wait_s)
                wait_s *= 2
    
    def infer(self, messages: List[TextChatMessage], **kwargs) -> Tuple[str, dict, bool]:
        params = deepcopy(self.llm_config.generate_params)
        if kwargs:
            params.update(kwargs)
        params["messages"] = messages
        
        cache_lookup = self.cache.read(params)
        if cache_lookup is not None:
            cached = True
            message, metadata = cache_lookup
        else:
            cached = False
            temperature = params.get("temperature", 0.0)
            model_id = params.get("model", self.global_config.llm_name)
            response = self.__llm_call(model_id, messages, temperature)
            message = response.choices[0].message.content
            metadata = {
                "prompt_tokens": response.usage.prompt_tokens, 
                "completion_tokens": response.usage.completion_tokens,
                "finish_reason": response.choices[0].finish_reason,
            }
            self.cache.write(params, message, metadata)

        return message, metadata, cached
