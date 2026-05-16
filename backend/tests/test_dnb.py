"""Unit tests for app.dnb — DNB SRU client and MARC21 parser.

Tests cover:
  - fetch_dnb_by_isbn HTTP layer (success, timeout, network error, non-200)
  - _parse_sru_response (invalid XML, missing record element)
  - _parse_marc_record field extraction (title, series, authors, pub year,
    page count, description, chapters, language, demographic, dnb_id, isbn)
  - _parse_chapters (labeled, numbered, decimal, unstructured, empty)
  - _detect_media_type heuristic
"""
import pytest
import respx
import httpx

from app import dnb


DNB_SRU = "https://services.dnb.de/sru/dnb"

# ---------------------------------------------------------------------------
# XML fixture helpers
# ---------------------------------------------------------------------------

def _sru_wrap(marc_inner: str) -> bytes:
    """Wrap a MARC21 <record> element in a full SRU response envelope."""
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <numberOfRecords>1</numberOfRecords>
  <records>
    <record>
      <recordData>
        {marc_inner}
      </recordData>
    </record>
  </records>
</searchRetrieveResponse>"""
    return xml.encode("utf-8")


def _marc(fields: str, ctrl: str = "") -> bytes:
    """Minimal MARC21 record with the given control fields and datafields."""
    return _sru_wrap(f"""
<record xmlns="http://www.loc.gov/MARC21/slim">
  <controlfield tag="001">TEST001</controlfield>
  {ctrl}
  {fields}
</record>""")


# Full Naruto vol-73 fixture — exercises every major field
NARUTO_XML = _sru_wrap("""
<record xmlns="http://www.loc.gov/MARC21/slim">
  <controlfield tag="001">1234567890</controlfield>
  <controlfield tag="008">240101s2024    gw |||||||||||||ger  </controlfield>
  <datafield tag="020" ind1=" " ind2=" ">
    <subfield code="a">9783551710963 (Gb.)</subfield>
  </datafield>
  <datafield tag="100" ind1="1" ind2=" ">
    <subfield code="a">Kishimoto, Masashi</subfield>
  </datafield>
  <datafield tag="245" ind1="1" ind2="0">
    <subfield code="a">Naruto</subfield>
    <subfield code="n">73</subfield>
    <subfield code="p">The Final Battle</subfield>
  </datafield>
  <datafield tag="246" ind1="1" ind2="3">
    <subfield code="a">&#12490;&#12523;&#12488;</subfield>
  </datafield>
  <datafield tag="264" ind1=" " ind2="1">
    <subfield code="c">2024</subfield>
  </datafield>
  <datafield tag="300" ind1=" " ind2=" ">
    <subfield code="a">192 Seiten</subfield>
  </datafield>
  <datafield tag="490" ind1="1" ind2=" ">
    <subfield code="a">Naruto</subfield>
    <subfield code="v">73</subfield>
  </datafield>
  <datafield tag="520" ind1=" " ind2=" ">
    <subfield code="a">Narutos Abenteuer gehen weiter.</subfield>
  </datafield>
  <datafield tag="505" ind1="0" ind2=" ">
    <subfield code="a">Kapitel 697: Naruto und Sasuke -- Kapitel 698: Das Ende</subfield>
  </datafield>
  <datafield tag="041" ind1=" " ind2=" ">
    <subfield code="a">ger</subfield>
  </datafield>
  <datafield tag="650" ind1=" " ind2="7">
    <subfield code="a">Sh&#333;nen-Manga</subfield>
  </datafield>
</record>
""")


# ---------------------------------------------------------------------------
# fetch_dnb_by_isbn — HTTP layer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_fetch_success():
    respx.get(DNB_SRU).respond(200, content=NARUTO_XML)
    result = await dnb.fetch_dnb_by_isbn("9783551710963")
    assert result is not None
    assert result["title"] == "Naruto"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_timeout_returns_none():
    respx.get(DNB_SRU).mock(side_effect=httpx.TimeoutException("timeout"))
    assert await dnb.fetch_dnb_by_isbn("9783551710963") is None


@pytest.mark.asyncio
@respx.mock
async def test_fetch_request_error_returns_none():
    respx.get(DNB_SRU).mock(side_effect=httpx.RequestError("refused"))
    assert await dnb.fetch_dnb_by_isbn("9783551710963") is None


@pytest.mark.asyncio
@respx.mock
async def test_fetch_non200_returns_none():
    respx.get(DNB_SRU).respond(503)
    assert await dnb.fetch_dnb_by_isbn("9783551710963") is None


# ---------------------------------------------------------------------------
# _parse_sru_response — XML parsing
# ---------------------------------------------------------------------------

def test_parse_invalid_xml_returns_none():
    assert dnb._parse_sru_response(b"not xml at all", "isbn") is None


def test_parse_empty_bytes_returns_none():
    assert dnb._parse_sru_response(b"", "isbn") is None


def test_parse_no_marc_record_returns_none():
    xml = b"""<?xml version="1.0"?>
<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">
  <numberOfRecords>0</numberOfRecords>
</searchRetrieveResponse>"""
    assert dnb._parse_sru_response(xml, "isbn") is None


# ---------------------------------------------------------------------------
# Full record parsing — Naruto fixture
# ---------------------------------------------------------------------------

def test_naruto_title():
    r = dnb._parse_sru_response(NARUTO_XML, "9783551710963")
    assert r["title"] == "Naruto"


def test_naruto_volume_number_from_490():
    """490 $v takes priority over 245 $n for volume number."""
    r = dnb._parse_sru_response(NARUTO_XML, "")
    assert r["volume_number"] == "73"


def test_naruto_volume_title_from_245p():
    r = dnb._parse_sru_response(NARUTO_XML, "")
    assert r["volume_title"] == "The Final Battle"


def test_naruto_series_name():
    r = dnb._parse_sru_response(NARUTO_XML, "")
    assert r["series_name"] == "Naruto"


def test_naruto_author_normalized():
    """'Kishimoto, Masashi' → 'Masashi Kishimoto'."""
    r = dnb._parse_sru_response(NARUTO_XML, "")
    assert r["authors"] == ["Masashi Kishimoto"]


def test_naruto_pub_year():
    r = dnb._parse_sru_response(NARUTO_XML, "")
    assert r["publication_year"] == 2024


def test_naruto_page_count():
    r = dnb._parse_sru_response(NARUTO_XML, "")
    assert r["page_count"] == 192


def test_naruto_description():
    r = dnb._parse_sru_response(NARUTO_XML, "")
    assert r["description"] == "Narutos Abenteuer gehen weiter."


def test_naruto_language():
    r = dnb._parse_sru_response(NARUTO_XML, "")
    assert r["language"] == "ger"


def test_naruto_demographic_shounen():
    r = dnb._parse_sru_response(NARUTO_XML, "")
    assert r["demographic"] == "shounen"


def test_naruto_media_type_manga():
    r = dnb._parse_sru_response(NARUTO_XML, "")
    assert r["media_type"] == "manga"


def test_naruto_dnb_id():
    r = dnb._parse_sru_response(NARUTO_XML, "")
    assert r["dnb_id"] == "1234567890"


def test_naruto_isbn_qualifier_stripped():
    r = dnb._parse_sru_response(NARUTO_XML, "9783551710963")
    assert r["isbn"] == "9783551710963"


def test_naruto_chapters_parsed():
    r = dnb._parse_sru_response(NARUTO_XML, "")
    assert len(r["chapters"]) == 2
    assert r["chapters"][0]["chapter_number"] == "697"
    assert r["chapters"][0]["title"] == "Naruto und Sasuke"
    assert r["chapters"][1]["chapter_number"] == "698"


def test_naruto_original_title_cjk():
    """CJK characters in 246 are stored as original_title."""
    r = dnb._parse_sru_response(NARUTO_XML, "")
    assert r["original_title"] is not None
    assert len(r["original_title"]) > 0


# ---------------------------------------------------------------------------
# Individual field edge cases
# ---------------------------------------------------------------------------

def test_isbn_qualifier_variants():
    """Various parenthetical qualifiers are stripped from ISBN."""
    for qualifier in ["(Gb.)", "(kart.)", "(Br.)"]:
        xml = _marc(f"""
<datafield tag="020" ind1=" " ind2=" ">
  <subfield code="a">9781234567890 {qualifier}</subfield>
</datafield>
<datafield tag="245" ind1=" " ind2=" ">
  <subfield code="a">Test</subfield>
</datafield>""")
        r = dnb._parse_sru_response(xml, "")
        assert r["isbn"] == "9781234567890", f"Failed for qualifier {qualifier}"


def test_author_no_comma_single_name():
    """Author with no comma (e.g. CLAMP) stays unchanged."""
    xml = _marc("""
<datafield tag="100" ind1="1" ind2=" ">
  <subfield code="a">CLAMP</subfield>
</datafield>
<datafield tag="245" ind1=" " ind2=" ">
  <subfield code="a">Cardcaptor Sakura</subfield>
</datafield>""")
    r = dnb._parse_sru_response(xml, "")
    assert r["authors"] == ["CLAMP"]


def test_multiple_authors_700():
    """100 + 700 entries are both collected and de-duplicated."""
    xml = _marc("""
<datafield tag="100" ind1="1" ind2=" ">
  <subfield code="a">Oda, Eiichiro</subfield>
</datafield>
<datafield tag="700" ind1="1" ind2=" ">
  <subfield code="a">Müller, Petra</subfield>
</datafield>
<datafield tag="245" ind1=" " ind2=" ">
  <subfield code="a">One Piece</subfield>
</datafield>""")
    r = dnb._parse_sru_response(xml, "")
    assert "Eiichiro Oda" in r["authors"]
    assert "Petra Müller" in r["authors"]
    assert len(r["authors"]) == 2


def test_page_count_seiten():
    xml = _marc("""
<datafield tag="245" ind1=" " ind2=" "><subfield code="a">T</subfield></datafield>
<datafield tag="300" ind1=" " ind2=" ">
  <subfield code="a">228 Seiten</subfield>
</datafield>""")
    assert dnb._parse_sru_response(xml, "")["page_count"] == 228


def test_page_count_pages_english():
    xml = _marc("""
<datafield tag="245" ind1=" " ind2=" "><subfield code="a">T</subfield></datafield>
<datafield tag="300" ind1=" " ind2=" ">
  <subfield code="a">310 pages</subfield>
</datafield>""")
    assert dnb._parse_sru_response(xml, "")["page_count"] == 310


def test_page_count_fallback_first_number():
    """When no 'Seiten'/'pages' keyword, first number is used."""
    xml = _marc("""
<datafield tag="245" ind1=" " ind2=" "><subfield code="a">T</subfield></datafield>
<datafield tag="300" ind1=" " ind2=" ">
  <subfield code="a">192 S. : Ill.</subfield>
</datafield>""")
    assert dnb._parse_sru_response(xml, "")["page_count"] == 192


def test_pub_year_from_264():
    xml = _marc("""
<datafield tag="245" ind1=" " ind2=" "><subfield code="a">T</subfield></datafield>
<datafield tag="264" ind1=" " ind2="1">
  <subfield code="c">© 2022</subfield>
</datafield>""")
    assert dnb._parse_sru_response(xml, "")["publication_year"] == 2022


def test_pub_year_from_008_fallback():
    """When 264 is absent, year is read from MARC 008 positions 7-10."""
    xml = _marc(
        """<datafield tag="245" ind1=" " ind2=" "><subfield code="a">T</subfield></datafield>""",
        ctrl='<controlfield tag="008">240101s2019    gw |||||||||||||ger  </controlfield>',
    )
    assert dnb._parse_sru_response(xml, "")["publication_year"] == 2019


def test_830_series_fallback():
    """830 used when 490 is absent."""
    xml = _marc("""
<datafield tag="245" ind1=" " ind2=" "><subfield code="a">Dragon Ball</subfield></datafield>
<datafield tag="830" ind1=" " ind2="0">
  <subfield code="a">Dragon Ball</subfield>
  <subfield code="v">1</subfield>
</datafield>""")
    r = dnb._parse_sru_response(xml, "")
    assert r["series_name"] == "Dragon Ball"
    assert r["volume_number"] == "1"


def test_volume_number_245n_fallback():
    """When no 490/830, volume number comes from 245 $n."""
    xml = _marc("""
<datafield tag="245" ind1=" " ind2=" ">
  <subfield code="a">My Hero Academia</subfield>
  <subfield code="n">5</subfield>
</datafield>""")
    r = dnb._parse_sru_response(xml, "")
    assert r["volume_number"] == "5"


def test_normalize_volume_number_no_digits():
    """Raw string with no digits returns the stripped string unchanged."""
    assert dnb._normalize_volume_number("Sonderband") == "Sonderband"


def test_normalize_volume_number_none():
    assert dnb._normalize_volume_number(None) is None


def test_demographic_all_values():
    for dnb_subject, expected in [
        ("Shōnen-Manga", "shounen"),
        ("Shōjo-Manga", "shoujo"),
        ("Seinen-Manga", "seinen"),
        ("Josei-Manga", "josei"),
    ]:
        xml = _marc(f"""
<datafield tag="245" ind1=" " ind2=" "><subfield code="a">T</subfield></datafield>
<datafield tag="650" ind1=" " ind2="7">
  <subfield code="a">{dnb_subject}</subfield>
</datafield>""")
        r = dnb._parse_sru_response(xml, "")
        assert r["demographic"] == expected, f"Expected {expected} for '{dnb_subject}'"


def test_enhanced_505_t_subfields():
    """Enhanced 505 with $t subfields per chapter."""
    xml = _marc("""
<datafield tag="245" ind1=" " ind2=" "><subfield code="a">T</subfield></datafield>
<datafield tag="505" ind1="0" ind2="0">
  <subfield code="t">Kapitel 1: Erster Teil</subfield>
  <subfield code="t">Kapitel 2: Zweiter Teil</subfield>
</datafield>""")
    r = dnb._parse_sru_response(xml, "")
    assert len(r["chapters"]) == 2


# ---------------------------------------------------------------------------
# _parse_chapters
# ---------------------------------------------------------------------------

def test_chapters_labeled_kapitel():
    chs = dnb._parse_chapters("Kapitel 1: Anfang -- Kapitel 2: Mitte -- Kapitel 3: Ende")
    assert len(chs) == 3
    assert chs[0] == {"order_index": 0, "chapter_number": "1", "title": "Anfang"}
    assert chs[2]["chapter_number"] == "3"


def test_chapters_labeled_chapter_english():
    chs = dnb._parse_chapters("Chapter 10: Something -- Chapter 11: Another")
    assert chs[0]["chapter_number"] == "10"
    assert chs[1]["chapter_number"] == "11"


def test_chapters_numbered_dot():
    chs = dnb._parse_chapters("1. First -- 2. Second")
    assert chs[0]["chapter_number"] == "1"
    assert chs[0]["title"] == "First"


def test_chapters_decimal_number():
    chs = dnb._parse_chapters("Kapitel 1.5: Bonus-Story")
    assert len(chs) == 1
    assert chs[0]["chapter_number"] == "1.5"


def test_chapters_unstructured_entries():
    """Entries without numbers are stored with chapter_number=None."""
    chs = dnb._parse_chapters("Extra -- Farbseiten -- Bonus-Kapitel")
    assert len(chs) == 3
    assert all(ch["chapter_number"] is None for ch in chs)
    assert chs[0]["title"] == "Extra"


def test_chapters_empty_string():
    assert dnb._parse_chapters("") == []


def test_chapters_order_index_monotonic():
    chs = dnb._parse_chapters("Kapitel 1: A -- Kapitel 2: B -- Kapitel 3: C")
    assert [c["order_index"] for c in chs] == sorted(c["order_index"] for c in chs)


def test_chapters_semicolon_separator():
    chs = dnb._parse_chapters("Kapitel 1: A; Kapitel 2: B")
    assert len(chs) == 2


# ---------------------------------------------------------------------------
# _detect_media_type
# ---------------------------------------------------------------------------

def test_detect_manga_from_subject():
    assert dnb._detect_media_type(["Shōnen-Manga", "Comic"], "") == "manga"


def test_detect_comic_from_subject():
    assert dnb._detect_media_type(["Comic"], "") == "comic"


def test_detect_manga_from_title():
    assert dnb._detect_media_type([], "Best Manga Ever") == "manga"


def test_detect_book_fallback():
    assert dnb._detect_media_type([], "Harry Potter") == "book"
    assert dnb._detect_media_type([], "") == "book"


# ---------------------------------------------------------------------------
# 246 alternate-title branch coverage
# ---------------------------------------------------------------------------

def test_246_no_subfield_a_skipped():
    """246 field with no $a subfield is silently skipped (continue branch)."""
    xml = _marc("""
<datafield tag="245" ind1=" " ind2=" "><subfield code="a">Title</subfield></datafield>
<datafield tag="246" ind1="1" ind2=" ">
  <subfield code="b">subtitle only, no $a</subfield>
</datafield>""")
    r = dnb._parse_sru_response(xml, "")
    assert r["original_title"] is None
    assert r["romanized_title"] is None


def test_246_ind2_3_sets_romanized_title():
    """Non-CJK 246 with ind2='3' is stored as romanized_title."""
    xml = _marc("""
<datafield tag="245" ind1=" " ind2=" "><subfield code="a">Naruto</subfield></datafield>
<datafield tag="246" ind1="1" ind2="3">
  <subfield code="a">Naruto</subfield>
</datafield>""")
    r = dnb._parse_sru_response(xml, "")
    assert r["romanized_title"] == "Naruto"
    assert r["original_title"] is None


def test_246_non_cjk_non_ind2_3_sets_original_title():
    """Non-CJK 246 without ind2='3' falls through to original_title."""
    xml = _marc("""
<datafield tag="245" ind1=" " ind2=" "><subfield code="a">Narutaru</subfield></datafield>
<datafield tag="246" ind1="1" ind2=" ">
  <subfield code="a">Shadow Star Narutaru</subfield>
</datafield>""")
    r = dnb._parse_sru_response(xml, "")
    assert r["original_title"] == "Shadow Star Narutaru"


# ---------------------------------------------------------------------------
# Publication year / page-count edge cases
# ---------------------------------------------------------------------------

def test_pub_year_008_non_numeric_chars():
    """MARC 008 with non-numeric year chars triggers ValueError → year stays None."""
    xml = _marc(
        """<datafield tag="245" ind1=" " ind2=" "><subfield code="a">T</subfield></datafield>""",
        ctrl='<controlfield tag="008">240101sXXXX    gw |||||||||||||ger  </controlfield>',
    )
    assert dnb._parse_sru_response(xml, "")["publication_year"] is None


def test_page_count_bare_number_no_keyword():
    """300 $a with a bare number and no Seiten/pages/S. keyword uses fallback regex."""
    xml = _marc("""
<datafield tag="245" ind1=" " ind2=" "><subfield code="a">T</subfield></datafield>
<datafield tag="300" ind1=" " ind2=" ">
  <subfield code="a">192 : farb. Ill.</subfield>
</datafield>""")
    assert dnb._parse_sru_response(xml, "")["page_count"] == 192
