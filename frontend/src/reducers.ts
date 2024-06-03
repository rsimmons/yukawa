import { ThunkAction, ThunkDispatch, UnknownAction, createAction, createReducer } from '@reduxjs/toolkit'
import { APIError, APIGrade, APILoginResponse, APIQuestion, apiAuth, apiGetQuestion, apiGetUserInfo, apiLogin, apiReportQuestionGrades } from './api';

const SESSION_TOKEN_LOCAL_STORAGE_KEY = 'yukawa-session-token';

export type StudyStage = 'listening' | 'grading_allowed' | 'grading_hearing' | 'grading_understanding' | 'grading_atoms' | 'loading_next';

export type InternalPage = {
  readonly type: 'home';
} | {
  readonly type: 'studyLoading';
} | {
  readonly type: 'study';
  readonly question: APIQuestion;
  readonly stage: StudyStage;
  readonly grades: {
    readonly heard: APIGrade | null;
    readonly understood: APIGrade | null;
    readonly atomsFailed: ReadonlyArray<string>;
  };
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
  const questionInfo = await apiGetQuestion(sessionToken);

  // fetch entire clip as blob, make object URL
  const blob = await fetch(questionInfo.mediaUrl).then((r) => r.blob());
  const mediaUrl = URL.createObjectURL(blob);

  dispatch(actionStudyLoadQuestion({
    ...questionInfo,
    mediaUrl,
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


export const thunkGradeUnderstanding = (understood: APIGrade): AppThunk => async (dispatch, getState) => {
  const state = getState();
  if (state.type !== 'loggedIn') {
    throw new Error('invalid state');
  }
  if (state.sess.page.type !== 'study') {
    throw new Error('invalid page');
  }
  if (state.sess.page.stage !== 'grading_understanding') {
    throw new Error('invalid stage');
  }
  if (state.sess.page.grades.heard === null) {
    throw new Error('invalid state');
  }

  if (understood === 'y') {
    dispatch(actionStudyLoadingNext());

    const sessionToken = state.sess.sessionToken;

    await apiReportQuestionGrades(sessionToken, 'es', state.sess.page.question.clipId, {
      heard: state.sess.page.grades.heard,
      understood,
      atoms_failed: state.sess.page.grades.atomsFailed,
    });

    await loadClip(dispatch, sessionToken);
  } else {
    dispatch(actionStudyGradeUnderstanding({
      understood,
    }));
  }
};

export const thunkSubmitGradeAtoms = (): AppThunk => async (dispatch, getState) => {
  const state = getState();
  if (state.type !== 'loggedIn') {
    throw new Error('invalid state');
  }
  if (state.sess.page.type !== 'study') {
    throw new Error('invalid page');
  }
  if (state.sess.page.stage !== 'grading_atoms') {
    throw new Error('invalid stage');
  }
  if (state.sess.page.grades.heard === null) {
    throw new Error('invalid state');
  }
  if (state.sess.page.grades.understood === null) {
    throw new Error('invalid state');
  }

  dispatch(actionStudyLoadingNext());

  const sessionToken = state.sess.sessionToken;

  await apiReportQuestionGrades(sessionToken, 'es', state.sess.page.question.clipId, {
    heard: state.sess.page.grades.heard,
    understood: state.sess.page.grades.understood,
    atoms_failed: state.sess.page.grades.atomsFailed,
  });

  await loadClip(dispatch, sessionToken);
};

export const actionCrash = createAction<string>('crash');
export const actionBecomeLoggingIn = createAction('becomeLoggingIn');
export const actionBecomeLoggedIn = createAction<{
  readonly sessionToken: string;
  readonly email: string;
}>('becomeLoggedIn');
export const actionEnterStudyLoading = createAction('enterStudyLoading');
export const actionStudyLoadQuestion = createAction<APIQuestion>('studyLoadQuestion');
export const actionStudyAllowGrading = createAction('studyAllowGrading');
export const actionStudyBeginGrading = createAction('studyBeginGrading');
export const actionStudyGradeHearing = createAction<{
  readonly heard: APIGrade;
}>('studyGradeHearing');
export const actionStudyGradeUnderstanding = createAction<{
  readonly understood: APIGrade;
}>('studyGradeUnderstanding');
export const actionStudyToggleAtomGrade = createAction<string>('studyToggleAtomGrade');
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
            question: action.payload,
            stage: 'listening',
            grades: {
              heard: null,
              understood: null,
              atomsFailed: [],
            },
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
      if (state.sess.page.stage !== 'listening') {
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
    .addCase(actionStudyBeginGrading, (state) => {
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
            stage: 'grading_hearing',
          },
        },
        status: state.status,
      };
    })
    .addCase(actionStudyGradeHearing, (state, action) => {
      if (state.type !== 'loggedIn') {
        return state;
      }
      if (state.sess.page.type !== 'study') {
        return state;
      }
      if (state.sess.page.stage !== 'grading_hearing') {
        return state;
      }
      return {
        type: 'loggedIn',
        sess: {
          ...state.sess,
          page: {
            ...state.sess.page,
            stage: 'grading_understanding',
            grades: {
              ...state.sess.page.grades,
              heard: action.payload.heard,
            },
          },
        },
        status: state.status,
      };
    })
    .addCase(actionStudyGradeUnderstanding, (state, action) => {
      if (state.type !== 'loggedIn') {
        return state;
      }
      if (state.sess.page.type !== 'study') {
        return state;
      }
      if (state.sess.page.stage !== 'grading_understanding') {
        return state;
      }
      return {
        type: 'loggedIn',
        sess: {
          ...state.sess,
          page: {
            ...state.sess.page,
            stage: 'grading_atoms',
            grades: {
              ...state.sess.page.grades,
              understood: action.payload.understood,
            },
          },
        },
        status: state.status,
      };
    })
    .addCase(actionStudyToggleAtomGrade, (state, action) => {
      if (state.type !== 'loggedIn') {
        return state;
      }
      if (state.sess.page.type !== 'study') {
        return state;
      }
      const atomId = action.payload;
      const atomsFailed = state.sess.page.grades.atomsFailed;
      const newAtomsFailed = atomsFailed.includes(atomId) ? atomsFailed.filter((atom) => atom !== atomId) : [...atomsFailed, atomId];
      return {
        type: 'loggedIn',
        sess: {
          ...state.sess,
          page: {
            ...state.sess.page,
            grades: {
              ...state.sess.page.grades,
              atomsFailed: newAtomsFailed,
            },
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
