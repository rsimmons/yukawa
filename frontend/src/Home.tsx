import { useSelector } from "react-redux";
import { RootState, SessionState, actionEnterStudy, thunkLogOut } from "./reducers";
import { useAppDispatch } from "./store";
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

  const handleLogOut = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault();
    dispatch(thunkLogOut());
  };

  return (
    <div className="Home">
      <div className="Home-header">Yukawa</div>
      <div><button className="StandardButton Home-study-button" onClick={handleClickStudy}>Study</button></div>
      <div className="Home-footer">
        <div>{sess.email}</div>
        <div><a href="#" className="ActionLink" onClick={handleLogOut}>Log Out</a></div>
      </div>
    </div>
  );
}
