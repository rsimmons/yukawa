import { useSelector } from "react-redux";
import { RootState, SessionState, thunkLoadClip } from "./reducers";
import { useAppDispatch } from "./store";

export default function Home() {
  const dispatch = useAppDispatch();

  const sess: SessionState = useSelector((state: RootState) => {
    if (state.type !== 'loggedIn') {
      throw new Error('invalid state');
    }
    return state.sess;
  });

  if (sess.page.type !== 'clip') {
    throw new Error('invalid page');
  }

  const handleClickNext = () => {
    dispatch(thunkLoadClip());
  };

  // show video clip
  return (
    <div>
      <video width="854" height="480" controls key={sess.page.clip ? sess.page.clip.mediaUrl : 'noclip'}>
        {sess.page.clip &&
          <source src={sess.page.clip.mediaUrl} type="video/mp4" />
        }
        Your browser does not support the video tag.
      </video>
      <div><button onClick={handleClickNext}>Next</button></div>
    </div>
  );
}
