"""Deterministic safety gates (English + Arabic). Pure Python - no LLM, no I/O, unit-testable.

Design rule: a false positive costs one staff message; a false negative is clinical advice
from a bot. The lists therefore lean towards over-triggering.
"""
import re

_MARKS = re.compile(r"[ً-ٟـ]")  # Arabic diacritics + tatweel
_PAIN_FREE = re.compile(r"pain[\s-]*(?:free|less)")
_AR = r"[ء-غف-ي]"  # Arabic letters only - punctuation such as '؟' must count as a boundary


def _norm(text: str) -> str:
    text = (text or "").lower()
    for ch in "’‘`´":
        text = text.replace(ch, "'")
    return _MARKS.sub("", text)


def _ar_words(words: str) -> str:
    """Whole Arabic word, tolerating a one-letter clitic prefix, 'ال', and a pronoun suffix."""
    return rf"(?<!{_AR})[وبفلك]?(?:ال)?(?:{words})(?:ني|ي|ك|ه|ها|نا)?(?!{_AR})"


# --- Tier 0: emergencies -> immediate warning + staff alert -----------------
_EMERGENCY_EN = re.compile(
    r"""
    can'?t\s+(?:breathe|swallow) | cannot\s+(?:breathe|swallow)
  | (?:difficulty|trouble|struggling)\s+(?:breathing|swallowing|to\s+breathe)
  | (?:face|jaw|neck)\s+(?:is\s+)?(?:swelling|swollen) | facial\s+swelling
  | (?:won'?t|will\s+not|doesn'?t)\s+stop\s+bleeding
  | bleeding\s+(?:won'?t|doesn'?t|will\s+not)\s+stop | uncontrolled\s+bleeding
  | knocked\s+out | severe\s+trauma
  | hit\s+(?:in|my)\s+(?:the\s+)?(?:face|jaw|mouth)
    """,
    re.X,
)
_EMERGENCY_AR = re.compile(
    r"(?:مش|لا|ما)\s*(?:قادر|اقدر|أقدر|استطيع|أستطيع|بقدر)\w*\s*(?:ا|أ)?(?:تنفس|بلع|ابلع|أبلع)"
    r"|نزيف\s*(?:لا|مش|ما)\s*(?:يتوقف|بيقف|يقف|بيوقف)"
    r"|(?:تورم|ورم)\s*(?:في|ف)?\s*(?:ال)?(?:وجه|وش|وشي)"
    r"|صعوبة\s*(?:في|ف)?\s*(?:ال)?(?:تنفس|بلع)"
)

# --- Tier 1: symptom / medication language -> straight to staff -------------
_CLINICAL_EN = re.compile(
    r"""\b(?:
    pain(?:ful)? | aching | throbbing | hurting
  | (?:it|tooth|teeth|gums?|jaw|mouth)\s+hurts? | my\s+\w+\s+hurts?
  | swelling | swollen | bleeds? | bleeding | abscess | pus | fever | infect(?:ion|ed)
  | antibiotics? | ibuprofen | amoxicillin | paracetamol | acetaminophen | panadol | advil | aspirin
  | painkillers? | medications? | medicines? | dosage | doses? | prescri(?:be|bed|ption)
  | should\s+i\s+take | is\s+it\s+(?:normal|ok|okay|safe)\s+(?:that|if|to)
  | numb(?:ness)? | (?:chipped|cracked|broken)\s+tooth | loose\s+tooth
    )\b""",
    re.X,
)
_CLINICAL_AR = re.compile(
    _ar_words(
        r"ألم|الم|وجع|ورم|تورم|نزيف|صديد|سخونية|سخونة|حمى|التهاب|عدوى|دواء|دوا|جرعة|مسكن|مسكنات"
        r"|بنادول|بروفين|بيوجع|بتوجع|بينزف|بتنزف|مضاد\s+حيوي|مضادات\s+حيوية"
    )
)

# --- Output guard: things the bot must never say ------------------------------
_OUTPUT_EN = re.compile(
    r"""
    \b\d+(?:\.\d+)?\s?(?:mg|mcg|ml|milligrams?|tablets?|pills?|capsules?)\b
  | \b(?:ibuprofen|amoxicillin|paracetamol|acetaminophen|panadol|advil|augmentin|metronidazole
       |clindamycin|aspirin|antibiotics?|painkillers?)\b
  | \byou(?:\s+(?:probably|likely|may|might))?\s+(?:have|has|are\s+suffering\s+from)\s+(?:an?\s+)?
       (?:infection|abscess|cavity|cavities|gingivitis|periodontitis|decay|fracture)
  | \b(?:this|that|it)\s+(?:is|sounds\s+like|looks\s+like|could\s+be|might\s+be)\s+(?:an?\s+)?
       (?:infection|abscess|emergency|cavity|gingivitis|periodontitis)
  | \bdiagnos(?:is|ed|e|ing)\b
  | \b(?:twice|three\s+times|once)\s+(?:a|per)\s+day\b | \bevery\s+\d+\s+hours\b | \bdaily\s+dose\b
    """,
    re.X,
)
_OUTPUT_AR = re.compile(_ar_words(r"جرعة|مضاد\s+حيوي|مضادات\s+حيوية|ملجم|ملغ|بروفين|بنادول"))


def is_emergency(text: str) -> bool:
    n = _norm(text)
    return bool(_EMERGENCY_EN.search(n) or _EMERGENCY_AR.search(n))


def clinical_match(text: str) -> str | None:
    """Matched snippet if the message contains symptom/medication language, else None."""
    n = _PAIN_FREE.sub(" ", _norm(text))
    m = _CLINICAL_EN.search(n) or _CLINICAL_AR.search(n)
    return m.group(0).strip() if m else None


def output_violation(text: str) -> str | None:
    """Matched snippet if a generated answer contains dosage/diagnosis/medication language."""
    n = _norm(text)
    m = _OUTPUT_EN.search(n) or _OUTPUT_AR.search(n)
    return " ".join(m.group(0).split()) if m else None
