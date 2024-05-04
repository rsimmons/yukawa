import { useSelector } from "react-redux";
import { RootState, SessionState, StudyQuestion, thunkLoadClip } from "./reducers";
import { AppDispatch, useAppDispatch } from "./store";
import { useEffect, useRef } from "react";
import './Study.css';

function StudyLoading() {
  return <div>Loading...</div>;
}

function StudyLoaded({dispatch, question}: {dispatch: AppDispatch, question: StudyQuestion}) {
  const handleClickNext = () => {
    dispatch(thunkLoadClip());
  };

  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'r') {
        if (videoRef.current) {
          videoRef.current.currentTime = 0;
          videoRef.current.play();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  return (
    <div>
      <video className="Study-video" controls key={question.mediaUrl} autoPlay={true} ref={videoRef}>
        <source src={question.mediaUrl} type="video/mp4" />
        Your browser does not support the video tag.
      </video>
      <div className="Study-trans">
        <div className="Study-transcription">{question.transcription}</div>
        <div className="Study-trans-sep"></div>
        <div className="Study-translation">{question.translation}</div>
      </div>
      <div className="Study-pad"></div>
      <div className="Study-controls">
        <div className="Study-controls-inner">
          <div className="Study-controls-instructions">Push the buttons</div>
          <div className="Study-controls-buttons">
            <div><button className="Study-button" onClick={handleClickNext}>Next</button></div>
            <div><button className="Study-button" >Foo</button></div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Study() {
  const dispatch = useAppDispatch();

  const sess: SessionState = useSelector((state: RootState) => {
    if (state.type !== 'loggedIn') {
      throw new Error('invalid state');
    }
    return state.sess;
  });

  if (sess.page.type !== 'study') {
    throw new Error('invalid page');
  }

  const question = sess.page.question;
  return question ? <StudyLoaded dispatch={dispatch} question={question} /> : <StudyLoading />;
}
