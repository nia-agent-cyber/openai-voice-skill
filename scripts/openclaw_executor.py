#!/usr/bin/env python3
"""
OpenClaw Executor - Execute requests through the OpenClaw agent.

This module provides a bridge between the OpenAI Realtime voice session
and the OpenClaw agent's full tool capabilities.
"""

import asyncio
import json
import logging
import os
import subprocess
from typing import AsyncGenerator, Optional

from smart_chunker import SmartChunker

logger = logging.getLogger(__name__)

# Configuration
# Reduced from 30s to 5s for voice responsiveness (users expect fast replies)
OPENCLAW_TIMEOUT = int(os.getenv("OPENCLAW_VOICE_TIMEOUT", os.getenv("OPENCLAW_TIMEOUT", "5")))
OPENCLAW_MODEL = os.getenv("OPENCLAW_MODEL", "")  # Empty = use default

# Global call_id for error tracking (set per-request)
_current_call_id: Optional[str] = None


def set_call_id(call_id: str):
    """Set the current call_id for error tracking in logs."""
    global _current_call_id
    _current_call_id = call_id


def get_call_id() -> str:
    """Get the current call_id or 'unknown' if not set."""
    return _current_call_id or "unknown"


class OpenClawExecutor:
    """Execute requests through the OpenClaw agent."""
    
    def __init__(self, timeout: int = OPENCLAW_TIMEOUT):
        self.timeout = timeout
        self.model = OPENCLAW_MODEL
    
    async def execute(self, request: str) -> str:
        """
        Execute a request through OpenClaw and return the result.
        
        Uses CLI for simplicity. The request is passed as a one-shot
        message to the OpenClaw agent which has full tool access.
        
        Args:
            request: Natural language request to execute
            
        Returns:
            String result suitable for speaking back to the caller
        """
        call_id = get_call_id()
        
        if not request or not request.strip():
            logger.warning(f"[call_id={call_id}] Empty request received")
            return "I didn't receive a valid request. Could you repeat that?"
        
        logger.info(f"[call_id={call_id}] Executing request (timeout={self.timeout}s): {request[:100]}...")
        
        try:
            # Build command - use 'agent' command with a dedicated voice session
            cmd = [
                "openclaw", "agent",
                "--message", request,
                "--session-id", "agent:main:main",  # Dedicated session for voice calls
                "--local"
            ]
            
            # Add thinking for complex requests
            cmd.extend(["--thinking", "low"])
            
            # Execute with timeout
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout
            )
            
            if process.returncode == 0:
                result = stdout.decode().strip()
                
                # Post-process for voice output
                result = self._format_for_voice(result)
                
                logger.info(f"[call_id={call_id}] Request completed successfully ({len(result)} chars)")
                return result
            else:
                error_msg = stderr.decode().strip() or stdout.decode().strip()
                logger.error(f"[call_id={call_id}] Command failed (exit={process.returncode}): {error_msg[:200]}")
                return "I ran into an issue processing that request. Let me try a different approach, or you can try asking again."
        
        except asyncio.TimeoutError:
            logger.error(f"[call_id={call_id}] Request timed out after {self.timeout}s: {request[:50]}...")
            return "That request took too long. Could you try a simpler request?"
        
        except FileNotFoundError:
            logger.error(f"[call_id={call_id}] openclaw CLI not found in PATH")
            return "I'm having trouble connecting to my tools right now. Please try again in a moment."
        
        except Exception as e:
            logger.error(f"[call_id={call_id}] Execution error: {type(e).__name__}: {e}")
            return "Something went wrong processing that request. Let me know if you'd like to try again."
    
    async def execute_streaming(
        self,
        request: str,
        chunk_size: int = 500
    ) -> AsyncGenerator[str, None]:
        """
        Execute a request through OpenClaw, yielding chunks as they're generated.
        
        Runs `openclaw agent` as a subprocess and streams stdout line-by-line,
        using SmartChunker to buffer and yield chunks at natural boundaries.
        
        Args:
            request: Natural language request to execute
            chunk_size: Target chunk size in characters (~500 for TTS)
            
        Yields:
            Text chunks as they become available
        """
        call_id = get_call_id()
        
        if not request or not request.strip():
            logger.warning(f"[call_id={call_id}] Empty streaming request received")
            yield "I didn't receive a valid request. Could you repeat that?"
            return
        
        logger.info(f"[call_id={call_id}] Streaming request (timeout={self.timeout}s): {request[:100]}...")
        
        process = None
        chunker = SmartChunker(target_size=chunk_size, min_size=100, max_size=1000)
        chunks_yielded = 0
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Build command
            cmd = [
                "openclaw", "agent",
                "--message", request,
                "--session-id", "agent:main:main",
                "--local"
            ]
            cmd.extend(["--thinking", "low"])
            
            # Start subprocess with pipe for stdout
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Read stdout line-by-line as it's generated
            async def read_with_timeout():
                """Read lines with overall timeout."""
                stream_start = asyncio.get_event_loop().time()
                
                while True:
                    # Check timeout
                    elapsed = asyncio.get_event_loop().time() - stream_start
                    if elapsed > self.timeout:
                        raise asyncio.TimeoutError()
                    
                    # Read next line with short timeout
                    try:
                        line = await asyncio.wait_for(
                            process.stdout.readline(),
                            timeout=min(5.0, self.timeout - elapsed)
                        )
                    except asyncio.TimeoutError:
                        # No data available - check if process ended
                        if process.returncode is not None:
                            break
                        continue
                    
                    if not line:
                        break  # EOF
                    
                    yield line.decode()
            
            # Process lines and yield chunks
            async for line in read_with_timeout():
                # Format and add to chunker
                formatted = self._format_for_voice(line)
                if formatted and formatted.strip():
                    chunker.add_text(formatted + " ")
                    
                    # Yield any ready chunks
                    for chunk in chunker.get_chunks():
                        chunk = chunk.strip()
                        if chunk:
                            chunks_yielded += 1
                            logger.debug(f"[call_id={call_id}] Yielding chunk {chunks_yielded}: {len(chunk)} chars")
                            yield chunk
            
            # Wait for process to finish
            await process.wait()
            
            # Flush remaining buffer
            final = chunker.flush()
            if final and final.strip():
                final = final.strip()
                chunks_yielded += 1
                logger.debug(f"[call_id={call_id}] Yielding final chunk {chunks_yielded}: {len(final)} chars")
                yield final
            
            # Handle empty output
            if chunks_yielded == 0:
                logger.warning(f"[call_id={call_id}] No output returned from request")
                yield "Done."
            
            # Check for errors
            if process.returncode != 0:
                stderr_data = await process.stderr.read()
                error_msg = stderr_data.decode().strip() if stderr_data else "Unknown error"
                logger.error(f"[call_id={call_id}] Process failed (exit={process.returncode}): {error_msg[:200]}")
                # Only yield error if we haven't yielded anything useful
                if chunks_yielded == 0:
                    yield "I ran into an issue processing that request."
            
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.info(f"[call_id={call_id}] Streaming completed: {chunks_yielded} chunks in {elapsed:.1f}s")
        
        except asyncio.TimeoutError:
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.error(f"[call_id={call_id}] Streaming timed out after {elapsed:.1f}s (limit={self.timeout}s)")
            if chunks_yielded > 0:
                yield "... I'm still working on this, but it's taking too long."
            else:
                yield "That request took too long. Could you try a simpler request?"
        
        except FileNotFoundError:
            logger.error(f"[call_id={call_id}] openclaw CLI not found in PATH")
            yield "I'm having trouble connecting to my tools right now."
        
        except Exception as e:
            logger.error(f"[call_id={call_id}] Streaming error: {type(e).__name__}: {e}")
            if chunks_yielded > 0:
                yield "... Something went wrong while processing."
            else:
                yield "Something went wrong processing that request."
        
        finally:
            # Clean up process if still running
            if process and process.returncode is None:
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=2.0)
                except:
                    process.kill()
                logger.debug(f"[call_id={call_id}] Cleaned up lingering process")
    
    def _format_for_voice(self, text: str) -> str:
        """
        Format text output for voice (TTS) delivery.
        
        - Remove markdown formatting
        - Truncate overly long responses
        - Clean up code blocks
        """
        if not text:
            return "Done."
        
        # Remove markdown code blocks
        import re
        text = re.sub(r'```[\s\S]*?```', '[code snippet omitted]', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)  # Inline code
        
        # Remove markdown headers
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        
        # Remove markdown bold/italic
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'__([^_]+)__', r'\1', text)
        text = re.sub(r'_([^_]+)_', r'\1', text)
        
        # Remove markdown links, keep text
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        
        # Remove bullet points
        text = re.sub(r'^[-*+]\s+', '', text, flags=re.MULTILINE)
        
        # Collapse multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Truncate if too long (voice should be concise)
        max_chars = 2000  # ~30 seconds of speech
        if len(text) > max_chars:
            text = text[:max_chars].rsplit(' ', 1)[0] + "... I can provide more details if you'd like."
        
        return text.strip()


# Singleton instance for the webhook server
executor = OpenClawExecutor()


async def execute_openclaw_request(request: str) -> str:
    """
    Convenience function for executing OpenClaw requests.
    
    Usage:
        from openclaw_executor import execute_openclaw_request
        result = await execute_openclaw_request("Check my calendar for today")
    """
    return await executor.execute(request)


async def execute_openclaw_streaming(request: str) -> AsyncGenerator[str, None]:
    """
    Convenience function for streaming OpenClaw requests.
    
    Usage:
        from openclaw_executor import execute_openclaw_streaming
        async for chunk in execute_openclaw_streaming("Tell me about today"):
            send_to_tts(chunk)
    """
    async for chunk in executor.execute_streaming(request):
        yield chunk


# CLI test interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python openclaw_executor.py [--stream] 'request'")
        sys.exit(1)
    
    # Parse args
    stream_mode = "--stream" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--stream"]
    request = ' '.join(args)
    
    async def test():
        if stream_mode:
            print("\n--- Streaming Result ---")
            chunk_num = 0
            async for chunk in execute_openclaw_streaming(request):
                chunk_num += 1
                print(f"[Chunk {chunk_num}]: {chunk}")
            print(f"\n--- Done ({chunk_num} chunks) ---")
        else:
            result = await execute_openclaw_request(request)
            print(f"\n--- Result ---\n{result}")
    
    asyncio.run(test())
