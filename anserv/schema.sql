-- e.g. a Netflix series or YouTube channel/playlist
CREATE TABLE source (
  id INTEGER PRIMARY KEY,
  url TEXT NOT NULL UNIQUE, -- canonicalized
  kind TEXT NOT NULL, -- "video", "audio", etc.
  title TEXT NOT NULL, -- title of the source
  image_id INTEGER, -- id of the thumbnail image file in the image table. NULL if the source does not have an image
  time_updated INTEGER -- UNIX timestamp the source was last updated, i.e. list of pieces fetched. NULL if never finished (or started) updating
);

-- a single piece of content, e.g. a Netflix episode or YouTube video
-- table is updated transactionally, so fields (including referenced image and audio) are consistent
CREATE TABLE piece (
  id INTEGER PRIMARY KEY,
  url TEXT NOT NULL UNIQUE, -- canonicalized
  kind TEXT NOT NULL, -- must match source_id.kind if source_id is not NULL
  title TEXT NOT NULL, -- title of the piece
  image_id INTEGER, -- id of the thumbnail image file in the image table. NULL if the piece does not have an image
  audio_id INTEGER, -- id of the audio file in the audio table. NULL if the piece did not have audio
  stt_method TEXT, -- speech to text. a string representing how text was derived from the speech audio. might be something like "human" or "youtube-auto" or "openai-api-whisper-large-v2". can be NULL if the piece was originally text
  text_format TEXT NOT NULL, -- format of the text column, e.g. "vtt"
  text TEXT NOT NULL, -- the full text(-equivalent) of the piece, e.g. a subtitle file in VTT format
  analysis TEXT NOT NULL, -- JSON of object that maps from analysis "algo" to "words" (really lexical items) to their frequency (count) in this piece
  time_fetched INTEGER NOT NULL, -- UNIX timestamp the original media was retrieved
  time_updated INTEGER NOT NULL -- UNIX timestamp the piece was last updated (i.e. text was updated from new ASR, analysis was updated, etc.)
);

-- a many-to-many relationship between sources and pieces. e.g. a YouTube video could belong to multiple playlists, and a source could be a playlist
CREATE TABLE piece_source (
  piece_id INTEGER NOT NULL,
  source_id INTEGER NOT NULL,
  PRIMARY KEY (piece_id, source_id)
);

CREATE TABLE audio (
  id INTEGER PRIMARY KEY,
  extension TEXT NOT NULL, -- e.g. "webm" or "m4a"
  md5 TEXT NOT NULL, -- hex MD5 hash of audio data
  data BLOB NOT NULL -- the raw audio data
);

CREATE table image (
  id INTEGER PRIMARY KEY,
  extension TEXT NOT NULL, -- e.g. "jpg" or "png"
  md5 TEXT NOT NULL, -- hex MD5 hash of image data
  data BLOB NOT NULL, -- the raw image data
  width INTEGER NOT NULL,
  height INTEGER NOT NULL
);
