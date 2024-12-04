import { useState } from "react";
import { thunkLogIn } from "./reducers";
import { useAppDispatch } from "./store";
import './Login.css';

type LoginFormState = 'entering' | 'waiting' | 'invalid_email' | 'email_sent';

export default function Login() {
  const dispatch = useAppDispatch();

  const [formState, setFormState] = useState<LoginFormState>('entering');
  const [email, setEmail] = useState<string>('');

  const handleEmailChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setEmail(event.target.value);
  }

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    setFormState('waiting');
    dispatch(thunkLogIn(email, (resp) => {
      if (resp.status === 'ok') {
        setFormState('email_sent');
      } else if (resp.status === 'invalid_email') {
        setFormState('invalid_email');
      } else {
        throw new Error('unexpected status');
      }
    }));
    event.preventDefault();
  };

  return (
    <div className="Login">
      <div className="Login-header">
        <div className="Login-header-name">Yukawa</div>
        <div className="Login-header-proto">prototype·Spanish</div>
      </div>
      <div className="Login-main">
        <div className="Login-title">Log In or Sign Up</div>
        {(formState === 'email_sent') ? (
          <div>A login link has been sent to {email}</div>
        ) : (
          <>
            <form onSubmit={handleSubmit}>
              <div><input className="StandardInput Login-email" type="text" name="email" onChange={handleEmailChange} value={email} placeholder="Email address" /></div>
              <div><input className="StandardButton Login-button" type="submit" value="Send Link" /></div>
            </form>
            <div className="Login-message">
              {(() => {
                if (formState === 'invalid_email') {
                  return <span>Invalid email</span>;
                } else if (formState === 'waiting') {
                  return <span>...</span>;
                } else {
                  return <span></span>;
                }
              })()}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
