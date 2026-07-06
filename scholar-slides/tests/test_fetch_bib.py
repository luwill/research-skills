"""Unit + (live) integration tests for the citation resolver."""
import fetch_bib as fb
import pytest


class TestClassify:
    def test_arxiv(self):
        assert fb.classify_query("1706.03762") == ("arxiv", "1706.03762")
        assert fb.classify_query("arXiv:1706.03762v5") == ("arxiv", "1706.03762")

    def test_doi(self):
        assert fb.classify_query("10.1145/3292500.3330701") == ("doi", "10.1145/3292500.3330701")

    def test_title(self):
        assert fb.classify_query("Attention Is All You Need") == ("title", "Attention Is All You Need")


def test_title_match_guards_wrong_crossref_hit():
    assert fb.title_match("Attention Is All You Need", "Attention is All you Need")  # casing
    # both real wrong hits Crossref returned for this query must be rejected:
    assert not fb.title_match("Attention Is All You Need", "From Human Attention to Computational Attention")
    assert not fb.title_match("Attention Is All You Need", "Is Attention All You Need?")  # reordered = different paper
    # a legitimate subtitle extension of the same paper is accepted:
    assert fb.title_match("FlashAttention-2: Faster Attention", "FlashAttention-2: Faster Attention with Better Parallelism")
    # a too-generic prefix must NOT match
    assert not fb.title_match("Attention", "Attention Is All You Need")


def test_make_key():
    assert fb.make_key(["Ashish Vaswani", "Noam Shazeer"], "2017") == "vaswani2017"
    assert fb.make_key([], None) == "anon"


def test_format_reference_truncates_authors():
    e = {"authors": ["A B", "C D", "E F", "G H", "I J", "K L", "M N"], "year": "2017",
         "title": "Attention Is All You Need", "venue": "NeurIPS", "arxiv": "1706.03762"}
    ref = fb.format_reference(e)
    assert "et al." in ref and "(2017)" in ref and "arXiv:1706.03762" in ref


def test_parse_crossref_message():
    msg = {
        "title": ["Attention Is All You Need"],
        "author": [{"given": "Ashish", "family": "Vaswani"}, {"given": "Noam", "family": "Shazeer"}],
        "issued": {"date-parts": [[2017, 6, 12]]},
        "container-title": ["NeurIPS"],
        "DOI": "10.5555/3295222.3295349",
        "type": "proceedings-article",
    }
    e = fb.parse_crossref_message(msg)
    assert e["resolved"] and e["key"] == "vaswani2017"
    assert e["year"] == "2017" and e["type"] == "inproceedings"
    assert e["authors"][0] == "Ashish Vaswani" and e["doi"].startswith("10.5555")


def test_parse_arxiv_atom():
    xml = """<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <entry>
        <id>http://arxiv.org/abs/1706.03762v7</id>
        <published>2017-06-12T17:57:34Z</published>
        <title>Attention Is All You Need</title>
        <author><name>Ashish Vaswani</name></author>
        <author><name>Noam Shazeer</name></author>
      </entry></feed>"""
    e = fb.parse_arxiv_atom(xml)
    assert e["resolved"] and e["arxiv"] == "1706.03762" and e["year"] == "2017"
    assert e["key"] == "vaswani2017" and e["title"] == "Attention Is All You Need"


@pytest.mark.integration
def test_resolve_arxiv_live():
    e = fb.resolve("1706.03762")
    assert e.get("resolved") and "Attention" in e["title"] and e["arxiv"] == "1706.03762"
