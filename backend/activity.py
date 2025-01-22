from typing import Union
from dataclasses import dataclass

@dataclass
class ATText:
    text: str
    trans: list[str]
    anno: None

@dataclass
class ActivityBase:
    atoms_introduced: list[str]
    atoms_exposed: list[str]
    atoms_tested: list[str]

@dataclass
class IntroSlideAudioImage:
    attext: ATText
    audio_fn: str
    image_fn: str
    kind: str = 'audio_image' # for JSON serialization

# later: IntroSlideAudio?

IntroSlide = Union[
    IntroSlideAudioImage,
]

@dataclass
class ActivityIntroSlides(ActivityBase):
    slides: list[IntroSlide]
    kind: str = 'intro_slides' # for JSON serialization

@dataclass
class PresAudio:
    attext: ATText
    audio_fn: str
    kind: str = 'audio' # for JSON serialization

# later: PresVideo
# later: PresAudioMulti
# later: PresVideoSubs

Pres = Union[
    PresAudio,
]

@dataclass
class ImageOption:
    correct: bool
    image_fn: str
    atoms_passed: list[str]
    atoms_failed: list[str]

@dataclass
class QuesChoiceImage:
    prompt: str | None
    options: list[ImageOption]
    kind: str = 'choice_image'

# later: QuesChoiceText

Ques = Union[
    QuesChoiceImage,
]

@dataclass
class ActivityReview(ActivityBase):
    pres: Pres
    ques: Ques
    kind: str = 'review' # for JSON serialization

Activity = Union[
    ActivityIntroSlides,
    ActivityReview,
]

@dataclass
class ReportedResult:
    atoms_introduced: list[str]
    atoms_exposed: list[str]
    # atoms_forgotten: list[str]
    atoms_tested: dict[str, bool]
