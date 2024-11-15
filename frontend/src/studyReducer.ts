import { ThunkDispatch, UnknownAction, createAction, createReducer } from '@reduxjs/toolkit'
import { APIActivity, apiPickActivity, APIPickActivityResponse, apiReportResult } from './api';
import { AppThunk, RootState } from './reducers';
import { genRandomStr64 } from './util';

// maps "filename" returned by API to object URL of preloaded media
// type PreloadMap = ReadonlyMap<string, string>;
export interface PreloadMap {
  [filename: string]: string;
}

export const mergeArraysUnique = <T>(a: ReadonlyArray<T>, b: ReadonlyArray<T>): ReadonlyArray<T> => {
  return Array.from(new Set([...a, ...b]));
}

export const combineAtomReports = (prev: AtomReports, next: AtomReports): AtomReports => {
  return {
    atomsIntroduced: mergeArraysUnique(prev.atomsIntroduced, next.atomsIntroduced),
    atomsExposed: mergeArraysUnique(prev.atomsExposed, next.atomsExposed),
    atomsForgot: mergeArraysUnique(prev.atomsForgot, next.atomsForgot),
    atomsPassed: mergeArraysUnique(prev.atomsPassed, next.atomsPassed),
    atomsFailed: mergeArraysUnique(prev.atomsFailed, next.atomsFailed),
  };
};

export interface AtomReports {
  readonly atomsIntroduced: ReadonlyArray<string>;
  readonly atomsExposed: ReadonlyArray<string>;
  readonly atomsForgot: ReadonlyArray<string>;
  readonly atomsPassed: ReadonlyArray<string>;
  readonly atomsFailed: ReadonlyArray<string>;
}

export interface StudyState {
  readonly loading: boolean; // true during initial or subsequent loading of next activity
  readonly activityState: {
    readonly uid: string;
    readonly activity: APIActivity;
    readonly preloadMap: PreloadMap;
    readonly sectionIndex: number;
    readonly accumAtomReports: AtomReports;
  } | undefined; // undefined before initial load
}

export const initialStudyState: StudyState = {
  loading: true,
  activityState: undefined,
};

const preloadFilename = async (filename: string, mediaUrlPrefix: string): Promise<string> => {
  const blob = await fetch(mediaUrlPrefix + filename).then((r) => r.blob());
  return URL.createObjectURL(blob);
}

const getActivityMediaFilenames = (activity: APIActivity): ReadonlySet<string> => {
  const filenames = new Set<string>();

  for (const section of activity.sections) {
    switch (section.kind) {
      case 'tts_slides':
        for (const slide of section.slides) {
          filenames.add(slide.audioFn);
          filenames.add(slide.imageFn);
        }
        break;

      case 'qmti':
        filenames.add(section.audioFn);
        for (const choice of section.choices) {
          filenames.add(choice.imageFn);
        }
        break;

      default:
        throw new Error('invalid section kind');
    }
  }

  return filenames;
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

/*
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
*/

export const thunkStudyFinishedSection = (atomReports: AtomReports): AppThunk => async (dispatch, getState) => {
  const state = getState();
  if (state.type !== 'loggedIn') {
    throw new Error('invalid state');
  }
  if (state.sess.page.type !== 'study') {
    throw new Error('invalid page');
  }
  if (state.sess.page.studyState.activityState === undefined) {
    throw new Error('invalid study state');
  }

  dispatch(actionAccumAtomReports(atomReports));

  const activityState = state.sess.page.studyState.activityState;
  const activity = activityState.activity;
  const newSectionIndex = activityState.sectionIndex + 1;
  if (newSectionIndex >= activity.sections.length) {
    dispatch(actionAccumAtomReports({
      atomsIntroduced: activity.introAtoms,
      atomsExposed: [],
      atomsForgot: [],
      atomsPassed: [],
      atomsFailed: [],
    }));

    const updatedState = getState();
    if (updatedState.type !== 'loggedIn') {
      throw new Error('invalid state');
    }
    if (updatedState.sess.page.type !== 'study') {
      throw new Error('invalid page');
    }
    if (updatedState.sess.page.studyState.activityState === undefined) {
      throw new Error('invalid study state');
    }
    const updatedAtomReports = updatedState.sess.page.studyState.activityState.accumAtomReports;

    await apiReportResult(state.sess.sessionToken, 'es', {
      atomsIntroduced: Array.from(updatedAtomReports.atomsIntroduced),
      atomsExposed: Array.from(updatedAtomReports.atomsExposed),
      atomsForgot: Array.from(updatedAtomReports.atomsForgot),
      atomsPassed: Array.from(updatedAtomReports.atomsPassed),
      atomsFailed: Array.from(updatedAtomReports.atomsFailed),
    });

    loadActivity(dispatch, state.sess.sessionToken);
  } else {
    dispatch(actionStudyNextSection());
  }
}

const actionStudyLoadActivity = createAction<{
  readonly activity: APIActivity;
  readonly preloadMap: PreloadMap;
}>('studyLoadActivity');
export const actionAccumAtomReports = createAction<AtomReports>('accumAtomReports');
const actionStudyNextSection = createAction('studyNextSection');


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
        activityState: {
          uid: genRandomStr64(),
          activity: action.payload.activity,
          preloadMap: action.payload.preloadMap,
          sectionIndex: 0,
          accumAtomReports: {
            atomsIntroduced: [],
            atomsExposed: [],
            atomsForgot: [],
            atomsPassed: [],
            atomsFailed: [],
          },
        },
      };
    })
    .addCase(actionStudyNextSection, (state, _action) => {
      if (state.activityState === undefined) {
        return state;
      }

      const activityState = state.activityState;
      const sections = activityState.activity.sections;

      const newSectionIndex = activityState.sectionIndex + 1;
      if (newSectionIndex >= sections.length) {
        throw new Error('invalid section index');
      }

      return {
        loading: false,
        activityState: {
          ...state.activityState,
          sectionIndex: newSectionIndex
        },
      };
    }).addCase(actionAccumAtomReports, (state, action) => {
      if (state.activityState === undefined) {
        return state;
      }

      return {
        ...state,
        activityState: {
          ...state.activityState,
          accumAtomReports: combineAtomReports(state.activityState.accumAtomReports, action.payload),
        },
      };
    });
});

export default studyReducer;
