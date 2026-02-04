"""
Smart Chunker for Streaming Tool Responses

Intelligently splits streaming text into chunks at natural boundaries
for optimal real-time delivery. Designed for voice/TTS applications
where mid-word or mid-sentence breaks sound unnatural.

Boundary priority (best to worst):
1. Paragraph breaks (\n\n)
2. List items (numbered/bulleted)
3. Sentence endings (. ! ?)
4. Clause endings (, ; :)
5. Word boundaries (spaces)
"""

import re
from typing import List, Optional


class SmartChunker:
    """
    Buffers streaming text and yields chunks at natural boundaries.
    
    Usage:
        chunker = SmartChunker(target_size=500)
        
        for data in stream:
            chunker.add_text(data)
            for chunk in chunker.get_chunks():
                send_to_tts(chunk)
        
        # End of stream
        final = chunker.flush()
        if final:
            send_to_tts(final)
    """
    
    # Boundary patterns in priority order (higher = better break point)
    PARAGRAPH_BREAK = re.compile(r'\n\n+')
    LIST_ITEM = re.compile(r'\n(?=\s*[-*•]\s|\s*\d+[.)]\s)')
    SENTENCE_END = re.compile(r'(?<=[.!?])\s+')
    CLAUSE_END = re.compile(r'(?<=[,;:])\s+')
    WORD_BOUNDARY = re.compile(r'\s+')
    
    def __init__(
        self,
        target_size: int = 500,
        min_size: int = 100,
        max_size: int = 1000
    ):
        """
        Initialize the chunker.
        
        Args:
            target_size: Ideal chunk size in characters (~500 for TTS)
            min_size: Minimum chunk size before forcing output
            max_size: Maximum chunk size (hard limit, will break at word boundary)
        """
        self.target_size = target_size
        self.min_size = min_size
        self.max_size = max_size
        self._buffer = ""
        self._ready_chunks: List[str] = []
    
    def add_text(self, text: str) -> None:
        """
        Add incoming text to the buffer.
        
        Args:
            text: Text fragment from stream
        """
        if not text:
            return
        
        self._buffer += text
        self._process_buffer()
    
    def get_chunks(self) -> List[str]:
        """
        Return complete chunks ready to send.
        
        Returns:
            List of text chunks at natural boundaries
        """
        chunks = self._ready_chunks
        self._ready_chunks = []
        return chunks
    
    def flush(self) -> str:
        """
        Return remaining buffer content (call at end of stream).
        
        Returns:
            Any remaining buffered text
        """
        remaining = self._buffer.strip()
        self._buffer = ""
        return remaining
    
    def _process_buffer(self) -> None:
        """Process buffer and extract complete chunks."""
        while len(self._buffer) >= self.min_size:
            chunk = self._extract_chunk()
            if chunk:
                self._ready_chunks.append(chunk)
            else:
                break
    
    def _extract_chunk(self) -> Optional[str]:
        """
        Extract one chunk from buffer at the best available boundary.
        
        Returns:
            Extracted chunk or None if no good boundary found
        """
        # Don't extract if buffer is too small
        if len(self._buffer) < self.min_size:
            return None
        
        # Search window: from min_size to min(max_size, buffer_length)
        search_end = min(self.max_size, len(self._buffer))
        search_text = self._buffer[:search_end]
        
        # Find best boundary in priority order
        break_pos = self._find_best_boundary(search_text)
        
        if break_pos is None:
            # No boundary found - only force break if we hit max_size
            if len(self._buffer) >= self.max_size:
                break_pos = self._force_word_boundary(search_text)
            else:
                return None
        
        # Extract chunk and update buffer
        chunk = self._buffer[:break_pos].strip()
        self._buffer = self._buffer[break_pos:].lstrip()
        
        return chunk if chunk else None
    
    def _find_best_boundary(self, text: str) -> Optional[int]:
        """
        Find the best boundary position in text.
        
        Searches from target_size backward, preferring higher-priority
        boundaries (paragraphs > sentences > clauses > words).
        
        Args:
            text: Text to search for boundaries
            
        Returns:
            Position of best boundary or None
        """
        # Ideal: find boundary near target_size
        # Search backward from target to find natural break
        search_start = max(self.min_size, self.target_size // 2)
        search_end = min(len(text), self.target_size + 100)
        search_region = text[search_start:search_end]
        
        # Try each boundary type in priority order
        boundaries = [
            (self.PARAGRAPH_BREAK, 'paragraph'),
            (self.LIST_ITEM, 'list'),
            (self.SENTENCE_END, 'sentence'),
            (self.CLAUSE_END, 'clause'),
            (self.WORD_BOUNDARY, 'word'),
        ]
        
        for pattern, _ in boundaries:
            matches = list(pattern.finditer(search_region))
            if matches:
                # Find match closest to target_size
                best_match = self._closest_to_target(matches, search_start)
                return search_start + best_match.end()
        
        return None
    
    def _closest_to_target(self, matches: list, offset: int) -> re.Match:
        """Find match closest to target size."""
        target_pos = self.target_size - offset
        return min(matches, key=lambda m: abs(m.start() - target_pos))
    
    def _force_word_boundary(self, text: str) -> int:
        """
        Force a break at a word boundary when max_size reached.
        
        Args:
            text: Text to find word boundary in
            
        Returns:
            Position of last word boundary before max_size
        """
        # Find last space before max_size
        last_space = text.rfind(' ')
        if last_space > self.min_size:
            return last_space + 1
        
        # No space found - break at max_size (shouldn't happen with normal text)
        return self.max_size
    
    @property
    def buffer_size(self) -> int:
        """Current buffer size in characters."""
        return len(self._buffer)
    
    @property
    def has_content(self) -> bool:
        """Whether buffer has any content."""
        return bool(self._buffer.strip())
    
    def clear(self) -> None:
        """Clear buffer and ready chunks."""
        self._buffer = ""
        self._ready_chunks = []


def chunk_text(text: str, target_size: int = 500) -> List[str]:
    """
    Convenience function to chunk a complete text.
    
    Args:
        text: Complete text to chunk
        target_size: Target chunk size
        
    Returns:
        List of chunks
    """
    chunker = SmartChunker(target_size=target_size)
    chunker.add_text(text)
    chunks = chunker.get_chunks()
    
    final = chunker.flush()
    if final:
        chunks.append(final)
    
    return chunks
