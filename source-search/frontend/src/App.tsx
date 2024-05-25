import { useEffect, useRef, useState } from 'react'
import vtt from 'vtt.js'
import './App.css'

interface SearchHit {
  readonly id: string;
  readonly text: string;
  readonly highlight: string;
  readonly start: number;
  readonly end: number;
  readonly mediaUrl: string;
  readonly captionsUrl: string;
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

type VideoState = 'init' | 'seeking' | 'ready';

interface Cue {
  startTime: number;
  endTime: number;
  text: string;
}

function HitDetails({ hit }: { hit: SearchHit }) {
  const videoState = useRef<VideoState>('init');
  const [cues, setCues] = useState<Array<Cue>>([]);
  const [currentCue, setCurrentCue] = useState<Cue | null>(null);

  const handleVideoCanPlay = (event: React.SyntheticEvent<HTMLVideoElement>) => {
    if (videoState.current === 'init') {
      videoState.current = 'seeking';
      event.currentTarget.currentTime = hit.start;
    } else if (videoState.current === 'seeking') {
      videoState.current = 'ready';
      event.currentTarget.play();
    }
  };

  const handleVideoTimeUpdate = (event: React.SyntheticEvent<HTMLVideoElement>) => {
    const video = event.currentTarget;
    const currentTime = video.currentTime;
    const matchCue = cues.find(cue => (cue.startTime <= currentTime) && (currentTime < cue.endTime));
    if (matchCue) {
      setCurrentCue(matchCue);
    }
  };

  useEffect(() => {
    fetch(hit.captionsUrl)
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
      video.currentTime = cue.startTime;
    }
  };

  return (
    <div>
      <video controls key={hit.id} onCanPlay={handleVideoCanPlay} onTimeUpdate={handleVideoTimeUpdate}>
        <source src={hit.mediaUrl} type="video/mp4" />
      </video>
      <div className="HitDetails-cues">
        {cues.map((cue) => (
          <div key={cue.startTime} className={'HitDetails-cue' + ((cue == currentCue) ? ' HitDetails-cue-current' : '')} onClick={() => { handleCueClick(cue) }}>
            {cue.text}
          </div>
        ))}
      </div>
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
        {selectedHit && <HitDetails key={selectedHit.id} hit={selectedHit} />}
      </div>
    </div>
  )
}

export default App
