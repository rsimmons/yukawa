import { useSelector } from "react-redux";
import { RootState } from "./reducers";
import { useAppDispatch } from "./store";
import { useRef } from "react";
import { useEffectOnce, useRAF } from "./util";
import { actionStudyPresItemFinished, PreloadMap, StudyState, thunkLessonCompleted, thunkQuizAnswered, thunkStudyInit } from "./studyReducer";
import './Study.css';
import { APIActivityPresItem } from "./api";

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
function PresItem(props: {item: APIActivityPresItem, preloadMap: PreloadMap, finished: () => void}) {
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
            props.finished();
            notifiedFinished.current = true;
          }
        }
      }
    }
  });

  return (
    <div>
      {props.item.imageFn && (
        <img src={props.preloadMap[props.item.imageFn]} />
      )}
      <audio src={props.preloadMap[props.item.audioFn!]} autoPlay={false} ref={audioRef} />
      {/* <div>{props.item.text}</div> */}
    </div>
  );
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

  /*
  const handleBeginGrading = () => {
    dispatch(actionStudyBeginGrading());
  };

  const handleGradeHearing = (grade: APIGrade) => {
    dispatch(actionStudyGradeHearing({heard: grade}));
  };

  const handleGradeUnderstanding = (grade: APIGrade) => {
    dispatch(thunkGradeUnderstanding(grade));
  };

  const handleGradeWords = () => {
    // TODO: get failed atoms
    dispatch(thunkSubmitGradeAtoms());
  };

  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const grade_hearing_or_understanding = (grade: APIGrade) => {
        if (page.stage === 'grading_hearing') {
          handleGradeHearing(grade);
        } else if (page.stage === 'grading_understanding') {
          handleGradeUnderstanding(grade);
        }
      };

      if (event.key === 'r') {
        if (videoRef.current) {
          videoRef.current.currentTime = 0;
          videoRef.current.play();
        }
      } else if (event.key === ' ') {
        if (page.stage === 'grading_allowed') {
          handleBeginGrading();
        } else if (page.stage === 'grading_atoms') {
          handleGradeWords();
        }
      } else if (event.key === '1') {
        grade_hearing_or_understanding('n');
      } else if (event.key === '2') {
        grade_hearing_or_understanding('m');
      } else if (event.key === '3') {
        grade_hearing_or_understanding('y');
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  });

  const handleVideoTimeUpdate = () => {
    if (videoRef.current) {
      if (videoRef.current.currentTime > (videoRef.current.duration-1)) {
        if (page.stage === 'listening') {
          dispatch(actionStudyAllowGrading());
        }
      }
    }
  };

  const handleVideoClick = () => {
    if (videoRef.current) {
      if (videoRef.current.paused) {
        videoRef.current.play();
      } else {
        videoRef.current.pause();
      }
    }
  };
  */

  return (
    <div>
      {(studyState.preloadedActivity ? (
        <div>{(() => {
          const preAct = studyState.preloadedActivity;
          const presIdx = preAct.state.presIndex;
          const presItem = preAct.activity.pres.items[presIdx];

          const handleContinueLesson = () => {
            dispatch(thunkLessonCompleted());
          };

          return (
            <div key={preAct.uid}>
              <PresItem
                key={presIdx}
                item={presItem}
                preloadMap={preAct.preloadMap}
                finished={() => {
                  dispatch(actionStudyPresItemFinished());
                }}
              />
              {(() => {
                switch (preAct.activity.kind) {
                  case 'lesson':
                    return (
                      <div style={{textAlign: 'center'}}>{preAct.state.everFinishedPres ? (
                        <button onClick={handleContinueLesson}>Continue</button>
                      ) : (
                        <button onClick={handleContinueLesson}>Skip</button>
                      )}</div>
                    );

                  case 'quiz':
                    return (
                      <div>
                        {preAct.activity.choices.map((choice) => {
                          const handleClick = () => {
                            dispatch(thunkQuizAnswered(choice));
                          };
                          return <img key={choice.imageFn} src={preAct.preloadMap[choice.imageFn]} onClick={handleClick} />
                        })}
                      </div>
                    );

                  default:
                    throw new Error('invalid activity kind');
                }
              })()}
            </div>
          );
        })()}</div>
      ) : (
        <div>Loading...</div>
      ))}
    </div>
  );

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
