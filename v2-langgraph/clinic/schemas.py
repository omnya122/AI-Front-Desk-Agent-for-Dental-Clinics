from typing import Literal, Optional

from pydantic import BaseModel, Field


class Respond(BaseModel):
    """Deliver the final reply to the patient. Call this exactly once, as your very last step."""

    answer: str = Field(description="Reply text, in the same language the patient wrote in (Arabic or English).")
    category: Literal["pricing", "hours", "insurance", "doctors", "policy", "booking", "other"]
    confidence: float = Field(description="0.0-1.0: how well the tool results support the answer.")
    clinical_flag: bool = Field(
        description="True if the message asks for medical/clinical guidance (symptoms, pain, medication, "
        "diagnosis, treatment decisions). Do NOT answer such questions."
    )
    needs_staff: bool = Field(
        description="True ONLY if the patient is asking you to change or cancel THEIR OWN existing appointment, "
        "or has a complaint. Questions ABOUT policies (cancellation policy, fees, notice) are normal questions: "
        "answer them and set False. If a tool simply has no information, answer that you don't know and set False."
    )
    sources: list[str] = Field(default_factory=list, description="Tool names / document filenames you relied on.")
    offered_slots: list[str] = Field(
        default_factory=list,
        description="Up to 3 slot_id values copied EXACTLY from check_availability, if you are offering times.",
    )
    procedure: Optional[str] = Field(default=None, description="Procedure the patient wants to book, if known.")
