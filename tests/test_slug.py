from scout.utils.slug import slugify


def test_basic_ascii():
    assert slugify("Hello World") == "hello-world"


def test_punctuation_collapses_to_hyphen():
    assert slugify("RAG is dead, long live agents!") == "rag-is-dead-long-live-agents"


def test_chinese_falls_back_to_untitled():
    # Without transliteration, all CJK chars are stripped — defensive default
    assert slugify("微调技巧") == "untitled"


def test_keeps_digits():
    assert slugify("Llama 3.1 vs GPT-4o") == "llama-3-1-vs-gpt-4o"


def test_truncates_to_max_len():
    s = slugify("a" * 200, max_len=20)
    assert len(s) <= 20


def test_empty_input():
    assert slugify("") == "untitled"
    assert slugify("   ") == "untitled"
