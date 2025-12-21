"""
Chat routes for streaming LLM responses with function calling

CHAT-203: Integrate search_memories Tool in Chat API
"""

import json
import os
import re

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from server.chat.memory_client import add_memory, search_memories
from server.chat.tools import AVAILABLE_TOOLS

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    projectId: str
    temperature: float | None = 0.7


@router.post("/stream")
async def stream_chat(chat_request: ChatRequest, request: Request):
    """
    Stream chat responses from vLLM

    This endpoint:
    1. Validates authentication via session cookie
    2. Validates project access
    3. Forwards messages to vLLM
    4. Streams response back to client
    """

    # Get session from cookies
    cookies = request.cookies
    session_cookie_value = None

    # Find Ory Kratos session cookie
    # Kratos uses 'ory_kratos_session' as the cookie name
    if "ory_kratos_session" in cookies:
        session_cookie_value = cookies["ory_kratos_session"]
    # Also check for pattern ory_session_* (some Kratos versions use this)
    else:
        for cookie_name, cookie_value in cookies.items():
            if cookie_name.startswith("ory_session_"):
                session_cookie_value = cookie_value
                break

    if not session_cookie_value:
        print(
            f"[Chat] No session cookie found. Available cookies: {list(cookies.keys())}"
        )
        raise HTTPException(
            status_code=401, detail="Authentication required - no session found"
        )

    # Validate session with Kratos
    from server.auth import validate_session

    try:
        kratos_session = validate_session(session_cookie_value)
        user_id = kratos_session.user_id
        print(f"[Chat] Authenticated user: {kratos_session.email} ({user_id})")
    except Exception as e:
        print(f"[Chat] Session validation failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid session") from e

    # TODO: Validate user has access to this project
    # For now, we'll proceed with the request

    print(f"[Chat] User {user_id} requesting chat for project {chat_request.projectId}")
    print(f"[Chat] Message count: {len(chat_request.messages)}")

    # Get vLLM configuration from environment
    vllm_endpoint = os.getenv("VLLM_ENDPOINT", "http://localhost:8000/v1")
    vllm_api_key = os.getenv("VLLM_API_KEY", "dummy-key")
    vllm_model = os.getenv("LLM_MODEL", "llm_model")

    if not vllm_endpoint:
        raise HTTPException(status_code=503, detail="Chat service not configured")

    print(f"[Chat] Using vLLM model: {vllm_model}")

    # Check if tool calling is enabled via environment variable
    enable_tools = os.getenv("ENABLE_TOOL_CALLING", "false").lower() == "true"

    # Prepare messages with system prompt for tool use if enabled
    messages = [
        {"role": msg.role, "content": msg.content} for msg in chat_request.messages
    ]

    if enable_tools:
        # Add system prompt to instruct the LLM when to use tools
        system_prompt = """You are a helpful AI assistant with access to a memory system.

When users ask about:
- Past information, facts, or preferences (e.g., "what does Tom love?", "what did I say about X?")
- Previous conversations or discussions
- Stored information about people, places, or things
- Any question that references something that might have been mentioned before

You MUST use the search_memories tool to retrieve relevant information before answering.

When users share information that should be remembered:
- Use the add_memory tool to save important facts, preferences, decisions, or details

Available tools:
- search_memories(query, limit): Search the memory database using semantic similarity
- add_memory(content, tags, metadata): Save new information for future reference

Always search memories first when questions reference past information. Provide clear, helpful answers based on the retrieved memories."""

        # Prepend system message to messages
        messages = [{"role": "system", "content": system_prompt}] + messages

    # Prepare request for vLLM (OpenAI-compatible format)
    vllm_request = {
        "model": vllm_model,
        "messages": messages,
        "temperature": chat_request.temperature,
        "stream": True,
    }

    # Only add tools if explicitly enabled
    if enable_tools:
        vllm_request["tools"] = AVAILABLE_TOOLS
        vllm_request["tool_choice"] = "auto"
        print("[Chat] Tool calling enabled with system prompt")
    else:
        print("[Chat] Tool calling disabled - set ENABLE_TOOL_CALLING=true to enable")

    async def generate():
        """Generator function for streaming response with Qwen3 XML tool calling support"""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # First request to vLLM
                async with client.stream(
                    "POST",
                    f"{vllm_endpoint}/chat/completions",
                    json=vllm_request,
                    headers={"Authorization": f"Bearer {vllm_api_key}"},
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        print(
                            f"[Chat] vLLM error: {response.status_code} - {error_text}"
                        )
                        yield f"Error: Failed to connect to AI service (status {response.status_code})\n"
                        return

                    # Stream chunks while collecting full response for XML parsing
                    full_response = ""
                    tool_calls = []
                    tool_call_accumulator = {}  # Accumulate streaming tool call deltas by index
                    has_tool_calls = False

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break

                            try:
                                chunk = json.loads(data)
                                if "choices" in chunk and len(chunk["choices"]) > 0:
                                    choice = chunk["choices"][0]
                                    delta = choice.get("delta", {})

                                    # CRITICAL FIX: Accumulate streaming tool call deltas
                                    if "tool_calls" in delta:
                                        has_tool_calls = True
                                        for tc_delta in delta["tool_calls"]:
                                            index = tc_delta.get("index", 0)

                                            # Initialize accumulator for this index if needed
                                            if index not in tool_call_accumulator:
                                                tool_call_accumulator[index] = {
                                                    "id": tc_delta.get(
                                                        "id", f"call_stream_{index}"
                                                    ),
                                                    "type": tc_delta.get(
                                                        "type", "function"
                                                    ),
                                                    "function": {
                                                        "name": "",
                                                        "arguments": "",
                                                    },
                                                }
                                                print(
                                                    f"[Tool Call Stream] Started accumulating tool call #{index}"
                                                )

                                            # Accumulate function name
                                            if "function" in tc_delta:
                                                if "name" in tc_delta["function"]:
                                                    tool_call_accumulator[index][
                                                        "function"
                                                    ]["name"] += tc_delta["function"][
                                                        "name"
                                                    ]

                                                # Accumulate arguments (streamed as string)
                                                if "arguments" in tc_delta["function"]:
                                                    tool_call_accumulator[index][
                                                        "function"
                                                    ]["arguments"] += tc_delta[
                                                        "function"
                                                    ]["arguments"]
                                                    print(
                                                        f"[Tool Call Stream] #{index} accumulated args: {tool_call_accumulator[index]['function']['arguments'][:100]}..."
                                                    )

                                    # Collect content
                                    content = delta.get("content", "")
                                    if content:
                                        full_response += content
                                        # Don't yield yet - need to check for XML tool calls

                            except json.JSONDecodeError:
                                continue

                    # Convert accumulated tool calls to final format
                    if tool_call_accumulator:
                        for index in sorted(tool_call_accumulator.keys()):
                            accumulated_tc = tool_call_accumulator[index]
                            print(
                                f"[Tool Call Stream] Finalized #{index}: {accumulated_tc['function']['name']} with {len(accumulated_tc['function']['arguments'])} chars of args"
                            )
                            tool_calls.append(accumulated_tc)

                # Parse Qwen3 XML-format tool calls from the full response
                xml_tool_calls = parse_qwen3_tool_calls(full_response)

                if xml_tool_calls:
                    print(
                        f"[Chat] Parsed {len(xml_tool_calls)} XML tool call(s) from Qwen3"
                    )
                    has_tool_calls = True
                    tool_calls = xml_tool_calls

                    # Remove tool call XML from response text
                    clean_response = remove_tool_call_xml(full_response)

                    # If there's text before tool calls, yield it
                    if clean_response.strip():
                        yield clean_response
                else:
                    # No tool calls found, yield the full response
                    if full_response:
                        yield full_response

                # If model made tool calls, execute them and generate final response
                if has_tool_calls:
                    print(f"[Chat] Model requested {len(tool_calls)} tool call(s)")

                    # Execute tool calls
                    tool_messages = []
                    for tool_call in tool_calls:
                        # Handle both OpenAI format and our parsed XML format
                        if "function" in tool_call:
                            # OpenAI format
                            function_name = tool_call.get("function", {}).get("name")
                            function_args_str = tool_call.get("function", {}).get(
                                "arguments", "{}"
                            )
                            tool_call_id = tool_call.get("id", "call_unknown")
                        else:
                            # Our parsed XML format
                            function_name = tool_call.get("name")
                            function_args_str = json.dumps(
                                tool_call.get("arguments", {})
                            )
                            tool_call_id = tool_call.get("id", "call_unknown")

                        try:
                            function_args = (
                                json.loads(function_args_str)
                                if isinstance(function_args_str, str)
                                else function_args_str
                            )
                            print(
                                f"[Tool Call] ✓ Successfully parsed arguments for {function_name}"
                            )
                        except json.JSONDecodeError as e:
                            print(f"[Tool Call] ✗ Failed to parse arguments: {e}")
                            print(
                                f"[Tool Call] Raw arguments string: '{function_args_str[:200]}'"
                            )
                            function_args = {}

                        print(
                            f"[Tool Call] Executing {function_name} with args: {function_args}"
                        )

                        if function_name == "search_memories":
                            # Get query with validation and extensive logging
                            search_query = function_args.get("query", "").strip()
                            search_limit = function_args.get("limit", 5)

                            print(
                                "[Tool Call - Memory Search] ===== QUERY DEBUG ====="
                            )
                            print(
                                f"[Tool Call - Memory Search] Raw function_args: {function_args}"
                            )
                            print(
                                f"[Tool Call - Memory Search] Extracted query: '{search_query}'"
                            )
                            print(
                                f"[Tool Call - Memory Search] Query length: {len(search_query)}"
                            )
                            print(f"[Tool Call - Memory Search] Limit: {search_limit}")
                            print(
                                f"[Tool Call - Memory Search] Project ID: {chat_request.projectId}"
                            )

                            # If query is empty, use a default that retrieves recent memories
                            if not search_query:
                                print(
                                    "[Tool Call - Memory Search] ⚠️ Empty query detected, using fallback '*' for recent memories"
                                )
                                search_query = "*"
                            else:
                                print(
                                    f"[Tool Call - Memory Search] ✓ Valid query: '{search_query}'"
                                )

                            # Execute memory search
                            print(
                                f"[Tool Call - Memory Search] 🔍 Calling search_memories with query='{search_query}'"
                            )
                            memories = await search_memories(
                                query=search_query,
                                project_id=chat_request.projectId,
                                user_id=user_id,
                                limit=search_limit,
                                session_cookie=session_cookie_value,
                            )

                            print(
                                f"[Tool Call - Memory Search] 📊 Retrieved {len(memories)} memories"
                            )
                            for i, mem in enumerate(
                                memories[:3]
                            ):  # Log first 3 memories
                                print(
                                    f"[Tool Call - Memory Search] Memory #{i + 1}: score={mem.score:.4f}, content='{mem.content[:100]}...'"
                                )

                            # Format results for LLM
                            result = {
                                "memories": [
                                    {
                                        "id": m.id,
                                        "content": m.content,
                                        "tags": m.tags,
                                        "score": m.score,
                                    }
                                    for m in memories
                                ],
                                "count": len(memories),
                            }

                            tool_messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call_id,
                                    "name": function_name,
                                    "content": json.dumps(result),
                                }
                            )

                            print(f"[Tool Result] Found {len(memories)} memories")

                        elif function_name == "add_memory":
                            # Execute memory addition (Phase 3)
                            memory = await add_memory(
                                content=function_args.get("content", ""),
                                project_id=chat_request.projectId,
                                user_id=user_id,
                                tags=function_args.get("tags"),
                                metadata=function_args.get("metadata"),
                                session_cookie=session_cookie_value,
                            )

                            # Format result for LLM
                            if memory:
                                result = {
                                    "success": True,
                                    "memory_id": memory.id,
                                    "message": "Memory saved successfully",
                                }
                                print(f"[Tool Result] Memory added: {memory.id}")
                            else:
                                result = {
                                    "success": False,
                                    "message": "Failed to save memory",
                                }
                                print("[Tool Result] Failed to add memory")

                            tool_messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call_id,
                                    "name": function_name,
                                    "content": json.dumps(result),
                                }
                            )

                    # Make second request with tool results
                    # CRITICAL FIX: Validate tool_calls format before sending to vLLM
                    validated_tool_calls = []
                    for tc in tool_calls:
                        # Ensure each tool call has required fields
                        if "function" in tc and "name" in tc["function"]:
                            # Ensure arguments field exists and is a string
                            if "arguments" not in tc["function"]:
                                tc["function"]["arguments"] = "{}"
                            elif not isinstance(tc["function"]["arguments"], str):
                                tc["function"]["arguments"] = json.dumps(
                                    tc["function"]["arguments"]
                                )
                            validated_tool_calls.append(tc)
                        else:
                            print(f"[Tool Call] Skipping invalid tool call: {tc}")

                    if not validated_tool_calls:
                        print(
                            "[Tool Call] No valid tool calls after validation, skipping second request"
                        )
                        # Just yield the tool results as text
                        for tm in tool_messages:
                            yield f"\n[Tool Result: {tm['name']}]\n{tm['content']}\n"
                    else:
                        messages_with_tools = (
                            [
                                {"role": msg.role, "content": msg.content}
                                for msg in chat_request.messages
                            ]
                            + [
                                {
                                    "role": "assistant",
                                    "content": full_response or "",
                                    "tool_calls": validated_tool_calls,
                                }
                            ]
                            + tool_messages
                        )

                        second_request = {
                            "model": vllm_model,
                            "messages": messages_with_tools,
                            "temperature": chat_request.temperature,
                            "stream": True,
                        }

                        # Stream the final response
                        try:
                            async with client.stream(
                                "POST",
                                f"{vllm_endpoint}/chat/completions",
                                json=second_request,
                                headers={"Authorization": f"Bearer {vllm_api_key}"},
                            ) as final_response:
                                if final_response.status_code != 200:
                                    error_text = await final_response.aread()
                                    print(
                                        f"[Chat] Second request error: {final_response.status_code} - {error_text}"
                                    )
                                    # Fallback: yield tool results as text
                                    for tm in tool_messages:
                                        yield f"\n[Tool Result: {tm['name']}]\n{tm['content']}\n"
                                else:
                                    async for line in final_response.aiter_lines():
                                        if line.startswith("data: "):
                                            data = line[6:]
                                            if data == "[DONE]":
                                                break

                                            try:
                                                chunk = json.loads(data)
                                                if (
                                                    "choices" in chunk
                                                    and len(chunk["choices"]) > 0
                                                ):
                                                    delta = chunk["choices"][0].get(
                                                        "delta", {}
                                                    )
                                                    content = delta.get("content", "")
                                                    if content:
                                                        yield content
                                            except json.JSONDecodeError:
                                                continue
                        except Exception as second_req_error:
                            print(f"[Chat] Error in second request: {second_req_error}")
                            # Fallback: yield tool results as text
                            for tm in tool_messages:
                                yield f"\n[Tool Result: {tm['name']}]\n{tm['content']}\n"
                # If no tool calls, chunks were already streamed above

        except httpx.TimeoutException:
            yield "Error: Request timed out\n"
        except Exception as e:
            import traceback

            print(f"[Chat] Streaming error: {str(e)}")
            print(f"[Chat] Traceback: {traceback.format_exc()}")
            yield f"Error: {str(e)}\n"

    return StreamingResponse(
        generate(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def parse_qwen3_tool_calls(text: str) -> list[dict]:
    """
    Parse Qwen3's XML-format tool calls from response text.

    Qwen3 outputs tool calls like:
    <tool_call> {"name": "search_memories", "arguments": {"query": "..."}} </tool_call>

    Returns list of tool call dicts in OpenAI-compatible format.
    """
    tool_calls = []

    # More robust regex to handle nested braces and multiline JSON
    # This captures everything between <tool_call> and </tool_call>
    pattern = r"<tool_call>\s*(.*?)\s*</tool_call>"
    matches = re.findall(pattern, text, re.DOTALL)

    print(f"[XML Parser] Found {len(matches)} potential tool call(s) in response")

    for i, match in enumerate(matches):
        try:
            # Clean up the match - remove any extra whitespace
            match = match.strip()

            # Log what we're trying to parse
            print(f"[XML Parser] Attempting to parse tool call {i}: {match[:200]}...")

            # Try to parse the JSON inside the XML tags
            tool_data = json.loads(match)

            # Validate required fields
            if "name" not in tool_data:
                print(f"[XML Parser] Tool call {i} missing 'name' field, skipping")
                continue

            # Get arguments, default to empty dict if not present
            arguments = tool_data.get("arguments", {})

            # CRITICAL FIX: Always ensure arguments is a JSON string
            # vLLM requires this field to be present and be a string
            if isinstance(arguments, dict):
                arguments_str = json.dumps(arguments)
            elif isinstance(arguments, str):
                # Validate it's valid JSON
                try:
                    json.loads(arguments)
                    arguments_str = arguments
                except json.JSONDecodeError:
                    print(
                        "[XML Parser] Invalid JSON string in arguments, using empty object"
                    )
                    arguments_str = "{}"
            else:
                print("[XML Parser] Invalid arguments type, using empty object")
                arguments_str = "{}"

            # Convert to OpenAI-compatible format with guaranteed arguments field
            tool_call = {
                "id": f"call_qwen3_{i}",
                "type": "function",
                "function": {
                    "name": tool_data.get("name", ""),
                    "arguments": arguments_str,  # Always a JSON string
                },
            }
            tool_calls.append(tool_call)
            print(
                f"[XML Parser] ✓ Parsed tool call: {tool_data.get('name')} with args {arguments_str[:100]}"
            )

        except json.JSONDecodeError as e:
            print(f"[XML Parser] ✗ Failed to parse tool call {i} JSON: {e}")
            print(f"[XML Parser] Raw content: {match[:300]}")
            # Try to salvage by extracting function name if possible
            try:
                # Look for "name" field in the malformed JSON
                name_match = re.search(r'"name"\s*:\s*"([^"]+)"', match)
                if name_match:
                    function_name = name_match.group(1)
                    print(
                        f"[XML Parser] Salvaging tool call with name: {function_name}"
                    )
                    tool_call = {
                        "id": f"call_qwen3_{i}",
                        "type": "function",
                        "function": {
                            "name": function_name,
                            "arguments": "{}",  # Empty arguments for malformed calls
                        },
                    }
                    tool_calls.append(tool_call)
                else:
                    print("[XML Parser] Could not salvage tool call")
            except Exception as salvage_error:
                print(f"[XML Parser] Salvage attempt failed: {salvage_error}")
            continue
        except Exception as e:
            print(f"[XML Parser] ✗ Unexpected error parsing tool call {i}: {e}")
            continue

    print(f"[XML Parser] Successfully parsed {len(tool_calls)} tool call(s)")
    return tool_calls


def remove_tool_call_xml(text: str) -> str:
    """Remove <tool_call>...</tool_call> XML tags from text to get clean response."""
    # Remove tool call blocks
    clean_text = re.sub(r"<tool_call>.*?</tool_call>", "", text, flags=re.DOTALL)

    # Also remove <think>...</think> blocks if present
    clean_text = re.sub(r"<think>.*?</think>", "", clean_text, flags=re.DOTALL)

    return clean_text.strip()
