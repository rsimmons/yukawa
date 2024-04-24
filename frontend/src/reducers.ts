import { ThunkAction, ThunkDispatch, UnknownAction, createAction, createReducer } from '@reduxjs/toolkit'
import { APIError, APILoginResponse, apiAuth, apiGetUserInfo, apiLogin } from './api';

const SESSION_TOKEN_LOCAL_STORAGE_KEY = 'yukawa-session-token';

export interface SessionState {
  readonly sessionToken: string;
  readonly email: string;
}

export type CoarseState = {
  readonly type: 'initial';
} | {
  readonly type: 'loggingIn';
} | {
  readonly type: 'loggedIn';
  readonly sess: SessionState;
} | {
  readonly type: 'crashed';
  readonly msg: string;
};

export interface StatusState {
  readonly status: {
    // TODO: for async loading, include a map from unique ids to some info about the request
  };
};

export type RootState = CoarseState & StatusState;

export type AppThunk<ReturnType = void> = ThunkAction<
  ReturnType,
  RootState,
  unknown,
  UnknownAction
>

const initialState: RootState = {
  type: 'initial',
  status: {},
};

// helper for thunks below
const completeLogin = async (dispatch: ThunkDispatch<RootState, unknown, UnknownAction>, sessionToken: string) => {
  const userInfo = await apiGetUserInfo(sessionToken);
  dispatch(actionBecomeLoggedIn({
    sessionToken,
    email: userInfo.email,
  }));
};

export const thunkInit = (authToken?: string): AppThunk => async (dispatch, _getState) => {
  if (authToken) {
    // user must have clicked on auth link in email
    // TODO: show some loading indicator?
    const resp = await apiAuth(authToken);
    if (resp.status === 'ok') {
      const sessionToken = resp.token;
      await completeLogin(dispatch, sessionToken);
      localStorage.setItem(SESSION_TOKEN_LOCAL_STORAGE_KEY, sessionToken);
    } else if (resp.status === 'expired_token') {
      dispatch(actionCrash('expired token'));
    } else if (resp.status === 'invalid_token') {
      dispatch(actionCrash('invalid token'));
    } else {
      throw new Error('unrecognized auth status');
    }
  } else {
    // no auth token
    const sessionToken = localStorage.getItem(SESSION_TOKEN_LOCAL_STORAGE_KEY);

    if (sessionToken) {
      await completeLogin(dispatch, sessionToken);
    } else {
      dispatch(actionBecomeLoggingIn());
    }
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

export const actionCrash = createAction<string>('crash');
export const actionBecomeLoggingIn = createAction('becomeLoggingIn');
export const actionBecomeLoggedIn = createAction<{sessionToken: string, email: string}>('becomeLoggedIn');

const rootReducer = createReducer<RootState>(initialState, (builder) => {
  builder
    .addCase(actionCrash, (state, action) => {
      return {
        type: 'crashed',
        msg: action.payload,
        status: state.status,
      };
    })
    .addCase(actionBecomeLoggingIn, (state, _action) => {
      return {
        type: 'loggingIn',
        status: state.status,
      };
    })
    .addCase(actionBecomeLoggedIn, (state, action) => {
      return {
        type: 'loggedIn',
        sess: {
          sessionToken: action.payload.sessionToken,
          email: action.payload.email,
        },
        status: state.status,
      };
    })
});

export default rootReducer;
