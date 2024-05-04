import { useSelector } from "react-redux";
import { RootState, SessionState, thunkLoadClip } from "./reducers";
import { useAppDispatch } from "./store";

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

  const handleClickNext = () => {
    dispatch(thunkLoadClip());
  };

  // show video clip
  return (
    <div>
      <video width="854" height="480" controls key={sess.page.question ? sess.page.question.mediaUrl : 'noclip'}>
        {sess.page.question &&
          <source src={sess.page.question.mediaUrl} type="video/mp4" />
        }
        Your browser does not support the video tag.
      </video>
      <div>{sess.page.question && sess.page.question.transcription}</div>
      <div>{sess.page.question && sess.page.question.translation}</div>
      <div><button onClick={handleClickNext}>Next</button></div>
    </div>
  );
}
