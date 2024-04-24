import { useSelector } from "react-redux";
import { RootState, SessionState } from "./reducers";

export default function Home() {
  const sess: SessionState = useSelector((state: RootState) => {
    if (state.type !== 'loggedIn') {
      throw new Error('invalid state');
    }
    return state.sess;
  });

  return (
    <div>
      <div>Home {sess.email}</div>
      <p>|ENV TEST|{import.meta.env.VITE_FOOBAR}|{import.meta.env.MODE}|</p>
    </div>
  );
}
