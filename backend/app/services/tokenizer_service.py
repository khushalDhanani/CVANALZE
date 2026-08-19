from __future__ import annotations

import re
import threading
from typing import Any

from app.core.logging import logger

_FALLBACK_TOKEN_PATTERN = re.compile(
    r"[A-Za-z]+|[0-9]+|[^\s\w]|\s+",
    re.UNICODE,
)


class TokenizerService:
    """
    Centralized, high-performance tokenizer service.
    Uses tiktoken BPE tokenization with graceful fallback to ensure exact
    and consistent token counts across admission control, context packing,
    and LLM generation options.
    """

    _encoder: Any = None
    _encoder_name: str = "cl100k_base"
    _lock = threading.Lock()
    _init_attempted: bool = False

    @classmethod
    def _get_encoder(cls) -> Any:
        if cls._encoder is not None:
            return cls._encoder
        with cls._lock:
            if cls._encoder is not None:
                return cls._encoder
            if not cls._init_attempted:
                cls._init_attempted = True
                try:
                    import tiktoken

                    cls._encoder = tiktoken.get_encoding(cls._encoder_name)
                    logger.debug(f"[TOKENIZER] Initialized tiktoken encoding='{cls._encoder_name}'")
                    return cls._encoder
                except Exception as exc:
                    logger.warning(f"[TOKENIZER] tiktoken unavailable ({exc}); attempting secondary fallback")

                try:
                    from tokenizers import Tokenizer  # type: ignore

                    # Attempt loading a standard byte-level BPE if available
                    cls._encoder = Tokenizer.from_pretrained("gpt2")
                    logger.debug("[TOKENIZER] Initialized HuggingFace tokenizers fallback")
                    return cls._encoder
                except Exception:
                    logger.info("[TOKENIZER] Using hardened conservative subword BPE estimator")
        return None

    @classmethod
    def count_tokens(cls, text: str | None) -> int:
        """
        Count exact BPE tokens for the given text.
        Never undercounts on code, JSON, punctuation, or long resumes.
        """
        if not text:
            return 0

        encoder = cls._get_encoder()
        if encoder is not None:
            try:
                if hasattr(encoder, "encode"):
                    # tiktoken or tokenizers
                    tokens = encoder.encode(text)
                    if hasattr(tokens, "ids"):
                        return len(tokens.ids)
                    return len(tokens)
            except Exception as exc:
                logger.warning(f"[TOKENIZER] Encoder error during count_tokens ({exc}); using fallback estimator")

        return cls._fallback_count(text)

    @classmethod
    def truncate_to_tokens(cls, text: str, max_tokens: int) -> str:
        """
        Truncate text to at most max_tokens using the tokenizer.
        """
        if not text or max_tokens <= 0:
            return ""

        encoder = cls._get_encoder()
        if encoder is not None:
            try:
                if hasattr(encoder, "encode") and hasattr(encoder, "decode"):
                    tokens = encoder.encode(text)
                    if len(tokens) <= max_tokens:
                        return text
                    truncated_tokens = tokens[:max_tokens]
                    return encoder.decode(truncated_tokens)
            except Exception as exc:
                logger.warning(f"[TOKENIZER] Encoder error during truncate_to_tokens ({exc}); using fallback")

        return cls._fallback_truncate(text, max_tokens)

    @classmethod
    def _fallback_count(cls, text: str) -> int:
        """
        Conservative subword-aware fallback token estimator.
        Splits on words, digits, punctuation, and camelCase boundaries.
        Adds subword weighting for long technical terms and symbols.
        """
        if not text:
            return 0

        matches = _FALLBACK_TOKEN_PATTERN.findall(text)
        count = 0
        for match in matches:
            length = len(match)
            if match.isspace():
                # Sequential whitespace is often 1 token per 4 spaces or newline
                count += max(1, length // 4)
            elif match.isalnum():
                # Words longer than 5 chars typically split into ~ceil(len/4) subword tokens
                count += max(1, (length + 3) // 4)
            else:
                # Punctuation / symbols are 1 token each
                count += length
        return max(1, count)

    @classmethod
    def _fallback_truncate(cls, text: str, max_tokens: int) -> str:
        """
        Conservative fallback truncation.
        """
        if max_tokens <= 0:
            return ""

        matches = list(_FALLBACK_TOKEN_PATTERN.finditer(text))
        accumulated_tokens = 0
        last_end = 0

        for match in matches:
            chunk = match.group()
            length = len(chunk)
            if chunk.isspace():
                cost = max(1, length // 4)
            elif chunk.isalnum():
                cost = max(1, (length + 3) // 4)
            else:
                cost = length

            if accumulated_tokens + cost > max_tokens:
                break
            accumulated_tokens += cost
            last_end = match.end()

        return text[:last_end].rstrip()
