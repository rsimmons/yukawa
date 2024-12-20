import { useEffectOnce } from "./util";
import { useAppDispatch } from "./store";
import { RootState, thunkInit } from "./reducers";
import Login from './Login.tsx';
import Home from './Home.tsx';
import Study from './Study.tsx';
import './Root.css';
import { useSelector } from "react-redux";

function Crashed() {
  const msg = useSelector((state: RootState) => {
    if (state.type !== 'crashed') {
      throw new Error('invalid state');
    }
    return state.msg;
  });

  return <div>Crashed: {msg}</div>;
}

function LoggedIn() {
  const sessState = useSelector((state: RootState) => {
    if (state.type !== 'loggedIn') {
      throw new Error('invalid state');
    }
    return state.sess;
  });

  switch (sessState.page.type) {
    case 'home':
      return <Home />;

    case 'study':
      return <Study />;

    default:
      throw new Error('invalid page');
  }
}

export default function Root() {
  const dispatch = useAppDispatch();
  const stateType = useSelector((state: RootState) => state.type);

  useEffectOnce(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const authToken = urlParams.get('authtoken') || undefined;

    if (authToken) {
      // remove the auth token from the URL
      window.history.replaceState(null, '', window.location.pathname);
    }

    dispatch(thunkInit(authToken));
  });

  return (
    <>{(() => {
      switch (stateType) {
        case 'initial':
          return <div>Loading...</div>;

        case 'loggingIn':
          return <Login />;

        case 'loggedIn':
          return <LoggedIn />;

        case 'crashed':
          return <Crashed />;

        default:
          throw new Error('invalid state');
      }
    })()}</>
  );
}
