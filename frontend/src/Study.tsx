import { useSelector } from "react-redux";
import { actionExitStudy, RootState } from "./reducers";
import { AppDispatch, useAppDispatch } from "./store";
import { forwardRef, useEffect, useImperativeHandle, useLayoutEffect, useRef, useState } from "react";
import { useEffectOnce, useRAF } from "./util";
import { ActivityState, AtomReports, PreloadMap, StudyState, thunkStudyFinishedActivity, thunkStudyInit } from "./studyReducer";
import './Study.css';
import { APIActivityIntroSlides, APIActivityReview, APIAnno, APIAtomsInfo, APIIntroSlide, ATText } from "./api";
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

function TranscriptionTranslation(props: {attext: ATText, atomsInfo: APIAtomsInfo}) {
  return (
    <div className="TranscriptionTranslation">
      <div className="TranscriptionTranslation-transcription"><Transcription anno={props.attext.anno} atomsInfo={props.atomsInfo} atomsFailed={[]} /></div>
      <div className="TranscriptionTranslation-sep"></div>
      <div className="TranscriptionTranslation-translations">
        {props.attext.trans.map((translation, i) => (
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

function IntroSlide(props: {slide: APIIntroSlide, preloadMap: PreloadMap, atomsInfo: APIAtomsInfo, isLastSlide: boolean, onFinished: () => void}) {
  const [showText, setShowText] = useState(false);

  const handleAudioFinished = () => {
    setShowText(true);
  };

  const handleClickNext = () => {
    props.onFinished();
  };

  return (
    <div className="IntroSlide">
      <ImageAudioPlayer imageFn={props.preloadMap[props.slide.imageFn]} audioFn={props.preloadMap[props.slide.audioFn]} onFinished={handleAudioFinished} />
      {showText && <TranscriptionTranslation attext={props.slide.attext} atomsInfo={props.atomsInfo} />}
      {showText && <div className="IntroSlide-bottom"><button className="StandardButton" onClick={handleClickNext}>{props.isLastSlide ? 'Continue' : 'Next'}</button></div>}
    </div>
  );
}

function ActivityIntroSlides(props: {activity: APIActivityIntroSlides, preloadMap: PreloadMap, atomsInfo: APIAtomsInfo, onFinished: (atomReports: AtomReports) => void}) {
  const [slideIndex, setSlideIndex] = useState(0);

  return (
    <IntroSlide
      key={slideIndex}
      slide={props.activity.slides[slideIndex]}
      preloadMap={props.preloadMap}
      atomsInfo={props.atomsInfo}
      isLastSlide={slideIndex === (props.activity.slides.length-1)}
      onFinished={() => {
        if (slideIndex === (props.activity.slides.length-1)) {
          if (props.activity.atomsTested.length > 0) {
            throw new Error('unexpected atoms tested');
          }
          props.onFinished({
            atomsIntroduced: props.activity.atomsIntroduced,
            atomsExposed: props.activity.atomsExposed,
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

function ActivityReview(props: {activity: APIActivityReview, preloadMap: PreloadMap, atomsInfo: APIAtomsInfo, onFinished: (atomReports: AtomReports) => void}) {
  const [selectedChoiceIdx, setSelectedChoiceIdx] = useState<number | null>(null);
  const successAudioRef = useRef<HTMLAudioElement>(null);
  const failureAudioRef = useRef<HTMLAudioElement>(null);

  const handleClickChoice = (choiceIdx: number) => {
    setSelectedChoiceIdx(choiceIdx);
    const choice = props.activity.ques.options[choiceIdx];
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

    const choice = props.activity.ques.options[selectedChoiceIdx];
    let atomsPassed: ReadonlyArray<string>;
    let atomsFailed: ReadonlyArray<string>;
    if (choice.correct) {
      atomsPassed = choice.atomsPassed;
      atomsFailed = [];
    } else {
      atomsPassed = [];
      atomsFailed = choice.atomsFailed;
    }
    if (props.activity.atomsIntroduced.length > 0) {
      throw new Error('unexpected atoms introduced');
    }
    props.onFinished({
      atomsIntroduced: [],
      atomsExposed: props.activity.atomsExposed,
      atomsForgot: [],
      atomsPassed,
      atomsFailed,
    });
  };

  return (
    <div className="ActivityReview">
      <AudioPlayer audioUrl={props.preloadMap[props.activity.pres.audioFn]} onFinished={() => {}} />
      {(selectedChoiceIdx !== null) && (
        <TranscriptionTranslation attext={props.activity.pres.attext} atomsInfo={props.atomsInfo} />
      )}
      <div className="ActivityReview-bottom">
        <div className="ActivityReview-options">
          {props.activity.ques.options.map((option, optionIdx) => {
            const isSelected = selectedChoiceIdx === optionIdx;
            const isCorrect = option.correct;
            const classList = ['ActivityReview-option-image'];
            if (selectedChoiceIdx === null) {
              classList.push('ActivityReview-option-selectable');
            } else {
              classList.push('ActivityReview-option-unselectable');
              if (isCorrect) {
                classList.push('ActivityReview-option-correct');
              }
              if (isSelected && !isCorrect) {
                classList.push('ActivityReview-option-incorrect');
              }
            }
            return (
              <img
                className={classList.join(' ')}
                key={option.imageFn}
                src={props.preloadMap[option.imageFn]}
                onClick={() => handleClickChoice(optionIdx)}
              />
            );
          })}
          {(selectedChoiceIdx !== null) && (
            <div className="ActivityReview-continue-overlay">
              <button className="StandardButton" onClick={handleClickContinue}>Continue</button>
            </div>
          )}
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

  // scroll to top on activity start
  useLayoutEffect(() => {
    document.documentElement.scrollTo({top:0, left:0, behavior: "instant"});
  }, []);

  const handleFinished = (atomReports: AtomReports) => {
    props.dispatch(thunkStudyFinishedActivity(atomReports));
  }

  switch (activity.kind) {
    case 'intro_slides':
      return (
        <ActivityIntroSlides
          activity={activity}
          preloadMap={activityState.preloadMap}
          atomsInfo={activityState.atomsInfo}
          onFinished={handleFinished}
        />
      );

    case 'review':
      return (
        <ActivityReview
          activity={activity}
          preloadMap={activityState.preloadMap}
          atomsInfo={activityState.atomsInfo}
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
}
