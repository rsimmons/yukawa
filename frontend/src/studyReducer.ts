import { ThunkDispatch, UnknownAction, createAction, createReducer } from '@reduxjs/toolkit'
import { APIActivity, APIActivityPres, apiPickActivity, APIPickActivityResponse, APIQuizChoice, apiReportResult } from './api';
import { AppThunk, RootState } from './reducers';
import { genRandomStr64 } from './util';

// maps "filename" returned by API to object URL of preloaded media
// type PreloadMap = ReadonlyMap<string, string>;
export interface PreloadMap {
  [filename: string]: string;
}

interface ActivityState {
  readonly presIndex: number;
  readonly everFinishedPres: boolean;
}

export interface StudyState {
  readonly loading: boolean; // true during initial or subsequent loading of next activity
  readonly preloadedActivity: {
    readonly uid: string;
    readonly activity: APIActivity;
    readonly preloadMap: PreloadMap;
    readonly state: ActivityState;
  } | undefined; // undefined before initial load
}

export const initialStudyState: StudyState = {
  loading: true,
  preloadedActivity: undefined,
};

const preloadFilename = async (filename: string, mediaUrlPrefix: string): Promise<string> => {
  const blob = await fetch(mediaUrlPrefix + filename).then((r) => r.blob());
  return URL.createObjectURL(blob);
}

const getActivityPresMediaFilenames = (pres: APIActivityPres): ReadonlySet<string> => {
  const filenames = new Set<string>();

  for (const item of pres.items) {
    if (item.audioFn !== undefined) {
      filenames.add(item.audioFn);
    }
    if (item.imageFn !== undefined) {
      filenames.add(item.imageFn);
    }
  }

  return filenames;
};

const getActivityMediaFilenames = (activity: APIActivity): ReadonlySet<string> => {
  switch (activity.kind) {
    case 'lesson':
      return getActivityPresMediaFilenames(activity.pres);

    case 'quiz': {
      const presMediaFns = getActivityPresMediaFilenames(activity.pres);

      const choiceMediaFns = new Set<string>();
      for (const choice of activity.choices) {
        choiceMediaFns.add(choice.imageFn);
      }

      return new Set([...presMediaFns, ...choiceMediaFns]);
    }

    default:
      throw new Error('unknown activity kind');
  }
};

const preloadActivityMedia = async (pickActivityResp: APIPickActivityResponse, mediaUrlPrefix: string): Promise<PreloadMap> => {
  const preloadMap: PreloadMap = {};

  // find all media filenames
  const mediaFilenames = getActivityMediaFilenames(pickActivityResp.activity);
  for (const filename of mediaFilenames) { // TODO: load in parallel
    preloadMap[filename] = await preloadFilename(filename, mediaUrlPrefix);
  }

  return preloadMap;
}

const loadActivity = async (dispatch: ThunkDispatch<RootState, unknown, UnknownAction>, sessionToken: string): Promise<void> => {
  const pickActivityResp = await apiPickActivity(sessionToken);

  // preload media
  const preloadMap = await preloadActivityMedia(pickActivityResp, pickActivityResp.mediaUrlPrefix);

  dispatch(actionStudyLoadActivity({
    activity: pickActivityResp.activity,
    preloadMap,
  }));
}

export const thunkStudyInit = (): AppThunk => async (dispatch, getState) => {
  const state = getState();
  if (state.type !== 'loggedIn') {
    throw new Error('invalid state');
  }

  await loadActivity(dispatch, state.sess.sessionToken);
};

export const thunkLessonCompleted = (): AppThunk => async (dispatch, getState) => {
  const state = getState();
  if (state.type !== 'loggedIn') {
    throw new Error('invalid state');
  }
  if (state.sess.page.type !== 'study') {
    throw new Error('invalid page');
  }
  if (state.sess.page.studyState.preloadedActivity === undefined) {
    throw new Error('invalid study state');
  }
  if (state.sess.page.studyState.preloadedActivity.activity.kind !== 'lesson') {
    throw new Error('invalid activity kind');
  }

  const introAtoms = state.sess.page.studyState.preloadedActivity.activity.introAtoms;

  await apiReportResult(state.sess.sessionToken, 'es', {
    atomsIntroduced: introAtoms,
    atomsExposed: [],
    atomsForgot: [],
    atomsPassed: [],
    atomsFailed: [],
  });

  loadActivity(dispatch, state.sess.sessionToken);
};

export const thunkQuizAnswered = (choice: APIQuizChoice): AppThunk => async (dispatch, getState) => {
  const state = getState();
  if (state.type !== 'loggedIn') {
    throw new Error('invalid state');
  }
  if (state.sess.page.type !== 'study') {
    throw new Error('invalid page');
  }
  if (state.sess.page.studyState.preloadedActivity === undefined) {
    throw new Error('invalid study state');
  }
  if (state.sess.page.studyState.preloadedActivity.activity.kind !== 'quiz') {
    throw new Error('invalid activity kind');
  }

  let atomsPassed: readonly string[];
  let atomsFailed: readonly string[];
  const targetAtoms = state.sess.page.studyState.preloadedActivity.activity.targetAtoms;
  if (choice.correct) {
    atomsPassed = targetAtoms;
    atomsFailed = [];
  } else {
    atomsPassed = [];
    atomsFailed = [...targetAtoms, ...(choice.failAtoms || [])];
  }

  await apiReportResult(state.sess.sessionToken, 'es', {
    atomsIntroduced: [],
    atomsExposed: [],
    atomsForgot: [],
    atomsPassed,
    atomsFailed,
  });

  loadActivity(dispatch, state.sess.sessionToken);
}

export const actionStudyLoadActivity = createAction<{
  readonly activity: APIActivity;
  readonly preloadMap: PreloadMap;
}>('studyLoadActivity');
export const actionStudyPresItemFinished = createAction('studyPresItemFinished');

/*
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
*/

/*
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

    await loadActivity(dispatch, sessionToken);
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

  await loadActivity(dispatch, sessionToken);
};
*/

const studyReducer = createReducer<StudyState>(initialStudyState, (builder) => {
  builder
    .addCase(actionStudyLoadActivity, (_state, action) => {
      return {
        loading: false,
        preloadedActivity: {
          uid: genRandomStr64(),
          activity: action.payload.activity,
          preloadMap: action.payload.preloadMap,
          state: {
            presIndex: 0,
            everFinishedPres: false,
          },
        },
      };
    })
    .addCase(actionStudyPresItemFinished, (state, _action) => {
      if (state.preloadedActivity === undefined) {
        return state;
      }

      const activityState = state.preloadedActivity.state;
      const items = state.preloadedActivity.activity.pres.items;

      let newPresIndex: number;
      let newEverFinished: boolean;
      if ((activityState.presIndex + 1) >= items.length) {
        newPresIndex = activityState.presIndex;
        newEverFinished = true;
      } else {
        newPresIndex = activityState.presIndex + 1;
        newEverFinished = activityState.everFinishedPres;
      }

      return {
        loading: false,
        preloadedActivity: {
          ...state.preloadedActivity,
          state: {
            presIndex: newPresIndex,
            everFinishedPres: newEverFinished,
          },
        },
      };
    });
});

export default studyReducer;
