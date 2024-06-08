import { useState } from "react";
import { thunkLogIn } from "./reducers";
import { useAppDispatch } from "./store";
import Header from "./Header";
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
      <Header />
      {(formState === 'email_sent') ? (
        <div>We emailed you at {email}</div>
      ) : (
        <>
          <form onSubmit={handleSubmit}>
            If you enter <input className="Login-email" type="text" name="email" onChange={handleEmailChange} value={email} placeholder="your email address" /><br/>
            and press <input type="submit" value="Send" style={{margin: '4px 0'}} /><br />
            we'll send you a link to log in.
          </form>
          <div>
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
  );
}
