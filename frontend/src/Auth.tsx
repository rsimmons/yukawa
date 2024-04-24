import { useNavigate } from "react-router-dom";
import { thunkAuth, actionCrash } from "./reducers";
import { useAppDispatch } from "./store";
import { useEffectOnce } from "./util";
import { useState } from "react";

type AuthPageState = 'waiting' | 'expired_token' | 'invalid_token';

export default function Auth() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();

  const [pageState, setPageState] = useState<AuthPageState>('waiting');

  useEffectOnce(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const authToken = urlParams.get('token');
    if (authToken) {
      dispatch(thunkAuth(authToken, navigate, (error) => {
        setPageState(error);
      }));
    } else {
      dispatch(actionCrash('No auth token found'));
    }
  });

  return (
    <div>
      <div>Auth</div>
      {(() => {
        if (pageState === 'waiting') {
          return <div>...</div>;
        } else if (pageState === 'expired_token') {
          return <div>Expired token</div>;
        } else if (pageState === 'invalid_token') {
          return <div>Invalid token</div>;
        } else {
          return <div></div>;
        }
      })()}
    </div>
  );
}
