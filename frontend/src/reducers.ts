import { ThunkAction, ThunkDispatch, UnknownAction, createAction, createReducer } from '@reduxjs/toolkit'
import { APIError, APILoginResponse, apiAuth, apiGetRandomClip, apiGetUserInfo, apiLogin, apiReportClipUnderstood } from './api';

const SESSION_TOKEN_LOCAL_STORAGE_KEY = 'yukawa-session-token';

export interface StudyQuestion {
  readonly clipId: string;
  readonly mediaUrl: string;
  readonly transcription: string;
  readonly translation: string;
}

export type StudyStage = 'input' | 'grading_allowed' | 'grading' | 'loading_next';

export type InternalPage = {
  readonly type: 'home';
} | {
  readonly type: 'studyLoading';
} | {
  readonly type: 'study';
  readonly question: StudyQuestion;
  readonly stage: StudyStage;
};

export interface SessionState {
  readonly sessionToken: string;
  readonly email: string;
  readonly page: InternalPage;
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

export const loadClip = async (dispatch: ThunkDispatch<RootState, unknown, UnknownAction>, sessionToken: string) => {
  const clipInfo = await apiGetRandomClip(sessionToken);

  // fetch entire clip as blob, make object URL
  const blob = await fetch(clipInfo.mediaUrl).then((r) => r.blob());
  const mediaUrl = URL.createObjectURL(blob);

  dispatch(actionStudyLoadQuestion({
    clipId: clipInfo.clipId,
    mediaUrl,
    transcription: clipInfo.transcription,
    translation: clipInfo.translation,
  }));
}

export const thunkEnterStudy = (): AppThunk => async (dispatch, getState) => {
  const state = getState();
  if (state.type !== 'loggedIn') {
    throw new Error('invalid state');
  }

  dispatch(actionEnterStudyLoading());

  const sessionToken = state.sess.sessionToken;
  await loadClip(dispatch, sessionToken);
};

export type UnderstoodGrade = 'no' | 'mostly' | 'fully';
export const thunkSubmitGrade = (clipId: string, grade: UnderstoodGrade): AppThunk => async (dispatch, getState) => {
  dispatch(actionStudyLoadingNext());

  const state = getState();
  if (state.type !== 'loggedIn') {
    throw new Error('invalid state');
  }

  const sessionToken = state.sess.sessionToken;

  await apiReportClipUnderstood(sessionToken, clipId, grade);

  await loadClip(dispatch, sessionToken);
};

export const actionCrash = createAction<string>('crash');
export const actionBecomeLoggingIn = createAction('becomeLoggingIn');
export const actionBecomeLoggedIn = createAction<{
  readonly sessionToken: string;
  readonly email: string;
}>('becomeLoggedIn');
export const actionEnterStudyLoading = createAction('enterStudyLoading');
export const actionStudyLoadQuestion = createAction<{
  readonly clipId: string;
  readonly mediaUrl: string;
  readonly transcription: string;
  readonly translation: string;
}>('loadQuestion');
export const actionStudyAllowGrading = createAction('studyAllowGrading');
export const actionStudyRevealAnswer = createAction('studyRevealAnswer');
export const actionStudyLoadingNext = createAction('studyLoadingNext');

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
          page: {
            type: 'home',
          },
        },
        status: state.status,
      };
    })
    .addCase(actionEnterStudyLoading, (state, _action) => {
      if (state.type !== 'loggedIn') {
        return state;
      }
      return {
        type: 'loggedIn',
        sess: {
          ...state.sess,
          page: {
            type: 'studyLoading',
          },
        },
        status: state.status,
      };
    })
    .addCase(actionStudyLoadQuestion, (state, action) => {
      if (state.type !== 'loggedIn') {
        return state;
      }
      if (!((state.sess.page.type === 'study') || (state.sess.page.type === 'studyLoading'))) {
        return state;
      }
      return {
        type: 'loggedIn',
        sess: {
          ...state.sess,
          page: {
            type: 'study',
            question: {
              clipId: action.payload.clipId,
              mediaUrl: action.payload.mediaUrl,
              transcription: action.payload.transcription,
              translation: action.payload.translation,
            },
            stage: 'input',
          },
        },
        status: state.status,
      };
    })
    .addCase(actionStudyAllowGrading, (state) => {
      if (state.type !== 'loggedIn') {
        return state;
      }
      if (state.sess.page.type !== 'study') {
        return state;
      }
      if (state.sess.page.stage !== 'input') {
        return state;
      }
      return {
        type: 'loggedIn',
        sess: {
          ...state.sess,
          page: {
            ...state.sess.page,
            stage: 'grading_allowed',
          },
        },
        status: state.status,
      };
    })
    .addCase(actionStudyRevealAnswer, (state) => {
      if (state.type !== 'loggedIn') {
        return state;
      }
      if (state.sess.page.type !== 'study') {
        return state;
      }
      if (state.sess.page.stage !== 'grading_allowed') {
        return state;
      }
      return {
        type: 'loggedIn',
        sess: {
          ...state.sess,
          page: {
            ...state.sess.page,
            stage: 'grading',
          },
        },
        status: state.status,
      };
    })
    .addCase(actionStudyLoadingNext, (state) => {
      if (state.type !== 'loggedIn') {
        return state;
      }
      if (state.sess.page.type !== 'study') {
        return state;
      }
      if (state.sess.page.stage !== 'grading') {
        return state;
      }
      return {
        type: 'loggedIn',
        sess: {
          ...state.sess,
          page: {
            ...state.sess.page,
            stage: 'loading_next',
          },
        },
        status: state.status,
      };
    });
});

export default rootReducer;
