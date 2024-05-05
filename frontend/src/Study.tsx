import { useSelector } from "react-redux";
import { InternalPage, RootState, UnderstoodGrade, actionStudyAllowGrading, actionStudyRevealAnswer, thunkSubmitGrade } from "./reducers";
import { useAppDispatch } from "./store";
import { useEffect, useRef } from "react";
import { touchAvail } from "./util";
import './Study.css';

function StudyButton(props: {text: string, shortcut?: string, onClick: () => void}) {
  return (
    <button className="Study-button" onClick={props.onClick}>{props.text}{props.shortcut && !touchAvail && (
      <span className="Study-button-shortcut"> {props.shortcut}</span>
    )}</button>
  );
}

export default function Study() {
  const dispatch = useAppDispatch();

  const page: InternalPage = useSelector((state: RootState) => {
    if (state.type !== 'loggedIn') {
      throw new Error('invalid state');
    }
    return state.sess.page;
  });

  if (page.type !== 'study') {
    throw new Error('invalid page');
  }

  const handleRevealAnswer = () => {
    dispatch(actionStudyRevealAnswer());
  };

  const handleGrade = (grade: UnderstoodGrade) => {
    dispatch(thunkSubmitGrade(page.question.clipId, grade));
  };

  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'r') {
        if (videoRef.current) {
          videoRef.current.currentTime = 0;
          videoRef.current.play();
        }
      } else if (event.key === ' ') {
        if (page.stage === 'grading_allowed') {
          handleRevealAnswer();
        }
      } else if (event.key === '1') {
        if (page.stage === 'grading') {
          handleGrade('no');
        }
      } else if (event.key === '2') {
        if (page.stage === 'grading') {
          handleGrade('mostly');
        }
      } else if (event.key === '3') {
        if (page.stage === 'grading') {
          handleGrade('fully');
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  });

  const handleVideoTimeUpdate = () => {
    if (videoRef.current) {
      if (videoRef.current.currentTime > (videoRef.current.duration-0.5)) {
        if (page.stage === 'input') {
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

  const question = page.question;
  return (
    <div>
      <video className="Study-video" playsInline key={question.mediaUrl} autoPlay={true} ref={videoRef} onTimeUpdate={handleVideoTimeUpdate} onClick={handleVideoClick}>
        <source src={question.mediaUrl} type="video/mp4" />
        Your browser does not support the video tag.
      </video>
      {((page.stage === 'grading') || (page.stage === 'loading_next')) && (
        <div className="Study-trans">
          <div className="Study-transcription">{question.transcription}</div>
          <div className="Study-trans-sep"></div>
          <div className="Study-translation">{question.translation}</div>
        </div>
      )}
      <div className="Study-pad"></div>
      {(() => {
        switch (page.stage) {
          case 'input':
            return (
              <div className="Study-controls">
                <div className="Study-controls-instructions">Listen carefully</div>
              </div>
            );

          case 'grading_allowed':
            return (
              <div className="Study-controls">
                <div className="Study-controls-instructions">Could you understand it?<br/>{touchAvail ? 'R' : '[R]'}eplay if needed</div>
                <div className="Study-controls-buttons">
                  <StudyButton text="Reveal Subtitles" shortcut="[space]" onClick={handleRevealAnswer} />
                </div>
              </div>
            );

          case 'grading':
            return (
              <div className="Study-controls">
                <div className="Study-controls-instructions">Did you understand it correctly?</div>
                <div className="Study-controls-buttons">
                  <StudyButton text="No" shortcut="[1]" onClick={() => {handleGrade('no')}} />
                  <StudyButton text="Mostly" shortcut="[2]" onClick={() => {handleGrade('mostly')}} />
                  <StudyButton text="Fully" shortcut="[3]" onClick={() => {handleGrade('fully')}} />
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
}
