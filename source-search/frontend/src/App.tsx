import { useEffect, useRef, useState } from 'react'
import vtt from 'vtt.js'
import yaml from 'js-yaml'
import './App.css'

interface SearchHit {
  readonly id: string;
  readonly text: string;
  readonly highlight: string;
  readonly start: number;
  readonly end: number;
  readonly src_title: string;
  readonly src_url: string;
  readonly vid_fn: string;
  readonly media_url: string;
  readonly captions_url: string;
}

interface SearchResults {
  readonly uid: string;
  readonly hitCount: number;
  readonly hits: ReadonlyArray<SearchHit>;
}

const LANG_OPTIONS = [
  'es',
  'ja',
];

type VideoState =
  'init' | // initial state, waiting for video to load
  'seeking' | // a programmatic seek was requested, waiting for canplay event
  'other'; // we're not waiting for a canplay event

interface Cue {
  startTime: number;
  endTime: number;
  text: string;
}

function approxEquals(a: number, b: number, epsilon: number = 0.01) {
  return Math.abs(a - b) < epsilon;
}

function roundTime(time: number) {
  return Math.round(time * 100) / 100;
}

function HitDetails({ hit, lang }: { hit: SearchHit, lang: string }) {
  const videoState = useRef<VideoState>('init');
  const [cues, setCues] = useState<Array<Cue>>([]);
  const [currentCue, setCurrentCue] = useState<Cue | null>(null);
  const [clipStart, setClipStart] = useState<number>(hit.start);
  const [clipEnd, setClipEnd] = useState<number>(hit.end);
  const [clipMetadata, setClipMetadata] = useState<string>('');

  const setRoundClipStart = (time: number) => {
    setClipStart(roundTime(time));
  };
  const setRoundClipEnd = (time: number) => {
    setClipEnd(roundTime(time));
  };

  const seekTo = (time: number) => {
    const video = document.querySelector('video');
    if (video) {
      videoState.current = 'seeking';
      video.currentTime = time;
    }
  };

  const handleVideoCanPlay = (event: React.SyntheticEvent<HTMLVideoElement>) => {
    console.log('canplay');
    if (videoState.current === 'init') {
      seekTo(hit.start);
    } else if (videoState.current === 'seeking') {
      videoState.current = 'other';
      event.currentTarget.play();
    }
  };

  const handleVideoTimeUpdate = (event: React.SyntheticEvent<HTMLVideoElement>) => {
    const video = event.currentTarget;
    if (video.currentTime >= clipEnd) {
      video.pause();
    }
  };

  useEffect(() => {
    fetch(hit.captions_url)
      .then((response) => response.text())
      .then((data) => {
        const cues: Array<Cue> = [];
        const parser = new vtt.WebVTT.Parser(window, vtt.WebVTT.StringDecoder());
        parser.oncue = function(cue: Cue) {
          cues.push(cue);
        };
        parser.parse(data);
        parser.flush();
        setCues(cues);

        const matchCue = cues.find(cue => approxEquals(cue.startTime, hit.start) && approxEquals(cue.endTime, hit.end));
        if (matchCue) {
          setCurrentCue(matchCue);
        }
      });
  }, []);

  useEffect(() => {
    // scroll to current cue
    if (currentCue) {
      const cueElement = document.querySelector('.HitDetails-cue-current');
      if (cueElement) {
        cueElement.scrollIntoView();
      }
    }
  }, [currentCue]);

  const handleCueClick = (cue: Cue) => {
    const video = document.querySelector('video');
    if (video) {
      seekTo(cue.startTime);
    }
    setCurrentCue(cue);
    setRoundClipStart(cue.startTime);
    setRoundClipEnd(cue.endTime);
    setClipMetadata('');
  };

  const adjustStart = (delta: number) => {
    const newClipStart = clipStart + delta;
    setRoundClipStart(newClipStart);
    seekTo(newClipStart);
  };

  const adjustEnd = (delta: number) => {
    const newClipEnd = clipEnd + delta;
    setRoundClipEnd(newClipEnd);
    seekTo(Math.max(clipStart, (newClipEnd-0.5)));
  };

  const doReplay = () => {
    seekTo(clipStart);
  };

  const handleCut = () => {
    fetch('http://localhost:4650/cut', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        lang,
        vid_fn: hit.vid_fn,
        start: clipStart,
        end: clipEnd,
      }),
    }).then((response) => response.json()).then((data) => {
      console.log('cut response', data);
      if (data.status !== 'ok') {
        throw new Error('cut failed');
      }

      const metaYaml = yaml.dump({
        'file': data.clip_fn,
        'kind': 'generated',
        'src_title': hit.src_title,
        'src_url': hit.src_url,
        'src_path': hit.vid_fn,
        'cut_start': clipStart,
        'cut_end': clipEnd,
      });

      setClipMetadata(metaYaml);
    });
  };

  const handleClipMetadataCopy = () => {
    navigator.clipboard.writeText(clipMetadata);
  };

  return (
    <div>
      <video controls key={hit.id} onCanPlay={handleVideoCanPlay} onTimeUpdate={handleVideoTimeUpdate}>
        <source src={hit.media_url} type="video/mp4" />
      </video>
      <div className="HitDetails-cues">
        {cues.map((cue) => (
          <div key={cue.startTime} className={'HitDetails-cue' + ((cue == currentCue) ? ' HitDetails-cue-current' : '')} onClick={() => { handleCueClick(cue) }}>
            {cue.text}
          </div>
        ))}
      </div>
      <div className="HitDetails-timing-controls">
        <div className="HitDetails-timing-controls-start">
          <div>
            {clipStart}
          </div>
          <div>
            <button className="HitDetails-timing-button" onClick={() => { adjustStart(-1) }}>⇇</button>
            <button className="HitDetails-timing-button" onClick={() => { adjustStart(-0.03) }}>←</button>
            <button className="HitDetails-timing-button" onClick={() => { adjustStart(0.03) }}>→</button>
            <button className="HitDetails-timing-button" onClick={() => { adjustStart(1) }}>⇉</button>
          </div>
        </div>
        <div>
          <div>&nbsp;</div>
          <div>
            <button className="HitDetails-timing-button" onClick={doReplay}>R</button>
          </div>
        </div>
        <div className="HitDetails-timing-controls-end">
          <div>
            {clipEnd}
          </div>
          <div>
          <button className="HitDetails-timing-button" onClick={() => { adjustEnd(-1) }}>⇇</button>
            <button className="HitDetails-timing-button" onClick={() => { adjustEnd(-0.03) }}>←</button>
            <button className="HitDetails-timing-button" onClick={() => { adjustEnd(0.03) }}>→</button>
            <button className="HitDetails-timing-button" onClick={() => { adjustEnd(1) }}>⇉</button>
          </div>
        </div>
      </div>
      {!clipMetadata && (
        <div className="HitDetails-cut-section">
          <button className="HitDetails-cut-button" onClick={handleCut}>Cut</button>
        </div>
      )}
      {clipMetadata && (
        <div className="HitDetails-clip-metadata-section">
          <div><button onClick={handleClipMetadataCopy} className="HitDetails-cut-button">Copy YAML</button></div>
          <pre className="HitDetails-clip-metadata">{clipMetadata}</pre>
        </div>
      )}
    </div>
);
}

function App() {
  const [lang, setLang] = useState('es');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResults | null>(null);
  const [selectedHit, setSelectedHit] = useState<SearchHit | null>(null);

  const updateSearch = (lang: string, query: string) => {
    setSelectedHit(null);

    fetch(`http://localhost:4650/search?lang=${lang}&query=${encodeURIComponent(query)}`)
      .then((response) => response.json())
      .then((data) => {
        setResults({
          uid: Math.random().toString(),
          ...data,
        });
      });
  };

  const handleLangChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setLang(event.target.value);
    updateSearch(event.target.value, query);
  };

  const handleSearchInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(event.target.value);
  };

  const handleSearchInputKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      updateSearch(lang, event.currentTarget.value);
    }
  };

  const handleResultClick = (hit: SearchHit) => {
    setSelectedHit(hit);
  };

  return (
    <div className="App">
      <div className="App-search-column">
        <div>
          <select value={lang} onChange={handleLangChange}>
            {LANG_OPTIONS.map((lang) => (
              <option key={lang} value={lang}>{lang}</option>
            ))}
          </select>
          <input type="text" value={query} onChange={handleSearchInputChange} onKeyDown={handleSearchInputKeyDown} />
        </div>
        {results && (
          <div key={results.uid}>
            {results.hitCount} hits
            <ul className="App-results-list">
              {results.hits.map(hit => (
                <li key={hit.id} onClick={() => {handleResultClick(hit)}} className={(hit == selectedHit) ? 'App-result-selected' : ''}>{hit.text}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
      <div className="App-cut-column">
        {selectedHit && <HitDetails key={selectedHit.id} lang={lang} hit={selectedHit} />}
      </div>
    </div>
  )
}

export default App
