from scout.filter.keywords import parse

CONFIG = """
# global default
LLM
RAG

[Frameworks]
LangChain
DSPy
+production
!course

[Models]
GPT-5
/llama-?\\d/i => llama-N
"""


def test_default_group_basic_match():
    kw = parse(CONFIG)
    names, groups, score = kw.match("LLM scaling laws revisited")
    assert names == ["LLM"]
    assert "_default" in groups
    assert score == 1


def test_must_word_required():
    kw = parse(CONFIG)
    # LangChain hit but no 'production' -> Frameworks group skipped
    names, groups, _ = kw.match("LangChain v2 changelog")
    assert "Frameworks" not in groups
    # Add 'production' -> hits
    names, groups, _ = kw.match("LangChain v2 in production at scale")
    assert "Frameworks" in groups
    assert "LangChain" in names


def test_forbid_blocks_globally():
    kw = parse(CONFIG)
    # Forbid 'course' should block even if other groups match
    names, groups, _ = kw.match("LangChain production course - 50% off")
    assert names == []
    assert groups == []


def test_regex_with_alias():
    kw = parse(CONFIG)
    names, _, _ = kw.match("Benchmarking llama-3 against gpt-4")
    assert "llama-N" in names


def test_compound_token_no_word_boundary_failure():
    kw = parse(CONFIG)
    # GPT-5 has a hyphen — must still match
    names, _, _ = kw.match("OpenAI announces GPT-5 with reasoning improvements")
    assert "GPT-5" in names


def test_blank_lines_and_comments_ignored():
    kw = parse("""
    # this is a comment

    LLM

    """)
    names, _, _ = kw.match("LLM news")
    assert names == ["LLM"]
