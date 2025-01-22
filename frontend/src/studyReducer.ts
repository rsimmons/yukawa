import { ThunkDispatch, UnknownAction, createAction, createReducer } from '@reduxjs/toolkit'
import { APIActivity, APIAtomsInfo, apiPickActivity, APIPickActivityResponse, apiReportResult } from './api';
import { AppThunk, RootState } from './reducers';
import { genRandomStr64 } from './util';

// maps "filename" returned by API to object URL of preloaded media
// type PreloadMap = ReadonlyMap<string, string>;
export interface PreloadMap {
  [filename: string]: string;
}

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
  readonly atomsInfo: APIAtomsInfo;
  readonly preloadMap: PreloadMap;
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

  switch (activity.kind) {
    case 'intro_slides':
      for (const slide of activity.slides) {
        switch (slide.kind) {
          case 'audio_image':
            filenames.add(slide.audioFn);
            filenames.add(slide.imageFn);
            break;

          default:
            throw new Error('invalid slide kind');
        }
      }
      break;

    case 'review':
      switch (activity.pres.kind) {
        case 'audio':
          filenames.add(activity.pres.audioFn);
          break;

        default:
          throw new Error('invalid pres kind');
      }
      switch (activity.ques.kind) {
        case 'choice_image':
          for (const option of activity.ques.options) {
            filenames.add(option.imageFn);
          }
          break;

        default:
          throw new Error('invalid ques kind');
      }
      break;

    default:
      throw new Error('invalid activity kind');
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
    atomsInfo: pickActivityResp.atomsInfo,
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

export const thunkStudyFinishedActivity = (atomReports: AtomReports): AppThunk => async (dispatch, getState) => {
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

  await apiReportResult(state.sess.sessionToken, 'es', {
    atomsIntroduced: Array.from(atomReports.atomsIntroduced),
    atomsExposed: Array.from(atomReports.atomsExposed),
    atomsForgot: Array.from(atomReports.atomsForgot),
    atomsPassed: Array.from(atomReports.atomsPassed),
    atomsFailed: Array.from(atomReports.atomsFailed),
  });

  loadActivity(dispatch, state.sess.sessionToken);
}

const actionStudyLoadActivity = createAction<{
  readonly activity: APIActivity;
  readonly atomsInfo: APIAtomsInfo;
  readonly preloadMap: PreloadMap;
}>('studyLoadActivity');

const studyReducer = createReducer<StudyState>(initialStudyState, (builder) => {
  builder
    .addCase(actionStudyLoadActivity, (_state, action) => {
      return {
        loading: false,
        activityState: {
          uid: genRandomStr64(),
          activity: action.payload.activity,
          preloadMap: action.payload.preloadMap,
          atomsInfo: action.payload.atomsInfo,
        },
      };
    });
});

export default studyReducer;
