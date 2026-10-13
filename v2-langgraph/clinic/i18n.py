import re

_ARABIC = re.compile(r"[؀-ۿ]")

MESSAGES: dict[str, dict[str, str]] = {
    "welcome": {
        "en": "👋 Welcome to Bright Smile Clinic! I can help with prices, opening hours, doctors, insurance, "
              "clinic policies and booking appointments.\n\nNote: I provide administrative help only — for any "
              "pain, symptoms or medication questions I'll connect you with our staff.",
        "ar": "👋 أهلاً بك في عيادة Bright Smile! أقدر أساعدك في الأسعار ومواعيد العمل والأطباء والتأمين وسياسات "
              "العيادة وحجز المواعيد.\n\nملاحظة: أقدم مساعدة إدارية فقط — لأي أسئلة عن الألم أو الأعراض أو الأدوية "
              "سأحولك لفريقنا.",
    },
    "non_text": {
        "en": "Sorry, I can only understand text messages right now — could you type your question?",
        "ar": "عذراً، أستطيع فهم الرسائل النصية فقط حالياً — ممكن تكتب سؤالك؟",
    },
    "rate_limited": {
        "en": "You've reached the hourly message limit. Please try again later or call the clinic directly.",
        "ar": "وصلت للحد الأقصى من الرسائل في الساعة. حاول مرة أخرى لاحقاً أو اتصل بالعيادة مباشرة.",
    },
    "emergency": {
        "en": "⚠️ This may be a dental emergency. Please call the clinic immediately, or go to the nearest "
              "emergency room if you are having trouble breathing or swallowing or the bleeding won't stop. "
              "I've alerted our staff.",
        "ar": "⚠️ قد تكون هذه حالة طارئة. يرجى الاتصال بالعيادة فوراً أو التوجه لأقرب طوارئ إذا كان لديك صعوبة "
              "في التنفس أو البلع أو نزيف لا يتوقف. تم تنبيه فريقنا.",
    },
    "escalated": {
        "en": "This looks like something our staff should handle directly — I can't give medical advice. "
              "I've passed your request to our team and they will contact you. If it's urgent, please call the clinic.",
        "ar": "هذا الموضوع يحتاج لفريقنا مباشرة — لا أستطيع تقديم نصائح طبية. تم تحويل طلبك لفريق العيادة "
              "وسيتواصلون معك. إذا كان الأمر عاجلاً يرجى الاتصال بالعيادة.",
    },
    "error": {
        "en": "Sorry, something went wrong on our side. One moment — I'm connecting you with our team.",
        "ar": "عذراً، حدث خطأ من جانبنا. لحظة من فضلك — سأحولك لفريقنا.",
    },
    "slot_gone": {
        "en": "Sorry, that time is no longer available. Tell me which day you'd prefer and I'll find other times.",
        "ar": "عذراً، هذا الموعد لم يعد متاحاً. أخبرني باليوم المناسب وسأبحث عن مواعيد أخرى.",
    },
    "ask_name": {
        "en": "Great choice! What's your full name? (send 'cancel' to stop)",
        "ar": "اختيار ممتاز! ما اسمك الكامل؟ (اكتب 'إلغاء' للتوقف)",
    },
    "bad_name": {
        "en": "Please send your full name (letters only).",
        "ar": "من فضلك أرسل اسمك الكامل (حروف فقط).",
    },
    "ask_phone": {
        "en": "Thanks! What's the best phone number to reach you?",
        "ar": "شكراً! ما أفضل رقم هاتف للتواصل معك؟",
    },
    "bad_phone": {
        "en": "That doesn't look like a valid mobile number. Please send an Egyptian mobile number of 11 digits, "
              "e.g. 01012345678 (or an international number starting with +).",
        "ar": "هذا لا يبدو رقم موبايل صحيحاً. من فضلك أرسل رقم موبايل مصري من 11 رقماً، مثال: 01012345678 "
              "(أو رقم دولي يبدأ بـ +).",
    },
    "confirm_summary": {
        "en": "Please confirm your booking:\n📅 {when}\n🦷 {procedure}\n👤 {name}\n📞 {phone}",
        "ar": "من فضلك أكّد حجزك:\n📅 {when}\n🦷 {procedure}\n👤 {name}\n📞 {phone}",
    },
    "btn_confirm": {"en": "✅ Confirm", "ar": "✅ تأكيد"},
    "btn_cancel": {"en": "❌ Cancel", "ar": "❌ إلغاء"},
    "booked": {
        "en": "✅ You're booked for {when}. See you then! To change or cancel, message us and our team will help.",
        "ar": "✅ تم حجز موعدك يوم {when}. نراك قريباً! للتعديل أو الإلغاء راسلنا وسيساعدك فريقنا.",
    },
    "already_booked": {
        "en": "You're already booked for {when} — nothing more to do.",
        "ar": "موعدك محجوز بالفعل يوم {when} — لا شيء آخر مطلوب.",
    },
    "expired": {
        "en": "That request has expired or was already handled.",
        "ar": "انتهت صلاحية هذا الطلب أو تمت معالجته بالفعل.",
    },
    "booking_cancelled": {
        "en": "No problem — booking cancelled. Anything else I can help with?",
        "ar": "لا مشكلة — تم إلغاء الحجز. هل هناك شيء آخر؟",
    },
    "default_procedure": {"en": "General visit", "ar": "زيارة عامة"},
}

CANCEL_WORDS = {"cancel", "/cancel", "stop", "إلغاء", "الغاء", "الغي"}


def detect_lang(text: str) -> str:
    return "ar" if len(_ARABIC.findall(text or "")) >= 2 else "en"


def t(key: str, lang: str = "en", **kwargs: str) -> str:
    entry = MESSAGES[key]
    return entry.get(lang, entry["en"]).format(**kwargs)
