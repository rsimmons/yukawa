import { ThunkAction, ThunkDispatch, UnknownAction, createAction, createReducer } from '@reduxjs/toolkit'
import { APIError, APILoginResponse, apiAuth, apiGetUserInfo, apiLogin } from './api';
import { useNavigate } from "react-router-dom";

type NavigateFn = ReturnType<typeof useNavigate>;

const SESSION_TOKEN_LOCAL_STORAGE_KEY = 'yukawa-session-token';

export interface SessionState {
  sessionToken: string;
  email: string;
}

export type RootState =
  {
    type: 'initial';
  } | {
    type: 'loggedOut';
  } | {
    type: 'loggedIn';
    sess: SessionState;
  } | {
    type: 'loading';
  } | {
    type: 'crashed';
    msg: string;
  }

export type AppThunk<ReturnType = void> = ThunkAction<
  ReturnType,
  RootState,
  unknown,
  UnknownAction
>

const initialState: RootState = { type: 'initial' };

// helper for thunks below
const completeLogin = async (dispatch: ThunkDispatch<RootState, unknown, UnknownAction>, sessionToken: string) => {
  const userInfo = await apiGetUserInfo(sessionToken);
  dispatch(actionLoggedIn({
    sessionToken,
    email: userInfo.email,
  }));
};

export const thunkInit = (navigate: NavigateFn): AppThunk => async (dispatch, _getState) => {
  const sessionToken = localStorage.getItem(SESSION_TOKEN_LOCAL_STORAGE_KEY);
  if (sessionToken) {
    dispatch(actionLoading());
    await completeLogin(dispatch, sessionToken);
    navigate('/home', { replace: true });
  } else {
    dispatch(actionLoggedOut());
    navigate('/login', { replace: true });
  }
};

export const thunkLogIn = (email: string, onUpdate: (resp: APILoginResponse) => void): AppThunk => async (dispatch, _getState) => {
  try {
    const resp = await apiLogin(email);
    onUpdate(resp);
  } catch (e) {
    if (e instanceof APIError) {
      dispatch(actionCrash(e.message));
      return;
    } else {
      throw e;
    }
  }
};

// This is dispatched when the user clicks the link in the email we send
type ThunkAuthError = 'expired_token' | 'invalid_token';
export const thunkAuth = (authToken: string, navigate: NavigateFn, onError: (error: ThunkAuthError) => void): AppThunk => async (dispatch, _getState) => {
  dispatch(actionLoading());
  const resp = await apiAuth(authToken);
  if (resp.status === 'ok') {
    const sessionToken = resp.token;
    await completeLogin(dispatch, sessionToken);
    localStorage.setItem(SESSION_TOKEN_LOCAL_STORAGE_KEY, sessionToken);
    navigate('/home', { replace: true });
  } else if (resp.status === 'expired_token') {
    console.log('expired token');
    onError('expired_token');
  } else if (resp.status === 'invalid_token') {
    onError('invalid_token');
  } else {
    throw new Error('unrecognized auth status');
  }
};

export const actionCrash = createAction<string>('crash');
export const actionLoading = createAction('loading');
export const actionLoggedOut = createAction('loggedOut');
export const actionLoggedIn = createAction<{sessionToken: string, email: string}>('loggedIn');

const rootReducer = createReducer<RootState>(initialState, (builder) => {
  builder
    .addCase(actionCrash, (_state, action) => {
      return { type: 'crashed', msg: action.payload };
    })
    .addCase(actionLoading, (_state, _action) => {
      return { type: 'loading' };
    })
    .addCase(actionLoggedOut, (_state, _action) => {
      return { type: 'loggedOut' };
    })
    .addCase(actionLoggedIn, (_state, action) => {
      return {
        type: 'loggedIn',
        sess: {
          sessionToken: action.payload.sessionToken,
          email: action.payload.email,
        },
      };
    })
});

export default rootReducer;
