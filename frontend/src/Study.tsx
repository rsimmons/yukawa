import { useSelector } from "react-redux";
import { actionExitStudy, RootState } from "./reducers";
import { AppDispatch, useAppDispatch } from "./store";
import { useLayoutEffect, useRef, useState } from "react";
import { useEffectOnce, useRAF } from "./util";
import { ActivityState, AtomReports, PreloadMap, StudyState, thunkStudyFinishedSection, thunkStudyInit } from "./studyReducer";
import './Study.css';
import { APIActivitySectionQMTI, APIActivitySectionTTSSlides, APIActivityTTSSlide } from "./api";
import backArrow from './back-arrow.svg';

/*
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

function TranscriptionSpans(props: {spans: APIQuestion['spans'], atomInfo: APIQuestion['atomInfo'], atomsFailed: ReadonlyArray<string>, dispatch: AppDispatch}) {
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
    const span = props.spans[i];
    if (span.a) {
      props.dispatch(actionStudyToggleAtomGrade(span.a));
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
      {props.spans.map((span, i) => {
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
                <AtomPopup atomId={span.a} meaning={props.atomInfo[span.a]!.meaning} notes={props.atomInfo[span.a]!.notes} />
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

function StudyButton(props: {text: string, shortcut?: string, onClick: () => void}) {
  return (
    <button className="Study-button" onClick={props.onClick}>{props.text}{props.shortcut && !touchAvail && (
      <span className="Study-button-shortcut"> {props.shortcut}</span>
    )}</button>
  );
}
*/

const AUDIO_PADDING = 1.0;
function AudioPlayer(props: {audioFn: string, preloadMap: PreloadMap, onFinished: () => void}) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const playedAudio = useRef(false);
  const audioEndTime = useRef<number | null>(null);
  const notifiedFinished = useRef(false);

  useRAF((elapsedTime) => {
    if (!playedAudio.current && (elapsedTime > AUDIO_PADDING)) {
      if (audioRef.current) {
        audioRef.current.play();
        playedAudio.current = true;
      }
    } else if (playedAudio.current) {
      if (audioEndTime.current === null) {
        if (audioRef.current) {
          if (audioRef.current.ended) {
            audioEndTime.current = elapsedTime;
          }
        }
      } else {
        if (elapsedTime > (audioEndTime.current + AUDIO_PADDING)) {
          if (!notifiedFinished.current) {
            props.onFinished();
            notifiedFinished.current = true;
          }
        }
      }
    }
  });

  return (
    <audio src={props.preloadMap[props.audioFn]} autoPlay={false} ref={audioRef} />
  );
}

function SectionTTSSlide(props: {slide: APIActivityTTSSlide, preloadMap: PreloadMap, onFinished: () => void}) {
  return (
    <div>
      <img className="SectionTTSSlide-img" src={props.preloadMap[props.slide.imageFn]} />
      <AudioPlayer audioFn={props.slide.audioFn} preloadMap={props.preloadMap} onFinished={props.onFinished} />
    </div>
  );
}

function SectionTTSSlides(props: {section: APIActivitySectionTTSSlides, preloadMap: PreloadMap, onFinished: (atomReports: AtomReports) => void}) {
  const [slideIndex, setSlideIndex] = useState(0);

  return (
    <SectionTTSSlide
      key={slideIndex}
      slide={props.section.slides[slideIndex]}
      preloadMap={props.preloadMap}
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

function SectionQMTI(props: {section: APIActivitySectionQMTI, preloadMap: PreloadMap, onFinished: (atomReports: AtomReports) => void}) {
  const handleAudioFinished = () => {
    // TODO: do nothing for now
  };

  return (
    <div className="SectionQMTI">
      <AudioPlayer audioFn={props.section.audioFn} preloadMap={props.preloadMap} onFinished={handleAudioFinished} />
      <div className="SectionQMTI-choices">
        {props.section.choices.map((choice) => {
          const handleClick = () => {
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
          return <img className="SectionQMTI-choice-image" key={choice.imageFn} src={props.preloadMap[choice.imageFn]} onClick={handleClick} />
        })}
      </div>
    </div>
  )
}

function Activity(props: {activityState: ActivityState, dispatch: AppDispatch}) {
  const activityState = props.activityState;
  const sectionIndex = activityState.sectionIndex
  const section = activityState.activity.sections[sectionIndex];

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
          onFinished={handleFinished}
        />
      );

    case 'qmti':
      return (
        <SectionQMTI
          key={sectionIndex}
          section={section}
          preloadMap={activityState.preloadMap}
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
        <div className="Study-header-back"><img src={backArrow} onClick={onClickBack} width="20px" height="20px" /></div>
        <div>Yukawa</div>
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
