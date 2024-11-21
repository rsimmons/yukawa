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

export interface APIAtomInfo {
  readonly meaning: string | null;
  readonly notes: string | null;
}

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
  readonly onFail: 'report' | 'restart';
  readonly text: string;
  readonly trans: ReadonlyArray<string>;
  readonly anno: APIAnno;
  readonly audioFn: string;
  readonly choices: ReadonlyArray<APIQuestionChoice>;
}

export type APIActivitySection = APIActivitySectionTTSSlides | APIActivitySectionQMTI;

export interface APIActivity {
  readonly introAtoms: ReadonlyArray<string>;
  readonly reqAtoms: ReadonlyArray<string>;
  readonly testedAtoms: ReadonlyArray<string>;
  readonly sections: ReadonlyArray<APIActivitySection>;
}

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
        onFail: section.on_fail,
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
    sections: activity.sections.map((section: any) => mapActivitySection(section)),
  };
};

export interface APIPickActivityResponse {
  readonly mediaUrlPrefix: string;
  readonly activity: APIActivity;
  readonly atomInfo: {[key: string]: APIAtomInfo};
}

export const apiPickActivity = async (sessionToken: string): Promise<APIPickActivityResponse> => {
  const resp = await post('/pick_activity', {'lang': 'es'}, sessionToken);

  console.log('picked activity', resp.activity)

  return {
    mediaUrlPrefix: resp.media_url_prefix,
    activity: mapActivity(resp.activity),
    atomInfo: resp.atom_info,
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
