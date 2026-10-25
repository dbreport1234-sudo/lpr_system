from lpr.thai_plate import match_province, normalize_plate, parse_lines


def test_normalize():
    assert normalize_plate("1กข 1234") == "1กข1234"
    assert normalize_plate("๑กข ๑๒๓๔") == "1กข1234"
    assert normalize_plate("ฮฮ 5") == "ฮฮ5"
    assert normalize_plate("abc") is None


def test_ocr_confusion():
    assert normalize_plate("1กข 12З4".replace("З", "3")) == "1กข1234"
    assert normalize_plate("lกข 1234") == "1กข1234"


def test_province():
    assert match_province("กรุงเทพมหานคร") == "กรุงเทพมหานคร"
    assert match_province("กรุงเทพ") == "กรุงเทพมหานคร"
    assert match_province("ชลบรี") == "ชลบุรี"
    assert match_province("12") is None


def test_parse_lines():
    assert parse_lines(["1กข 1234", "ชลบุรี"]) == ("1กข1234", "ชลบุรี")
    assert parse_lines(["1กข", "1234", "กรุงเทพมหานคร"]) == ("1กข1234", "กรุงเทพมหานคร")
