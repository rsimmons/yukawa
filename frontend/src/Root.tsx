import { Outlet, useLocation, useMatches, useNavigate } from "react-router-dom";
import { useEffectOnce } from "./util";
import { useAppDispatch } from "./store";
import { thunkInit } from "./reducers";
import './Root.css';

export default function Root() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  useEffectOnce(() => {
    dispatch(thunkInit(navigate));
  });

  const location = useLocation();
  console.log('Root location', location);

  const matches = useMatches();
  console.log('Root matches', matches);

  return (
    <>
      <h1>Yukawa</h1>
      <Outlet />
    </>
  );
}
