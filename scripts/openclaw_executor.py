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
from typing import Optional

logger = logging.getLogger(__name__)

# Configuration
OPENCLAW_TIMEOUT = int(os.getenv("OPENCLAW_TIMEOUT", "30"))
OPENCLAW_MODEL = os.getenv("OPENCLAW_MODEL", "")  # Empty = use default


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
        if not request or not request.strip():
            return "I didn't receive a valid request. Could you repeat that?"
        
        logger.info(f"OpenClaw executing request: {request[:100]}...")
        
        try:
            # Build command - use 'agent' command with a dedicated voice session
            cmd = [
                "openclaw", "agent",
                "--message", request,
                "--session-id", "voice-assistant",  # Dedicated session for voice calls
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
                
                logger.info(f"OpenClaw completed successfully ({len(result)} chars)")
                return result
            else:
                error_msg = stderr.decode().strip() or stdout.decode().strip()
                logger.error(f"OpenClaw command failed: {error_msg}")
                return "I ran into an issue processing that request. Let me try a different approach, or you can try asking again."
        
        except asyncio.TimeoutError:
            logger.warning(f"OpenClaw request timed out after {self.timeout}s")
            return "That request took too long. Could you try a simpler request?"
        
        except FileNotFoundError:
            logger.error("openclaw CLI not found in PATH")
            return "I'm having trouble connecting to my tools right now. Please try again in a moment."
        
        except Exception as e:
            logger.error(f"OpenClaw execution error: {e}")
            return "Something went wrong processing that request. Let me know if you'd like to try again."
    
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


# CLI test interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python openclaw_executor.py 'request'")
        sys.exit(1)
    
    request = ' '.join(sys.argv[1:])
    
    async def test():
        result = await execute_openclaw_request(request)
        print(f"\n--- Result ---\n{result}")
    
    asyncio.run(test())
