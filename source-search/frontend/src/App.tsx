import { useRef, useState } from 'react'
import './App.css'

interface SearchHit {
  readonly id: string;
  readonly text: string;
  readonly highlight: string;
  readonly start: number;
  readonly end: number;
  readonly mediaUrl: string;
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

function App() {
  const [lang, setLang] = useState('es');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResults | null>(null);
  const [selectedHit, setSelectedHit] = useState<SearchHit | null>(null);
  const videoState = useRef<VideoState>('init');

  const updateSearch = (lang: string, query: string) => {
    setSelectedHit(null);
    videoState.current = 'init';
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
    videoState.current = 'init';
  };

  const handleVideoCanPlay = (event: React.SyntheticEvent<HTMLVideoElement>) => {
    if (videoState.current === 'init') {
      videoState.current = 'seeking';
      event.currentTarget.currentTime = selectedHit!.start;
    } else if (videoState.current === 'seeking') {
      videoState.current = 'ready';
      event.currentTarget.play();
    }
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
        {selectedHit && (
          <div>
            <video controls key={selectedHit.id} onCanPlay={handleVideoCanPlay}>
              <source src={selectedHit.mediaUrl} type="video/mp4" />
            </video>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
