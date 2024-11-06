import { useSelector } from "react-redux";
import { RootState, SessionState, actionEnterStudy, thunkLogOut } from "./reducers";
import { useAppDispatch } from "./store";
import Header from "./Header";
import './Home.css';

export default function Home() {
  const dispatch = useAppDispatch();

  const sess: SessionState = useSelector((state: RootState) => {
    if (state.type !== 'loggedIn') {
      throw new Error('invalid state');
    }
    return state.sess;
  });

  const handleClickStudy = () => {
    dispatch(actionEnterStudy());
  };

  const handleLogOut = () => {
    dispatch(thunkLogOut());
  };

  return (
    <div className="Home">
      <Header />
      <div>Greetings! You are logged in as {sess.email}</div>
      <p>You may <button onClick={handleClickStudy}>Study</button> or <button onClick={handleLogOut}>Log Out</button></p>
    </div>
  );
}
