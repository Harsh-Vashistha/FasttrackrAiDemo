"""
Audio transcription via OpenAI Whisper (local model).

Whisper is a heavy optional dependency that requires PyTorch.
Install: pip install openai-whisper
See:     https://github.com/openai/whisper#setup

This module is intentionally minimal — it does one thing: convert an
audio file into a plain-text transcript.  All AI extraction logic lives
in parsers/agent.py (the LangGraph pipeline).
"""


def transcribe_audio(file_path: str) -> str:
    """
    Transcribe an audio file using OpenAI Whisper running locally.

    Whisper is loaded lazily on first call.  The "base" model runs on CPU
    without a GPU; upgrade to "small" or "medium" for better accuracy on
    accented speech or financial terminology.

    Args:
        file_path: Absolute path to the audio file.
                   Supported formats: mp3, mp4, wav, m4a, ogg, flac, webm.

    Returns:
        Full transcript as a plain UTF-8 string.

    Raises:
        RuntimeError: If openai-whisper or PyTorch is not installed.
    """
    try:
        import whisper
    except ImportError as exc:
        raise RuntimeError(
            "openai-whisper is not installed.\n"
            "Run: pip install openai-whisper\n"
            "Note: requires PyTorch — see https://pytorch.org/get-started/\n"
            f"Original error: {exc}"
        ) from exc

    model = whisper.load_model("base")
    result = model.transcribe(file_path)
    return result["text"]
