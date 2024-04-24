import { useEffect, useRef } from "react";
import { Navigate } from "react-router-dom";
import { RootState, SessionState } from "./reducers";
import { useSelector } from "react-redux";

export const useEffectOnce = (effect: () => void) => {
  const hasRun = useRef(false);
  useEffect(() => {
    if (!hasRun.current) {
      effect();
      hasRun.current = true;
    }
  }, []);
}

export const InternalPage = (Page: (props: {sess: SessionState}) => JSX.Element) => () => {
  const sess = useSelector((state: RootState) => {
    if (state.type !== 'loggedIn') {
      return undefined;
    }
    return state.sess;
  });

  if (sess) {
    return <Page sess={sess} />
  } else {
    return <Navigate to="/login" replace={true} />;
  }
}
