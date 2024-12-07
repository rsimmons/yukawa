import { useSelector } from "react-redux";
import { actionExitStudy, RootState } from "./reducers";
import { AppDispatch, useAppDispatch } from "./store";
import { forwardRef, useEffect, useImperativeHandle, useLayoutEffect, useRef, useState } from "react";
import { useEffectOnce, useRAF } from "./util";
import { ActivityState, AtomReports, PreloadMap, StudyState, thunkStudyFinishedSection, thunkStudyInit } from "./studyReducer";
import './Study.css';
import { APIActivitySectionQMTI, APIActivitySectionTTSSlides, APIActivityTTSSlide, APIAnno, APIAtomsInfo } from "./api";
import backArrowSvg from './back-arrow.svg';
import audioSvg from './audio.svg';
import audioBgSvg from './audio-bg.svg';
import replaySvg from './replay.svg';
import replayBgSvg from './replay-bg.svg';
import successSfx from './sfx/success.wav';
import failureSfx from './sfx/failure.wav';

function AtomPopup(props: {atomId: string, meaning: string | null, notes: string | null}) {
  return (
    <div className="Study-atom-popup">
      {props.meaning && (
        <div className="Study-atom-popup-title">{props.meaning}</div>
      )}
      {props.notes && (
        <div className="Study-atom-popup-notes">{props.notes}</div>
      )}
    </div>
  );
}

function Transcription(props: {anno: APIAnno, atomsInfo: APIAtomsInfo, atomsFailed: ReadonlyArray<string>}) {
  const [openSpan, setOpenSpan] = useState<{readonly idx: number, readonly fromClick: boolean} | null>(null);

  const handleSpanMouseEnter = (i: number) => {
    setOpenSpan(prev => {
      if (prev && prev.fromClick) {
        return prev;
      } else {
        return {idx: i, fromClick: false};
      }
    });
  };

  const handleSpanMouseLeave = (i: number) => {
    setOpenSpan(prev => {
      if (prev && (prev.idx === i) && !prev.fromClick) {
        return null;
      } else {
        return prev;
      }
    });
  };

  const handleSpanClick = (i: number) => {
    setOpenSpan(prev => {
      if (prev && (prev.idx === i) && prev.fromClick) {
        return null;
      } else {
        return {idx: i, fromClick: true};
      }
    });
    const span = props.anno[i];
    if (span.a) {
      // props.dispatch(actionStudyToggleAtomGrade(span.a));
    }
  };

  const handleClick = (event: MouseEvent) => {
    if (openSpan && (!event.target || !(event.target as HTMLElement).closest('.Study-transcription-span-atom-wrapper'))) {
      setOpenSpan(null);
    }
  };

  useEffect(() => {
    window.addEventListener('click', handleClick);
    return () => {
      window.removeEventListener('click', handleClick);
    };
  }, [handleClick]);

  return (
    <span>
      {props.anno.map((span, i) => {
        if (span.a) {
          const classList: string[] = [];
          if (openSpan && (openSpan.idx === i)) {
            classList.push('Study-transcription-span-atom-open');
          }
          if (props.atomsFailed.includes(span.a)) {
            classList.push('Study-transcription-span-atom-failed');
          }
          return (
            <span key={i} className="Study-transcription-span-atom-wrapper">
              <span
                className={classList.join(' ')}
                data-atom={span.a}
                onMouseEnter={() => handleSpanMouseEnter(i)}
                onMouseLeave={() => handleSpanMouseLeave(i)}
                onClick={() => handleSpanClick(i)}
              >{span.t}</span>
              {openSpan && (openSpan.idx === i) && (
                <AtomPopup atomId={span.a} meaning={props.atomsInfo[span.a]!.meaning} notes={props.atomsInfo[span.a]!.notes} />
              )}
            </span>
          );
        } else {
          return <span key={i}>{span.t}</span>
        }
      })}
    </span>
  );
}

/*
function StudyButton(props: {text: string, shortcut?: string, onClick: () => void}) {
  return (
    <button className="Study-button" onClick={props.onClick}>{props.text}{props.shortcut && !touchAvail && (
      <span className="Study-button-shortcut"> {props.shortcut}</span>
    )}</button>
  );
}
*/

function TranscriptionTranslation(props: {anno: APIAnno, atomsInfo: APIAtomsInfo, trans: ReadonlyArray<string>}) {
  return (
    <div>
      <div className="TranscriptionTranslation-transcription"><Transcription anno={props.anno} atomsInfo={props.atomsInfo} atomsFailed={[]} /></div>
      <div className="TranscriptionTranslation-sep"></div>
      <div className="TranscriptionTranslation-translations">
        {props.trans.map((translation, i) => (
          <div key={i} className="TranscriptionTranslation-translation">{translation}</div>
        ))}
      </div>
    </div>
  );
}

const AUDIO_PADDING = 0.5;
const AudioPlayback = forwardRef((props: {audioUrl: string, onFinished: () => void}, ref) => {
  const audioRef = useRef<HTMLAudioElement>(null);
  const playbackStartTime = useRef<number>(Date.now() / 1000);
  const audioStarted = useRef(false);
  const notifiedFinished = useRef(false);
  const progressBarRef = useRef<HTMLDivElement>(null);

  useImperativeHandle(ref, () => ({
    restart() {
      if (audioRef.current) {
        audioRef.current.currentTime = 0;
        audioStarted.current = false;
        playbackStartTime.current = Date.now() / 1000;
        notifiedFinished.current = false;
      }
    },
  }));

  useRAF(() => {
    const elapsed = (Date.now() / 1000) - playbackStartTime.current;

    if (audioRef.current) {
      if (!audioStarted.current && (elapsed > AUDIO_PADDING)) {
        audioRef.current.play();
        audioStarted.current = true;
      }

      const dur = audioRef.current.duration;
      if (!Number.isNaN(dur) && (playbackStartTime.current !== null)) {
        const progress = Math.min(elapsed / (dur + 2*AUDIO_PADDING), 1);
        if (progressBarRef.current) {
          progressBarRef.current.style.width = `${progress*100}%`;
        }

        if (progress >= 1) {
          if (!notifiedFinished.current) {
            props.onFinished();
            notifiedFinished.current = true;
          }
        }
      }
    }
  });

  return (
    <>
      <audio src={props.audioUrl} autoPlay={false} ref={audioRef} />
      <div className="ProgressBar" ref={progressBarRef}></div>
    </>
  );
});

function ImageAudioPlayer(props: {imageFn: string, audioFn: string, onFinished: () => void}) {
  const [showReplay, setShowReplay] = useState(false);
  const audioPlaybackRef = useRef<{restart: () => void} | null>(null);

  const handleClickReplay = () => {
    setShowReplay(false);
    audioPlaybackRef.current?.restart();
  };

  const handleAudioFinished = () => {
    setShowReplay(true);
    props.onFinished();
  };

  return (
    <div className="ImageAudioPlayer">
      <img className="ImageAudioPlayer-img" src={props.imageFn} />
      <AudioPlayback audioUrl={props.audioFn} onFinished={handleAudioFinished} ref={audioPlaybackRef} />
      <div className="ImageAudioPlayer-audio-icon">
        <img src={audioBgSvg} />
      </div>
      {showReplay && (
        <div className="ImageAudioPlayer-replay-icon" onClick={handleClickReplay}>
          <img src={replayBgSvg} />
        </div>
      )}
    </div>
  );
}

function AudioPlayer(props: {audioUrl: string, onFinished: () => void}) {
  const audioPlaybackRef = useRef<{restart: () => void} | null>(null);
  const [showReplay, setShowReplay] = useState(false);

  const handleClickReplay = () => {
    setShowReplay(false);
    audioPlaybackRef.current?.restart();
  };

  const handleAudioFinished = () => {
    setShowReplay(true);
    props.onFinished();
  };

  return (
    <div>
      { showReplay ? (
        <img className="AudioPlayer-replay-svg" src={replaySvg} onClick={handleClickReplay} />
      ) : (
        <img className="AudioPlayer-audio-svg" src={audioSvg} />
      )}
      <AudioPlayback audioUrl={props.audioUrl} onFinished={handleAudioFinished} ref={audioPlaybackRef} />
    </div>
  );
}

function SectionTTSSlide(props: {slide: APIActivityTTSSlide, preloadMap: PreloadMap, atomsInfo: APIAtomsInfo, isLastSlide: boolean, onFinished: () => void}) {
  const [showText, setShowText] = useState(false);

  const handleAudioFinished = () => {
    setShowText(true);
  };

  const handleClickNext = () => {
    props.onFinished();
  };

  return (
    <div className="SectionTTSSlide">
      <ImageAudioPlayer imageFn={props.preloadMap[props.slide.imageFn]} audioFn={props.preloadMap[props.slide.audioFn]} onFinished={handleAudioFinished} />
      {showText && <TranscriptionTranslation anno={props.slide.anno} trans={props.slide.trans} atomsInfo={props.atomsInfo} />}
      {showText && <div className="SectionTTSSlide-bottom"><button className="StandardButton" onClick={handleClickNext}>{props.isLastSlide ? 'Continue' : 'Next'}</button></div>}
    </div>
  );
}

function SectionTTSSlides(props: {section: APIActivitySectionTTSSlides, preloadMap: PreloadMap, atomsInfo: APIAtomsInfo, onFinished: (atomReports: AtomReports) => void}) {
  const [slideIndex, setSlideIndex] = useState(0);

  return (
    <SectionTTSSlide
      key={slideIndex}
      slide={props.section.slides[slideIndex]}
      preloadMap={props.preloadMap}
      atomsInfo={props.atomsInfo}
      isLastSlide={slideIndex === (props.section.slides.length-1)}
      onFinished={() => {
        if (slideIndex === (props.section.slides.length-1)) {
          props.onFinished({
            atomsIntroduced: [],
            atomsExposed: [],
            atomsForgot: [],
            atomsPassed: [],
            atomsFailed: [],
          });
        } else {
          setSlideIndex(slideIndex + 1);
        }
      }}
    />
  )
}

function SectionQMTI(props: {section: APIActivitySectionQMTI, preloadMap: PreloadMap, atomsInfo: APIAtomsInfo, onFinished: (atomReports: AtomReports) => void}) {
  const [selectedChoiceIdx, setSelectedChoiceIdx] = useState<number | null>(null);
  const successAudioRef = useRef<HTMLAudioElement>(null);
  const failureAudioRef = useRef<HTMLAudioElement>(null);

  const handleClickChoice = (choiceIdx: number) => {
    setSelectedChoiceIdx(choiceIdx);
    const choice = props.section.choices[choiceIdx];
    if (choice.correct) {
      successAudioRef.current?.play();
    } else {
      failureAudioRef.current?.play();
    }
  };

  const handleClickContinue = () => {
    if (selectedChoiceIdx === null) {
      throw new Error('invalid state');
    }

    const choice = props.section.choices[selectedChoiceIdx];
    let atomsPassed: ReadonlyArray<string>;
    let atomsFailed: ReadonlyArray<string>;
    if (choice.correct) {
      atomsPassed = props.section.testedAtoms;
      atomsFailed = [];
    } else {
      atomsPassed = [];
      const extraFailed = choice.failAtoms ? choice.failAtoms : [];
      atomsFailed = [...props.section.testedAtoms, ...extraFailed];
    }
    props.onFinished({
      atomsIntroduced: [],
      atomsExposed: [],
      atomsForgot: [],
      atomsPassed,
      atomsFailed,
    });
  };

  return (
    <div className="SectionQMTI">
      <AudioPlayer audioUrl={props.preloadMap[props.section.audioFn]} onFinished={() => {}} />
      {(selectedChoiceIdx !== null) && (
        <TranscriptionTranslation anno={props.section.anno} trans={props.section.trans} atomsInfo={props.atomsInfo} />
      )}
      <div className="SectionQMTI-bottom">
        {(selectedChoiceIdx !== null) && (
          <div className="SectionQMTI-continue-section">
            <button className="StandardButton" onClick={handleClickContinue}>Continue</button>
          </div>
        )}
        <div className="SectionQMTI-choices">
          {props.section.choices.map((choice, choiceIdx) => {
            const isSelected = selectedChoiceIdx === choiceIdx;
            const isCorrect = choice.correct;
            const classList = ['SectionQMTI-choice-image'];
            if (selectedChoiceIdx === null) {
              classList.push('SectionQMTI-choice-selectable');
            } else {
              if (isCorrect) {
                classList.push('SectionQMTI-choice-correct');
              }
              if (isSelected && !isCorrect) {
                classList.push('SectionQMTI-choice-incorrect');
              }
            }
            return (
              <img
                className={classList.join(' ')}
                key={choice.imageFn}
                src={props.preloadMap[choice.imageFn]}
                onClick={() => handleClickChoice(choiceIdx)}
              />
            );
          })}
        </div>
      </div>
      <audio ref={successAudioRef} src={successSfx} />
      <audio ref={failureAudioRef} src={failureSfx} />
    </div>
  );
}

function Activity(props: {activityState: ActivityState, dispatch: AppDispatch}) {
  const activityState = props.activityState;
  const activity = activityState.activity;
  const sectionIndex = activityState.sectionIndex
  const section = activity.sections[sectionIndex];

  // scroll to top on activity start, and on section change
  useLayoutEffect(() => {
    document.documentElement.scrollTo({top:0, left:0, behavior: "instant"});
  }, [sectionIndex]);

  const handleFinished = (atomReports: AtomReports) => {
    props.dispatch(thunkStudyFinishedSection(atomReports));
  }

  switch (section.kind) {
    case 'tts_slides':
      return (
        <SectionTTSSlides
          key={sectionIndex}
          section={section}
          preloadMap={activityState.preloadMap}
          atomsInfo={activity.atomsInfo}
          onFinished={handleFinished}
        />
      );

    case 'qmti':
      return (
        <SectionQMTI
          key={sectionIndex}
          section={section}
          preloadMap={activityState.preloadMap}
          atomsInfo={activity.atomsInfo}
          onFinished={handleFinished}
        />
      );

    default:
      throw new Error('invalid section kind');
  }
}

export default function Study() {
  const dispatch = useAppDispatch();

  const studyState: StudyState = useSelector((state: RootState) => {
    if (state.type !== 'loggedIn') {
      throw new Error('invalid state');
    }
    if (state.sess.page.type !== 'study') {
      throw new Error('invalid page');
    }
    return state.sess.page.studyState;
  });

  useEffectOnce(() => {
    dispatch(thunkStudyInit());
  });

  const onClickBack = () => {
    dispatch(actionExitStudy());
  };

  return (
    <div className="Study">
      <div className="Study-header">
        <div className="Study-header-back">
          <img src={backArrowSvg} />
          <div className="Study-header-back-overlay" onClick={onClickBack}></div>
        </div>
      </div>
      {(() => {
        if (studyState.activityState === undefined) {
          return <div>Loading...</div>;
        } else {
          const activityState = studyState.activityState;

          return <Activity
            key={activityState.uid}
            activityState={activityState}
            dispatch={dispatch}
          />
        }
      })()}
    </div>
  )
  /*
  const question = page.question;
  return (
    <div>
      <video className="Study-video" playsInline key={question.mediaUrl} autoPlay={true} ref={videoRef} onTimeUpdate={handleVideoTimeUpdate} onClick={handleVideoClick}>
        <source src={question.mediaUrl} type="video/mp4" />
        Your browser does not support the video tag.
      </video>
      {((page.stage === 'grading_hearing') || (page.stage === 'grading_understanding') || (page.stage === 'grading_atoms')) && (
        <div className="Study-transcription"><TranscriptionSpans spans={question.spans} atomInfo={question.atomInfo} atomsFailed={page.grades.atomsFailed} dispatch={dispatch} /></div>
      )}
      {((page.stage === 'grading_understanding') || (page.stage === 'grading_atoms')) && (
        <div className="Study-translations">
          {question.translations.map((translation, i) => (
            <div key={i} className="Study-translation">{translation}</div>
          ))}
          {question.notes && <div className="Study-translation-notes">{question.notes}</div>}
        </div>
      )}
      <div className="Study-pad"></div>
      {(() => {
        switch (page.stage) {
          case 'listening':
            return (
              <div className="Study-controls">
                <div className="Study-controls-instructions">Listen carefully</div>
              </div>
            );

          case 'grading_allowed':
            return (
              <div className="Study-controls">
                <div className="Study-controls-instructions">Can you understand it?<br/>{touchAvail ? 'R' : '[R]'}eplay if needed</div>
                <div className="Study-controls-buttons">
                  <StudyButton text="Reveal Captions" shortcut="[space]" onClick={handleBeginGrading} />
                </div>
              </div>
            );

          case 'grading_hearing':
            return (
              <div className="Study-controls">
                <div className="Study-controls-instructions">Did you correctly hear the words before seeing captions?</div>
                <div className="Study-controls-buttons">
                  <StudyButton text="No" shortcut="[1]" onClick={() => {handleGradeHearing('n')}} />
                  <StudyButton text="Mostly" shortcut="[2]" onClick={() => {handleGradeHearing('m')}} />
                  <StudyButton text="Fully" shortcut="[3]" onClick={() => {handleGradeHearing('y')}} />
                </div>
              </div>
            );

          case 'grading_understanding':
            return (
              <div className="Study-controls">
                <div className="Study-controls-instructions">Did you correctly understand the meaning before seeing the translation?</div>
                <div className="Study-controls-buttons">
                  <StudyButton text="No" shortcut="[1]" onClick={() => {handleGradeUnderstanding('n')}} />
                  <StudyButton text="Mostly" shortcut="[2]" onClick={() => {handleGradeUnderstanding('m')}} />
                  <StudyButton text="Fully" shortcut="[3]" onClick={() => {handleGradeUnderstanding('y')}} />
                </div>
              </div>
            );

          case 'grading_atoms':
            return (
              <div className="Study-controls">
                <div className="Study-controls-instructions">Mark any words you didn't know/remember</div>
                <div className="Study-controls-buttons">
                <StudyButton text="Continue" shortcut="[space]" onClick={handleGradeWords} />
                </div>
              </div>
            );

          case 'loading_next':
            return (
              <div className="Study-controls">
                <div className="Study-controls-instructions">Loading...</div>
              </div>
            );

          default:
            throw new Error('invalid stage');
        }
      })()}
    </div>
  );
  */
}
