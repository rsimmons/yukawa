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
  API_ENDPOINT = 'https://api.example.com';
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

export interface APIClipInfo {
  readonly clipId: string;
  readonly mediaUrl: string;
  readonly transcription: string;
  readonly translation: string;
}

export const apiGetRandomClip = async (sessionToken: string): Promise<APIClipInfo> => {
  const resp = await post('/random_clip', {}, sessionToken);

  return {
    clipId: resp.clip_id,
    mediaUrl: resp.media_url,
    transcription: resp.transcription,
    translation: resp.translation,
  };
};

export type APIGrade = 'n' | 'm' | 'y';
export const apiReportClipUnderstood = async (sessionToken: string, clipId: string, grade: APIGrade): Promise<void> => {
  await post('/report_clip_understood', { clip_id: clipId, grade }, sessionToken);
};

export interface APISpan {
  readonly t: string; // text
  readonly a?: string; // atom id
}

export interface APIAtomInfo {
  readonly meaning: string | null;
  readonly notes: string | null;
}

export interface APIQuestion {
  readonly clipId: string;
  readonly mediaUrl: string;
  readonly spans: ReadonlyArray<APISpan>;
  readonly translations: ReadonlyArray<string>;
  readonly notes: string | null;
  readonly atomInfo: {[key: string]: APIAtomInfo};
}

export const apiGetQuestion = async (sessionToken: string): Promise<APIQuestion> => {
  const resp = await post('/pick_question', {'lang': 'es'}, sessionToken);

  return {
    clipId: resp.clip_id,
    mediaUrl: resp.media_url,
    spans: resp.spans,
    translations: resp.translations,
    notes: resp.notes,
    atomInfo: resp.atom_info,
  };
};

export interface APIQuestionGrades {
  readonly heard: APIGrade;
  readonly understood: APIGrade;
  readonly atoms_failed: ReadonlyArray<string>;
}

export const apiReportQuestionGrades = async (sessionToken: string, lang: string, clipId: string, grades: APIQuestionGrades): Promise<void> => {
  await post('/report_question_grades', {
    lang,
    clip_id: clipId,
    grades,
  }, sessionToken);
}
