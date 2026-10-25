"""กฎป้ายทะเบียนไทย: ทำความสะอาดผล OCR, ตรวจรูปแบบ, จับคู่จังหวัด"""
import difflib
import re
import unicodedata

THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
# ตัวอักษรละตินที่ OCR มักอ่านสับสนกับตัวเลข
LATIN_TO_DIGIT = {"O": "0", "o": "0", "Q": "0", "D": "0", "I": "1", "l": "1",
                  "|": "1", "Z": "2", "S": "5", "B": "8"}

PLATE_RE = re.compile(r"([0-9]?[ก-ฮ]{1,2}[0-9]{1,4})$")

PROVINCES = [
    "กรุงเทพมหานคร", "กระบี่", "กาญจนบุรี", "กาฬสินธุ์", "กำแพงเพชร", "ขอนแก่น", "จันทบุรี",
    "ฉะเชิงเทรา", "ชลบุรี", "ชัยนาท", "ชัยภูมิ", "ชุมพร", "เชียงราย", "เชียงใหม่", "ตรัง",
    "ตราด", "ตาก", "นครนายก", "นครปฐม", "นครพนม", "นครราชสีมา", "นครศรีธรรมราช", "นครสวรรค์",
    "นนทบุรี", "นราธิวาส", "น่าน", "บึงกาฬ", "บุรีรัมย์", "ปทุมธานี", "ประจวบคีรีขันธ์",
    "ปราจีนบุรี", "ปัตตานี", "พระนครศรีอยุธยา", "พะเยา", "พังงา", "พัทลุง", "พิจิตร",
    "พิษณุโลก", "เพชรบุรี", "เพชรบูรณ์", "แพร่", "ภูเก็ต", "มหาสารคาม", "มุกดาหาร",
    "แม่ฮ่องสอน", "ยโสธร", "ยะลา", "ร้อยเอ็ด", "ระนอง", "ระยอง", "ราชบุรี", "ลพบุรี", "ลำปาง",
    "ลำพูน", "เลย", "ศรีสะเกษ", "สกลนคร", "สงขลา", "สตูล", "สมุทรปราการ", "สมุทรสงคราม",
    "สมุทรสาคร", "สระแก้ว", "สระบุรี", "สิงห์บุรี", "สุโขทัย", "สุพรรณบุรี", "สุราษฎร์ธานี",
    "สุรินทร์", "หนองคาย", "หนองบัวลำภู", "อ่างทอง", "อำนาจเจริญ", "อุดรธานี", "อุตรดิตถ์",
    "อุทัยธานี", "อุบลราชธานี",
]
ALIASES = {"กทม": "กรุงเทพมหานคร", "กรุงเทพ": "กรุงเทพมหานคร", "กรุงเทพฯ": "กรุงเทพมหานคร",
           "อยุธยา": "พระนครศรีอยุธยา", "โคราช": "นครราชสีมา"}


def normalize_plate(text: str):
    """คืนเลขทะเบียนแบบไม่มีเว้นวรรค เช่น '1กข1234' หรือ None ถ้ารูปแบบไม่ถูก"""
    s = unicodedata.normalize("NFC", text).translate(THAI_DIGITS)
    s = "".join(LATIN_TO_DIGIT.get(c, c) for c in s)
    s = "".join(c for c in s if c in "0123456789" or "ก" <= c <= "ฮ")
    m = PLATE_RE.search(s)
    return m.group(1) if m else None


def match_province(text: str):
    s = "".join(c for c in text if "\u0e00" <= c <= "\u0e7f")
    if len(s) < 3:
        return None
    if s in ALIASES:
        return ALIASES[s]
    if s in PROVINCES:
        return s
    hit = difflib.get_close_matches(s, PROVINCES, n=1, cutoff=0.62)
    return hit[0] if hit else None


def parse_lines(lines):
    """รับข้อความรายบรรทัด (บน→ล่าง) คืน (plate, province)"""
    plate, province, leftovers = None, None, []
    for ln in lines:
        p = normalize_plate(ln)
        if p and plate is None:
            plate = p
            continue
        pv = match_province(ln)
        if pv:
            province = province or pv
        else:
            leftovers.append(ln)
    if plate is None and leftovers:
        plate = normalize_plate("".join(leftovers))
    return plate, province
