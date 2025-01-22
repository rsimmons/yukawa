export class APIError extends Error {
  constructor(m?: string) {
    super(m);
    Object.setPrototypeOf(this, APIError.prototype);
  }
}

let API_ENDPOINT: string;
if (import.meta.env.MODE === 'development') {
  const loc = window.location;
  API_ENDPOINT = `${loc.protocol}//${loc.hostname}:4649`
} else {
  API_ENDPOINT = 'https://backend.yukawa.app';
}

const post = async(path: string, params: any, sessionToken?: string): Promise<any> => {
  let response: Response;
  const headers: any = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
  };
  if (sessionToken) {
    headers['X-Session-Token'] = sessionToken;
  }
  try {
    response = await fetch(API_ENDPOINT + path, {
      method: 'POST',
      headers,
      body: JSON.stringify(params),
    });
  } catch {
    throw new APIError('post fetch failed');
  }

  if (!response.ok) {
    throw new APIError('post bad HTTP status');
  }

  const resultObj = await response.json();

  return resultObj;
};

export type APILoginResponse =
  { status: 'ok' } |
  { status: 'invalid_email' };
export const apiLogin = async (email: string): Promise<APILoginResponse> => {
  const resp = await post('/login', { email }) as APILoginResponse;
  return resp;
};

// returns session token
type APIAuthResponse =
  { status: 'ok', token: string } |
  { status: 'invalid_token' } |
  { status: 'expired_token' };
export const apiAuth = async (authToken: string): Promise<APIAuthResponse> => {
  const resp = await post('/auth', { token: authToken }) as APIAuthResponse;
  return resp;
};

export interface APIUserInfo {
  readonly email: string,
}

export const apiGetUserInfo = async (sessionToken: string): Promise<APIUserInfo> => {
  const resp = await post('/user', {}, sessionToken);
  return resp;
};

export interface APISpan {
  readonly t: string; // text
  readonly a?: string; // atom id
}

export type APIAnno = ReadonlyArray<APISpan>;

/*
export interface APIQuestionChoice {
  readonly correct: boolean;
  readonly imageFn: string;
  readonly failAtoms?: ReadonlyArray<string>;
}

export interface APIActivityTTSSlide {
  readonly text: string;
  readonly trans: ReadonlyArray<string>;
  readonly anno: APIAnno;
  readonly audioFn: string;
  readonly imageFn: string;
}

export type APIActivitySectionTTSSlides = {
  readonly kind: 'tts_slides';
  readonly slides: ReadonlyArray<APIActivityTTSSlide>;
}

export type APIActivitySectionQMTI = {
  readonly kind: 'qmti';
  readonly testedAtoms: ReadonlyArray<string>;
  readonly text: string;
  readonly trans: ReadonlyArray<string>;
  readonly anno: APIAnno;
  readonly audioFn: string;
  readonly choices: ReadonlyArray<APIQuestionChoice>;
}

export type APIActivitySection = APIActivitySectionTTSSlides | APIActivitySectionQMTI;
*/

export interface APIAtomInfo {
  readonly meaning: string | null;
  readonly notes: string | null;
}

export type APIAtomsInfo = {[key: string]: APIAtomInfo};

export interface ATText {
  readonly text: string;
  readonly trans: ReadonlyArray<string>;
  readonly anno: APIAnno;
}

interface APIActivityBase {
  readonly atomsIntroduced: ReadonlyArray<string>;
  readonly atomsExposed: ReadonlyArray<string>;
  readonly atomsTested: ReadonlyArray<string>;
}

export interface APIIntroSlideAudioImage {
  readonly kind: 'audio_image';
  readonly attext: ATText;
  readonly audioFn: string;
  readonly imageFn: string;
}

export type APIIntroSlide = APIIntroSlideAudioImage;

export interface APIActivityIntroSlides extends APIActivityBase {
  readonly kind: 'intro_slides';
  readonly slides: ReadonlyArray<APIIntroSlide>;
}

export interface APIPresAudio {
  readonly kind: 'audio';
  readonly audioFn: string;
  readonly attext: ATText;
}

type APIPres = APIPresAudio;

export interface APIImageOption {
  readonly correct: boolean;
  readonly imageFn: string;
  readonly atomsPassed: ReadonlyArray<string>;
  readonly atomsFailed: ReadonlyArray<string>;
}

export interface APIQuesChoiceImage {
  readonly kind: 'choice_image';
  readonly prompt: string | null;
  readonly options: ReadonlyArray<APIImageOption>;
}

export type APIQues = APIQuesChoiceImage;

export interface APIActivityReview extends APIActivityBase {
  readonly kind: 'review';
  readonly pres: APIPres;
  readonly ques: APIQues;
}

export type APIActivity = APIActivityIntroSlides | APIActivityReview;

/*
const mapActivitySection = (section: any): APIActivitySection => {
  switch (section.kind) {
    case 'tts_slides':
      return {
        kind: 'tts_slides',
        slides: section.slides.map((slide: any) => ({
          text: slide.text,
          trans: slide.trans,
          anno: slide.anno,
          audioFn: slide.audio_fn,
          imageFn: slide.image_fn,
        })),
      };

    case 'qmti':
      return {
        kind: 'qmti',
        testedAtoms: section.tested_atoms,
        text: section.text,
        trans: section.trans,
        anno: section.anno,
        audioFn: section.audio_fn,
        choices: section.choices.map((choice: any) => ({
          correct: choice.correct,
          imageFn: choice.image_fn,
          failAtoms: choice.fail_atoms,
        })),
      };

    default:
      throw new APIError('invalid section kind');
  }
}

const mapActivity = (activity: any): APIActivity => {
  return {
    introAtoms: activity.intro_atoms,
    reqAtoms: activity.req_atoms,
    testedAtoms: activity.tested_atoms,
    atomsInfo: activity.atoms_info,
    sections: activity.sections.map((section: any) => mapActivitySection(section)),
  };
};
*/

const mapATText = (attext: any): ATText => {
  return {
    text: attext.text,
    trans: attext.trans,
    anno: attext.anno,
  };
}

const mapIntroSlide = (slide: any): APIIntroSlide => {
  switch (slide.kind) {
    case 'audio_image':
      return {
        kind: 'audio_image',
        attext: mapATText(slide.attext),
        audioFn: slide.audio_fn,
        imageFn: slide.image_fn,
      };

    default:
      throw new APIError('invalid intro slide kind');
  }
}

const mapPres = (pres: any): APIPres => {
  switch (pres.kind) {
    case 'audio':
      return {
        kind: 'audio',
        audioFn: pres.audio_fn,
        attext: mapATText(pres.attext),
      };

    default:
      throw new APIError('invalid pres kind');
  }
}

const mapQues = (ques: any): APIQuesChoiceImage => {
  switch (ques.kind) {
    case 'choice_image':
      return {
        kind: 'choice_image',
        prompt: ques.prompt,
        options: ques.options.map((option: any): APIImageOption => ({
          correct: option.correct,
          imageFn: option.image_fn,
          atomsPassed: option.atoms_passed,
          atomsFailed: option.atoms_failed,
        })),
      };

    default:
      throw new APIError('invalid ques kind');
  }
}

const mapActivity = (activity: any): APIActivity => {
  switch (activity.kind) {
    case 'intro_slides':
      return {
        kind: 'intro_slides',
        atomsIntroduced: activity.atoms_introduced,
        atomsExposed: activity.atoms_exposed,
        atomsTested: activity.atoms_tested,
        slides: activity.slides.map((slide: any): APIIntroSlide => mapIntroSlide(slide)),
      };

    case 'review':
      return {
        kind: 'review',
        atomsIntroduced: activity.atoms_introduced,
        atomsExposed: activity.atoms_exposed,
        atomsTested: activity.atoms_tested,
        pres: mapPres(activity.pres),
        ques: mapQues(activity.ques),
      };

    default:
      throw new APIError('invalid activity kind');
  }
}

export interface APIPickActivityResponse {
  readonly mediaUrlPrefix: string;
  readonly activity: APIActivity;
  readonly atomsInfo: APIAtomsInfo;
}

export const apiPickActivity = async (sessionToken: string): Promise<APIPickActivityResponse> => {
  const resp = await post('/pick_activity', {'lang': 'es'}, sessionToken);

  console.log('picked activity', resp.activity)

  return {
    mediaUrlPrefix: resp.media_url_prefix,
    activity: mapActivity(resp.activity),
    atomsInfo: resp.atoms_info,
  };
};

export interface APIReportedResult {
  readonly atomsIntroduced: ReadonlyArray<string>;
  readonly atomsExposed: ReadonlyArray<string>;
  readonly atomsForgot: ReadonlyArray<string>;
  readonly atomsPassed: ReadonlyArray<string>;
  readonly atomsFailed: ReadonlyArray<string>;
}

export const apiReportResult = async (sessionToken: string, lang: string, result: APIReportedResult): Promise<void> => {
  console.log('reporting result', result);
  await post('/report_result', {
    lang,
    result: {
      atoms_introduced: result.atomsIntroduced,
      atoms_exposed: result.atomsExposed,
      atoms_forgot: result.atomsForgot,
      atoms_passed: result.atomsPassed,
      atoms_failed: result.atomsFailed,
    },
  }, sessionToken);
}
