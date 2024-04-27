export class APIError extends Error {
  constructor(m?: string) {
    super(m);
    Object.setPrototypeOf(this, APIError.prototype);
  }
}

const API_ENDPOINT = 'http://localhost:4649';

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
  email: string,
}

export const apiGetUserInfo = async (sessionToken: string): Promise<APIUserInfo> => {
  const resp = await post('/user', {}, sessionToken);
  return resp;
};

export interface APIClipInfo {
  mediaUrl: string,
}

export const apiGetRandomClip = async (sessionToken: string): Promise<APIClipInfo> => {
  const resp = await post('/random_clip', {}, sessionToken);

  return {
    mediaUrl: resp.media_url,
  };
}
