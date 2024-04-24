import { useState } from "react";
import { thunkLogIn } from "./reducers";
import { useAppDispatch } from "./store";

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
    <div>
      <div>Login</div>
      {(formState === 'email_sent') ? (
        <div>Email sent to {email}</div>
      ) : (
        <>
          <form onSubmit={handleSubmit}>
            <label>
              Email:
              <input type="text" name="email" onChange={handleEmailChange} value={email} />
            </label>
            <input type="submit" value="Log In" />
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
