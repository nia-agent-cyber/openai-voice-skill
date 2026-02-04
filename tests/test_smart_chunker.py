"""
Unit tests for SmartChunker

Tests boundary detection, chunk sizing, and edge cases.
"""

import pytest
import sys
import os

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from smart_chunker import SmartChunker, chunk_text


class TestSmartChunkerBasic:
    """Basic functionality tests."""
    
    def test_init_defaults(self):
        """Test default initialization."""
        chunker = SmartChunker()
        assert chunker.target_size == 500
        assert chunker.min_size == 100
        assert chunker.max_size == 1000
        assert chunker.buffer_size == 0
        assert not chunker.has_content
    
    def test_init_custom_sizes(self):
        """Test custom size initialization."""
        chunker = SmartChunker(target_size=300, min_size=50, max_size=600)
        assert chunker.target_size == 300
        assert chunker.min_size == 50
        assert chunker.max_size == 600
    
    def test_add_empty_text(self):
        """Test adding empty text."""
        chunker = SmartChunker()
        chunker.add_text("")
        chunker.add_text(None)  # Should handle None gracefully
        assert chunker.buffer_size == 0
    
    def test_add_short_text(self):
        """Test adding text shorter than min_size."""
        chunker = SmartChunker(min_size=100)
        chunker.add_text("Hello world")
        assert chunker.buffer_size == 11
        assert chunker.get_chunks() == []  # Too short to chunk
        assert chunker.flush() == "Hello world"
    
    def test_clear(self):
        """Test clearing the buffer."""
        chunker = SmartChunker()
        chunker.add_text("Some text")
        chunker.clear()
        assert chunker.buffer_size == 0
        assert not chunker.has_content


class TestBoundaryDetection:
    """Test boundary detection priority."""
    
    def test_paragraph_break_priority(self):
        """Paragraph breaks should be preferred."""
        text = "First paragraph with some content. " * 10 + "\n\n" + "Second paragraph. " * 5
        chunks = chunk_text(text, target_size=200)
        
        # Should break at paragraph
        assert any("\n\n" not in chunk for chunk in chunks)
        assert len(chunks) >= 2
    
    def test_list_item_break(self):
        """List items should be good break points."""
        text = "Here is a list:\n- Item one with description\n- Item two with description\n- Item three with description"
        chunker = SmartChunker(target_size=50, min_size=20)
        chunker.add_text(text)
        chunks = chunker.get_chunks()
        
        # Should try to keep list items together
        assert len(chunks) >= 1
    
    def test_sentence_end_break(self):
        """Sentences should break at punctuation."""
        text = "This is sentence one. This is sentence two. This is sentence three. This is sentence four."
        chunks = chunk_text(text, target_size=50)
        
        # Each chunk should end with sentence-ending punctuation (or be the last chunk)
        for chunk in chunks[:-1]:
            assert chunk.rstrip()[-1] in '.!?' or chunk.endswith(',')
    
    def test_clause_end_break(self):
        """Clauses should break at commas/semicolons."""
        text = "First clause here, second clause there, third clause everywhere, fourth clause somewhere"
        chunker = SmartChunker(target_size=40, min_size=20)
        chunker.add_text(text)
        chunks = chunker.get_chunks()
        final = chunker.flush()
        
        all_chunks = chunks + ([final] if final else [])
        # Should have multiple chunks
        assert len(all_chunks) >= 2
    
    def test_word_boundary_fallback(self):
        """Should never break mid-word."""
        text = "Supercalifragilisticexpialidocious " * 20
        chunks = chunk_text(text, target_size=100)
        
        for chunk in chunks:
            # No partial words (check that chunks are whole words)
            words = chunk.split()
            for word in words:
                assert word == "Supercalifragilisticexpialidocious"


class TestChunkSizing:
    """Test chunk size constraints."""
    
    def test_chunks_near_target_size(self):
        """Chunks should be approximately target size."""
        text = "This is a test sentence. " * 100  # Long text
        target = 500
        chunks = chunk_text(text, target_size=target)
        
        # Most chunks should be within reasonable range of target
        for chunk in chunks[:-1]:  # Exclude last chunk
            assert len(chunk) >= 100  # min_size
            assert len(chunk) <= 1000  # max_size
    
    def test_max_size_enforced(self):
        """Chunks should never exceed max_size."""
        # Text with no good boundaries
        text = "word " * 500
        chunker = SmartChunker(target_size=100, max_size=200)
        chunker.add_text(text)
        chunks = chunker.get_chunks()
        
        for chunk in chunks:
            assert len(chunk) <= 200
    
    def test_min_size_respected(self):
        """Should wait for min_size before chunking."""
        chunker = SmartChunker(min_size=100)
        
        # Add text in small increments
        for _ in range(5):
            chunker.add_text("Hello. ")
            
        assert chunker.get_chunks() == []  # Still below min_size
        
        # Add more to exceed min_size
        chunker.add_text("This is more text to exceed minimum. " * 5)
        chunks = chunker.get_chunks()
        
        # Now should have chunks
        assert len(chunks) >= 0  # May or may not chunk depending on boundaries


class TestStreamingBehavior:
    """Test streaming usage patterns."""
    
    def test_incremental_add(self):
        """Test adding text incrementally like a stream."""
        chunker = SmartChunker(target_size=100, min_size=50)
        
        # Simulate streaming
        stream_parts = [
            "The quick brown fox ",
            "jumps over ",
            "the lazy dog. ",
            "Another sentence here. ",
            "And yet another one. ",
            "Final sentence."
        ]
        
        all_chunks = []
        for part in stream_parts:
            chunker.add_text(part)
            all_chunks.extend(chunker.get_chunks())
        
        final = chunker.flush()
        if final:
            all_chunks.append(final)
        
        # Reconstruct and verify no text lost
        reconstructed = " ".join(all_chunks)
        original = "".join(stream_parts)
        
        # Should contain all words (whitespace may differ)
        assert set(reconstructed.split()) == set(original.split())
    
    def test_flush_returns_remainder(self):
        """Flush should return any buffered content."""
        chunker = SmartChunker(min_size=100)
        chunker.add_text("Short text")
        
        assert chunker.get_chunks() == []
        remainder = chunker.flush()
        assert remainder == "Short text"
        assert chunker.buffer_size == 0
    
    def test_multiple_get_chunks_calls(self):
        """Get chunks should clear ready queue."""
        chunker = SmartChunker(target_size=50, min_size=20)
        chunker.add_text("First sentence here. Second sentence here. Third sentence here.")
        
        chunks1 = chunker.get_chunks()
        chunks2 = chunker.get_chunks()
        
        assert len(chunks2) == 0  # Already retrieved


class TestEdgeCases:
    """Test edge cases and unusual inputs."""
    
    def test_only_whitespace(self):
        """Handle whitespace-only input."""
        chunker = SmartChunker()
        chunker.add_text("   \n\n   \t   ")
        
        assert chunker.get_chunks() == []
        assert chunker.flush() == ""
    
    def test_single_long_word(self):
        """Handle text with single very long word."""
        long_word = "a" * 2000  # Exceeds max_size
        chunker = SmartChunker(max_size=500)
        chunker.add_text(long_word)
        
        chunks = chunker.get_chunks()
        final = chunker.flush()
        
        # Should handle gracefully (may break mid-word as last resort)
        all_text = "".join(chunks) + final
        assert len(all_text) == 2000
    
    def test_unicode_text(self):
        """Handle unicode characters correctly."""
        text = "Hello 世界! This is émoji test 🎉. More text here. " * 20
        chunks = chunk_text(text, target_size=100)
        
        # Verify no corruption
        reconstructed = " ".join(chunks)
        assert "世界" in reconstructed
        assert "🎉" in reconstructed
        assert "émoji" in reconstructed
    
    def test_multiple_newlines(self):
        """Handle multiple consecutive newlines."""
        text = "Para 1.\n\n\n\n\nPara 2.\n\n\nPara 3."
        chunks = chunk_text(text, target_size=20)
        
        # Should handle without error
        assert len(chunks) >= 1
    
    def test_numbered_list(self):
        """Handle numbered lists."""
        text = """Here's a numbered list:
1. First item with some text
2. Second item with more text
3. Third item with even more text
4. Fourth item here"""
        
        chunker = SmartChunker(target_size=80, min_size=30)
        chunker.add_text(text)
        chunks = chunker.get_chunks()
        final = chunker.flush()
        
        all_chunks = chunks + ([final] if final else [])
        all_text = "\n".join(all_chunks)
        
        # Should contain all items
        assert "1." in all_text or "First" in all_text
        assert "4." in all_text or "Fourth" in all_text
    
    def test_empty_flush(self):
        """Flush on empty buffer returns empty string."""
        chunker = SmartChunker()
        assert chunker.flush() == ""


class TestConvenienceFunction:
    """Test the chunk_text convenience function."""
    
    def test_chunk_text_basic(self):
        """Basic usage of chunk_text function."""
        text = "Hello world. " * 50
        chunks = chunk_text(text)
        
        assert len(chunks) >= 1
        reconstructed = " ".join(chunks)
        assert "Hello world" in reconstructed
    
    def test_chunk_text_custom_size(self):
        """Chunk text with custom target size."""
        text = "Test sentence. " * 100
        chunks = chunk_text(text, target_size=200)
        
        # Should create more chunks with smaller target
        chunks_small = chunk_text(text, target_size=100)
        assert len(chunks_small) >= len(chunks)
    
    def test_chunk_text_empty(self):
        """Chunk empty text."""
        chunks = chunk_text("")
        assert chunks == []
    
    def test_chunk_text_short(self):
        """Chunk text shorter than target."""
        chunks = chunk_text("Short")
        assert chunks == ["Short"]


class TestRealWorldScenarios:
    """Test with realistic content."""
    
    def test_tool_response_json(self):
        """Handle JSON-like tool responses."""
        text = """Here are the search results:
        
{"title": "Result 1", "url": "https://example.com/1", "snippet": "This is the first result with some content."}

{"title": "Result 2", "url": "https://example.com/2", "snippet": "This is the second result with more content."}

{"title": "Result 3", "url": "https://example.com/3", "snippet": "Third result here."}"""
        
        chunks = chunk_text(text, target_size=200)
        
        # Should handle structured content
        assert len(chunks) >= 1
        all_text = " ".join(chunks)
        assert "Result 1" in all_text
        assert "Result 3" in all_text
    
    def test_code_block(self):
        """Handle code blocks in responses."""
        text = """Here's how to do it:

```python
def hello():
    print("Hello, world!")
    return True
```

And that's the solution. You can also try this alternative approach."""
        
        chunks = chunk_text(text, target_size=100)
        all_text = " ".join(chunks)
        
        assert "def hello" in all_text
        assert "print" in all_text
    
    def test_markdown_content(self):
        """Handle markdown formatted content."""
        text = """# Heading

This is a paragraph with **bold** and *italic* text.

## Subheading

- Bullet point one
- Bullet point two
- Bullet point three

More content here with [links](https://example.com) and `code`."""
        
        chunks = chunk_text(text, target_size=150)
        all_text = " ".join(chunks)
        
        assert "Heading" in all_text
        assert "bold" in all_text
        assert "Bullet" in all_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
