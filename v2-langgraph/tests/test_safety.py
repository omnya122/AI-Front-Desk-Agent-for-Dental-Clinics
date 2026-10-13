"""Unit tests for the deterministic gates (no network, no database).   Run: pytest"""
import pytest

from clinic import safety


@pytest.mark.parametrize("text", [
    "My tooth is throbbing, should I take antibiotics?",
    "I have swelling on my gum",
    "Can I take ibuprofen after my extraction?",
    "my gums bleed when I brush",
    "my tooth hurts",
    "Is it normal that my filling feels sharp?",
    "What dose of paracetamol is safe?",
    "ضرسي بيوجعني جداً أعمل إيه؟",
    "عندي ورم في اللثة",
    "هل أستطيع أخذ مضاد حيوي؟",
])
def test_clinical_language_is_caught(text):
    assert safety.clinical_match(text)


@pytest.mark.parametrize("text", [
    "How much is a teeth cleaning?",
    "What are your opening hours on Saturday?",
    "Do you offer pain-free dentistry?",
    "Does whitening hurt?",           # ambiguous: left to the agent layer on purpose
    "Where is the clinic located?",
    "كم سعر تنظيف الأسنان؟",
    "ما هي مواعيد الدوام يوم السبت؟",
    "ما هو عنوان المنطقة؟",
])
def test_admin_questions_pass_the_keyword_gate(text):
    assert safety.clinical_match(text) is None


@pytest.mark.parametrize("text", [
    "I can't breathe properly and my face is swelling",
    "my gum bleeding won't stop",
    "I am struggling to breathe",
    "I got hit in the face and a tooth was knocked out",
    "مش قادر اتنفس",
])
def test_emergencies(text):
    assert safety.is_emergency(text)


@pytest.mark.parametrize("text", ["I need a cleaning", "My gums bleed a little", "كم سعر الحشو؟"])
def test_non_emergencies(text):
    assert not safety.is_emergency(text)


@pytest.mark.parametrize("text", [
    "Take 400 mg of ibuprofen twice a day.",
    "You have an infection, you should start antibiotics.",
    "This sounds like an abscess.",
    "خذ جرعة واحدة من المضاد الحيوي",
])
def test_output_guard_blocks_clinical_answers(text):
    assert safety.output_violation(text)


@pytest.mark.parametrize("text", [
    "A teeth cleaning costs 600 EGP and takes 45 minutes.",
    "We are open Saturday 12:00-20:00. You have a free slot at 14:00.",
    "Bupa Egypt covers 70% of preventive care.",
])
def test_output_guard_allows_admin_answers(text):
    assert safety.output_violation(text) is None
