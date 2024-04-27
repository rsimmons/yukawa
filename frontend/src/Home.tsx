import { useSelector } from "react-redux";
import { RootState, SessionState, thunkViewClips } from "./reducers";
import { useAppDispatch } from "./store";

export default function Home() {
  const dispatch = useAppDispatch();

  const sess: SessionState = useSelector((state: RootState) => {
    if (state.type !== 'loggedIn') {
      throw new Error('invalid state');
    }
    return state.sess;
  });

  const handleClickClips = () => {
    dispatch(thunkViewClips());
  };

  return (
    <div>
      <div>Home {sess.email}</div>
      <p>|ENV TEST|{import.meta.env.VITE_FOOBAR}|{import.meta.env.MODE}|</p>
      <p><button onClick={handleClickClips}>Random Clips</button></p>
    </div>
  );
}
