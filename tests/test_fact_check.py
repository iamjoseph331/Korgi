from korgi.resume import fact_check


def test_split_sentences_skips_headings_and_short():
    md = """# Title

## 概要

これは一文目です。これは二文目です。

- 箇条書きは無視

短い。
"""
    sents = fact_check._split_sentences(md)
    assert any("一文目" in s for s in sents)
    assert any("二文目" in s for s in sents)
    assert not any(s.startswith("#") for s in sents)
    assert "短い。" not in sents  # below min length threshold
