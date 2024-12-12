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

export interface ActivityState {
  readonly uid: string;
  readonly activity: APIActivity;
  readonly preloadMap: PreloadMap;
  readonly sectionIndex: number;
  readonly accumAtomReports: AtomReports;
}

export interface StudyState {
  readonly loading: boolean; // true during initial or subsequent loading of next activity
  readonly activityState: ActivityState | undefined; // undefined before initial load
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

export const thunkStudyFinishedSection = (atomReports: AtomReports, failed: boolean | undefined): AppThunk => async (dispatch, getState) => {
  console.log('thunkStudyFinishedSection', atomReports, failed);
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

  const activityState = state.sess.page.studyState.activityState;
  const activity = activityState.activity;

  const curSectionIndex = activityState.sectionIndex;
  const curSection = activity.sections[curSectionIndex];
  if ((curSection.kind === 'qmti') && (curSection.onFail === 'restart') && (failed === true)) {
    dispatch(actionGoToSection(0));
  } else {
    dispatch(actionAccumAtomReports(atomReports));
    const newSectionIndex = curSectionIndex + 1;

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
      dispatch(actionGoToSection(newSectionIndex));
    }
  }
}

const actionStudyLoadActivity = createAction<{
  readonly activity: APIActivity;
  readonly preloadMap: PreloadMap;
}>('studyLoadActivity');
export const actionAccumAtomReports = createAction<AtomReports>('accumAtomReports');
const actionGoToSection = createAction<number>('goToSection');

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
    .addCase(actionGoToSection, (state, action) => {
      if (state.activityState === undefined) {
        return state;
      }

      return {
        loading: false,
        activityState: {
          ...state.activityState,
          sectionIndex: action.payload,
        },
      };
    })
    .addCase(actionAccumAtomReports, (state, action) => {
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
