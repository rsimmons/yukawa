import { SessionState } from "./reducers";
import { InternalPage } from "./util";

const Home = InternalPage(({sess}: {sess: SessionState}) => {
  return (
    <div>
      <div>Home {sess.email}</div>
      <p>|ENV TEST|{import.meta.env.VITE_FOOBAR}|{import.meta.env.MODE}|</p>
    </div>
  );
});

export default Home;
